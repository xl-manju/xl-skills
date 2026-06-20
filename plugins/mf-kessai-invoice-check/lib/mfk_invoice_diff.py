#!/usr/bin/env python3
"""発行漏れ判定の純関数。MF掛け払いの billing 一覧から前月−今月の差集合を取る。

副作用なし・ネットワークなし。pytest で単体テストする (tests/test_invoice_diff.py)。
入力は /billings/qualified の items 配列 (dict のリスト)。
"""
from __future__ import annotations


def _issued_customer_ids(billings):
    """status=invoice_issued の billing から customer_id 集合を返す。"""
    return {b["customer_id"] for b in billings if b.get("status") == "invoice_issued"}


def _to_int(v):
    """金額を int 化。None/空文字/float文字列/小数に堅牢 (API由来の型揺れを吸収)。"""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def _amount_by_customer(billings):
    """customer_id → amount 合計 (同一顧客に複数billingがあれば合算)。"""
    out = {}
    for b in billings:
        if b.get("status") != "invoice_issued":
            continue
        cid = b["customer_id"]
        out[cid] = out.get(cid, 0) + _to_int(b.get("amount"))
    return out


def detect_gaps(prev_billings, curr_billings):
    """前月/今月の billing 一覧から発行状況を分類して返す。

    返り値 dict:
      gap_candidates : 前月発行・今月未発行 (発行漏れ候補) — sorted list
      continuing     : 前月・今月とも発行 (金額変動候補) — sorted list
      new_this_month : 今月のみ発行 — sorted list
      prev_amount    : {customer_id: 前月金額}
      curr_amount    : {customer_id: 今月金額}
    """
    P = _issued_customer_ids(prev_billings)
    C = _issued_customer_ids(curr_billings)
    prev_amount = _amount_by_customer(prev_billings)
    curr_amount = _amount_by_customer(curr_billings)
    return {
        "gap_candidates": sorted(P - C),
        "continuing": sorted(P & C),
        "new_this_month": sorted(C - P),
        "prev_amount": prev_amount,
        "curr_amount": curr_amount,
    }


def amount_changed(continuing, prev_amount, curr_amount):
    """継続発行のうち金額が前月と変わった customer_id を返す。"""
    return sorted(
        cid for cid in continuing
        if prev_amount.get(cid) != curr_amount.get(cid)
    )
