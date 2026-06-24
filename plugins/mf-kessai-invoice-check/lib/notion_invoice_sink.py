#!/usr/bin/env python3
"""発行漏れチェック結果を Notion DB に冪等 upsert する sink (顧客ID集約モデル)。

upsert キー = customer_id 単独。1顧客=1 Notion ページ。既存顧客は月が変わっても同じページを
更新し、未登録顧客だけ新規ページを作成する。月ごとの重複ページは作らない。月次履歴は各顧客ページの**本文 table block**
(Notion type:"table") に 1 行=1 対象年月で蓄積する(自然キー=period_ym, 同月再実行は
既存行更新で冪等)。DBプロパティはその顧客の「最新月スナップショット」(事実列のみ)を
書き込み、管理列(初回契約月/請求要否/支払サイクル/チェック済/備考)には触れない
(人の運用記入を自動実行が上書きしないため)。
Notion トークンは Keychain から取得。service/account は env > config(notion.keychain_service/
account) > default の順で解決し (MF キー側 mfk_keychain と対称)、共通リゾルバ
mfk_keychain.resolve_service / fetch_secret を経由する。
"""
import datetime
import json
import os
import re
import time
import urllib.error
import urllib.request

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# 本文 table block の固定列定義 (1行=1対象年月)。順序がセル順を規定する。
TABLE_COLUMNS = ["対象年月", "今月の発行状況", "前月金額", "今月金額", "確認済み日時"]
# 後方互換: 旧ヘッダ ("判定") の既存 table を月次履歴として認識し続けるための別名。
# 既存ページ本文の table は旧ヘッダのまま残るため、新ヘッダだけ見ると _find_table_id が
# 月次履歴 table を取りこぼし、二重 table を append する事故が起きる。これを防ぐ。
TABLE_COLUMNS_LEGACY = ["対象年月", "判定", "前月金額", "今月金額", "確認済み日時"]
TABLE_WIDTH = len(TABLE_COLUMNS)


def _notion_cfg(cfg=None):
    """cfg の notion セクション (dict) を返す。

    cfg を明示渡し (空 dict 含む) ならその notion セクション、cfg=None (未指定) なら
    load_config() を遅延 import で読む。import 失敗時は空 dict (= env+default のみで解決)。
    """
    if cfg is not None:
        return cfg.get("notion") or {}
    try:
        from mfk_api import load_config  # 遅延 import (実行経路により lib が後付け sys.path)
        return (load_config() or {}).get("notion") or {}
    except Exception:
        return {}


def _notion_service(cfg=None):
    """env(NOTION_KEYCHAIN_SERVICE) > config(notion.keychain_service) > default の順で解決。

    MF キー側 (mfk_keychain._service) と同じ共通リゾルバ resolve_service を共有し、解決規則を
    対称化する。cfg 未指定なら load_config() を遅延 import で読み、config から Notion service を
    設定可能にする (MF 側 keychain_service と対称)。
    """
    from mfk_keychain import DEFAULT_NOTION_SERVICE, resolve_service
    return resolve_service(
        "NOTION_KEYCHAIN_SERVICE", _notion_cfg(cfg).get("keychain_service"), DEFAULT_NOTION_SERVICE)


def _notion_account(cfg=None):
    """env(NOTION_KEYCHAIN_ACCOUNT) > config(notion.keychain_account) > default の順で解決。"""
    from mfk_keychain import DEFAULT_ACCOUNT, resolve_service
    return resolve_service(
        "NOTION_KEYCHAIN_ACCOUNT", _notion_cfg(cfg).get("keychain_account"), DEFAULT_ACCOUNT)


def _notion_token(cfg=None):
    """Notion API トークンを取得して生値 (文字列) を返す。

    解決順: env(NOTION_API_KEY) > Keychain(service/account)。service/account は
    env > config(notion.keychain_service/account) > default の順で `_notion_service`/
    `_notion_account` が解決する (MF 側と対称)。シグネチャは引数省略可で従来の引数なし呼出と
    互換。Keychain 取得は mfk_keychain.fetch_secret (MF 側と同一の共通コア) を経由する。
    """
    env = os.environ.get("NOTION_API_KEY")
    if env and env.strip():
        return env.strip()
    service = _notion_service(cfg)
    account = _notion_account(cfg)
    from mfk_keychain import fetch_secret
    token = fetch_secret(service, account)
    if not token:
        raise RuntimeError(f"Notion token lookup failed (service={service}, account={account})")
    return token


def _req(method, path, token, body=None):
    url = NOTION_API + path
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(4):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Notion-Version", NOTION_VERSION)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", "replace")
            if e.code in {429, 502, 503, 504} and attempt < 3:
                retry_after = e.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else 2 ** attempt
                time.sleep(min(delay, 8))
                continue
            raise RuntimeError(f"Notion {method} {path}: HTTP {e.code} {body_text}")


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


def _rich_text_plain(prop):
    """Notion rich_text プロパティを plain text へ連結する (空/欠落は '')。"""
    if not isinstance(prop, dict):
        return ""
    return "".join(
        (rt.get("text") or {}).get("content") or rt.get("plain_text") or ""
        for rt in (prop.get("rich_text") or [])
    )


def _select_name(prop):
    """Notion select プロパティの name を返す (空/欠落は '')。"""
    if not isinstance(prop, dict):
        return ""
    sel = prop.get("select") or {}
    return sel.get("name") or ""


def fetch_initial_contract_months(database_id, token=None):
    """Notion DB を全件クエリし年間抑制用の契約情報を返す (read-only)。

    返り値は {customer_id: {"initial_contract_month": "YYYY-MM", "payment_cycle": "年間払い"}}。
    `支払サイクル` が年間払いの顧客だけを返す。月払い/空欄/不正値は dict に含めず、
    発行漏れ候補に残す fail-safe に倒す。token は未指定なら Keychain から取得する。

    返り値 dict は collect() の `initial_contract_months` 引数へ渡し suppress_annual_period_gaps
    で年間期間中の顧客を発行漏れ候補から除外する。GET/POST(query) のみで DB を変更しない。
    """
    token = token or _notion_token()
    out = {}
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = _req("POST", f"/databases/{database_id}/query", token, body)
        for page in res.get("results", []):
            props = page.get("properties") or {}
            cid = _rich_text_plain(props.get("顧客ID")).strip()
            month = _rich_text_plain(props.get("初回契約月")).strip()
            cycle = _select_name(props.get("支払サイクル")).strip()
            if cid and cycle == "年間払い" and re.fullmatch(r"\d{4}-\d{2}", month):
                out[cid] = {"initial_contract_month": month, "payment_cycle": cycle}
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return out


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
        # 表示プロパティ名は「今月の発行状況」。内部 verdict キー・enum値 (発行漏れ候補/
        # 継続発行/今月新規) は不変で、Notion 表示名だけを改名した。
        "今月の発行状況": {"select": {"name": row.get("verdict", "発行漏れ候補")}},
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
    return props


def _create_props(row):
    """新規ページ作成時のプロパティ。

    _props (fact_column の最新月スナップショット) に加え、managed_column の
    `初回契約月` を**空欄で初期化**する。これにより MF API から取得できない契約開始月が
    未入力の顧客を Notion の「空欄」フィルタで拾い、人が YYYY-MM で補正できる。
    既存ページ更新では `_props` を使い `初回契約月` (人の運用列) には一切触れない
    (再投入で人の記入を上書きしないため = 新規時のみ初期化する関数境界で機械保証)。
    """
    props = _props(row)
    props["初回契約月"] = {"rich_text": [{"text": {"content": ""}}]}
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
    """ページ本文から月次履歴 table のブロック id を返す。無ければ None。

    人がページ本文の上部に別用途の table を追加しても誤追記しないよう、先頭行が
    月次履歴ヘッダと一致する table だけを月次履歴 table として採用する。
    ヘッダは新 TABLE_COLUMNS だけでなく旧 TABLE_COLUMNS_LEGACY (判定列名) も認める。
    改名前に作られた既存ページの table は旧ヘッダのまま残るため、新ヘッダだけ照合すると
    月次履歴を取りこぼして二重 table を append する事故が起きる。両方を後方互換で拾う。
    """
    for blk in _all_block_children(page_id, token):
        if blk.get("type") == "table":
            rows = _all_block_children(blk["id"], token)
            if not rows:
                continue
            cells = (rows[0].get("table_row") or {}).get("cells") or []
            header = [_cell_plain(c) for c in cells]
            if header in (TABLE_COLUMNS, TABLE_COLUMNS_LEGACY):
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

    # customer_id でグループ化。DBプロパティは最新 period_ym の行をスナップショットに
    # 採用し、本文 table には同一顧客の全 period_ym 行を upsert する。
    by_customer = {}
    for row in rows:
        cid = row["customer_id"]
        by_customer.setdefault(cid, []).append(row)

    created = updated = 0
    for cid, customer_rows in by_customer.items():
        enriched_rows = []
        for row in sorted(customer_rows, key=lambda r: r.get("period_ym") or ""):
            enriched = dict(row)
            enriched.setdefault("checked_at", checked_at)
            enriched.setdefault("run_id", run_id)
            enriched_rows.append(enriched)
        snapshot = enriched_rows[-1]
        page_id = _find_page(database_id, cid, token)
        if page_id:
            _req("PATCH", f"/pages/{page_id}", token, {"properties": _props(snapshot)})
            for enriched in enriched_rows:
                _upsert_month_row(page_id, enriched, token)
            updated += 1
        else:
            res = _req("POST", "/pages", token, {
                "parent": {"database_id": database_id},
                "properties": _create_props(snapshot),
                "children": [_table_block(
                    [_header_row_block()] + [_table_row_block(_month_values(r)) for r in enriched_rows]
                )],
            })
            _ = res  # 新規ページは作成時に table を同梱済み。追加処理不要。
            created += 1
    return {"created": created, "updated": updated, "period_ym": period_ym, "run_id": run_id}
