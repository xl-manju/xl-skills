#!/usr/bin/env python3
"""lib/mfk_invoice_diff.py の純関数を単体テストする (pytest, API不要)。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from mfk_invoice_diff import amount_changed, detect_gaps  # noqa: E402


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
