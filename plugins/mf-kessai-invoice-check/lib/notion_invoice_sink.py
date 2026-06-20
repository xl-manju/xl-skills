#!/usr/bin/env python3
"""発行漏れチェック結果を Notion DB に冪等 upsert する sink。

キー: customer_id × 対象年月(period_ym)。毎月実行で重複行を作らず既存行を更新する。
**事実列のみ** を書き込み、管理列(請求要否/対応状況/チェック済/備考)には触れない
(人の運用記入を自動実行が上書きしないため)。
各月につき `__monthly_summary__ × 対象年月` の月次サマリ行も upsert し、候補0件の月でも
「確認済み」の記録を残す。各ページ本文には実行履歴を追記し、過去の確認証跡を消さない。
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
SUMMARY_CUSTOMER_ID = "__monthly_summary__"


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


def _find_page(database_id, customer_id, period_ym, token):
    """customer_id × period_ym で既存ページを検索。あれば page_id を返す。"""
    body = {"filter": {"and": [
        {"property": "顧客ID", "rich_text": {"equals": customer_id}},
        {"property": "対象年月", "rich_text": {"equals": period_ym}},
    ]}}
    res = _req("POST", f"/databases/{database_id}/query", token, body)
    items = res.get("results", [])
    if len(items) > 1:  # 冪等キーが壊れている。暗黙に先頭採用せず運用者に気づかせる
        raise RuntimeError(
            f"重複行検出: 顧客ID={customer_id} 対象年月={period_ym} が {len(items)}件存在。"
            "手動で重複を解消してから再実行してください (customer_id×対象年月 は一意のはず)。")
    return items[0]["id"] if items else None


def _props(row):
    """発行漏れ結果1件を Notion プロパティ形式に変換 (事実列のみ)。"""
    def rt(v):
        return {"rich_text": [{"text": {"content": str(v if v is not None else "")}}]}

    def num(v):
        return {"number": (int(v) if v is not None else None)}

    props = {
        "取引先企業名": {"title": [{"text": {"content": row.get("company_name", "")}}]},
        "レコード種別": {"select": {"name": row.get("record_type", "明細")}},
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
    # 月次サマリ行が持つ件数。明細行は該当キーが無く num(None)→{"number": None} で全行共通可。
    props["発行漏れ件数"] = num(row.get("gap_count"))
    props["金額変動件数"] = num(row.get("changed_count"))
    props["チェック件数合計"] = num(row.get("total_count"))
    return props


def _plain(text):
    return {"type": "text", "text": {"content": str(text)}}


def _paragraph(text):
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [_plain(text)]}}


def _audit_children(row, action):
    checked_at = row.get("checked_at") or ""
    run_id = row.get("run_id") or ""
    if row.get("record_type") == "月次サマリ":
        lines = [
            f"月次チェック完了: {row.get('period_ym')} ({checked_at})",
            f"実行ID: {run_id}",
            f"候補: {row.get('gap_count', 0)} / 金額変動(継続発行のうち金額が変わった件数): {row.get('changed_count', 0)} / 合計: {row.get('total_count', 0)}",
            f"Notion処理: {action}",
        ]
    else:
        lines = [
            f"チェック記録: {row.get('period_ym')} ({checked_at})",
            f"実行ID: {run_id}",
            f"判定: {row.get('verdict')} / 前月金額: {row.get('prev_amount')} / 今月金額: {row.get('curr_amount')}",
            f"Notion処理: {action}",
        ]
    return [
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [_plain("MF掛け払い 月次チェック履歴")]},
        },
        *[_paragraph(line) for line in lines],
    ]


def _has_run_id_block(page_id, run_id, token):
    """既存ページ本文に同一 run_id の履歴ブロックがあるか(冪等判定)。"""
    res = _req("GET", f"/blocks/{page_id}/children?page_size=100", token)
    for blk in res.get("results", []):
        para = blk.get("paragraph") or {}
        for rt in para.get("rich_text", []):
            if run_id and run_id in ((rt.get("text") or {}).get("content") or ""):
                return True
    return False


def _append_audit(page_id, row, token, action):
    run_id = row.get("run_id") or ""
    if run_id and _has_run_id_block(page_id, run_id, token):
        return  # 同一実行の履歴は既存。冪等スキップ(過去証跡は保持)
    _req("PATCH", f"/blocks/{page_id}/children", token, {"children": _audit_children(row, action)})


def _run_id(checked_at):
    return "mfk-" + checked_at.replace(":", "").replace("-", "").replace("+", "").replace(".", "")


def _summary_row(period_ym, rows, checked_at, run_id):
    gap_count = sum(1 for r in rows if r.get("verdict") == "発行漏れ候補")
    changed_count = sum(1 for r in rows if r.get("verdict") == "継続発行")
    return {
        "customer_id": SUMMARY_CUSTOMER_ID,
        "period_ym": period_ym,
        "company_name": f"月次チェックサマリ {period_ym}",
        "record_type": "月次サマリ",
        "verdict": "月次サマリ",
        "product_name": "月次チェック完了記録",
        "prev_amount": None,
        "curr_amount": None,
        "checked_at": checked_at,
        "run_id": run_id,
        "gap_count": gap_count,
        "changed_count": changed_count,
        "total_count": len(rows),
    }


def upsert(database_id, rows, token=None, period_ym=None, checked_at=None):
    """rows を customer_id×period_ym キーで冪等 upsert。作成/更新件数を返す。

    rows: [{customer_id, period_ym, company_name, verdict, product_name,
            prev_amount, curr_amount, issue_date?, updated_at?}, ...]
    period_ym: rows が空の月でも月次サマリを残すための対象年月。
    """
    token = token or _notion_token()
    checked_at = checked_at or datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    run_id = _run_id(checked_at)
    if rows:
        period_ym = period_ym or rows[0]["period_ym"]
    if not period_ym:
        raise ValueError("period_ym is required when rows is empty")

    detail_rows = []
    for row in rows:
        enriched = dict(row)
        enriched.setdefault("record_type", "明細")
        enriched.setdefault("checked_at", checked_at)
        enriched.setdefault("run_id", run_id)
        detail_rows.append(enriched)
    all_rows = [_summary_row(period_ym, detail_rows, checked_at, run_id), *detail_rows]

    created = updated = 0
    for row in all_rows:
        page_id = _find_page(database_id, row["customer_id"], row["period_ym"], token)
        if page_id:
            _req("PATCH", f"/pages/{page_id}", token, {"properties": _props(row)})
            _append_audit(page_id, row, token, "updated")
            updated += 1
        else:
            res = _req("POST", "/pages", token,
                       {"parent": {"database_id": database_id}, "properties": _props(row)})
            _append_audit(res["id"], row, token, "created")
            created += 1
    return {"created": created, "updated": updated, "period_ym": period_ym, "run_id": run_id}
