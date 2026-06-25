#!/usr/bin/env python3
"""lib/mfk_invoice_diff.py の純関数を単体テストする (pytest, API不要)。"""
from mfk_invoice_diff import (
    amount_changed,
    billing_lifecycle,
    detect_gaps,
    months_elapsed,
    suppress_annual_period_gaps,
)


def _b(cid, amount, status="invoice_issued"):
    return {"customer_id": cid, "amount": amount, "status": status}


def test_gap_candidates():
    """前月発行・今月未発行が発行漏れ候補になる。"""
    r = detect_gaps([_b("A", 100), _b("B", 200)], [_b("A", 100)])
    assert r["gap_candidates"] == ["B"]
    assert r["continuing"] == ["A"]
    assert r["new_this_month"] == []


def test_amount_changed():
    """継続発行で金額が変わったら検出する。"""
    r = detect_gaps([_b("A", 100)], [_b("A", 150)])
    assert amount_changed(r["continuing"], r["prev_amount"], r["curr_amount"]) == ["A"]


def test_amount_unchanged_not_flagged():
    """金額が同じなら変動扱いしない。"""
    r = detect_gaps([_b("A", 100)], [_b("A", 100)])
    assert amount_changed(r["continuing"], r["prev_amount"], r["curr_amount"]) == []


def test_ignores_non_issued():
    """scheduled(未発行)は発行扱いしないので漏れ候補にならない。"""
    r = detect_gaps([_b("A", 100, "scheduled")], [])
    assert r["gap_candidates"] == []


def test_new_this_month():
    """今月のみ発行は new_this_month。"""
    r = detect_gaps([], [_b("C", 300)])
    assert r["new_this_month"] == ["C"]
    assert r["gap_candidates"] == []


def test_multi_billing_amount_sum():
    """同一顧客の複数billingは金額合算される。"""
    r = detect_gaps([_b("A", 100), _b("A", 50)], [_b("A", 100), _b("A", 50)])
    assert r["prev_amount"]["A"] == 150
    assert r["curr_amount"]["A"] == 150


def test_amount_null_does_not_crash():
    """amount が null(キー有り値None)でも落ちず 0 扱い。"""
    r = detect_gaps([_b("A", None)], [_b("A", None)])
    assert r["prev_amount"]["A"] == 0
    assert amount_changed(r["continuing"], r["prev_amount"], r["curr_amount"]) == []


def test_amount_float_string_truncates():
    """amount が float 文字列でも int 化して落ちない。"""
    r = detect_gaps([_b("A", "1500.50")], [])
    assert r["prev_amount"]["A"] == 1500


# --- 契約ライフサイクル (年間→月払い自動切替) ----------------------------------

def test_months_elapsed_basic():
    """初回契約月から対象月までの経過月数。"""
    assert months_elapsed("2026-04", "2026-06") == 2
    assert months_elapsed("2026-04", "2026-04") == 0
    assert months_elapsed("2026-04", "2027-04") == 12  # 13ヶ月目
    assert months_elapsed("2026-04", "2025-04") == -12  # 過去


def test_months_elapsed_invalid_returns_none():
    """不正形式/None は None。"""
    assert months_elapsed(None, "2026-06") is None
    assert months_elapsed("2026-13", "2026-06") is None  # 月13は不正
    assert months_elapsed("2026-04", "bad") is None


def test_lifecycle_annual_period():
    """経過 0〜11ヶ月は年間払い・年間期間中 (発行漏れ判定から除外対象)。"""
    for target in ("2026-04", "2026-05", "2027-03"):  # 経過 0, 1, 11
        life = billing_lifecycle("2026-04", target, "年間払い")
        assert life["cadence"] == "年間払い"
        assert life["in_annual_period"] is True


def test_lifecycle_monthly_after_12_months():
    """経過 12ヶ月以降 (13ヶ月目) は月払い・年間期間外。"""
    life = billing_lifecycle("2026-04", "2027-04", "年間払い")  # 経過12
    assert life["cadence"] == "月払い"
    assert life["in_annual_period"] is False
    assert billing_lifecycle("2026-04", "2028-01", "年間払い")["cadence"] == "月払い"


def test_lifecycle_unknown_initial_is_failsafe():
    """初回契約月不明は判定不能・年間期間扱いにしない (真の漏れを隠さない fail-safe)。"""
    life = billing_lifecycle(None, "2026-06")
    assert life["cadence"] is None
    assert life["in_annual_period"] is False
    assert billing_lifecycle("", "2026-06", "年間払い")["in_annual_period"] is False


def test_lifecycle_monthly_cycle_is_failsafe_even_with_initial_month():
    """月払い顧客は初回契約月が入っていても年間抑制しない。"""
    life = billing_lifecycle("2026-04", "2026-06", "月払い")
    assert life["cadence"] == "月払い"
    assert life["in_annual_period"] is False


def test_lifecycle_target_before_contract_not_annual():
    """対象月が初回契約月より前 (経過マイナス) は年間期間にしない。"""
    life = billing_lifecycle("2026-04", "2026-01", "年間払い")
    assert life["in_annual_period"] is False
    assert life["cadence"] == "月払い"


def test_suppress_annual_period_gaps():
    """発行漏れ候補から年間契約期間中の顧客を除外し、月払い/不明は残す。"""
    initial = {
        "ANNUAL": {"initial_contract_month": "2026-06", "payment_cycle": "年間払い"},
        "MONTHLY": {"initial_contract_month": "2026-06", "payment_cycle": "月払い"},
        "OLD": {"initial_contract_month": "2025-01", "payment_cycle": "年間払い"},
        # "UNKNOWN" は初回契約月なし → fail-safe で残す
    }
    real, in_annual = suppress_annual_period_gaps(
        ["ANNUAL", "MONTHLY", "OLD", "UNKNOWN"], initial, "2026-06")
    assert in_annual == ["ANNUAL"]
    assert real == ["MONTHLY", "OLD", "UNKNOWN"]


def test_suppress_annual_legacy_month_only_mapping_is_failsafe():
    """旧形式 {customer_id: YYYY-MM} は支払サイクル不明なので抑制しない。"""
    real, in_annual = suppress_annual_period_gaps(["c1"], {"c1": "2026-06"}, "2026-06")
    assert real == ["c1"]
    assert in_annual == []
