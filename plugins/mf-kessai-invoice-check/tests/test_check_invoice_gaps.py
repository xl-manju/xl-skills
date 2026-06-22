#!/usr/bin/env python3
"""check_invoice_gaps.py の出力先解決(F2)・確定リスト昇格(F1)・schema検証(F4)の回帰テスト。

ネットワーク/Notion を伴わない純ファイル操作部分のみを対象とする。
"""
import json
import os

import check_invoice_gaps as c


# --- F2: 出力先解決 env > project > cwd ---

def test_eval_log_prefers_env(monkeypatch):
    monkeypatch.setenv("MFK_OUTPUT_DIR", "/tmp/mfk-a")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/tmp/mfk-b")
    assert c.eval_log_dir() == "/tmp/mfk-a/eval-log"


def test_eval_log_falls_back_to_project(monkeypatch):
    monkeypatch.delenv("MFK_OUTPUT_DIR", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/tmp/mfk-b")
    assert c.eval_log_dir() == "/tmp/mfk-b/eval-log"


def test_eval_log_falls_back_to_cwd(monkeypatch, tmp_path):
    monkeypatch.delenv("MFK_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert c.eval_log_dir() == os.path.join(str(tmp_path), "eval-log")


def test_no_repo_root_assumption():
    """_REPO_ROOT 派生 (repo 配置前提) が撤廃されていること。"""
    assert not hasattr(c, "_REPO_ROOT")
    assert not hasattr(c, "DEFAULT_CANDIDATES")


# --- F4: schema 検証 ---

def test_validate_rows_ok():
    rows = [{"customer_id": "c1", "period_ym": "2026-06", "verdict": "発行漏れ候補"}]
    assert c.validate_rows(rows) == []


def test_validate_rows_rejects_empty_period():
    rows = [{"customer_id": "c1", "period_ym": "", "verdict": "発行漏れ候補"}]
    errs = c.validate_rows(rows)
    assert errs and "period_ym" in errs[0]


def test_validate_rows_rejects_bad_verdict_and_empty_cid():
    rows = [{"customer_id": "", "period_ym": "2026-06", "verdict": "謎判定"}]
    errs = c.validate_rows(rows)
    assert any("customer_id" in e for e in errs)
    assert any("verdict" in e for e in errs)


# --- F1: finalize による確定リスト昇格 (誤検出除外) ---

def _cands(tmp_path):
    p = tmp_path / "mfk-gap-candidates.json"
    p.write_text(json.dumps([
        {"customer_id": "c1", "period_ym": "2026-06", "verdict": "発行漏れ候補"},
        {"customer_id": "c2", "period_ym": "2026-06", "verdict": "発行漏れ候補"},
        {"customer_id": "c3", "period_ym": "2026-06", "verdict": "継続発行"},
    ], ensure_ascii=False), encoding="utf-8")
    return p


def test_finalize_excludes_false_positive(tmp_path):
    src = _cands(tmp_path)
    out = tmp_path / "verified.json"
    rc = c.finalize(["c2"], str(src), str(out))
    assert rc == 0
    kept = json.loads(out.read_text(encoding="utf-8"))
    ids = {r["customer_id"] for r in kept}
    assert ids == {"c1", "c3"}  # 誤検出 c2 のみ除外、継続発行 c3 は素通し


def test_finalize_keeps_all_when_no_exclusions(tmp_path):
    src = _cands(tmp_path)
    out = tmp_path / "verified.json"
    rc = c.finalize([""], str(src), str(out))  # 除外なし (空文字は無視)
    assert rc == 0
    kept = json.loads(out.read_text(encoding="utf-8"))
    assert len(kept) == 3


def test_finalize_does_not_exclude_non_gap(tmp_path):
    """継続発行は誤検出除外の対象外 (発行漏れ候補のみ exclude 可)。"""
    src = _cands(tmp_path)
    out = tmp_path / "verified.json"
    c.finalize(["c3"], str(src), str(out))
    kept = json.loads(out.read_text(encoding="utf-8"))
    assert "c3" in {r["customer_id"] for r in kept}


def test_finalize_rejects_invalid_input(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"customer_id": "x", "period_ym": "", "verdict": "発行漏れ候補"}]),
                   encoding="utf-8")
    out = tmp_path / "v.json"
    assert c.finalize([], str(bad), str(out)) == 2
    assert not out.exists()


# --- 改修1: collect が全チェック対象顧客 (継続発行全件含む) を rows 化 ---

def _billing(cid, amount, bid=None):
    return {"customer_id": cid, "amount": amount, "status": "invoice_issued",
            "id": bid or f"b-{cid}", "issue_date": "2026-06-10"}


def _patch_collect_api(monkeypatch, prev, curr):
    """fetch_issued/resolve_names/detail_of を差し替え、detail_of 呼び出しを記録する。"""
    calls = {"detail_of": []}

    def fake_fetch(ym):
        # prev_month 側か当月側かを引数の月で判定する (collect は prev→curr の順で呼ぶ)。
        return prev if ym == c.prev_month("2026-06") else curr

    def fake_names(ids):
        return {cid: f"会社{cid}" for cid in ids}

    def fake_detail(billing_id):
        calls["detail_of"].append(billing_id)
        return {"product_name": f"商品-{billing_id}", "updated_at": "2026-06-11T00:00:00Z"}

    monkeypatch.setattr(c, "fetch_issued", fake_fetch)
    monkeypatch.setattr(c, "resolve_names", fake_names)
    monkeypatch.setattr(c, "detail_of", fake_detail)
    return calls


def test_collect_includes_all_continuing(monkeypatch):
    """継続発行は金額変動の有無に関わらず全件 rows 化される (チェック証跡の穴埋め)。"""
    prev = [_billing("gap", 1000), _billing("same", 500), _billing("chg", 200)]
    curr = [_billing("same", 500), _billing("chg", 900), _billing("new", 300)]
    _patch_collect_api(monkeypatch, prev, curr)
    res, rows = c.collect("2026-06")
    by_verdict = {}
    for r in rows:
        by_verdict.setdefault(r["verdict"], []).append(r)
    # 発行漏れ候補 gap / 継続発行 same+chg (変動なし same も含む) / 今月新規 new。
    assert {r["customer_id"] for r in by_verdict["発行漏れ候補"]} == {"gap"}
    assert {r["customer_id"] for r in by_verdict["継続発行"]} == {"same", "chg"}
    assert {r["customer_id"] for r in by_verdict["今月新規"]} == {"new"}
    # 全 verdict が enum 準拠 (validate_rows OK)。
    for r in rows:
        r.setdefault("period_ym", "2026-06")
    assert c.validate_rows(rows) == []


def test_collect_records_unchanged_continuing_amount(monkeypatch):
    """金額変動なし継続発行も前月/今月金額を記録する (verdict=継続発行, 金額は埋まる)。"""
    prev = [_billing("same", 500)]
    curr = [_billing("same", 500)]
    _patch_collect_api(monkeypatch, prev, curr)
    _res, rows = c.collect("2026-06")
    same = [r for r in rows if r["customer_id"] == "same"][0]
    assert same["verdict"] == "継続発行"
    assert same["prev_amount"] == 500 and same["curr_amount"] == 500


def test_collect_skips_detail_of_for_unchanged_continuing(monkeypatch):
    """金額変動のない継続発行は detail_of(/transactions)をスキップし API 負荷を抑える。"""
    prev = [_billing("gap", 1000), _billing("same", 500), _billing("chg", 200)]
    curr = [_billing("same", 500), _billing("chg", 900), _billing("new", 300)]
    calls = _patch_collect_api(monkeypatch, prev, curr)
    _res, rows = c.collect("2026-06")
    # detail_of は注目顧客 (発行漏れ候補 gap / 変動継続 chg / 今月新規 new) の billing_id のみ。
    assert set(calls["detail_of"]) == {"b-gap", "b-chg", "b-new"}
    assert "b-same" not in calls["detail_of"]
    # スキップした same は product_name 空・updated_at None。
    same = [r for r in rows if r["customer_id"] == "same"][0]
    assert same["product_name"] == "" and same["updated_at"] is None


# --- 改修2: backfill 範囲一括投入 ---

def _row(cid, ym, verdict, prev_amt, curr_amt):
    """collect が返す行と同形 (全キーあり) のテスト用 row。_print_summary が落ちないよう全キー埋める。"""
    return {"customer_id": cid, "period_ym": ym, "company_name": f"会社{cid}",
            "verdict": verdict, "product_name": "", "prev_amount": prev_amt,
            "curr_amount": curr_amt, "issue_date": "2026-06-10", "updated_at": None}


def test_month_iter_ascending_inclusive():
    assert list(c.month_iter("2026-05", "2026-08")) == ["2026-05", "2026-06", "2026-07", "2026-08"]
    assert list(c.month_iter("2025-11", "2026-02")) == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert list(c.month_iter("2026-06", "2026-06")) == ["2026-06"]
    assert list(c.month_iter("2026-08", "2026-05")) == []  # from > to は空


def test_backfill_processes_each_month_ascending(monkeypatch):
    """backfill は範囲の各月を昇順で collect→sink する。"""
    seen = []

    def fake_collect(ym):
        seen.append(("collect", ym))
        rows = [_row("same", ym, "継続発行", 500, 500)]
        res = {"gap_candidates": [], "continuing": ["same"], "new_this_month": [],
               "prev_amount": {"same": 500}, "curr_amount": {"same": 500}}
        return res, rows

    sink_calls = []

    def fake_upsert(db_id, rows, period_ym=None, **kw):
        sink_calls.append(period_ym)
        return {"created": len(rows), "updated": 0, "period_ym": period_ym, "run_id": "rid"}

    monkeypatch.setattr(c, "collect", fake_collect)
    monkeypatch.setattr(c.notion_invoice_sink, "upsert", fake_upsert)
    rc = c.backfill("2026-04", "2026-06", "db123")
    assert rc == 0
    # collect と sink が 4,5,6 月の昇順で呼ばれた。
    assert [ym for _, ym in seen] == ["2026-04", "2026-05", "2026-06"]
    assert sink_calls == ["2026-04", "2026-05", "2026-06"]


def test_backfill_skips_gap_candidates_by_default(monkeypatch):
    """既定 backfill は未検証の発行漏れ候補をスキップし、継続発行/今月新規のみ投入する。"""
    def fake_collect(ym):
        rows = [
            _row("gap", ym, "発行漏れ候補", 1000, None),
            _row("same", ym, "継続発行", 500, 500),
            _row("new", ym, "今月新規", None, 300),
        ]
        res = {"gap_candidates": ["gap"], "continuing": ["same"], "new_this_month": ["new"],
               "prev_amount": {"gap": 1000, "same": 500}, "curr_amount": {"same": 500, "new": 300}}
        return res, rows

    sunk = []

    def fake_upsert(db_id, rows, period_ym=None, **kw):
        sunk.extend(r["verdict"] for r in rows)
        return {"created": len(rows), "updated": 0, "period_ym": period_ym, "run_id": "rid"}

    monkeypatch.setattr(c, "collect", fake_collect)
    monkeypatch.setattr(c.notion_invoice_sink, "upsert", fake_upsert)
    assert c.backfill("2026-06", "2026-06", "db123") == 0
    # 発行漏れ候補は投入されず、継続発行/今月新規のみ。
    assert "発行漏れ候補" not in sunk
    assert set(sunk) == {"継続発行", "今月新規"}


def test_backfill_force_unverified_includes_gaps(monkeypatch):
    """--force-unverified 時は発行漏れ候補も未検証のまま投入する。"""
    def fake_collect(ym):
        rows = [_row("gap", ym, "発行漏れ候補", 1000, None)]
        res = {"gap_candidates": ["gap"], "continuing": [], "new_this_month": [],
               "prev_amount": {"gap": 1000}, "curr_amount": {}}
        return res, rows

    sunk = []

    def fake_upsert(db_id, rows, period_ym=None, **kw):
        sunk.extend(r["verdict"] for r in rows)
        return {"created": len(rows), "updated": 0, "period_ym": period_ym, "run_id": "rid"}

    monkeypatch.setattr(c, "collect", fake_collect)
    monkeypatch.setattr(c.notion_invoice_sink, "upsert", fake_upsert)
    assert c.backfill("2026-06", "2026-06", "db123", force_unverified=True) == 0
    assert sunk == ["発行漏れ候補"]
