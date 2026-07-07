#!/usr/bin/env python3
"""notion_report_sink.py (C06) を fake-store req モックで完全オフライン検証する。

網羅する 7 観点 (component-inventory C06 criteria 由来):
  1. 月次新規 DB 作成 (トグル配下 child_database)。
  2. 同一対象月の month_db_id 再利用 (二重 DB 0)。
  3. newest-on-top / YYYY-MM 昇順安定挿入。
  4. 月内冪等 (upsert 主キー {customer×contract_id×product} で 2 回投入 1 行収束・重複行 0)。
  5. 先月の金額 / 今月の金額 列充足。
  6. 列順と title 固定 (取引先名=title・build_property 踏襲・7 列 左→右)。
  7. 非破壊マージ (run-1={A,B} → run-2={A,C} で当月 DB が {A,B,C} 保持・deleted=0)。
ネットワークは一切叩かない (req を関数引数で差し替え)。
"""
import json

import notion_report_sink as sink


# ---------------------------------------------------------------------------
# fake Notion store: トグル子ブロック + DB + ページを in-memory dict で模す。
#   - GET  /blocks/{toggle}/children      → トグル子ブロック list
#   - POST /databases                     → child_database 作成 (id=database_id・子として登録)
#   - POST /databases/{db}/query          → その DB のページ list (= 当月行)
#   - POST /pages                         → ページ作成
#   - PATCH /pages/{id}                   → ページ更新
# ---------------------------------------------------------------------------

def _make_store(children=None):
    state = {
        "children": list(children or []),  # トグル配下のブロック list
        "pages": {},                       # page_id -> {"db": db_id, "properties": {...}}
        "dbs": {},                         # db_id -> title
        "seq": 0,
        "calls": [],
    }

    def req(method, path, token, body=None):
        state["calls"].append((method, path, body))

        if method == "GET" and path.startswith("/blocks/") and "/children" in path:
            return {"results": list(state["children"]), "has_more": False}

        if method == "POST" and path == "/databases":
            # database の parent は page_id のみ許容 (block_id=トグルは Notion API 2022-06-28 で不可)。
            # block_id 親の再混入をこの fake-store が機械 fail させる (実 API 制約を offline で固定)。
            assert body["parent"]["type"] == "page_id" and body["parent"].get("page_id"), \
                f"database parent must be page_id (block_id 不可): {body['parent']}"
            state["seq"] += 1
            db_id = f"db-{state['seq']}"
            title = body["title"][0]["text"]["content"]
            state["dbs"][db_id] = title
            # child_database ブロックの id は database_id と一致する。
            state["children"].append(
                {"id": db_id, "type": "child_database", "child_database": {"title": title}})
            return {"id": db_id}

        if method == "POST" and path.startswith("/databases/") and path.endswith("/query"):
            db_id = path[len("/databases/"):-len("/query")]
            results = [{"id": pid, "properties": p["properties"]}
                       for pid, p in state["pages"].items() if p["db"] == db_id]
            return {"results": results, "has_more": False}

        if method == "POST" and path == "/pages":
            state["seq"] += 1
            pid = f"pg-{state['seq']}"
            db_id = body["parent"]["database_id"]
            state["pages"][pid] = {"db": db_id, "properties": dict(body["properties"])}
            return {"id": pid}

        if method == "PATCH" and path.startswith("/pages/"):
            pid = path[len("/pages/"):]
            state["pages"][pid]["properties"].update(body["properties"])
            return {"id": pid}

        raise AssertionError((method, path, body))

    return req, state


def _child_db(title):
    """既存 child_database ブロックを組む (id=database_id 一致)。"""
    return {"id": f"blk-{title}", "type": "child_database", "child_database": {"title": title}}


def _rows_in(state, db_id):
    """当月 DB の (取引先名, 商品名) キー集合 (fake store 上の実行後スナップショット)。"""
    keys = set()
    for p in state["pages"].values():
        if p["db"] != db_id:
            continue
        props = p["properties"]
        cust = sink._title_plain(props.get(sink.PROP_CUSTOMER))
        prod = "".join(
            (rt.get("text") or {}).get("content", "")
            for rt in (props.get(sink.PROP_PRODUCT, {}).get("rich_text") or []))
        keys.add((cust, prod))
    return keys


# ---------------------------------------------------------------------------
# 純関数
# ---------------------------------------------------------------------------

def test_target_to_yyyymm_and_title():
    assert sink.target_to_yyyymm("2607") == "2026-07"
    assert sink.month_db_title("2607") == "請求漏れ比較レポート 2026-07"


def test_valid_target():
    assert sink._valid_target("2607")
    assert sink._valid_target("2601")
    assert not sink._valid_target("2613")   # 月 13 は不正
    assert not sink._valid_target("260")     # 桁不足
    assert not sink._valid_target("26o7")    # 非数字


def test_parse_report_yyyymm_ignores_non_report_titles():
    assert sink._parse_report_yyyymm("請求漏れ比較レポート 2026-07") == "2026-07"
    assert sink._parse_report_yyyymm("メモ 2026-07") is None    # prefix 不一致
    assert sink._parse_report_yyyymm("請求漏れ比較レポート") is None  # 年月なし


def test_stored_key_is_recoverable_pair():
    # 回収可能キーは (取引先名, 商品名)。契約ID は 7 列に列が無く persist 不能ゆえ含まない。
    # キーは名寄せ SSOT mfk_reconcile.normalize (NFKC + 法人格/空白除去 + lower) を通す (F-11)。
    assert sink._stored_key("A社", "月額P") == ("a社", "月額p")


def test_stored_key_absorbs_name_drift():
    # F-11: 同一取引先が NFD↔NFC カタカナ / 全角半角 / 法人格差で raw 揺れしても同一キーへ収束し、
    # 同月2回実行の重複行 (冪等 C7/OUT1 崩れ) を防ぐ。
    import unicodedata
    nfc = "ダイヤ商事"  # 濁点付きカナは NFD で 基底カナ + 結合濁点 に分解される
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfd != nfc  # raw では別文字列 (macOS/MF API 由来の NFD 罠)
    assert sink._stored_key(nfd, "月額P") == sink._stored_key(nfc, "月額P")
    assert sink._stored_key("テスト株式会社", "P") == sink._stored_key("テスト㈱", "P")


def test_prefer_action_keeps_gap_over_normal():
    # F-α safe guard: 同一(取引先,商品)衝突時、要対応を正常が上書きして漏れを隠さない。
    normal = {"gap_check": "正常", "customer": "A社", "product": "P", "contract_id": "C1"}
    action = {"gap_check": "要対応", "customer": "A社", "product": "P", "contract_id": "C2"}
    assert sink._prefer_action(normal, action) is action   # 正常←→要対応 は要対応が残る
    assert sink._prefer_action(action, normal) is action   # 順序に依らず要対応が残る


def test_title_plain_and_child_db_title():
    assert sink._title_plain({"title": [{"text": {"content": "あ"}}, {"plain_text": "い"}]}) == "あい"
    assert sink._title_plain(None) == ""
    assert sink._child_db_title({"child_database": {"title": "T"}}) == "T"
    assert sink._child_db_title(None) == ""


# ---------------------------------------------------------------------------
# 観点 6: 7 列スキーマ (列順固定・build_property 踏襲・title=取引先名)
# ---------------------------------------------------------------------------

def test_schema_properties_column_order_and_types():
    props = sink.schema_properties()
    # 列順 SSOT (この左→右順)。取引先名=title を先頭に置き Notion の title 最左固定と一致させる。
    assert list(props.keys()) == [
        "取引先名", "漏れチェック", "商品名", "先月の金額", "今月の金額", "先月と今月の比較", "コメント"]
    # build_property 踏襲の型写像。
    assert "title" in props["取引先名"]                       # title = 取引先名
    assert "rich_text" in props["商品名"]
    assert props["先月の金額"]["number"]["format"] == "yen"    # 税抜金額 (yen)
    assert props["今月の金額"]["number"]["format"] == "yen"
    assert "rich_text" in props["先月と今月の比較"]
    assert "rich_text" in props["コメント"]
    assert "checkbox" in props["漏れチェック"]                 # 正常=✓ / 要対応=☐


# ---------------------------------------------------------------------------
# 観点 1: 月次新規 DB 作成 (トグル配下 child_database)
# ---------------------------------------------------------------------------

def test_create_month_db_under_page_as_child_database():
    req, state = _make_store()
    db_id, reused, placement = sink.find_or_create_month_db("2607", "PAGE", "tok", req=req)

    assert reused is False
    post = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/databases")
    body = post[2]
    # 指定ページ直下の child_database として作成 (parent=page_id・block_id 不可)。
    assert body["parent"] == {"type": "page_id", "page_id": "PAGE"}
    assert body["title"][0]["text"]["content"] == "請求漏れ比較レポート 2026-07"
    # 7 列スキーマが列順 SSOT で載る (取引先名=title を先頭に定義=Notion 表示順と一致)。
    assert list(body["properties"].keys())[:2] == ["取引先名", "漏れチェック"]
    assert state["dbs"][db_id] == "請求漏れ比較レポート 2026-07"
    assert placement["api_strategy"] == "append-child-database"


# ---------------------------------------------------------------------------
# 観点 2: 同一対象月の month_db_id 再利用 (二重 DB 0)
# ---------------------------------------------------------------------------

def test_reuse_existing_month_db_no_duplicate():
    existing = _child_db("請求漏れ比較レポート 2026-07")
    req, state = _make_store(children=[existing])
    db_id, reused, placement = sink.find_or_create_month_db("2607", "PAGE", "tok", req=req)

    assert reused is True
    assert db_id == existing["id"]           # 一致ブロックの id = database_id
    assert placement["reused"] is True
    # 二重 DB を作らない: POST /databases は一度も呼ばれない。
    assert all(not (c[0] == "POST" and c[1] == "/databases") for c in state["calls"])


def test_reuse_is_idempotent_across_two_runs():
    req, state = _make_store()
    id1, reused1, _ = sink.find_or_create_month_db("2607", "PAGE", "tok", req=req)
    id2, reused2, _ = sink.find_or_create_month_db("2607", "PAGE", "tok", req=req)
    assert reused1 is False and reused2 is True     # 2 回目は再利用
    assert id1 == id2                                # 同じ month_db_id
    assert sum(1 for c in state["calls"] if c[0] == "POST" and c[1] == "/databases") == 1


# ---------------------------------------------------------------------------
# 観点 3: newest-on-top / YYYY-MM 昇順安定挿入
# ---------------------------------------------------------------------------

def test_intended_index_newest_on_top():
    # 既存 [2026-07]。新月ほど上 (index 0)。
    assert sink.intended_index(["2026-07"], "2026-08") == 0   # より新しい → 先頭
    assert sink.intended_index(["2026-07"], "2026-06") == 1   # より古い → 07 の下
    assert sink.intended_index(["2026-08", "2026-06"], "2026-07") == 1  # 08 の下・06 の上
    assert sink.intended_index([], "2026-07") == 0


def test_late_added_past_month_does_not_jump_to_top():
    """過去月 --target 後追いでも先頭に割り込まず正しい下位位置へ入る (単純 prepend でない)。"""
    children = [_child_db("請求漏れ比較レポート 2026-08"),
                _child_db("請求漏れ比較レポート 2026-07")]
    req, state = _make_store(children=children)
    _, _, placement = sink.find_or_create_month_db("2606", "PAGE", "tok", req=req)
    # 2026-06 は既存 08/07 より古いので意図位置は末尾 (index 2)、先頭ではない。
    assert placement["intended_index"] == 2
    assert placement["sibling_month_dbs"] == 2


def test_find_or_create_dry_run_does_not_create():
    """apply=False で未発見なら DB を作らず (month_db_id=None・created=False)。"""
    req, state = _make_store()
    db_id, reused, placement = sink.find_or_create_month_db(
        "2607", "PAGE", "tok", req=req, apply=False)
    assert db_id is None and reused is False
    assert placement["created"] is False
    assert all(not (c[0] == "POST" and c[1] == "/databases") for c in state["calls"])


def test_placement_ignores_non_report_child_databases():
    """トグル配下のレポート以外の child_database は月順序判定から除外する。"""
    children = [_child_db("請求漏れ比較レポート 2026-07"), _child_db("その他メモDB")]
    req, state = _make_store(children=children)
    _, _, placement = sink.find_or_create_month_db("2608", "PAGE", "tok", req=req)
    assert placement["sibling_month_dbs"] == 1       # 「その他メモDB」は数えない
    assert placement["intended_index"] == 0          # 2026-08 は最新 → 先頭


# ---------------------------------------------------------------------------
# 観点 5 + 6: レポート行の作成 (先月/今月の金額列充足・7 列・title=取引先名)
# ---------------------------------------------------------------------------

def test_upsert_creates_row_with_all_seven_columns():
    req, state = _make_store()
    rows = [{
        "check": "正常", "customer": "A社", "contract_id": "C1", "product": "月額プラン",
        "prev_amount": 10000, "curr_amount": 12000,
        "comparison": "+2,000 (増額)", "comment": "継続発行・正常",
    }]
    res = sink.upsert_report_rows(rows, "db-1", "tok", req=req)
    assert res == {"created": 1, "updated": 0, "skipped": 0, "deleted": 0,
                   "collapsed_multi_contract": 0}

    props = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")[2]["properties"]
    # title = 取引先名。
    assert props[sink.PROP_CUSTOMER]["title"][0]["text"]["content"] == "A社"
    assert props[sink.PROP_MISSING_CHECK]["checkbox"] is True
    assert props[sink.PROP_PRODUCT]["rich_text"][0]["text"]["content"] == "月額プラン"
    # 観点 5: 先月/今月の金額列が充足する (税抜)。
    assert props[sink.PROP_PREV_AMOUNT]["number"] == 10000
    assert props[sink.PROP_CURR_AMOUNT]["number"] == 12000
    assert props[sink.PROP_COMPARISON]["rich_text"][0]["text"]["content"] == "+2,000 (増額)"
    assert props[sink.PROP_COMMENT]["rich_text"][0]["text"]["content"] == "継続発行・正常"


def test_prev_amount_zero_is_written():
    """先月の金額=0 は欠落でなく有効値として number に載る (is not None 判定)。"""
    req, state = _make_store()
    sink.upsert_report_rows([{"customer": "A社", "prev_amount": 0, "curr_amount": 5000}],
                            "db-1", "tok", req=req)
    props = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")[2]["properties"]
    assert props[sink.PROP_PREV_AMOUNT]["number"] == 0


def test_row_missing_customer_is_skipped():
    req, state = _make_store()
    res = sink.upsert_report_rows([{"product": "P", "curr_amount": 1}], "db-1", "tok", req=req)
    assert res == {"created": 0, "updated": 0, "skipped": 1, "deleted": 0,
                   "collapsed_multi_contract": 0}
    assert all(not (c[0] == "POST" and c[1] == "/pages") for c in state["calls"])


def test_comment_preserves_newlines():
    req, state = _make_store()
    comment = "年契約のため今月は請求なし\n(2026-04 に一括発行済)"
    sink.upsert_report_rows([{"customer": "A社", "comment": comment}], "db-1", "tok", req=req)
    content = (next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")
               [2]["properties"][sink.PROP_COMMENT]["rich_text"][0]["text"]["content"])
    assert content == comment
    assert content.count("\n") == 1


# ---------------------------------------------------------------------------
# 観点 4: 月内冪等 (2 回投入 1 行収束・重複行 0)
# ---------------------------------------------------------------------------

def test_idempotent_two_runs_collapse_to_one_row():
    """同月 DB へ同一 {customer×contract_id×product} 行を 2 回投入 → 1 行 (2 回目は更新)。"""
    req, state = _make_store()
    row = {"check": "正常", "customer": "A社", "contract_id": "C1", "product": "月額P",
           "prev_amount": 100, "curr_amount": 100, "comment": "初日"}

    res1 = sink.upsert_report_rows([row], "db-1", "tok", req=req)
    assert res1 == {"created": 1, "updated": 0, "skipped": 0, "deleted": 0,
                    "collapsed_multi_contract": 0}

    row2 = dict(row, comment="2営業日目")
    res2 = sink.upsert_report_rows([row2], "db-1", "tok", req=req)
    assert res2 == {"created": 0, "updated": 1, "skipped": 0, "deleted": 0,
                    "collapsed_multi_contract": 0}   # 2 回目は更新

    assert _rows_in(state, "db-1") == {("A社", "月額P")}                       # 重複行 0 = 1 行
    assert len([p for p in state["pages"].values() if p["db"] == "db-1"]) == 1


def test_same_run_duplicate_rows_collapse():
    """同一 run 内で同一キー行が複数あっても 1 行へ収束 (last-wins)。"""
    req, state = _make_store()
    rows = [
        {"customer": "A社", "contract_id": "C1", "product": "P", "comment": "old"},
        {"customer": "A社", "contract_id": "C1", "product": "P", "comment": "new"},
    ]
    res = sink.upsert_report_rows(rows, "db-1", "tok", req=req)
    assert res["created"] == 1
    assert len([p for p in state["pages"].values() if p["db"] == "db-1"]) == 1
    props = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")[2]["properties"]
    assert props[sink.PROP_COMMENT]["rich_text"][0]["text"]["content"] == "new"


def test_update_does_not_send_title():
    """更新 (PATCH) では不変な表示キー title (取引先名) を送らない。"""
    req, state = _make_store()
    row = {"customer": "A社", "product": "P", "comment": "x"}
    sink.upsert_report_rows([row], "db-1", "tok", req=req)
    sink.upsert_report_rows([dict(row, comment="y")], "db-1", "tok", req=req)
    patch = next(c for c in state["calls"] if c[0] == "PATCH")
    assert sink.PROP_CUSTOMER not in patch[2]["properties"]


# ---------------------------------------------------------------------------
# 観点 7: 非破壊マージ (run-1={A,B} → run-2={A,C} で {A,B,C} 保持・deleted=0)
# ---------------------------------------------------------------------------

def test_non_destructive_merge_keeps_prior_rows():
    req, state = _make_store()
    sink.upsert_report_rows(
        [{"customer": "A社", "product": "P"}, {"customer": "B社", "product": "P"}],
        "db-1", "tok", req=req)
    assert _rows_in(state, "db-1") == {("A社", "P"), ("B社", "P")}

    # run-2 は A と C のみ。B は入力に無いが削除しない (非破壊マージ)。
    res2 = sink.upsert_report_rows(
        [{"customer": "A社", "product": "P"}, {"customer": "C社", "product": "P"}],
        "db-1", "tok", req=req)
    assert res2["deleted"] == 0                                   # 常時 0
    assert res2["updated"] == 1 and res2["created"] == 1          # A=更新・C=新規
    assert _rows_in(state, "db-1") == {("A社", "P"), ("B社", "P"), ("C社", "P")}  # B が残る
    # clear-then-insert でない: B 宛ての削除/アーカイブ呼び出しが一切ない。
    assert all(c[0] != "DELETE" for c in state["calls"])
    assert all("archived" not in json.dumps(c[2] or {}) for c in state["calls"])


# ---------------------------------------------------------------------------
# query_month: ページング + dedup + 当月 DB スコープ
# ---------------------------------------------------------------------------

def test_query_month_paginates_and_dedups():
    pages = [
        {"results": [{"id": "a", "properties": {}}, {"id": "b", "properties": {}}],
         "has_more": True, "next_cursor": "c2"},
        {"results": [{"id": "b", "properties": {}}, {"id": "c", "properties": {}}],
         "has_more": False},
    ]
    cursors = []

    def req(method, path, token, body=None):
        cursors.append((body or {}).get("start_cursor"))
        assert path == "/databases/db-1/query"
        return pages.pop(0)

    out = sink.query_month("db-1", "tok", req=req)
    assert [p["id"] for p in out] == ["a", "b", "c"]   # b は dedup
    assert cursors == [None, "c2"]


def test_query_month_scoped_to_target_db_only():
    """query は当該 month DB のページだけ返す (別 DB=過去月は射程外)。"""
    req, state = _make_store()
    state["pages"] = {
        "p1": {"db": "db-cur", "properties": {sink.PROP_CUSTOMER: {"title": [{"text": {"content": "A"}}]}}},
        "p2": {"db": "db-old", "properties": {sink.PROP_CUSTOMER: {"title": [{"text": {"content": "B"}}]}}},
    }
    out = sink.query_month("db-cur", "tok", req=req)
    titles = {sink._title_plain(p["properties"].get(sink.PROP_CUSTOMER)) for p in out}
    assert titles == {"A"}


def test_list_block_children_paginates():
    pages = [
        {"results": [{"id": "x"}], "has_more": True, "next_cursor": "n2"},
        {"results": [{"id": "y"}], "has_more": False},
    ]
    seen = []

    def req(method, path, token, body=None):
        seen.append(path)
        return pages.pop(0)

    out = sink.list_block_children("PAGE", "tok", req=req)
    assert [b["id"] for b in out] == ["x", "y"]
    assert "start_cursor=n2" in seen[1]


# ---------------------------------------------------------------------------
# 失敗隔離
# ---------------------------------------------------------------------------

def test_failed_row_is_isolated_and_counted_as_skipped():
    posts = []

    def req(method, path, token, body=None):
        if method == "POST" and path.endswith("/query"):
            return {"results": [], "has_more": False}
        if method == "POST" and path == "/pages":
            posts.append(body)
            if len(posts) == 2:
                raise RuntimeError("boom")
            return {"id": f"pg{len(posts)}"}
        raise AssertionError((method, path))

    rows = [{"customer": "A社", "product": "P1"},
            {"customer": "B社", "product": "P2"},
            {"customer": "C社", "product": "P3"}]
    res = sink.upsert_report_rows(rows, "db-1", "tok", req=req)
    assert res == {"created": 2, "updated": 0, "skipped": 1, "deleted": 0,
                   "collapsed_multi_contract": 0}


# ---------------------------------------------------------------------------
# run() orchestration (find-or-create → upsert 配線) と dry-run
# ---------------------------------------------------------------------------

def test_run_apply_creates_db_and_upserts():
    req, state = _make_store()
    cfg = {"notion": {"report_parent_page": "PAGE"}}
    rows = [{"customer": "A社", "product": "P", "prev_amount": 1, "curr_amount": 2}]
    res = sink.run(rows, "2607", cfg, "tok", req=req, apply=True)

    assert res["created"] == 1
    assert res["deleted"] == 0
    assert res["month_db_reused"] is False
    assert res["month_db_id"] in state["dbs"]
    assert res["placement"]["target_yyyymm"] == "2026-07"


def test_run_reuses_db_on_second_call():
    req, state = _make_store()
    cfg = {"notion": {"report_parent_page": "PAGE"}}
    rows = [{"customer": "A社", "product": "P"}]
    r1 = sink.run(rows, "2607", cfg, "tok", req=req, apply=True)
    r2 = sink.run([dict(rows[0], comment="day2")], "2607", cfg, "tok", req=req, apply=True)
    assert r1["month_db_id"] == r2["month_db_id"]
    assert r2["month_db_reused"] is True
    assert r2["updated"] == 1 and r2["created"] == 0


def test_run_dry_run_touches_no_network():
    called = []

    def req(method, path, token, body=None):
        called.append((method, path))
        raise AssertionError("dry-run must not call network")

    cfg = {"notion": {"report_parent_page": "PAGE"}}
    res = sink.run([{"customer": "A社"}, {"product": "no-customer"}],
                   "2607", cfg, None, req=req, apply=False)
    assert called == []
    assert res["dry_run"] is True
    assert res["planned_rows"] == 1        # customer 無し行は除外
    assert res["skipped"] == 1
    assert res["month_db_id"] is None
    assert res["placement"]["note"].startswith("dry-run")


def test_run_invalid_target_raises():
    import pytest
    with pytest.raises(sink.SinkError):
        sink.run([], "2699", {"notion": {"report_parent_page": "P"}}, "tok", apply=True)


def test_run_missing_parent_page_raises_on_apply():
    import pytest
    # report_parent_page 未設定は fail-closed (月次 DB を置くページが不明)。
    with pytest.raises(sink.SinkError):
        sink.run([{"customer": "A"}], "2607", {"notion": {}}, "tok", apply=True)


# ---------------------------------------------------------------------------
# main() CLI (dry-run / apply / fail-closed)
# ---------------------------------------------------------------------------

def test_main_dry_run(tmp_path, capsys):
    rows_file = tmp_path / "rows.json"
    rows_file.write_text(json.dumps([{"customer": "A社", "product": "P"}]), encoding="utf-8")
    rc = sink.main(["--rows", str(rows_file), "--target", "2607"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True
    assert out["month_db_id"] is None


def test_main_apply_wires_fake_req(tmp_path, capsys, monkeypatch):
    rows_file = tmp_path / "rows.json"
    rows_file.write_text(json.dumps([{"customer": "A社", "product": "P", "curr_amount": 3}]),
                         encoding="utf-8")
    req, state = _make_store()

    monkeypatch.setattr(sink, "load_config",
                        lambda p=None: {"notion": {"report_parent_page": "PAGE"}})
    monkeypatch.setattr(sink, "_notion_token", lambda cfg=None: "tok")
    monkeypatch.setattr(sink, "_req", req)     # run() の req or _req が拾う

    rc = sink.main(["--rows", str(rows_file), "--target", "2607", "--apply", "--verified"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["created"] == 1
    assert out["month_db_id"] in state["dbs"]


def test_main_invalid_rows_json_fails_closed(tmp_path, capsys):
    rows_file = tmp_path / "rows.json"
    rows_file.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    rc = sink.main(["--rows", str(rows_file), "--target", "2607"])
    assert rc == 2
    assert "JSON list" in capsys.readouterr().err


def test_main_skipped_rows_exit_1(tmp_path, capsys, monkeypatch):
    rows_file = tmp_path / "rows.json"
    # customer 有り 1 + customer 無し 1 → apply で skipped=1 → exit 1。
    rows_file.write_text(json.dumps([{"customer": "A社"}, {"product": "P"}]), encoding="utf-8")
    req, state = _make_store()
    monkeypatch.setattr(sink, "load_config",
                        lambda p=None: {"notion": {"report_parent_page": "PAGE"}})
    monkeypatch.setattr(sink, "_notion_token", lambda cfg=None: "tok")
    monkeypatch.setattr(sink, "_req", req)
    rc = sink.main(["--rows", str(rows_file), "--target", "2607", "--apply", "--verified"])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["skipped"] == 1 and out["created"] == 1


def test_main_apply_without_verified_fails_closed(tmp_path, capsys):
    """--apply は --verified 必須 (書込ゲートを機械層で担保・prose でなく exit2)。"""
    rows_file = tmp_path / "rows.json"
    rows_file.write_text(json.dumps([{"customer": "A社"}]), encoding="utf-8")
    rc = sink.main(["--rows", str(rows_file), "--target", "2607", "--apply"])
    assert rc == 2
    assert "--verified" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# SEAM 統合テスト (C05 実出力 → C06 入力)
#   isolation では捕捉不能な『C05 出力キーと C06 入力キーの列名断裂』を、両端を実 pipe で
#   跨いで機械検証する。C05 producer キー gap_check/amount/period_diff が C06 の 7 列へ正しく
#   写像されないと 3 列が空になる (SKILL IN1 の verify_by:test の実体)。
# ---------------------------------------------------------------------------

def test_seam_c05_output_populates_all_seven_columns():
    import mfk_period_report as engine
    curr = {"target_month": "2606", "rows": [
        {"取引先": "継続社", "商品": "月額", "verdict": "MATCH_MONTHLY", "現行単価": 12000}]}
    prev = {"rows": [
        {"取引先": "継続社", "商品": "月額", "verdict": "MATCH_MONTHLY", "現行単価": 10000}]}
    rows = engine.build_report(curr, prev, target_month="2606")   # C05 の実出力形
    assert len(rows) == 1 and rows[0]["gap_check"] == "正常"

    req, state = _make_store()
    res = sink.upsert_report_rows(rows, "db-1", "tok", req=req)   # 無変換で C06 へ (直結パイプ)
    assert res["created"] == 1

    props = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")[2]["properties"]
    # seam 断裂なら 漏れチェック(gap_check)/今月の金額(amount)/比較(period_diff) が空になる。7 列全充足を固定。
    assert props[sink.PROP_CUSTOMER]["title"][0]["text"]["content"] == "継続社"
    assert props[sink.PROP_PRODUCT]["rich_text"][0]["text"]["content"] == "月額"
    assert props[sink.PROP_MISSING_CHECK]["checkbox"] is True          # ← gap_check
    assert props[sink.PROP_PREV_AMOUNT]["number"] == 10000
    assert props[sink.PROP_CURR_AMOUNT]["number"] == 12000                     # ← amount
    assert props[sink.PROP_COMPARISON]["rich_text"][0]["text"]["content"]      # ← period_diff
    assert props[sink.PROP_COMMENT]["rich_text"][0]["text"]["content"]


def test_seam_multi_contract_action_survives_collapse():
    """同一(取引先,商品)に契約ID違いの 正常+要対応 が来ても要対応が Notion に残る (F-α safe guard)。"""
    req, state = _make_store()
    rows = [
        {"gap_check": "正常", "customer": "A社", "product": "P", "contract_id": "C1", "comment": "正常契約"},
        {"gap_check": "要対応", "customer": "A社", "product": "P", "contract_id": "C2", "comment": "発行漏れ候補"},
    ]
    res = sink.upsert_report_rows(rows, "db-1", "tok", req=req)
    assert res["collapsed_multi_contract"] == 1                   # 多契約 collapse を計上 (可観測)
    posts = [c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages"]
    assert len(posts) == 1                                        # 1 行へ収束
    props = posts[0][2]["properties"]
    assert props[sink.PROP_MISSING_CHECK]["checkbox"] is False   # 要対応が生存=漏れ隠蔽なし


def test_seam_stopped_row_has_empty_curr_amount_but_populated_check():
    """今月なし(停止)行は今月の金額が正当に空・ただし漏れチェック/比較/コメントは埋まる。"""
    import mfk_period_report as engine
    curr = {"target_month": "2606", "rows": []}
    prev = {"rows": [{"取引先": "漏れ社", "商品": "月額", "verdict": "MATCH_MONTHLY", "現行単価": 5000}]}
    rows = engine.build_report(curr, prev, target_month="2606")
    assert len(rows) == 1 and rows[0]["gap_check"] == "要対応"     # 発行漏れ候補
    req, state = _make_store()
    sink.upsert_report_rows(rows, "db-1", "tok", req=req)
    props = next(c for c in state["calls"] if c[0] == "POST" and c[1] == "/pages")[2]["properties"]
    assert props[sink.PROP_MISSING_CHECK]["checkbox"] is False
    assert props[sink.PROP_PREV_AMOUNT]["number"] == 5000
    assert sink.PROP_CURR_AMOUNT not in props or props[sink.PROP_CURR_AMOUNT].get("number") is None
    assert props[sink.PROP_COMPARISON]["rich_text"][0]["text"]["content"]


# ---------------------------------------------------------------------------
# elegant-review Phase3 regression tests (F-2 / F-17 / F-A / F-15 / F-7)
# ---------------------------------------------------------------------------

def test_cross_run_action_not_downgraded_by_normal():
    """F-2: 前 run で立てた要対応を、次 run の正常が無条件上書きしない (cross-run safe guard)。"""
    req, state = _make_store()
    sink.upsert_report_rows(
        [{"gap_check": "要対応", "customer": "A社", "product": "P", "comment": "漏れ"}],
        "db-1", "tok", req=req)
    sink.upsert_report_rows(
        [{"gap_check": "正常", "customer": "A社", "product": "P", "comment": "正常"}],
        "db-1", "tok", req=req)
    pages = [p for p in state["pages"].values() if p["db"] == "db-1"]
    assert len(pages) == 1                                        # 同一行へ収束 (重複行なし)
    props = pages[0]["properties"]
    assert props[sink.PROP_MISSING_CHECK]["checkbox"] is False   # 要対応を保持=漏れ隠蔽なし
    note = "".join((rt.get("text") or {}).get("content", "")
                   for rt in props[sink.PROP_COMMENT]["rich_text"])
    assert "cross-run safe guard" in note                        # 保持した旨を注記


def test_same_severity_action_collapse_merges_comments():
    """F-17: 要対応×要対応(契約ID違い)の collapse で両方の漏れ詳細が消えない (情報保全)。"""
    a = {"gap_check": "要対応", "customer": "A社", "product": "P", "contract_id": "C1", "comment": "漏れ甲"}
    b = {"gap_check": "要対応", "customer": "A社", "product": "P", "contract_id": "C2", "comment": "漏れ乙"}
    merged = sink._prefer_action(a, b)
    assert "漏れ甲" in merged["comment"] and "漏れ乙" in merged["comment"]
    assert "C1" in merged["comment"] and "C2" in merged["comment"]
    # 正常×正常は従来どおり後着を採る (severity 差なし)。
    n1 = {"gap_check": "正常", "customer": "A社", "product": "P", "comment": "x"}
    n2 = {"gap_check": "正常", "customer": "A社", "product": "P", "comment": "y"}
    assert sink._prefer_action(n1, n2) is n2


def test_row_contract_maps_every_producer_key_to_column():
    """F-A: ROW_CONTRACT の各 producer キーが _build_row_props で mapped 列へ着地する (SSOT drift 検出)。"""
    sentinels = {
        "gap_check": "要対応", "customer": "顧客X", "product": "商品Y",
        "prev_amount": 111, "amount": 222, "period_diff": "比較Z", "comment": "コメントW",
    }
    props = sink._build_row_props(sentinels, creating=True)
    for producer_key, col in sink.ROW_CONTRACT.items():
        assert col in props, f"ROW_CONTRACT[{producer_key}]→{col} が _build_row_props 出力に不在 (SSOT drift)"
    assert props[sink.PROP_MISSING_CHECK]["checkbox"] is False
    assert props[sink.PROP_PREV_AMOUNT]["number"] == 111
    assert props[sink.PROP_CURR_AMOUNT]["number"] == 222
    assert props[sink.PROP_CUSTOMER]["title"][0]["text"]["content"] == "顧客X"


def test_token_missing_is_fail_closed_exit2(tmp_path, monkeypatch):
    """F-15: --apply で token 欠落は exit2 (fail-closed)。exit1 (部分成功誤認) にしない。"""
    rows_file = tmp_path / "rows.json"
    rows_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(sink, "load_config", lambda *a, **k: {"notion": {"report_parent_page": "P"}})

    def _boom(cfg):
        raise RuntimeError("NOTION_API_KEY 未設定")

    monkeypatch.setattr(sink, "_notion_token", _boom)
    rc = sink.main(["--rows", str(rows_file), "--target", "2607", "--apply", "--verified"])
    assert rc == 2


def test_apply_runtime_failure_is_fail_closed_exit2(tmp_path, monkeypatch):
    """F-15/F-B: apply 中の想定外例外 (Notion API 拒否等) は exit1 でなく exit2 (fail-closed)。"""
    rows_file = tmp_path / "rows.json"
    rows_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(sink, "load_config", lambda *a, **k: {"notion": {"report_parent_page": "P"}})
    monkeypatch.setattr(sink, "_notion_token", lambda cfg: "tok")

    def _api_reject(*a, **k):
        raise RuntimeError("Notion API: block_id parent は databases に使用不可")

    monkeypatch.setattr(sink, "run", _api_reject)
    rc = sink.main(["--rows", str(rows_file), "--target", "2607", "--apply", "--verified"])
    assert rc == 2


def test_target_month_mismatch_is_fail_closed():
    """F-7: 行の target_month と --target 不一致は誤月投入を防ぐため fail-closed。"""
    import pytest
    rows = [{"customer": "A社", "product": "P", "target_month": "2605"}]
    with pytest.raises(sink.SinkError):
        sink.run(rows, "2607", {"notion": {}}, None, apply=False)
    # 一致・target_month 無し行は通る (dry-run)。
    ok = sink.run([{"customer": "A社", "target_month": "2607"}], "2607", {"notion": {}}, None, apply=False)
    assert ok["dry_run"] is True
