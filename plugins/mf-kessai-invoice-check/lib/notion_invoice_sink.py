#!/usr/bin/env python3
"""発行漏れチェック結果を Notion DB に冪等 upsert する sink (顧客ID集約モデル)。

upsert キー = customer_id 単独。1顧客=1 Notion ページ。月が変わっても同じページを
更新し、新規ページを作らない。月次履歴は各顧客ページの**本文 table block**
(Notion type:"table") に 1 行=1 対象年月で蓄積する(自然キー=period_ym, 同月再実行は
既存行更新で冪等)。DBプロパティはその顧客の「最新月スナップショット」(事実列のみ)を
書き込み、管理列(請求要否/対応状況/チェック済/備考)には触れない
(人の運用記入を自動実行が上書きしないため)。
Notion トークンは Keychain (notion-api-key.xl-skills / xl-skills) から取得。
"""
import datetime
import json
import os
import subprocess
import urllib.error
import urllib.request

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# 本文 table block の固定列定義 (1行=1対象年月)。順序がセル順を規定する。
TABLE_COLUMNS = ["対象年月", "判定", "前月金額", "今月金額", "確認済み日時"]
TABLE_WIDTH = len(TABLE_COLUMNS)


def _notion_token():
    service = os.environ.get("NOTION_KEYCHAIN_SERVICE", "notion-api-key.xl-skills")
    account = os.environ.get("NOTION_KEYCHAIN_ACCOUNT", "xl-skills")
    env = os.environ.get("NOTION_API_KEY")
    if env and env.strip():
        return env.strip()
    res = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-s", service, "-a", account, "-w"],
        capture_output=True, text=True,
    )
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError(f"Notion token lookup failed (service={service}, account={account})")
    return res.stdout.strip()


def _req(method, path, token, body=None):
    url = NOTION_API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Notion-Version", NOTION_VERSION)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Notion {method} {path}: HTTP {e.code} {e.read().decode('utf-8', 'replace')}")


def _find_page(database_id, customer_id, token):
    """customer_id 単独で既存ページを検索。あれば page_id を返す。

    顧客IDは一意のはず。複数ヒットは冪等キー破壊なので暗黙に先頭採用せず raise する。
    """
    body = {"filter": {"property": "顧客ID", "rich_text": {"equals": customer_id}}}
    res = _req("POST", f"/databases/{database_id}/query", token, body)
    items = res.get("results", [])
    if len(items) > 1:
        raise RuntimeError(
            f"重複ページ検出: 顧客ID={customer_id} が {len(items)}件存在。"
            "手動で重複を解消してから再実行してください (顧客ID は一意のはず)。")
    return items[0]["id"] if items else None


def _props(row):
    """1 顧客の最新月スナップショットを Notion プロパティ形式に変換 (事実列のみ)。"""
    def rt(v):
        return {"rich_text": [{"text": {"content": str(v if v is not None else "")}}]}

    def num(v):
        return {"number": (int(v) if v is not None else None)}

    props = {
        "取引先企業名": {"title": [{"text": {"content": row.get("company_name", "")}}]},
        "顧客ID": rt(row.get("customer_id")),
        "対象年月": rt(row.get("period_ym")),
        "判定": {"select": {"name": row.get("verdict", "発行漏れ候補")}},
        "商品名": rt(row.get("product_name")),
        "前月金額": num(row.get("prev_amount")),
        "今月金額": num(row.get("curr_amount")),
    }
    if row.get("issue_date"):
        props["発行日"] = {"date": {"start": row["issue_date"]}}
    if row.get("updated_at"):
        props["更新日"] = {"date": {"start": row["updated_at"]}}
    if row.get("checked_at"):
        props["確認済み日時"] = {"date": {"start": row["checked_at"]}}
    if row.get("run_id"):
        props["チェック実行ID"] = rt(row["run_id"])
    return props


# --- 本文 table block (月次履歴) -------------------------------------------------

def _cell(text):
    """table_row の 1 セル。空セルも [] でなく content="" の text を1つ持たせる。"""
    return [{"type": "text", "text": {"content": str(text if text is not None else "")}}]


def _table_row_block(values):
    """values (TABLE_WIDTH 個の文字列) から table_row ブロックを構築する。"""
    return {
        "object": "block",
        "type": "table_row",
        "table_row": {"cells": [_cell(v) for v in values]},
    }


def _header_row_block():
    return _table_row_block(TABLE_COLUMNS)


def _month_values(row):
    """1 顧客の月次行 (TABLE_COLUMNS 順の値リスト)。"""
    return [
        row.get("period_ym") or "",
        row.get("verdict") or "",
        str(row.get("prev_amount") if row.get("prev_amount") is not None else ""),
        str(row.get("curr_amount") if row.get("curr_amount") is not None else ""),
        row.get("checked_at") or "",
    ]


def _table_block(header_and_rows):
    """新規ページ作成時に children へ渡す table ブロック (header + data 行群)。"""
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": TABLE_WIDTH,
            "has_column_header": True,
            "has_row_header": False,
            "children": header_and_rows,
        },
    }


def _cell_plain(cell):
    """table_row の 1 セル (rich_text 配列) を plain text へ連結する。"""
    return "".join((rt.get("text") or {}).get("content") or "" for rt in (cell or []))


def _all_block_children(block_id, token):
    """block の子要素を has_more/next_cursor で全ページ取得する。

    Notion はブロック子要素を既定 100 件/ページで返す。table の月次行が 100 行
    (約 8 年) を超えても既存行を取りこぼさないようカーソルで全件辿る。取りこぼすと
    period_ym 一致を見落として重複追記し、冪等 (同月は既存行更新) が壊れるため。
    """
    out = []
    cursor = None
    while True:
        query = "?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
        res = _req("GET", f"/blocks/{block_id}/children{query}", token)
        out.extend(res.get("results", []))
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return out


def _find_table_id(page_id, token):
    """ページ本文から type=="table" のブロック id を返す。無ければ None。"""
    for blk in _all_block_children(page_id, token):
        if blk.get("type") == "table":
            return blk["id"]
    return None


def _upsert_month_row(page_id, row, token):
    """既存ページの本文 table に当月行を upsert する (自然キー=period_ym)。

    手順: table 取得→無ければ append→既存行で period_ym 一致を探し更新、無ければ追加。
    同月の再 sink は既存行更新で重複しない。
    """
    period_ym = row.get("period_ym") or ""
    values = _month_values(row)
    table_id = _find_table_id(page_id, token)
    if table_id is None:
        # 後方データ移行: table が無い旧ページには header + 当月行で table を新規 append。
        _req("PATCH", f"/blocks/{page_id}/children", token,
             {"children": [_table_block([_header_row_block(), _table_row_block(values)])]})
        return

    table_rows = _all_block_children(table_id, token)
    # has_column_header の先頭行はヘッダなので除外して period_ym 一致を探す。
    for idx, blk in enumerate(table_rows):
        if idx == 0:
            continue
        cells = (blk.get("table_row") or {}).get("cells") or []
        if cells and _cell_plain(cells[0]) == period_ym:
            _req("PATCH", f"/blocks/{blk['id']}", token,
                 {"table_row": {"cells": [_cell(v) for v in values]}})
            return
    # 一致行なし → 末尾に追加。
    _req("PATCH", f"/blocks/{table_id}/children", token,
         {"children": [_table_row_block(values)]})


def _run_id(checked_at):
    return "mfk-" + checked_at.replace(":", "").replace("-", "").replace("+", "").replace(".", "")


def upsert(database_id, rows, token=None, period_ym=None, checked_at=None):
    """rows を customer_id キーで冪等 upsert。作成/更新件数を返す。

    1 顧客=1 ページ。DBプロパティは最新月スナップショット、月次履歴は本文 table block。
    rows: [{customer_id, period_ym, company_name, verdict, prev_amount, curr_amount,
            issue_date?, updated_at?, product_name, checked_at?, run_id?}, ...]
    period_ym: 今回チェックした対象月 (rows が空でも戻り値に含めるため)。
    rows が空なら何もせず {created:0, updated:0, ...} を返す (候補0件月の「チェック済」
    証跡は collect 側が全顧客行で担保する。sink はサマリ行を作らない)。
    """
    token = token or _notion_token()
    checked_at = checked_at or datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    run_id = _run_id(checked_at)
    if rows:
        period_ym = period_ym or rows[0]["period_ym"]

    # customer_id でグループ化し、各顧客は最新 period_ym の行をスナップショットに採用。
    by_customer = {}
    for row in rows:
        cid = row["customer_id"]
        prev = by_customer.get(cid)
        if prev is None or (row.get("period_ym") or "") >= (prev.get("period_ym") or ""):
            by_customer[cid] = row

    created = updated = 0
    for cid, row in by_customer.items():
        enriched = dict(row)
        enriched.setdefault("checked_at", checked_at)
        enriched.setdefault("run_id", run_id)
        page_id = _find_page(database_id, cid, token)
        if page_id:
            _req("PATCH", f"/pages/{page_id}", token, {"properties": _props(enriched)})
            _upsert_month_row(page_id, enriched, token)
            updated += 1
        else:
            res = _req("POST", "/pages", token, {
                "parent": {"database_id": database_id},
                "properties": _props(enriched),
                "children": [_table_block([_header_row_block(), _table_row_block(_month_values(enriched))])],
            })
            _ = res  # 新規ページは作成時に table を同梱済み。追加処理不要。
            created += 1
    return {"created": created, "updated": updated, "period_ym": period_ym, "run_id": run_id}
