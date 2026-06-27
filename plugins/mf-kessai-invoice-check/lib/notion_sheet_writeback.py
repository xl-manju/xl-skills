"""請求確認シート『判定』(5値select) + 『AI確認』(checkbox) への片方向ミラー書き戻し。

責務分離ハイブリッド (reconcile-redesign-plan §2) のシート投影面。判定 SoR は裏方台帳 (DB2) で、
シートの『判定』『AI確認』はそこから決定論的に再計算した 5 値投影にすぎない (片方向ミラー)。
stale は再実行で自己修復する (冪等)。経理は『判定=発行漏れ』など色付き select の保存ビュー 1 枚で回せる。

『確認ポイント』(rich_text) には verdict ごとの「何を確認すべきか」を行固有の警告詳細つきで書く
(要確認/発行漏れ で経理が次に何をすべきか分かるようにする。AIの確認OK/対象外 は空文字で stale を消す)。

非破壊規律 (managed 列):
  - 機械が常時上書きするのは『判定』(select) ・『AI確認』(checkbox) ・『確認ポイント』(rich_text) の 3 列。
  - 加えて『契約開始日』『契約終了月』は **空欄セルのみ** 派生値 (確認内容の期間/終了注記由来) で
    自動補完する (current_dates で現値を渡したとき)。人間が入力済みの非空値は上書きしない。
  - 人間列『チェック済み』『確認内容』『取引先』等には一切 PATCH しない。
  - 当月 (target_ym) の reconcile forward rows だけが入力なので、過去月のシート行は触れない。
  - ORPHAN (逆方向・シート行なし) は sheet_label=None で投影スキップ (verdict-mapping.json SSOT)。

判定→5値は verdict-mapping.json の sheet_label を唯一の正本とし、ここで別表記を作らない
(mfk_reconcile.sheet_label / is_check_verdict 経由で派生)。
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mfk_reconcile  # noqa: E402

PROP_JUDGE = "判定"        # シート 5 値 select (本 lib が新設・管理)
PROP_AI_CHECK = "AI確認"   # シート checkbox (既存・機械が片方向ミラー)
PROP_NOTE = "確認ポイント"  # シート rich_text (本 lib が新設・管理): 何を確認すべきかのガイダンス
PROP_START = "契約開始日"  # シート rich_text (既存・人間入力)。空欄のみ期間から自動補完する
PROP_END = "契約終了月"    # シート rich_text (既存・人間入力)。空欄のみ確認内容の終了注記から自動補完


def _iso_to_yymm(iso):
    """ISO 'YYYY-MM-DD' → 'YYMM' (契約終了月 列の既存フォーマットに合わせる)。不正は None。"""
    m = re.match(r"(\d{4})-(\d{2})", iso or "")
    return f"{m.group(1)[2:]}{m.group(2)}" if m else None

# 5 値 SSOT は verdict-mapping.json の sheet_labels。読込失敗時だけ既定値へ fail-soft。
def _sheet_labels():
    path = mfk_reconcile.VERDICT_MAPPING_PATH
    try:
        import json
        with open(path, encoding="utf-8") as fh:
            labels = json.load(fh).get("sheet_labels") or []
        if labels:
            return labels
    except (OSError, ValueError):
        pass
    return ["未照合", "AIの確認OK", "対象外", "要確認", "発行漏れ"]


SHEET_LABELS = _sheet_labels()
LABEL_COLORS = {
    "未照合": "default",
    "AIの確認OK": "green",
    "対象外": "gray",
    "要確認": "yellow",
    "発行漏れ": "red",
}


def ensure_judgment_property(sheet_db_id, token, req):
    """シートに『判定』select(5値・色付き)を冪等に用意する。

    既存 option は消さず、不足している 5 値だけを色付きで追加する (非破壊)。
    返り値: "created" / "updated" / "ok"。
    """
    res = req("GET", f"/databases/{sheet_db_id}", token)
    existing = res.get("properties", {}).get(PROP_JUDGE)
    # SSOT(verdict-mapping.json sheet_labels)に色未定義の6値目が増えても KeyError で
    # writeback 全停止しないよう fail-soft (未知ラベルは default 色)。
    want = [{"name": n, "color": LABEL_COLORS.get(n, "default")} for n in SHEET_LABELS]
    if existing is None:
        req("PATCH", f"/databases/{sheet_db_id}", token,
            {"properties": {PROP_JUDGE: {"select": {"options": want}}}})
        return "created"
    by_name = {o["name"]: o for o in (existing.get("select") or {}).get("options", [])}
    merged = list(by_name.values())
    changed = False
    for n in SHEET_LABELS:
        if n not in by_name:
            merged.append({"name": n, "color": LABEL_COLORS.get(n, "default")})
            changed = True
    if changed:
        req("PATCH", f"/databases/{sheet_db_id}", token,
            {"properties": {PROP_JUDGE: {"select": {"options": merged}}}})
        return "updated"
    return "ok"


def ensure_note_property(sheet_db_id, token, req):
    """シートに『確認ポイント』rich_text を冪等に用意する (無ければ追加)。"""
    res = req("GET", f"/databases/{sheet_db_id}", token)
    if PROP_NOTE not in res.get("properties", {}):
        req("PATCH", f"/databases/{sheet_db_id}", token,
            {"properties": {PROP_NOTE: {"rich_text": {}}}})
        return "created"
    return "ok"


def compose_note(verdict, warning, mapping=None):
    """『確認ポイント』本文 = verdict 定型ガイダンス + 行固有の警告詳細。

    ai_check(確認OK/対象外 に投影される verdict)は warning があっても必ず空文字を返す
    (Request3)。集約請求の MATCH_MONTHLY は engine(quantity_downgrade)が verdict を保ちつつ
    warning="MF 1明細に期待N件分が集約…" を付すが、判定が『AIの確認OK』である以上シートの
    確認ポイントには漏らさない。warning は DB2『警告』列に別途残るため情報は失われない
    (関心の分離)。要確認/発行漏れ系は定型ガイダンス + 行固有警告を返す。警告がガイダンスに
    未包含なら全角括弧で連結する (数量差の想定漏れ額等の行固有情報を残す)。
    """
    mp = mapping if mapping is not None else mfk_reconcile.load_verdict_mapping()
    # ai_check(AIの確認OK/対象外)は warning の有無に関わらず空 = stale を消す (Request3)。
    if mfk_reconcile.is_check_verdict(verdict, mp):
        return ""
    hint = mfk_reconcile.action_hint(verdict, mp)
    w = (warning or "").strip()
    if hint and w and w not in hint:
        return f"{hint}（{w}）"
    return hint or w


def build_writeback(forward_rows, mapping=None):
    """forward reconcile rows → [{page_id, sheet_label, ai_check, note, verdict, start, end_yymm}]。

    sheet_label が None (ORPHAN/未定義) の行は投影しない。1 契約=複数シート行は全行へ展開する。
    同一 page_id が複数契約に現れることは契約境界キー上ないが、保険で重複除去する。
    note は『確認ポイント』本文 (AIの確認OK/対象外は空 = stale を消す)。start(契約開始日 ISO)・
    end_yymm(契約終了月 YYMM) は空欄セルの自動補完候補 (派生値。writeback が空欄のみ書く)。
    """
    mp = mapping if mapping is not None else mfk_reconcile.load_verdict_mapping()
    out, seen = [], set()
    for r in forward_rows or []:
        verdict = r.get("verdict")
        label = mfk_reconcile.sheet_label(verdict, mp)
        if not label:
            continue
        ai = mfk_reconcile.is_check_verdict(verdict, mp)
        note = compose_note(verdict, r.get("warning"), mp)
        start = r.get("契約開始日") or None
        end_yymm = _iso_to_yymm(r.get("契約終了月"))
        for pid in (r.get("_sheet_row_ids") or []):
            if not pid or pid in seen:
                continue
            seen.add(pid)
            out.append({"page_id": pid, "sheet_label": label, "ai_check": bool(ai),
                        "note": note, "verdict": verdict, "start": start, "end_yymm": end_yymm})
    return out


def writeback(forward_rows, sheet_db_id, token, req, mapping=None, current_dates=None):
    """シート各行へ『判定』『AI確認』『確認ポイント』を冪等 PATCH し、空欄の『契約開始日』
    『契約終了月』を派生値で自動補完する (非破壊: 人間入力の非空値は上書きしない)。

    current_dates: {page_id: {"契約開始日": raw, "契約終了月": raw}}。当月シートの現値。これが
    空欄のセルにのみ派生 start(ISO)/end_yymm(YYMM) を書く。None なら日付補完をスキップ
    (後方互換・判定3列のみ)。人間列 (チェック済み/確認内容/取引先) には一切触れない。

    返り値: {"updated", "failed"(list), "targeted", "schema"}。個別失敗は握りつぶさず
    failed に積み、呼び出し側で stderr 可視化する (silent cap 禁止)。
    """
    schema_state = ensure_judgment_property(sheet_db_id, token, req)
    ensure_note_property(sheet_db_id, token, req)
    items = build_writeback(forward_rows, mapping)
    updated, failed = 0, []
    for it in items:
        props = {
            PROP_JUDGE: {"select": {"name": it["sheet_label"]}},
            PROP_AI_CHECK: {"checkbox": it["ai_check"]},
            # 確認ポイント: 空でも投入し stale を消す (片方向ミラー一貫性)。
            PROP_NOTE: {"rich_text": [{"text": {"content": it["note"][:1900]}}]},
        }
        # 契約開始日/契約終了月: 当月シートで空欄のセルだけ派生値で自動補完。current_dates が
        # None(現値不明)、または当該 page_id の現値が無いときは補完しない (非空=人間入力は不可侵)。
        rc = current_dates.get(it["page_id"]) if current_dates is not None else None
        if rc is not None:
            if it.get("start") and not (rc.get("契約開始日") or "").strip():
                props[PROP_START] = {"rich_text": [{"text": {"content": it["start"]}}]}
            if it.get("end_yymm") and not (rc.get("契約終了月") or "").strip():
                props[PROP_END] = {"rich_text": [{"text": {"content": it["end_yymm"]}}]}
        try:
            req("PATCH", f"/pages/{it['page_id']}", token, {"properties": props})
            updated += 1
        except Exception as e:  # noqa: BLE001 — 1 行失敗で全体を止めない
            failed.append({"page_id": it["page_id"], "error": str(e)[:200]})
    return {"updated": updated, "failed": failed,
            "targeted": len(items), "schema": schema_state}
