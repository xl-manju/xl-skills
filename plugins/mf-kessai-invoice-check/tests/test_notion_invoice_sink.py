#!/usr/bin/env python3
"""notion_invoice_sink.py の月次履歴保持ロジックを API なしで検証する。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import notion_invoice_sink as sink  # noqa: E402


def test_props_include_audit_fact_columns():
    row = {
        "customer_id": "c1",
        "period_ym": "2026-06",
        "company_name": "A社",
        "verdict": "発行漏れ候補",
        "record_type": "明細",
        "checked_at": "2026-06-20T00:00:00+00:00",
        "run_id": "mfk-20260620",
    }
    props = sink._props(row)
    assert props["レコード種別"]["select"]["name"] == "明細"
    assert props["確認済み日時"]["date"]["start"] == "2026-06-20T00:00:00+00:00"
    assert props["チェック実行ID"]["rich_text"][0]["text"]["content"] == "mfk-20260620"


def test_summary_row_records_zero_candidate_month():
    row = sink._summary_row("2026-06", [], "2026-06-20T00:00:00+00:00", "mfk-1")
    assert row["customer_id"] == sink.SUMMARY_CUSTOMER_ID
    assert row["record_type"] == "月次サマリ"
    assert row["verdict"] == "月次サマリ"
    assert row["period_ym"] == "2026-06"
    assert row["total_count"] == 0
    assert row["company_name"] == "月次チェックサマリ 2026-06"


def test_upsert_creates_summary_and_detail_with_audit(monkeypatch):
    calls = []

    def fake_req(method, path, token, body=None):
        calls.append((method, path, body))
        if method == "POST" and path.endswith("/query"):
            return {"results": []}
        if method == "POST" and path == "/pages":
            return {"id": f"page-{len([c for c in calls if c[1] == '/pages'])}"}
        if method == "GET" and "/blocks/" in path:
            return {"results": []}  # 新規ページなので既存履歴ブロックなし
        if method == "PATCH" and path.startswith("/blocks/"):
            return {}
        raise AssertionError((method, path, body))

    monkeypatch.setattr(sink, "_req", fake_req)
    rows = [{
        "customer_id": "c1",
        "period_ym": "2026-06",
        "company_name": "A社",
        "verdict": "発行漏れ候補",
        "product_name": "SaaS",
        "prev_amount": 100,
        "curr_amount": None,
    }]
    result = sink.upsert("db1", rows, token="token", checked_at="2026-06-20T00:00:00+00:00")
    assert result["created"] == 2
    assert result["updated"] == 0
    assert result["period_ym"] == "2026-06"

    created_payloads = [body for method, path, body in calls if method == "POST" and path == "/pages"]
    assert created_payloads[0]["properties"]["レコード種別"]["select"]["name"] == "月次サマリ"
    assert created_payloads[1]["properties"]["レコード種別"]["select"]["name"] == "明細"
    # 月次サマリ行は件数プロパティを持つ (gap_count=1, total_count=1)
    summary_props = created_payloads[0]["properties"]
    assert summary_props["発行漏れ件数"]["number"] == 1
    assert summary_props["チェック件数合計"]["number"] == 1
    # 明細行は件数プロパティが None
    detail_props = created_payloads[1]["properties"]
    assert detail_props["発行漏れ件数"]["number"] is None
    assert detail_props["チェック件数合計"]["number"] is None
    audit_calls = [body for method, path, body in calls if method == "PATCH" and path.startswith("/blocks/")]
    assert len(audit_calls) == 2
    assert "月次チェック完了" in audit_calls[0]["children"][1]["paragraph"]["rich_text"][0]["text"]["content"]


def test_append_audit_idempotent_skips_existing_run_id(monkeypatch):
    """同一 run_id の履歴ブロックが既存なら 2 回目の upsert で PATCH /blocks を呼ばない。"""
    appended = {}  # page_id -> 追記済み履歴段落テキスト (既存本文を模擬し過去証跡を保持)
    patch_blocks = {"n": 0}

    def fake_req(method, path, token, body=None):
        if method == "POST" and path.endswith("/query"):
            return {"results": [{"id": "page-fixed"}]}  # 2 回目以降も同一ページを更新
        if method == "POST" and path == "/pages":
            return {"id": "page-fixed"}
        if method == "PATCH" and path.startswith("/pages/"):
            return {}  # プロパティ更新 (件数等)。本テストの対象外
        if method == "GET" and "/blocks/" in path:
            pid = path.split("/blocks/")[1].split("/")[0]
            results = [{"paragraph": {"rich_text": [{"text": {"content": t}}]}}
                       for t in appended.get(pid, [])]
            return {"results": results}
        if method == "PATCH" and path.startswith("/blocks/"):
            patch_blocks["n"] += 1
            pid = path.split("/blocks/")[1].split("/")[0]
            for blk in body["children"]:
                for rt in blk.get("paragraph", {}).get("rich_text", []):
                    appended.setdefault(pid, []).append(rt["text"]["content"])
            return {}
        raise AssertionError((method, path, body))

    monkeypatch.setattr(sink, "_req", fake_req)
    rows = [{
        "customer_id": "c1",
        "period_ym": "2026-06",
        "company_name": "A社",
        "verdict": "発行漏れ候補",
        "product_name": "SaaS",
        "prev_amount": 100,
        "curr_amount": None,
    }]
    ca = "2026-06-20T00:00:00+00:00"

    # 1 回目: 既存履歴なし → 履歴ブロックを追記する (サマリ + 明細 = 2 ページ分)
    sink.upsert("db1", rows, token="token", checked_at=ca)
    assert patch_blocks["n"] >= 1, "1 回目は履歴を追記する"
    preserved = dict(appended)  # 過去証跡のスナップショット

    # 2 回目: 同一 checked_at → 同一 run_id。既存履歴を GET で検出し PATCH /blocks をスキップ
    patch_blocks["n"] = 0
    sink.upsert("db1", rows, token="token", checked_at=ca)
    assert patch_blocks["n"] == 0, "同一 run_id の履歴は冪等スキップされるべき"
    assert appended == preserved, "既存履歴 (過去証跡) は改変されない"


def test_upsert_empty_rows_requires_or_uses_period(monkeypatch):
    calls = []

    def fake_req(method, path, token, body=None):
        calls.append((method, path, body))
        if method == "POST" and path.endswith("/query"):
            return {"results": []}
        if method == "POST" and path == "/pages":
            return {"id": "summary-page"}
        if method == "GET" and "/blocks/" in path:
            return {"results": []}
        if method == "PATCH" and path.startswith("/blocks/"):
            return {}
        raise AssertionError((method, path, body))

    monkeypatch.setattr(sink, "_req", fake_req)
    result = sink.upsert("db1", [], token="token", period_ym="2026-07",
                         checked_at="2026-07-20T00:00:00+00:00")
    assert result["created"] == 1
    created_payloads = [body for method, path, body in calls if method == "POST" and path == "/pages"]
    assert created_payloads[0]["properties"]["取引先企業名"]["title"][0]["text"]["content"] == "月次チェックサマリ 2026-07"
