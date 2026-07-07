#!/usr/bin/env python3
"""scripts/mfk_period_report.py (C05: 前月↔今月の発行状態遷移分類) の単体テスト。

オフライン・fixture はテスト内 dict で自己完結 (network/ファイル不要。CLI は tmp_path を使う)。
検証観点 (component-inventory C05 の criteria 由来):
  - 対象月決定 (7/2 実行なら今月=6月分・先月=5月分)。
  - 取引先×商品集合の 4 状態 (継続発行 / 前月なし今月あり / 元々請求なし / 前月あり今月なし)。
  - 差分該当取引先限定の 12ヶ月遡り (根拠コメント補強のみ・既存判定を上書きしない)。
  - 年契約周期 (SUPPRESS_ANNUAL 一次源) / 年→月切替 / トライアル完了 (canon 前生名) /
    契約終了 (SUPPRESS_ENDED 消費・自由文非再パース) / 発行漏れ候補(要対応) の全分岐。
  - 継続発行も全行 emit・今月なし前月なしは非 emit。
  - 根拠なき終了月が REVIEW_ENDED_NO_BASIS で漏れ隠蔽されない安全弁。
"""
import datetime
import json

import mfk_period_report as P


# ---------------------------------------------------------------------------
# 行ビルダ (per-月 verdict 行を模す最小 dict)
# ---------------------------------------------------------------------------
def _row(customer, product, verdict, amount=50000, contract_id=None,
         end_month=None, kakunin=None, evidence_amount=None, raw=None):
    r = {"取引先": customer, "商品": product, "verdict": verdict, "現行単価": amount}
    if contract_id is not None:
        r["契約ID"] = contract_id
    if end_month is not None:
        r["契約終了月"] = end_month
    if kakunin is not None:
        r["確認内容"] = kakunin
    if raw is not None:
        r["商品生名"] = raw
    if evidence_amount is not None:
        r["evidence"] = {"amount": evidence_amount, "desc": "MF明細"}
    return r


def _classify(prev_rows, curr_rows, lookback=None, contract_end=None, target="2606"):
    pairing = P.compare_periods(prev_rows, curr_rows)
    return P.classify_period_transition(
        pairing, lookback=lookback, contract_end=contract_end, target_month=target)


def _by_customer(report, customer):
    return [r for r in report if r["customer"] == customer]


# ---------------------------------------------------------------------------
# 対象月決定
# ---------------------------------------------------------------------------
def test_resolve_target_months_july_run():
    # 2026-07-02 実行 → 今月=2606 (6月分)・先月=2605 (5月分)。
    curr, prev = P.resolve_target_months(datetime.date(2026, 7, 2))
    assert curr == "2606"
    assert prev == "2605"


def test_resolve_target_months_january_wraps_year():
    curr, prev = P.resolve_target_months(datetime.date(2026, 1, 15))
    assert curr == "2512"   # 前月=前年12月
    assert prev == "2511"


def test_resolve_target_months_default_today():
    # today 省略でも (YYMM, YYMM) を返す (network なし・例外なし)。
    curr, prev = P.resolve_target_months()
    assert len(curr) == 4 and len(prev) == 4


def test_prev_month_helpers_invalid():
    assert P._prev_month_ym("bad") is None
    assert P._prev_year_month("bad") is None


# ---------------------------------------------------------------------------
# compare_periods: 4 状態
# ---------------------------------------------------------------------------
def test_compare_periods_four_states():
    prev = [
        _row("継続社", "月額", "MATCH_MONTHLY"),
        _row("停止社", "月額", "MATCH_MONTHLY"),
        _row("既存対象外社", "年額", "SUPPRESS_ANNUAL"),
    ]
    curr = [
        _row("継続社", "月額", "MATCH_MONTHLY"),
        _row("新規社", "月額", "MATCH_MONTHLY"),
        _row("停止社", "月額", "GAP"),
        _row("既存対象外社", "年額", "SUPPRESS_ANNUAL"),
    ]
    pairing = {tuple(p["key"]): p["state"] for p in P.compare_periods(prev, curr)}
    assert pairing[(P.R.normalize("継続社"), P.R.normalize("月額"))] == P.STATE_CONTINUED
    assert pairing[(P.R.normalize("新規社"), P.R.normalize("月額"))] == P.STATE_NEW
    assert pairing[(P.R.normalize("停止社"), P.R.normalize("月額"))] == P.STATE_STOPPED
    assert pairing[(P.R.normalize("既存対象外社"), P.R.normalize("年額"))] == P.STATE_NONE


def test_none_state_not_emitted_and_continued_all_emitted():
    prev = [_row("継続社", "月額", "MATCH_MONTHLY"),
            _row("対象外社", "年額", "SUPPRESS_ANNUAL")]
    curr = [_row("継続社", "月額", "MATCH_MONTHLY"),
            _row("対象外社", "年額", "SUPPRESS_ANNUAL")]
    report = _classify(prev, curr)
    customers = {r["customer"] for r in report}
    assert "継続社" in customers          # 継続発行は emit
    assert "対象外社" not in customers     # 元々請求なしは非 emit
    cont = _by_customer(report, "継続社")[0]
    assert cont["gap_check"] == "正常"
    assert cont["period_diff"] == "継続発行"


def test_continued_amount_change_note():
    prev = [_row("値上げ社", "月額", "MATCH_MONTHLY", amount=40000)]
    curr = [_row("値上げ社", "月額", "MATCH_MONTHLY", amount=50000)]
    row = _classify(prev, curr)[0]
    assert row["amount"] == 50000
    assert row["prev_amount"] == 40000
    assert "金額変動" in row["comment"]


def test_issued_via_evidence_amount_only():
    # verdict が ISSUED 集合外でも evidence に正の金額があれば発行あり扱い。
    prev = [_row("証跡社", "月額", "REVIEW_QTY_MISMATCH", evidence_amount=12000)]
    curr = [_row("証跡社", "月額", "REVIEW_AMOUNT_MISMATCH", evidence_amount=12000)]
    row = _classify(prev, curr)[0]
    assert row["period_diff"] == "継続発行"


# ---------------------------------------------------------------------------
# 状態: 前月なし今月あり (新規 / 年→月切替)
# ---------------------------------------------------------------------------
def test_new_without_lookback_is_plain_new():
    curr = [_row("新規社", "月額", "MATCH_MONTHLY")]
    row = _classify([], curr)[0]
    assert row["gap_check"] == "正常"
    assert row["period_diff"] == "新規/年→月切替"
    assert "新規発行" in row["comment"]


def test_new_with_12mo_annual_lookback_is_switch():
    # 12ヶ月前 (2606→2506) に年契約一括発行あり → 年→月切替の裏付け。
    curr = [_row("年→月社", "月額", "MATCH_MONTHLY")]
    lookback = {"年→月社": [{"month": "2506", "annual": True},
                          {"month": "2601", "issued": True}]}
    row = _classify([], curr, lookback=lookback, target="2606")[0]
    assert row["period_diff"] == "新規/年→月切替"
    assert "2506" in row["comment"]
    assert "月額切替" in row["comment"]


def test_new_with_annual_history_other_month():
    # switch_month と一致しない年契約履歴でも二次分岐で年→月切替の可能性を返す。
    curr = [_row("年契約履歴社", "月額", "MATCH_MONTHLY")]
    lookback = [{"customer": "年契約履歴社", "month": "2509", "verdict": "MATCH_ANNUAL"}]
    row = _classify([], curr, lookback=lookback, target="2606")[0]
    assert "年→月切替" in row["comment"]


# ---------------------------------------------------------------------------
# 状態: 前月あり今月なし (非請求事情 → 発行漏れ候補)
# ---------------------------------------------------------------------------
def test_stopped_annual_suppress_is_normal():
    prev = [_row("年契約社", "年額", "MATCH_ANNUAL", evidence_amount=600000)]
    curr = [_row("年契約社", "年額", "SUPPRESS_ANNUAL")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "正常"
    assert "年契約周期" in row["period_diff"]
    assert "SUPPRESS_ANNUAL" in row["comment"]


def test_stopped_annual_with_lookback_reinforcement():
    prev = [_row("年契約社", "年額", "MATCH_ANNUAL", evidence_amount=600000)]
    curr = [_row("年契約社", "年額", "SUPPRESS_ANNUAL")]
    lookback = {"年契約社": [{"month": "2512", "annual_lump": True}]}
    row = _classify(prev, curr, lookback=lookback)[0]
    assert row["gap_check"] == "正常"          # 既存判定を上書きしない
    assert "12ヶ月履歴に年契約一括発行あり" in row["comment"]  # 補強のみ


def test_stopped_ended_with_basis_is_normal():
    # 既存 verdict SUPPRESS_ENDED を消費するのみ (自由文再パースなし)。
    prev = [_row("終了社", "月額", "MATCH_MONTHLY")]
    curr = [_row("終了社", "月額", "SUPPRESS_ENDED", end_month="2605")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "正常"
    assert "契約完了" in row["period_diff"]
    assert "契約終了月=2605" in row["comment"]


def test_stopped_ended_no_basis_is_gap_safety_valve():
    # 安全弁: 構造化列に契約終了月があっても REVIEW_ENDED_NO_BASIS なら抑制せず発行漏れ候補。
    prev = [_row("疑似終了社", "月額", "MATCH_MONTHLY")]
    curr = [_row("疑似終了社", "月額", "REVIEW_ENDED_NO_BASIS", end_month="2605")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "要対応"
    assert "根拠なき終了月" in row["period_diff"]
    assert "2605" in row["comment"]


def test_stopped_ended_no_basis_without_end_month_still_gap():
    prev = [_row("疑似終了社2", "月額", "MATCH_MONTHLY")]
    curr = [_row("疑似終了社2", "月額", "REVIEW_ENDED_NO_BASIS")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "要対応"
    assert "終了根拠なし" in row["comment"]


def test_stopped_trial_completion_is_normal():
    # トライアル完了は canon 前の生商品名を参照 (verdict は GAP でもトライアル信号で正常化)。
    prev = [_row("トライアル社", "利用料", "MATCH_MONTHLY",
                 raw="100億ThinkTankトライアル(利用料)")]
    curr = [_row("トライアル社", "利用料", "GAP",
                 raw="100億ThinkTankトライアル(利用料)")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "正常"
    assert "トライアル完了" in row["period_diff"]


def test_stopped_gap_candidate_requires_action():
    # 正常事情に該当しない停止 → 発行漏れ候補 (要対応)。
    prev = [_row("漏れ社", "月額", "MATCH_MONTHLY")]
    curr = [_row("漏れ社", "月額", "GAP")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "要対応"
    assert "発行漏れ候補" in row["period_diff"]
    assert row["prev_amount"] == 50000


def test_stopped_when_curr_row_absent():
    # 今月 verdict 行が全く無い (今月なし) 継続契約 → 既定は発行漏れ候補 (要対応)。
    prev = [_row("消失社", "月額", "MATCH_MONTHLY")]
    row = _classify(prev, [])[0]
    assert row["gap_check"] == "要対応"


def test_stopped_offmonth_suppress_is_normal_not_leak():
    # SUPPRESS_OFFMONTH (隔月/分割の対象外月・契約開始前) は verdict-mapping SSOT で
    # SUPPRESS_*→対象外。C05 は再判定せず正常(対象外)扱いにする (偽陽性の漏れ扱いを防ぐ)。
    prev = [_row("隔月社", "隔月保守", "MATCH_MONTHLY")]
    curr = [_row("隔月社", "隔月保守", "SUPPRESS_OFFMONTH")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "正常"
    assert "対象外" in row["period_diff"]
    assert "SUPPRESS_OFFMONTH" in row["comment"]


def test_stopped_oneshot_suppress_is_normal_not_leak():
    # SUPPRESS_ONESHOT (単発発行済・当月対象外) も対象外=正常。
    prev = [_row("単発社", "初期費用", "MATCH_MONTHLY")]
    curr = [_row("単発社", "初期費用", "SUPPRESS_ONESHOT")]
    row = _classify(prev, curr)[0]
    assert row["gap_check"] == "正常"
    assert "単発発行済" in row["comment"]


def test_contract_end_file_lookup_for_ended():
    # 契約終了月は行に無くても contract_end データ (二次情報) から解決する。
    prev = [_row("終了社X", "月額", "MATCH_MONTHLY")]
    curr = [_row("終了社X", "月額", "SUPPRESS_ENDED")]
    contract_end = {"records": [
        {"取引先": "終了社X", "商品": "月額", "end_month": "2604"}]}
    row = _classify(prev, curr, contract_end=contract_end)[0]
    assert "契約終了月=2604" in row["comment"]


def test_contract_end_customer_map_form():
    # {customer: end_month} 形の contract_end も受ける (商品空キー)。
    ce = P._index_contract_end({"顧客A": "2603"})
    assert ce[(P.R.normalize("顧客A"), P.R.normalize(""))] == "2603"


# ---------------------------------------------------------------------------
# 突合キー: contract_id disambiguation
# ---------------------------------------------------------------------------
def test_contract_id_disambiguation_same_customer_product():
    # 同一取引先×同一商品で 2 契約 → contract_id で別扱い。片方継続・片方停止。
    prev = [_row("複数契約社", "月額", "MATCH_MONTHLY", contract_id="C1"),
            _row("複数契約社", "月額", "MATCH_MONTHLY", contract_id="C2")]
    curr = [_row("複数契約社", "月額", "MATCH_MONTHLY", contract_id="C1"),
            _row("複数契約社", "月額", "GAP", contract_id="C2")]
    report = _by_customer(_classify(prev, curr), "複数契約社")
    by_cid = {r["contract_id"]: r for r in report}
    assert by_cid["C1"]["period_diff"] == "継続発行"
    assert by_cid["C2"]["gap_check"] == "要対応"


def test_no_disambiguation_when_single_contract():
    # 単一 contract_id なら取引先×商品のみで突合 (片側に契約ID欠落でも対応付く)。
    prev = [_row("単一社", "月額", "MATCH_MONTHLY", contract_id="C9")]
    curr = [_row("単一社", "月額", "MATCH_MONTHLY")]  # contract_id 欠落
    report = _by_customer(_classify(prev, curr), "単一社")
    assert len(report) == 1
    assert report[0]["period_diff"] == "継続発行"


# ---------------------------------------------------------------------------
# フィールド抽出ヘルパ
# ---------------------------------------------------------------------------
def test_customer_fallback_via_extract_names():
    # customer/取引先 が空でも確認内容から extract_names で取引先を拾う。
    row = {"商品": "月額", "verdict": "GAP", "確認内容": "株式会社テスト の件"}
    assert "テスト" in P._customer(row)


def test_amount_and_int_coercion():
    assert P._to_int("50,000") == 50000
    assert P._to_int(None) is None
    assert P._to_int("x") is None
    assert P._amount_of({"現行単価": "12,000"}) == 12000
    assert P._amount_of({"evidence": {"amount": 900}}) == 900
    assert P._amount_of({}) is None


def test_lookback_index_forms():
    # dict(customer→list) / dict(records) / list の 3 形を吸収する。
    a = P._index_lookback({"社": [{"month": "2501"}]})
    b = P._index_lookback({"records": [{"customer": "社", "month": "2501"}]})
    c = P._index_lookback([{"customer": "社", "month": "2501"}])
    key = P.R.normalize("社")
    assert a[key] and b[key] and c[key]
    assert P._index_lookback(None) == {}


# ---------------------------------------------------------------------------
# CLI (main) — I/O + exit code
# ---------------------------------------------------------------------------
def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_main_happy_path_exit0(tmp_path, capsys):
    prev = _write(tmp_path, "prev.json",
                  [_row("継続社", "月額", "MATCH_MONTHLY")])
    curr = _write(tmp_path, "curr.json",
                  {"target_month": "2606",
                   "rows": [_row("継続社", "月額", "MATCH_MONTHLY")]})
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["customer"] == "継続社"
    assert out[0]["target_month"] == "2606"


def test_main_gap_returns_exit1(tmp_path, capsys):
    prev = _write(tmp_path, "prev.json", [_row("漏れ社", "月額", "MATCH_MONTHLY")])
    curr = _write(tmp_path, "curr.json", [_row("漏れ社", "月額", "GAP")])
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev,
                 "--target-month", "2606"])
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out[0]["gap_check"] == "要対応"


def test_main_with_lookback_and_contract_end_files(tmp_path, capsys):
    prev = _write(tmp_path, "prev.json", [_row("年契約社", "年額", "MATCH_ANNUAL",
                                               evidence_amount=600000)])
    curr = _write(tmp_path, "curr.json", [_row("年契約社", "年額", "SUPPRESS_ANNUAL")])
    lb = _write(tmp_path, "lb.json", {"年契約社": [{"month": "2512", "annual": True}]})
    ce = _write(tmp_path, "ce.json", {"records": []})
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev,
                 "--lookback-12mo", lb, "--contract-end", ce, "--target-month", "2606"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert "年契約周期" in out[0]["period_diff"]


def test_main_missing_file_fail_closed(tmp_path):
    prev = _write(tmp_path, "prev.json", [])
    rc = P.main(["--curr-verdicts", str(tmp_path / "nope.json"),
                 "--prev-verdicts", prev])
    assert rc == 2


def test_main_bad_lookback_fail_closed(tmp_path):
    prev = _write(tmp_path, "prev.json", [])
    curr = _write(tmp_path, "curr.json", [])
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev,
                 "--lookback-12mo", str(tmp_path / "nope.json")])
    assert rc == 2


def test_main_bad_contract_end_fail_closed(tmp_path):
    prev = _write(tmp_path, "prev.json", [])
    curr = _write(tmp_path, "curr.json", [])
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev,
                 "--contract-end", str(tmp_path / "nope.json")])
    assert rc == 2


def test_main_default_target_when_absent(tmp_path, capsys):
    # target 指定も file の target_month も無いとき resolve_target_months で導出する。
    prev = _write(tmp_path, "prev.json", [_row("継続社", "月額", "MATCH_MONTHLY")])
    curr = _write(tmp_path, "curr.json", [_row("継続社", "月額", "MATCH_MONTHLY")])
    rc = P.main(["--curr-verdicts", curr, "--prev-verdicts", prev])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out[0]["target_month"]) == 4  # YYMM 導出


def test_rows_of_accepts_list_and_dict():
    assert P._rows_of([{"a": 1}, "skip"]) == [{"a": 1}]
    assert P._rows_of({"verdicts": [{"b": 2}]}) == [{"b": 2}]
    assert P._rows_of(123) == []


# ---------------------------------------------------------------------------
# F-1: 継続漏れ (両月未発行だが今月 GAP) を要対応として emit・対象外は非 emit を維持
# ---------------------------------------------------------------------------

def test_continuing_gap_emitted_as_action():
    # 前月も今月も未発行だが今月 verdict=GAP の継続漏れは要対応として残す (脱落させない)。
    rows = P.build_report(
        [_row("継続漏れ社", "月額", "GAP")],
        [_row("継続漏れ社", "月額", "GAP")], target_month="2606")
    assert len(rows) == 1
    assert rows[0]["gap_check"] == "要対応"
    assert rows[0]["customer"] == "継続漏れ社"
    assert "継続" in rows[0]["period_diff"]


def test_originally_unbilled_and_suppressed_still_dropped():
    # F-1 の裏: SUPPRESS_* の両月未発行は対象外=非 emit を維持 (過剰報告しない)。
    suppressed = P.build_report(
        [_row("隔月社", "月額", "SUPPRESS_OFFMONTH")],
        [_row("隔月社", "月額", "SUPPRESS_OFFMONTH")], target_month="2606")
    assert suppressed == []
    # curr に行が無い (元々請求なし/当月の発行期待なし) も非 emit。
    prev_only = P.build_report([], [_row("退会社", "月額", "GAP")], target_month="2606")
    assert prev_only == []
