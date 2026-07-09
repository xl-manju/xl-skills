#!/usr/bin/env python3
"""C12 発行漏れレポート根治ゴールデン回帰 (matching-rootcause plan・OUT1/OUT2)。

2026-07-09 の全段実データ調査で確定した独立6要因を再現する MF実績ゴールデン fixture に対し、
収集(C1)→R1決定論化(C2/C05)→分類(C3/C4)→collapse(C5/C03)→顧客ID結合(C6/C02) の各段根治を
end-to-end で凍結する。中核受入 = 「今月金額=null かつ忠実発行済み=偽発行漏れ」が 0 件 (OUT1)。

要因 → 症状社 → 検証:
  C1 収集 billing-status  paws             account_transfer_notified 発行を収集し MATCH (取得段で落とさない)
  C2 R1 curr=None 根治     2nd Community    決定論 producer が発行済み社の当月行を出す (curr=None にしない)
  C4 prev 取消の継続性     2nd Community    prev=REVIEW_CANCELED + curr MATCH が STATE_NEW でなく継続発行
  C3 STATE_NEW×MATCH_ANNUAL ThinkTank型     年契約新規行が lookback 無しでも正常 (過剰要対応にしない)
  C5 代理店 collapse       HOSONO           複数エンドクライアント発行が幻遷移なく突合・実額が隠れない
  C14 Goodhart 非依存      name-drift 社     個社会社名ハードコード無しで MF顧客ID 経路のみ MATCH
"""
import os
import sys

import mfk_reconcile as R
import mfk_period_report as P
import mfk_verdict_export as V
import mfk_collect_status as CS

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))


# ---------------------------------------------------------------------------
# fixture helpers
# ---------------------------------------------------------------------------
def _line(desc, amount, status="passed", canceled_at=None, billing_id="b1", paren=None):
    d = {"desc": desc, "amount": amount, "status": status,
         "canceled_at": canceled_at, "billing_id": billing_id}
    return d


def _mf(customers):
    return {"customers": customers, "canceled_count": 0}


def _sheet(torihiki, product, amount, **extra):
    row = {"取引先": torihiki, "商品": product, "確認内容": f"月額 {amount:,}円",
           "契約開始日": "2601", "契約終了月": ""}
    row.update(extra)
    return row


# ===========================================================================
# C1: 収集 billing-status (paws=account_transfer_notified を発行済みとして収集)
# ===========================================================================
def test_c1_collect_includes_post_issuance_status():
    # account_transfer_notified は発行後 status。収集対象に含める (取得段で落とさない=paws 根治)。
    assert CS.is_issued_billing("account_transfer_notified") is True
    assert CS.is_issued_billing("invoice_issued") is True
    # scheduled(発行前)/stopped(真の停止)は非収集。
    assert CS.is_issued_billing("scheduled") is False
    assert CS.is_issued_billing("stopped") is False


# ===========================================================================
# C2: R1 決定論 producer が発行済み社の当月行を出す (curr=None にしない)
# ===========================================================================
def test_c2_deterministic_producer_no_curr_none_for_issued():
    """2nd Community 型: MF実績で MATCH_MONTHLY なのに旧 R1(手組み)が curr=None にしていた症状。
    C05 producer は reconcile().rows 全件を persist するため発行済み社の当月行が必ず出る。"""
    mf = _mf({"c1": {"name": "セカンドコミュニティ株式会社",
                     "lines": [_line("月額サポート", 50000)]}})
    sheet = [_sheet("セカンドコミュニティ株式会社", "月額サポート", 50000)]
    curr_doc, _prev = V.export_curr_prev(sheet, mf, mf, "2606")
    # 発行済み社の当月行が curr-verdicts に存在する (curr=None でない)。
    issued = [r for r in curr_doc["rows"] if r.get("reliable_issued")]
    assert issued, "発行済み社の当月行が curr-verdicts に必ず出る (curr=None 根治)"
    assert V.validate_carrier(curr_doc) == []


# ===========================================================================
# C4: prev 取消の継続性 (prev=REVIEW_CANCELED + curr MATCH = 継続発行・STATE_NEW でない)
# ===========================================================================
def test_c4_prev_canceled_is_continuation_not_new():
    prev = {"取引先": "セカンドコミュニティ", "商品": "月額サポート", "verdict": "REVIEW_CANCELED",
            "actual_amount": None, "reliable_issued": False,
            "supply_state": R.mfk_actuals.SUPPLY_INACTIVE_CANCELED, "canceled_at": "2605-07-03"}
    curr = {"取引先": "セカンドコミュニティ", "商品": "月額サポート", "verdict": "MATCH_MONTHLY",
            "actual_amount": 50000, "reliable_issued": True,
            "supply_state": R.mfk_actuals.SUPPLY_ACTIVE, "canceled_at": None}
    pairing = P.compare_periods([prev], [curr])
    assert len(pairing) == 1
    assert pairing[0]["state"] == P.STATE_CONTINUED, "前月発行→取消の継続契約は STATE_NEW でなく継続発行"

    # 真の未発行 (supply_state=none) は従来どおり STATE_NEW のまま (区別される)。
    prev_none = dict(prev, supply_state=R.mfk_actuals.SUPPLY_NONE, canceled_at=None, verdict="GAP")
    pairing2 = P.compare_periods([prev_none], [curr])
    assert pairing2[0]["state"] == P.STATE_NEW, "真の未発行は STATE_NEW のまま (取消継続と混同しない)"


# ===========================================================================
# C3: STATE_NEW × MATCH_ANNUAL が lookback 無しで正常化 (過剰要対応にしない)
# ===========================================================================
def test_c3_annual_new_row_normal_without_lookback():
    curr = {"取引先": "ThinkTank社", "商品": "100億ThinkTank利用料", "verdict": "MATCH_ANNUAL",
            "actual_amount": 1200000, "reliable_issued": True,
            "supply_state": R.mfk_actuals.SUPPLY_ACTIVE, "canceled_at": None}
    pairing = P.compare_periods([], [curr])   # 前月なし今月あり = STATE_NEW
    assert pairing[0]["state"] == P.STATE_NEW
    # lookback 無し (None) でも MATCH_ANNUAL は正常☑ (GAP_OK)。
    rows = P.classify_period_transition(pairing, lookback=None, target_month="2606")
    annual_rows = [r for r in rows if "ThinkTank" in str(r.get("customer") or r.get("取引先") or "")]
    assert annual_rows, "MATCH_ANNUAL 新規行が emit される"
    assert annual_rows[0]["gap_check"] == P.GAP_OK, "年契約新規は lookback 無しでも正常 (過剰要対応にしない)"


# ===========================================================================
# C5 + C03: 代理店 collapse で発行済み実額が隠れない
# ===========================================================================
def test_c5_agency_multi_endclient_no_phantom_transition():
    """HOSONO 型: 1 商品に複数エンドクライアント契約 (contract_id 無し・異額)。
    エンドクライアント名粒度で disambiguate され幻の NEW+STOPPED を生まない。"""
    def _row(ec, amount):
        return {"取引先": "HOSONO", "商品": "チイキズカン業務委託費", "エンドクライアント名": ec,
                "verdict": "MATCH_MONTHLY", "actual_amount": amount, "reliable_issued": True,
                "supply_state": R.mfk_actuals.SUPPLY_ACTIVE, "canceled_at": None}
    prev = [_row("甲様", 210000), _row("乙様", 70000)]
    curr = [_row("甲様", 210000), _row("乙様", 70000)]
    pairing = P.compare_periods(prev, curr)
    # エンドクライアント粒度で 2 ペアに分離 (1 件へ潰れて幻遷移を生まない)。
    assert len(pairing) == 2, pairing
    assert all(p["state"] == P.STATE_CONTINUED for p in pairing), "両エンドクライアントとも継続発行"


def test_c5_sink_collapse_preserves_issued_amount():
    """sink 段 (C03): 同一 (対象月,取引先,商品) collapse で発行済み実額が要対応・null で潰れない。"""
    import notion_report_sink as sink
    issued = {"gap_check": "正常", "customer": "HOSONO", "product": "チイキズカン業務委託費",
              "amount": 70000, "reliable_issued": True, "comment": "（乙様）発行済み"}
    gap = {"gap_check": "要対応", "customer": "HOSONO", "product": "チイキズカン業務委託費",
           "amount": None, "reliable_issued": False, "comment": "（丙様）漏れ"}
    merged = sink._prefer_action(issued, gap)
    assert sink._severity_rank(merged) == 1, "要対応 severity を保持 (漏れを隠さない)"
    assert sink._amount(merged, "amount") == 70000, "発行済み実額を保全 (今月金額=null にしない)"


def test_c5_sink_collapse_sums_both_issued_amounts():
    """sink 段 (C03): 同一 (対象月,取引先,商品) の正常×正常 collapse (複数エンドクライアント全発行) で
    両発行済み実額を合算保全する — 後着だけ残して先行実額を黙って落とす過少表示 (F-TRADE-1 の正常×正常
    残穴) を根治する。HOSONO 甲様 210000 + 乙様 70000 が 70000 のみに潰れず 280000 で保全される。"""
    import notion_report_sink as sink
    ko = {"gap_check": "正常", "customer": "HOSONO", "product": "チイキズカン業務委託費",
          "amount": 210000, "reliable_issued": True, "comment": "（甲様）発行済み"}
    otsu = {"gap_check": "正常", "customer": "HOSONO", "product": "チイキズカン業務委託費",
            "amount": 70000, "reliable_issued": True, "comment": "（乙様）発行済み"}
    merged = sink._prefer_action(ko, otsu)
    assert sink._severity_rank(merged) == 0, "両正常なので正常 severity を保持"
    assert sink._amount(merged, "amount") == 280000, "両エンドクライアントの発行済み実額を合算 (片方を隠さない)"
    assert "合算" in (merged.get("comment") or ""), "合算した旨を注記して黙殺しない"
    # 3 件以上でも左畳込で総額を保全する (順序非依存)。
    hei = {"gap_check": "正常", "customer": "HOSONO", "product": "チイキズカン業務委託費",
           "amount": 30000, "reliable_issued": True, "comment": "（丙様）発行済み"}
    three = sink._prefer_action(sink._prefer_action(ko, otsu), hei)
    assert sink._amount(three, "amount") == 310000, "3 エンドクライアントの総額 (210000+70000+30000) を保全"
    # 片方 None は非 None を採り、後着 None で発行済み実額を上書きしない。
    otsu_null = dict(otsu, amount=None, reliable_issued=False)
    kept = sink._prefer_action(ko, otsu_null)
    assert sink._amount(kept, "amount") == 210000, "後着 None で発行済み実額を潰さない"


def test_c5_orphan_surfaced_as_master_registration():
    """C05 が分離した逆方向 orphans (MF実績あり×請求確認シートに契約なし) が build_report で
    『要マスタ登録』行として surface される — 下流 _rows_of が rows のみ読む seam で黙って落とさない
    (GAP-ID-ALIAS-BACKFILL-PATH: 寄らない残余を隠さずレポート可視化する closure)。"""
    mf = _mf({
        "c1": {"name": "登録済み社", "lines": [_line("月額", 50000)]},
        "cust-orphan": {"name": "未登録オーファン社", "lines": [_line("スポット業務", 90000)]},
    })
    sheet = [_sheet("登録済み社", "月額", 50000)]  # オーファン社はシートに契約なし
    curr_doc, prev_doc = V.export_curr_prev(sheet, mf, mf, "2606")
    assert curr_doc["orphans"], "MF実績あり×シート未登録が orphans へ分離される (curr=None にしない)"
    rows = P.build_report(curr_doc, prev_doc, target_month="2606")
    master_rows = [r for r in rows if r.get("period_diff") == "要マスタ登録"]
    assert master_rows, "orphan が build_report で要マスタ登録行として surface される (seam で落とさない)"
    assert any("未登録オーファン社" in str(r.get("customer")) for r in master_rows)
    assert master_rows[0]["gap_check"] == P.GAP_ACTION, "要マスタ登録は要対応 (マスタ登録の action が要る)"
    assert master_rows[0]["amount"] == 90000, "MF実額を要マスタ登録行の今月金額へ carry する"


# ===========================================================================
# C14: 個社会社名ハードコード非依存 (name-drift 社が MF顧客ID 経路のみで MATCH)
# ===========================================================================
def test_c14_name_drift_matches_via_customer_id_only():
    """ハードコード非対象の name-drift 社 (シート日本語名 ⇔ MF英語名) が、会社名照合では
    寄らないが MF顧客ID を契約へ carry すれば ID 優先経路で MATCH する (C02 一般解・Goodhart 防止)。"""
    # シート名「アルファ合同会社」/ MF名「Alpha LLC」は normalize しても会社名一致しない。
    mf = _mf({"cust-XYZ": {"name": "Alpha LLC", "lines": [_line("月額", 90000)]}})
    idx = R.build_mf_index(mf)
    # 会社名だけでは境界が寄らない (name-drift)。
    boundary_by_name, confirmed = R._boundary_customers(
        {"取引先": "アルファ合同会社"}, idx)
    assert boundary_by_name == [] and confirmed is False, "会社名照合では name-drift 社は寄らない"
    # MF顧客ID を契約へ carry すれば ID 優先経路で確定境界になる。
    boundary_by_id, confirmed_id = R._boundary_customers(
        {"取引先": "アルファ合同会社", "MF顧客ID": "cust-XYZ"}, idx)
    assert confirmed_id is True and boundary_by_id[0][0] == "cust-XYZ", \
        "MF顧客ID carry で ID 優先経路が確定境界を返す (会社名リテラル無しで MATCH)"


def test_c14_no_company_literals_in_matching_engine():
    """照合エンジンに個社会社名リテラルが 0 件 (RETRACT-1 の対症療法が撤去されている)。"""
    import inspect
    forbidden = ["2ndcommunity", "secondcommunity", "セカンドコミュニティ",
                 "hosono", "細野", "paws", "パウズ", "ポーズ"]
    for fn in (R._company_match, R._boundary_customers, R.find_mf_match):
        src = inspect.getsource(fn).lower()
        for lit in forbidden:
            assert lit.lower() not in src, f"{fn.__name__} に会社名リテラル {lit!r} (C14 違反)"


# ===========================================================================
# OUT1 統合: 「今月金額=null かつ忠実発行済み=偽発行漏れ」が 0 件
# ===========================================================================
def _run_report(sheet, mf_curr, mf_prev, target="2606", lookback=None):
    """C05 producer → period_report classify を通し分類済みレポート行を返す end-to-end 経路。"""
    curr_doc, prev_doc = V.export_curr_prev(sheet, mf_curr, mf_prev, target)
    pairing = P.compare_periods(prev_doc["rows"], curr_doc["rows"])
    rows = P.classify_period_transition(pairing, lookback=lookback, target_month=target)
    return rows, curr_doc


def test_out1_no_false_issue_gap_for_issued_companies():
    """OUT1 中核: 発行済み社が『今月金額=null かつ要対応(偽・発行漏れ)』に落ちない。

    2nd Community/HOSONO 型の発行済み社が当月 MATCH_MONTHLY で継続発行され、今月金額が実額で出る。
    """
    mf = _mf({
        "c1": {"name": "セカンドコミュニティ株式会社", "lines": [_line("月額サポート", 50000)]},
        "c2": {"name": "HOSONO株式会社", "lines": [_line("チイキズカン業務委託費", 70000)]},
    })
    sheet = [
        _sheet("セカンドコミュニティ株式会社", "月額サポート", 50000),
        _sheet("HOSONO株式会社", "チイキズカン業務委託費", 70000),
    ]
    rows, curr_doc = _run_report(sheet, mf, mf)
    # 偽・発行漏れ = 今月金額=null (None) かつ 要対応。発行済み社では 0 件であること。
    false_gaps = [
        r for r in rows
        if r.get("gap_check") == P.GAP_ACTION and P._amount_of(r) is None
        and any(r.get(k) for k in ("reliable_issued",))
    ]
    assert false_gaps == [], f"偽・発行漏れが 0 件でない: {false_gaps}"
    # 発行済み社は継続発行 (正常) で今月金額=実額。
    issued_rows = [r for r in rows if r.get("gap_check") == P.GAP_OK]
    assert issued_rows, "発行済み社が継続発行(正常)で emit される"
    assert all(P._amount_of(r) is not None for r in issued_rows), "発行済み行は今月金額=実額 (null でない)"
