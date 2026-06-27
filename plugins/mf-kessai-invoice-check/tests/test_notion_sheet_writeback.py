#!/usr/bin/env python3
"""lib/notion_sheet_writeback.py (請求確認シート 判定/AI確認 片方向ミラー) の単体テスト。

実ネットワークなし。fake req で GET databases / PATCH databases / PATCH pages を模す。
検証する不変条件:
  - 5値投影: GAP→発行漏れ / MATCH_*→AIの確認OK / SUPPRESS_*→対象外 / REVIEW_*→要確認。
  - ORPHAN(逆方向)はシート行が無いため投影しない (sheet_label=None)。
  - 1契約=複数シート行は全行へ展開し、重複 page_id は除去する。
  - 非破壊: PATCH props は『判定』『AI確認』『確認ポイント』のみ
    (日付補完は空欄だけ、人間列に触れない)。
  - ensure_judgment_property: 判定列が無ければ作成・既存optionは保持し不足5値だけ追加。
"""
import mfk_reconcile
import notion_sheet_writeback as wb


def _fake_req(db_props=None, writes=None, db_patches=None):
    """GET databases / PATCH databases / PATCH pages を扱う fake _req。"""
    def req(method, path, token, body=None):
        if method == "GET" and path.startswith("/databases/"):
            return {"properties": db_props or {}}
        if method == "PATCH" and path.startswith("/databases/"):
            if db_patches is not None:
                db_patches.append((body or {}).get("properties", {}))
            return {}
        if method == "PATCH" and path.startswith("/pages/"):
            if writes is not None:
                writes[path.split("/pages/")[1]] = (body or {}).get("properties", {})
            return {}
        raise AssertionError(f"想定外: {method} {path}")
    return req


def test_sheet_label_5value_mapping():
    assert mfk_reconcile.sheet_label("GAP") == "発行漏れ"
    assert mfk_reconcile.sheet_label("MATCH_MONTHLY") == "AIの確認OK"
    assert mfk_reconcile.sheet_label("MATCH_ANNUAL") == "AIの確認OK"
    assert mfk_reconcile.sheet_label("SUPPRESS_ANNUAL") == "対象外"
    assert mfk_reconcile.sheet_label("SUPPRESS_ENDED") == "対象外"
    assert mfk_reconcile.sheet_label("REVIEW_AMOUNT_MISMATCH") == "要確認"
    assert mfk_reconcile.sheet_label("REVIEW_ENDED_BUT_BILLED") == "要確認"
    # ORPHAN はシート行が無いため投影しない。
    assert mfk_reconcile.sheet_label("ORPHAN") is None
    # 未定義は None (fail-soft)。
    assert mfk_reconcile.sheet_label("__UNKNOWN__") is None


def test_build_writeback_expands_rows_and_excludes_orphan():
    rows = [
        {"verdict": "GAP", "_sheet_row_ids": ["p1", "p2"]},
        {"verdict": "MATCH_MONTHLY", "_sheet_row_ids": ["p3"]},
        {"verdict": "ORPHAN", "_sheet_row_ids": []},
        {"verdict": "REVIEW_QTY_MISMATCH", "_sheet_row_ids": ["p4"]},
        {"verdict": "GAP", "_sheet_row_ids": ["p1"]},  # 重複 p1 は除去
    ]
    items = wb.build_writeback(rows)
    by_pid = {it["page_id"]: it for it in items}
    assert set(by_pid) == {"p1", "p2", "p3", "p4"}
    assert by_pid["p1"]["sheet_label"] == "発行漏れ" and by_pid["p1"]["ai_check"] is False
    assert by_pid["p3"]["sheet_label"] == "AIの確認OK" and by_pid["p3"]["ai_check"] is True
    assert by_pid["p4"]["sheet_label"] == "要確認"


def test_writeback_is_nondestructive_three_columns_only():
    writes = {}
    req = _fake_req(db_props={"判定": {"select": {"options": [{"name": n} for n in wb.SHEET_LABELS]}},
                              "確認ポイント": {"rich_text": {}}},
                    writes=writes)
    rows = [{"verdict": "GAP", "_sheet_row_ids": ["pg1"]},
            {"verdict": "MATCH_MONTHLY", "_sheet_row_ids": ["pg2"]}]
    res = wb.writeback(rows, "sheetdb", "tok", req)
    assert res["updated"] == 2 and res["failed"] == []
    for props in writes.values():
        # 人間列『チェック済み』『確認内容』等に触れない (機械 3 列のみ)。
        assert set(props) == {"判定", "AI確認", "確認ポイント"}
    assert writes["pg1"]["判定"]["select"]["name"] == "発行漏れ"
    assert writes["pg1"]["AI確認"]["checkbox"] is False
    # 発行漏れ行には確認ポイントが入り、確認OK行は空。
    assert "発行" in writes["pg1"]["確認ポイント"]["rich_text"][0]["text"]["content"]
    assert writes["pg2"]["AI確認"]["checkbox"] is True
    assert writes["pg2"]["確認ポイント"]["rich_text"][0]["text"]["content"] == ""


def test_writeback_autofills_empty_dates_only():
    # 契約開始日(ISO)/契約終了月(YYMM)は空欄セルのみ派生値で自動補完し、人間入力の非空値は不可侵。
    writes = {}
    req = _fake_req(db_props={"判定": {"select": {"options": [{"name": n} for n in wb.SHEET_LABELS]}},
                              "確認ポイント": {"rich_text": {}}}, writes=writes)
    rows = [{"verdict": "GAP", "契約開始日": "2026-06-01", "契約終了月": "2026-05-01",
             "_sheet_row_ids": ["empty", "filled"]}]
    current = {
        "empty":  {"契約開始日": "", "契約終了月": ""},            # 空欄→補完される
        "filled": {"契約開始日": "2026/6/8", "契約終了月": "2605"},  # 非空→不可侵
    }
    wb.writeback(rows, "sheetdb", "tok", req, current_dates=current)
    # 空欄行: 契約開始日(ISOそのまま)・契約終了月(ISO→YYMM変換)が補完される。
    assert writes["empty"]["契約開始日"]["rich_text"][0]["text"]["content"] == "2026-06-01"
    assert writes["empty"]["契約終了月"]["rich_text"][0]["text"]["content"] == "2605"
    # 非空行: 日付列に触れない (人間入力不可侵)。判定3列は両行とも書く。
    assert "契約開始日" not in writes["filled"] and "契約終了月" not in writes["filled"]
    assert set(writes["empty"]) == {"判定", "AI確認", "確認ポイント", "契約開始日", "契約終了月"}
    assert set(writes["filled"]) == {"判定", "AI確認", "確認ポイント"}


def test_writeback_skips_date_autofill_without_current_dates():
    # current_dates 未指定なら日付補完しない (後方互換・判定3列のみ)。
    writes = {}
    req = _fake_req(db_props={"判定": {"select": {"options": [{"name": n} for n in wb.SHEET_LABELS]}},
                              "確認ポイント": {"rich_text": {}}}, writes=writes)
    rows = [{"verdict": "GAP", "契約開始日": "2026-06-01", "契約終了月": "2026-05-01",
             "_sheet_row_ids": ["p1"]}]
    wb.writeback(rows, "sheetdb", "tok", req)  # current_dates=None
    assert set(writes["p1"]) == {"判定", "AI確認", "確認ポイント"}


def test_compose_note_combines_hint_and_warning():
    # 定型ガイダンス + 行固有の警告詳細を全角括弧で連結。
    n = wb.compose_note("REVIEW_QTY_MISMATCH", "数量差: 期待2>MF供給1(想定漏れ額 330,000円)")
    assert "確認" in n and "想定漏れ額 330,000円" in n
    # AIの確認OK は空 (stale を消す)。
    assert wb.compose_note("MATCH_MONTHLY", "") == ""
    # 警告がガイダンスに包含済みなら二重化しない。
    assert wb.compose_note("GAP", "") == mfk_reconcile.action_hint("GAP")


def test_compose_note_ai_check_suppresses_nonempty_warning():
    # Request3 回帰防止: 集約請求の MATCH_MONTHLY は verdict を保ちつつ engine が warning を
    # 付すが、判定『AIの確認OK』ゆえシート確認ポイントには漏らさず必ず空を返す。
    assert mfk_reconcile.is_check_verdict("MATCH_MONTHLY") is True
    aggregated_warning = "MF 1明細に期待2件分が集約されているため数量差に降格しない"
    assert wb.compose_note("MATCH_MONTHLY", aggregated_warning) == ""
    # 対象外 (SUPPRESS 系) も ai_check のため warning 付きで空。
    assert mfk_reconcile.is_check_verdict("SUPPRESS_ENDED") is True
    assert wb.compose_note("SUPPRESS_ENDED", "契約終了済みだが当月MF実績あり (情報)") == ""
    # 一方 要確認/発行漏れ系 (非 ai_check) は warning を確認ポイントへ残す (漏らさないのは ai_check のみ)。
    assert mfk_reconcile.is_check_verdict("REVIEW_QTY_MISMATCH") is False
    assert wb.compose_note("REVIEW_QTY_MISMATCH", "行固有メモ") != ""


def test_ensure_note_property_creates_when_missing():
    req = _fake_req(db_props={})  # 確認ポイント無し
    assert wb.ensure_note_property("sheetdb", "tok", req) == "created"
    req2 = _fake_req(db_props={"確認ポイント": {"rich_text": {}}})
    assert wb.ensure_note_property("sheetdb", "tok", req2) == "ok"


def test_ensure_judgment_property_creates_when_missing():
    patches = []
    req = _fake_req(db_props={}, db_patches=patches)  # 判定列なし
    state = wb.ensure_judgment_property("sheetdb", "tok", req)
    assert state == "created"
    opts = patches[0]["判定"]["select"]["options"]
    names = [o["name"] for o in opts]
    assert names == wb.SHEET_LABELS
    assert {o["name"]: o["color"] for o in opts}["発行漏れ"] == "red"


def test_ensure_judgment_property_merges_missing_options():
    # 既存 option を保持しつつ不足 5 値だけ追加する。
    patches = []
    req = _fake_req(db_props={"判定": {"select": {"options": [{"name": "確認OK", "color": "green"}]}}},
                   db_patches=patches)
    state = wb.ensure_judgment_property("sheetdb", "tok", req)
    assert state == "updated"
    names = [o["name"] for o in patches[0]["判定"]["select"]["options"]]
    assert "確認OK" in names and "発行漏れ" in names and "未照合" in names


def test_ensure_judgment_property_noop_when_complete():
    req = _fake_req(db_props={"判定": {"select": {"options": [{"name": n} for n in wb.SHEET_LABELS]}}})
    assert wb.ensure_judgment_property("sheetdb", "tok", req) == "ok"


def test_ensure_judgment_property_fail_soft_on_unknown_label_color(monkeypatch):
    # SSOT に色未定義の 6 値目が増えても KeyError で全停止せず default 色で fail-soft 投影する。
    monkeypatch.setattr(wb, "SHEET_LABELS", wb.SHEET_LABELS + ["新ラベル"])
    # 作成パス (判定列なし) と マージパス (既存option保持) の両方で KeyError を出さない。
    patches = []
    req = _fake_req(db_props={}, db_patches=patches)
    assert wb.ensure_judgment_property("sheetdb", "tok", req) == "created"
    new_opt = {o["name"]: o["color"] for o in patches[0]["判定"]["select"]["options"]}["新ラベル"]
    assert new_opt == "default"
    patches2 = []
    req2 = _fake_req(db_props={"判定": {"select": {"options": [{"name": "発行漏れ", "color": "red"}]}}},
                     db_patches=patches2)
    assert wb.ensure_judgment_property("sheetdb", "tok", req2) == "updated"
    merged = {o["name"]: o.get("color") for o in patches2[0]["判定"]["select"]["options"]}
    assert merged["新ラベル"] == "default"


def test_writeback_failure_is_collected_not_raised():
    def req(method, path, token, body=None):
        if method == "GET":
            return {"properties": {"判定": {"select": {"options": []}}}}
        if method == "PATCH" and path.startswith("/databases/"):
            return {}
        if method == "PATCH" and path.startswith("/pages/"):
            raise RuntimeError("boom")
        raise AssertionError(path)
    res = wb.writeback([{"verdict": "GAP", "_sheet_row_ids": ["pg1"]}], "s", "t", req)
    assert res["updated"] == 0
    assert len(res["failed"]) == 1 and res["failed"][0]["page_id"] == "pg1"
