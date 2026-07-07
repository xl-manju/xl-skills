#!/usr/bin/env python3
# /// script
# name: mfk_period_report
# purpose: 既存 lib/mfk_reconcile.py の per-月 verdict を入力に取り、前月↔今月の発行状態遷移
#          だけを分類する薄い差分エンジン。取引先×商品を突合し 状態 (継続発行 / 新規・年→月切替 /
#          対象外(元々請求なし) / 前月あり今月なし / 継続漏れ=両月未発行だが今月GAP) へ分類し、前月あり今月なしは既存 verdict
#          (SUPPRESS_ENDED / SUPPRESS_ANNUAL / MATCH_ANNUAL / REVIEW_ENDED_NO_BASIS) を一次源に
#          正常な非請求事情の有無を確認して発行漏れ候補(要対応)を検出する。自由文の終了根拠は
#          再パースせず既存 verdict を消費するのみ (終了根拠判定 SSOT=mfk_reconcile)。
# inputs:
#   - argv: --curr-verdicts FILE (今月=target 請求対象月の per-月 verdict JSON)
#           --prev-verdicts FILE (先月=target-1ヶ月の per-月 verdict JSON)
#           --lookback-12mo FILE (差分該当取引先のみの12ヶ月発行履歴・任意)
#           --contract-end FILE  (契約終了月データ・任意)
#           --target-month YYMM  (対象月・省略時は curr-verdicts の target_month → 実行日から導出)
# outputs:
#   - stdout: 分類済みレポート行 JSON (list)。各行キー: customer / amount / prev_amount /
#             gap_check / period_diff / product / comment / contract_id / target_month
#   - stderr: violation 説明
#   - exit: 0=正常 / 1=分類上の要確認(要対応)あり / 2=fail-closed(入力欠落・読込失敗)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: [mfk_reconcile]
# requires-python: ">=3.11"
# ///
"""前月↔今月の発行状態遷移を分類する薄い差分エンジン (C05)。

本スクリプトは新しい照合ロジックを持たない。既存 lib/mfk_reconcile.py が算出した per-月
verdict (MATCH_* / SUPPRESS_* / GAP / REVIEW_*) を入力に取り、前月集合と今月集合の
**発行状態遷移だけ** を分類する (SSOT 尊重: 終了根拠の再パースや金額照合の再発明はしない)。

『今月』は実行日カレンダー月ではなく直近締め済みの請求対象月。例: 2026-07-02 実行なら
今月=2026-06分(2606)・先月=2026-05分(2605)。resolve_target_months がこの対象月決定を担う。

分類ロジック (取引先×商品を突合し発行状態で分類):
  今月あり×前月あり → 継続発行 (正常)。全行 emit する (全請求書一覧を成す)。
  今月あり×前月なし → 新規/年→月切替 (12ヶ月前の年契約一括が月額切替した可能性を lookback で補強)。
  今月なし×前月あり → 正常な非請求事情 (年契約期間内 / トライアル完了 / 契約終了) の有無を
                    確認し、該当なしを発行漏れ候補(要対応)として分類する。
  今月なし×前月なし → 原則 対象外 (元々請求なし)。emit しない。ただし今月 curr が実 GAP
                    verdict の「継続漏れ」(前月も今月も未発行だが mfk_reconcile が今月を発行漏れ
                    と判定) は真の漏れなので要対応として残す (漏れを隠さない安全側)。
                    正常抑制 (SUPPRESS_* / 年契約 / 契約完了 / トライアル) や curr 不在は非 emit を維持。

正常事情の一次情報源 (自由文を再パースしない = SSOT 尊重):
  契約完了 : 既存 verdict SUPPRESS_ENDED を消費するのみ。C05 は確認内容/備考を再パースしない。
             構造化列『契約終了月』に値があっても、既存判定が REVIEW_ENDED_NO_BASIS
             (終了根拠 has_end_basis なし) なら抑制せず発行漏れ候補(要対応)として残す
             (mfk_reconcile の漏れ隠蔽防止 安全弁を保全)。
  年契約   : 既存 verdict SUPPRESS_ANNUAL / MATCH_ANNUAL を一次源にする。12ヶ月ルックバックは
             根拠コメント補強に限定し既存判定を上書きしない (precedence: 既存 verdict > 遡り推定)。
  トライアル: canon 前の生商品名 or MF 明細 desc を参照して判定する (shohin_canon の4値正規化後は
             『トライアル』信号が消えるため、正規化前の生名を見る)。

突合キーは既存 mfk_reconcile.normalize / extract_names を再利用して取引先名の表記揺れを吸収する
(自作正規化を発明しない)。最終分類とコメント根拠は取引先×商品単位で照合し、同一取引先・同一商品に
複数契約があるときのみ contract_id を disambiguator に使う。12ヶ月遡りは差分該当取引先のみに限定
(呼出側が --lookback-12mo に差分該当分だけを渡す前提。API 負荷最小化)。
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from collections import defaultdict

# 既存 lib を単一 SSOT として消費する (normalize/extract_names/ym_int を再利用)。
# CLI 単体起動でも lib を解決できるよう path を通す (pytest.ini は既に lib を pythonpath 済)。
_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(_HERE)
_LIB = os.path.join(_PLUGIN_ROOT, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import mfk_reconcile as R  # noqa: E402


# ============================================================================
# 発行状態の語彙 (SSOT)
# ============================================================================
# 発行状態遷移の 4 分類 (内部コード)。
STATE_CONTINUED = "continued"      # 今月あり×前月あり = 継続発行 (正常)
STATE_NEW = "new_or_switch"        # 今月あり×前月なし = 新規/年→月切替
STATE_STOPPED = "stopped"          # 今月なし×前月あり = 非請求事情確認 → 発行漏れ候補
STATE_NONE = "none"                # 今月なし×前月なし = 対象外 (非 emit)

# 『発行あり(有効な MF 請求が当月に存在)』を表す既存 verdict 集合。これらは MF 側に有効供給
# (billing/evidence) がある = その月に発行された。SUPPRESS_* / GAP / REVIEW_ENDED_NO_BASIS /
# REVIEW_CANCELED 等は発行なし。判定は既存 verdict を消費するのみ (再照合しない)。
ISSUED_VERDICTS = frozenset({
    "MATCH_MONTHLY", "MATCH_ANNUAL", "MATCH_ENDED_FINAL",
    "REVIEW_AMOUNT_TYPO", "REVIEW_AMOUNT_MISMATCH",
    "REVIEW_ENDED_BUT_BILLED", "REVIEW_QTY_MISMATCH",
})

# 年契約期間内の正常抑制 (前月あり今月なしの一次源)。既存判定を上書きしない。
ANNUAL_NORMAL_VERDICTS = frozenset({"SUPPRESS_ANNUAL", "MATCH_ANNUAL"})

# その他の SUPPRESS_* (ENDED/ANNUAL 以外) の人間可読ラベル。verdict-mapping SSOT が
# SUPPRESS_*→対象外 と定めるため、これらは再判定せず『対象外=正常』として消費する。
_SUPPRESS_LABELS = {
    "SUPPRESS_OFFMONTH": "対象外月 (契約開始前/分割対象外月/隔月非請求月)",
    "SUPPRESS_ONESHOT": "単発発行済 (当月は対象外)",
}

# gap_check の分類値 (漏れチェック checkbox の元ラベル: 正常=✓ / 要対応=☐)。
GAP_OK = "正常"
GAP_ACTION = "要対応"


# ============================================================================
# 行フィールド抽出 (入力 verdict 行の別名を吸収・int 化)
# ============================================================================
def _to_int(v):
    """金額/件数を tax-excluded int へ堅牢に coerce (再パースはしない・単純 int 化のみ)。"""
    if v in (None, ""):
        return None
    try:
        return int(float(str(v).replace(",", "").replace("，", "")))
    except (TypeError, ValueError):
        return None


def _first(row, keys):
    """row から keys の最初の非空値を返す (別名吸収)。"""
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return v
    return None


def _customer(row):
    """行の取引先名 (customer/取引先)。空なら確認内容から extract_names で最尤候補を拾う。"""
    if not row:
        return ""
    v = _first(row, ("customer", "取引先"))
    if v:
        return str(v)
    names = R.extract_names("", row.get("確認内容", "") or "")
    return names[0] if names else ""


def _product(row):
    """行の商品名 (product/商品)。突合キーの一部。"""
    if not row:
        return ""
    v = _first(row, ("product", "商品"))
    return str(v) if v else ""


def _contract_id(row):
    """行の契約ID (contract_id/契約ID)。同一取引先×同一商品の disambiguator。"""
    if not row:
        return None
    v = _first(row, ("contract_id", "契約ID"))
    return str(v) if v not in (None, "") else None


def _amount_of(row):
    """行の金額 (税抜 int)。期待単価を優先し evidence.amount へ fail-soft。"""
    if not row:
        return None
    for k in ("現行単価", "amount", "expected_amount", "金額", "単価"):
        iv = _to_int(row.get(k))
        if iv is not None:
            return iv
    ev = row.get("evidence")
    if isinstance(ev, dict):
        return _to_int(ev.get("amount"))
    return None


def _raw_product_text(row):
    """canon 前の生商品名 + 確認内容/備考 + MF明細 desc を連結 (トライアル信号の探索源)。"""
    if not row:
        return ""
    parts = []
    for k in ("商品生名", "product_raw", "raw_product", "商品", "product", "確認内容", "備考"):
        v = row.get(k)
        if v:
            parts.append(str(v))
    ev = row.get("evidence")
    if isinstance(ev, dict) and ev.get("desc"):
        parts.append(str(ev.get("desc")))
    return " ".join(parts)


def _is_trial(row):
    """トライアル信号を canon 前の生商品名 / MF明細 desc から検出する。"""
    return "トライアル" in _raw_product_text(row)


def _is_issued(row):
    """当月に有効な MF 請求が発行されたか (既存 verdict を消費するのみ)。

    verdict が ISSUED_VERDICTS か、evidence に正の金額があるか、明示 issued フラグが True。
    """
    if not row:
        return False
    if row.get("issued") is True:
        return True
    if row.get("verdict") in ISSUED_VERDICTS:
        return True
    ev = row.get("evidence")
    if isinstance(ev, dict) and _to_int(ev.get("amount")):
        return True
    return False


# ============================================================================
# 突合キー (取引先×商品・複数契約時のみ contract_id で disambiguate)
# ============================================================================
def _base_key(row):
    """取引先×商品の突合キー (mfk_reconcile.normalize で表記揺れを吸収)。"""
    return (R.normalize(_customer(row)), R.normalize(_product(row)))


def _needs_disambiguation(rows):
    """同一 (取引先,商品) に複数の異なる contract_id が存在する base key 集合を返す。

    その base key だけ contract_id を突合キーへ足して混同を防ぐ (それ以外は取引先×商品で突合し、
    片側に contract_id が無くても対応付く)。
    """
    groups = defaultdict(set)
    for r in rows:
        cid = _contract_id(r)
        if cid:
            groups[_base_key(r)].add(cid)
    return {k for k, ids in groups.items() if len(ids) > 1}


def _match_key(row, disambig):
    base = _base_key(row)
    if base in disambig:
        return base + (str(_contract_id(row) or ""),)
    return base


# ============================================================================
# compare_periods — 前月集合と今月集合を突合し 4 状態のペアリングを返す純関数
# ============================================================================
def compare_periods(prev_rows, curr_rows):
    """前月 verdict 行と今月 verdict 行を取引先×商品で突合し 4 状態へペアリングする純関数。

    返り値 = list[dict] (base key 昇順)。各要素:
      {"key", "prev", "curr", "prev_issued", "curr_issued", "state"}。
      state は STATE_CONTINUED / STATE_NEW / STATE_STOPPED / STATE_NONE。
    """
    prev_rows = prev_rows or []
    curr_rows = curr_rows or []
    disambig = _needs_disambiguation(list(prev_rows) + list(curr_rows))

    prev_map, curr_map = {}, {}
    for r in prev_rows:
        prev_map.setdefault(_match_key(r, disambig), r)
    for r in curr_rows:
        curr_map.setdefault(_match_key(r, disambig), r)

    pairing = []
    for key in sorted(set(prev_map) | set(curr_map)):
        prev = prev_map.get(key)
        curr = curr_map.get(key)
        prev_issued = _is_issued(prev)
        curr_issued = _is_issued(curr)
        if curr_issued and prev_issued:
            state = STATE_CONTINUED
        elif curr_issued and not prev_issued:
            state = STATE_NEW
        elif not curr_issued and prev_issued:
            state = STATE_STOPPED
        else:
            state = STATE_NONE
        pairing.append({
            "key": key, "prev": prev, "curr": curr,
            "prev_issued": prev_issued, "curr_issued": curr_issued,
            "state": state,
        })
    return pairing


# ============================================================================
# 12ヶ月履歴 / 契約終了月 のインデックス (差分該当取引先のみ・呼出側で絞る前提)
# ============================================================================
def _index_lookback(lookback):
    """12ヶ月履歴を normalize(取引先) → [record] へ畳む (dict/list 双方の入力形を吸収)。"""
    idx = defaultdict(list)
    if not lookback:
        return idx
    if isinstance(lookback, dict):
        records = None
        for k in ("records", "history", "items"):
            if isinstance(lookback.get(k), list):
                records = lookback[k]
                break
        if records is not None:
            for rec in records:
                idx[R.normalize(rec.get("customer") or rec.get("取引先") or "")].append(rec)
        else:
            for cust, recs in lookback.items():
                for rec in (recs or []):
                    idx[R.normalize(cust)].append(rec)
    elif isinstance(lookback, list):
        for rec in lookback:
            idx[R.normalize(rec.get("customer") or rec.get("取引先") or "")].append(rec)
    return idx


def _rec_is_annual(rec):
    """12ヶ月履歴レコードが年契約一括発行か (annual フラグ or MATCH_ANNUAL verdict)。"""
    if not isinstance(rec, dict):
        return False
    if rec.get("annual") or rec.get("annual_lump"):
        return True
    return rec.get("verdict") == "MATCH_ANNUAL"


def _rec_month(rec):
    return str(rec.get("month") or rec.get("month_ym") or rec.get("target_month") or "")


def _index_contract_end(contract_end):
    """契約終了月データを base key → 終了月(YYMM) へ畳む (二次情報・cross-check 用)。"""
    idx = {}
    if not contract_end:
        return idx
    items = contract_end
    if isinstance(contract_end, dict):
        for k in ("records", "items", "contracts"):
            if isinstance(contract_end.get(k), list):
                items = contract_end[k]
                break
        else:
            # {customer: end_month} 形も許容 (product 無しは商品空キー)。
            for cust, end in contract_end.items():
                idx[(R.normalize(cust), R.normalize(""))] = str(end)
            return idx
    if isinstance(items, list):
        for rec in items:
            if not isinstance(rec, dict):
                continue
            end = rec.get("end_month") or rec.get("契約終了月")
            if not end:
                continue
            idx[_base_key(rec)] = str(end)
    return idx


def _end_month_for(prev, curr, end_idx):
    """行の契約終了月 (構造化列) を取得する。行の値 → contract_end データの順で解決。"""
    for r in (curr, prev):
        if r:
            v = r.get("契約終了月") or r.get("end_month")
            if v:
                return str(v)
    for r in (curr, prev):
        if r:
            k = _base_key(r)
            if k in end_idx:
                return end_idx[k]
    return None


# ============================================================================
# 対象月決定 (直近締め済みの請求対象月)
# ============================================================================
def _prev_month_ym(ym):
    """YYMM → 1ヶ月前の YYMM。不正は None。"""
    m = re.fullmatch(r"(\d{2})(\d{2})", str(ym or ""))
    if not m:
        return None
    yy, mm = int(m.group(1)), int(m.group(2))
    if mm == 1:
        yy, mm = yy - 1, 12
    else:
        mm -= 1
    return f"{yy:02d}{mm:02d}"


def _prev_year_month(ym):
    """YYMM → 12ヶ月前 (同月・前年) の YYMM。年→月切替の裏付け探索に使う。不正は None。"""
    m = re.fullmatch(r"(\d{2})(\d{2})", str(ym or ""))
    if not m:
        return None
    return f"{int(m.group(1)) - 1:02d}{m.group(2)}"


def resolve_target_months(today=None):
    """実行日から (今月=直近締め済みの請求対象月, 先月) を YYMM で返す。

    今月 = 実行日カレンダー月の前月 (直近で締め済みの請求対象月)。例: 2026-07-02 実行 →
    今月=2606 (2026-06分)・先月=2605 (2026-05分)。
    """
    d = today or datetime.date.today()
    y, mo = d.year, d.month
    if mo == 1:
        cy, cm = y - 1, 12
    else:
        cy, cm = y, mo - 1
    curr = f"{cy % 100:02d}{cm:02d}"
    return curr, _prev_month_ym(curr)


# ============================================================================
# classify_period_transition — ペアリング + 既存 verdict + 12ヶ月履歴から各行を決定する純関数
# ============================================================================
def _emit(customer, amount, prev_amount, gap_check, period_diff,
          product, comment, contract_id, target_month):
    return {
        "customer": customer,
        "amount": amount,
        "prev_amount": prev_amount,
        "gap_check": gap_check,
        "period_diff": period_diff,
        "product": product,
        "comment": comment,
        "contract_id": contract_id,
        "target_month": target_month,
    }


def _continued_comment(curr, prev):
    ca, pa = _amount_of(curr), _amount_of(prev)
    if ca is not None and pa is not None and ca != pa:
        base = f"継続発行 (金額変動: 先月{pa:,}円→今月{ca:,}円)"
    else:
        base = "継続発行 (前月・今月とも発行あり)"
    # 継続発行でも当月 verdict が REVIEW_* (金額差/過剰請求/数量差/終了後請求等) なら、
    # 発行漏れではないが reconcile 側の要確認事項ゆえコメントに surface する (継続扱いで
    # 不可視化しない)。gap_check は発行漏れ判定なので正常のまま (漏れではない)。
    verdict = (curr or {}).get("verdict")
    if verdict and str(verdict).startswith("REVIEW_"):
        base += f" / 要確認: 上流 verdict={verdict} (金額差/過剰請求等・単月照合 reconcile で確認)"
    return base


def _annual_lookback_note(row, lookback_idx):
    """年契約期間内の根拠コメント補強 (既存判定は上書きしない・補強のみ)。"""
    recs = lookback_idx.get(R.normalize(_customer(row))) or []
    for rec in recs:
        if _rec_is_annual(rec):
            m = _rec_month(rec)
            return f"12ヶ月履歴に年契約一括発行あり({m})=年契約周期内 (遡りは補強・既存verdict優先)"
    return ""


def _new_comment(row, lookback_idx, target_month, lookback_available=True):
    """新規/年→月切替のコメント。12ヶ月前の年契約一括発行を裏付けに年→月切替を推定 (補強)。

    lookback_available=False (12ヶ月ルックバックが未実行=--lookback-12mo 未指定) のときは、
    「12ヶ月確認したが年契約なし=真の新規」と「そもそも確認していない=未確認」を silent に
    同一視せず、**未確認である旨を明示**する。前月なし今月ありは年契約→月額切替の可能性が高い
    (ユーザー要件 C3) ため、確認できていない事実を隠して『新規発行』と断定しない。
    """
    recs = lookback_idx.get(R.normalize(_customer(row))) or []
    switch_month = _prev_year_month(target_month) if target_month else None
    for rec in recs:
        if _rec_is_annual(rec) and (switch_month is None or _rec_month(rec) == switch_month):
            return (f"12ヶ月前({_rec_month(rec)})に年契約一括発行→自動で月額切替した可能性 "
                    "(年→月切替・12ヶ月履歴で確認済み)")
    for rec in recs:
        if _rec_is_annual(rec):
            return (f"12ヶ月履歴に年契約一括発行あり({_rec_month(rec)})→年→月切替の可能性 "
                    "(12ヶ月履歴で確認済み)")
    if not lookback_available:
        # ルックバック自体が未実行 (--lookback-12mo 未指定 or 空データ)。年→月切替か真の新規かを
        # 未確認のまま『新規発行』と断定しない (確実性の開示)。データ源は MF 実績の12ヶ月履歴であり
        # 請求確認シートの開始月には依存しない。
        return ("⚠️ 12ヶ月ルックバック未実行 (12ヶ月履歴データなし)→年契約からの月額切替か"
                "真の新規発行か未確認。MF実績の12ヶ月履歴を渡して再実行し裏付けを取ること")
    # ルックバックは実行したが当該取引先に年契約一括の履歴なし=真の新規発行と確認できた。
    return "新規発行 (12ヶ月履歴を確認したが年契約一括の裏付けなし=真の新規)"


def _classify_stopped(prev, curr, lookback_idx, end_idx, target_month):
    """今月なし×前月ありの非請求事情を既存 verdict を一次源に分類する。

    返り値 = (gap_check, period_diff, comment)。
    自由文の終了根拠は再パースせず、既存 verdict (SUPPRESS_ENDED / REVIEW_ENDED_NO_BASIS /
    SUPPRESS_ANNUAL / MATCH_ANNUAL) を消費するのみ。契約終了月 (構造化列) は二次情報。
    """
    verdict = (curr or {}).get("verdict")
    end_month = _end_month_for(prev, curr, end_idx)

    # ① 契約完了 (終了根拠あり) = 既存 verdict SUPPRESS_ENDED を消費するのみ。
    if verdict == "SUPPRESS_ENDED":
        comment = "契約完了 (終了根拠あり・既存 verdict SUPPRESS_ENDED を消費)"
        if end_month:
            comment += f" 契約終了月={end_month}"
        return GAP_OK, "前月あり今月なし (契約完了)", comment

    # ② 根拠なき終了月 = 既存 verdict REVIEW_ENDED_NO_BASIS。安全弁: 抑制せず発行漏れ候補に残す。
    #    構造化列『契約終了月』に値があっても has_end_basis 根拠が無ければ漏れ隠蔽を防ぐため要対応。
    if verdict == "REVIEW_ENDED_NO_BASIS":
        if end_month:
            comment = (f"契約終了月={end_month} だが終了根拠なし (REVIEW_ENDED_NO_BASIS)"
                       "→継続契約の発行漏れの可能性・要対応")
        else:
            comment = ("終了根拠なし (REVIEW_ENDED_NO_BASIS)→継続契約の発行漏れの可能性・要対応")
        return GAP_ACTION, "前月あり今月なし (根拠なき終了月)", comment

    # ③ 年契約期間内 = 既存 verdict SUPPRESS_ANNUAL / MATCH_ANNUAL を一次源 (12ヶ月遡りは補強のみ)。
    if verdict in ANNUAL_NORMAL_VERDICTS:
        comment = f"年契約期間内 (既存 verdict {verdict} を一次源)"
        note = _annual_lookback_note(prev or curr, lookback_idx)
        if note:
            comment += " / " + note
        return GAP_OK, "前月あり今月なし (年契約周期)", comment

    # ④ トライアル完了 = canon 前の生商品名 / MF明細 desc の『トライアル』信号で判定。
    if _is_trial(prev) or _is_trial(curr):
        return GAP_OK, "前月あり今月なし (トライアル完了)", \
            "トライアル完了 (canon 前の生商品名/MF明細descで判定・正規化後は信号が消えるため)"

    # ⑤ その他の SUPPRESS_* (OFFMONTH=隔月/分割の対象外月・契約開始前 / ONESHOT=単発発行済 等)
    #    は reconcile が既に正常抑制と判定した『対象外』(verdict-mapping SSOT: SUPPRESS_*→対象外)。
    #    C05 はこの既存判定を消費するのみで再判定しない (再判定は SSOT 違反かつ隔月/単発契約の
    #    非請求月を偽陽性で漏れ扱いにする)。
    if verdict and str(verdict).startswith("SUPPRESS_"):
        label = _SUPPRESS_LABELS.get(verdict, "正常抑制 (対象外)")
        return GAP_OK, "前月あり今月なし (対象外)", \
            f"{label} (既存 verdict {verdict} を消費・対象外=正常)"

    # ⑥ 正常な非請求事情に該当せず (SUPPRESS_* でも年契約/契約終了でもトライアルでもない)
    #    → 発行漏れ候補 (要対応)。GAP verdict や verdict 欠落・REVIEW_* 等はここへ落ちる。
    tail = f" (既存 verdict {verdict})" if verdict else ""
    return GAP_ACTION, "前月あり今月なし (発行漏れ候補)", \
        "正常な非請求事情 (年契約/トライアル/契約終了/対象外抑制) に該当せず→発行漏れ候補・要対応" + tail


def _classify_continuing(pair, lookback_idx, end_idx, target_month):
    """STATE_NONE (両月未発行) のうち今月 curr が真の発行漏れ (継続漏れ) なら要対応行を返す。

    curr の既存 verdict を _classify_stopped と同じ SSOT で評価し、GAP_ACTION (年契約/契約完了/
    トライアル/SUPPRESS_* のいずれにも該当しない発行漏れ) のときだけ emit する。正常抑制や
    curr 不在 (元々請求なし=対象外) は None を返し従来どおり非 emit を維持する (漏れを隠さない
    が対象外を過剰報告もしない安全側)。
    """
    curr = pair.get("curr")
    if curr is None:
        return None  # 今月の verdict 行が無い = 元々請求なし (対象外)。
    prev = pair.get("prev")
    gap_check, _period, _comment = _classify_stopped(
        prev, curr, lookback_idx, end_idx, target_month)
    if gap_check != GAP_ACTION:
        return None  # 正常抑制 (年契約/契約完了/トライアル/対象外) は非 emit を維持。
    customer = _customer(curr)
    product = _product(curr)
    contract_id = _contract_id(curr) or _contract_id(prev)
    comment = ("継続発行漏れ (前月も今月も未発行・今月 verdict が発行漏れ)"
               "→継続契約の請求漏れの可能性・要対応 (単月照合と整合)")
    return _emit(customer, _amount_of(curr), _amount_of(prev), GAP_ACTION,
                 "継続 (前月も今月も未発行)", product, comment, contract_id, target_month)


def classify_period_transition(pairing, lookback=None, contract_end=None, target_month=None):
    """ペアリング + 既存 verdict + 12ヶ月履歴 から各行の period_diff/gap_check/comment を決定する純関数。

    STATE_NONE (今月なし×前月なし) は原則 emit しないが、今月 curr が実 GAP verdict の継続漏れ
    なら要対応として emit する (_classify_continuing)。継続発行は全行 emit する。
    返り値 = list[dict] (I/O 契約のレポート行)。
    """
    lookback_idx = _index_lookback(lookback)
    # 12ヶ月ルックバックのデータが 1 件でも渡されたか (未指定=未実行を STATE_NEW コメントで可視化する)。
    lookback_available = bool(lookback)
    end_idx = _index_contract_end(contract_end)
    out = []
    for pair in pairing:
        state = pair["state"]
        if state == STATE_NONE:
            # 原則 非 emit (元々請求なし=対象外)。ただし今月 curr が実 GAP verdict の継続漏れは
            # 真の漏れなので要対応として残す (5状態目=継続漏れ・漏れを隠さない)。
            row = _classify_continuing(pair, lookback_idx, end_idx, target_month)
            if row is not None:
                out.append(row)
            continue

        curr, prev = pair["curr"], pair["prev"]
        rep = curr or prev
        customer = _customer(rep)
        product = _product(rep)
        contract_id = _contract_id(curr) or _contract_id(prev)
        amount = _amount_of(curr)
        prev_amount = _amount_of(prev)

        if state == STATE_CONTINUED:
            row = _emit(customer, amount, prev_amount, GAP_OK, "継続発行",
                        product, _continued_comment(curr, prev), contract_id, target_month)
        elif state == STATE_NEW:
            comment = _new_comment(rep, lookback_idx, target_month, lookback_available)
            row = _emit(customer, amount, prev_amount, GAP_OK, "新規/年→月切替",
                        product, comment, contract_id, target_month)
        else:  # STATE_STOPPED
            gap_check, period_diff, comment = _classify_stopped(
                prev, curr, lookback_idx, end_idx, target_month)
            row = _emit(customer, amount, prev_amount, gap_check, period_diff,
                        product, comment, contract_id, target_month)
        out.append(row)
    return out


# ============================================================================
# I/O (argv → JSON 読込 → 分類 → stdout。副作用なし・network なし)
# ============================================================================
def _load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _rows_of(doc):
    """per-月 verdict JSON から行 list を取り出す (list そのもの or {rows/verdicts/...:[...]})。"""
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    if isinstance(doc, dict):
        for k in ("rows", "verdicts", "records", "items"):
            if isinstance(doc.get(k), list):
                return [r for r in doc[k] if isinstance(r, dict)]
    return []


def _target_of(doc, fallback):
    if isinstance(doc, dict):
        for k in ("target_month", "target_ym", "target"):
            v = doc.get(k)
            if v:
                return str(v)
    return fallback


def build_report(curr_doc, prev_doc, lookback=None, contract_end=None, target_month=None):
    """パース済みドキュメントからレポート行 list を組み立てる (I/O なしの純ロジック纏め)。"""
    curr_rows = _rows_of(curr_doc)
    prev_rows = _rows_of(prev_doc)
    if not target_month:
        target_month = _target_of(curr_doc, None) or resolve_target_months()[0]
    pairing = compare_periods(prev_rows, curr_rows)
    return classify_period_transition(
        pairing, lookback=lookback, contract_end=contract_end, target_month=target_month)


def main(argv=None):
    p = argparse.ArgumentParser(
        description="前月↔今月の発行状態遷移分類 (既存 per-月 verdict を消費する薄い差分エンジン)")
    p.add_argument("--curr-verdicts", dest="curr_verdicts", required=True,
                   help="今月=target 請求対象月の per-月 verdict JSON")
    p.add_argument("--prev-verdicts", dest="prev_verdicts", required=True,
                   help="先月=target-1ヶ月の per-月 verdict JSON")
    p.add_argument("--lookback-12mo", dest="lookback",
                   help="差分該当取引先のみの12ヶ月発行履歴 JSON (任意)")
    p.add_argument("--contract-end", dest="contract_end",
                   help="契約終了月データ JSON (任意・二次情報)")
    p.add_argument("--target-month", dest="target_month",
                   help="対象月 YYMM (省略時は curr-verdicts の target_month→実行日から導出)")
    a = p.parse_args(argv)

    try:
        curr_doc = _load_json(a.curr_verdicts)
        prev_doc = _load_json(a.prev_verdicts)
    except (OSError, ValueError) as e:
        sys.stderr.write(f"[period-report] verdict 入力の読込に失敗 (fail-closed): {e}\n")
        return 2

    lookback = None
    if a.lookback:
        try:
            lookback = _load_json(a.lookback)
        except (OSError, ValueError) as e:
            sys.stderr.write(f"[period-report] 12ヶ月履歴の読込に失敗 (fail-closed): {e}\n")
            return 2

    contract_end = None
    if a.contract_end:
        try:
            contract_end = _load_json(a.contract_end)
        except (OSError, ValueError) as e:
            sys.stderr.write(f"[period-report] 契約終了月データの読込に失敗 (fail-closed): {e}\n")
            return 2

    report = build_report(curr_doc, prev_doc, lookback=lookback,
                          contract_end=contract_end, target_month=a.target_month)

    # 12ヶ月ルックバック未実行の可視化 (ユーザー要件 C2/C3): --lookback-12mo 未指定のまま
    # 前月なし今月あり (新規/年→月切替) 行があると、年契約→月額切替の裏付けが未確認になる。
    # データ源は MF 実績の12ヶ月履歴であり請求確認シートの開始月には依存しない (源の取り違え防止)。
    # lookback は未指定 (a.lookback なし=None) でも空ファイル ([]/{}) でも「実質未実行」として
    # 一貫して警告する (loaded content の真偽で判定・空データ縁ケースの取りこぼしを防ぐ)。
    new_rows = sum(1 for r in report if r.get("period_diff") == "新規/年→月切替")
    if not lookback and new_rows:
        sys.stderr.write(
            f"[period-report] ⚠️ 12ヶ月履歴データなし (--lookback-12mo 未指定 or 空) のまま 前月なし今月あり "
            f"{new_rows} 件を分類しました。これらの『年契約→月額切替』裏付けは未確認です。MF実績(GET)の"
            "12ヶ月履歴を --lookback-12mo に渡して再実行してください (シート開始月とは無関係=省略しない)。\n")

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if any(r.get("gap_check") == GAP_ACTION for r in report):
        return 1  # 分類上の要確認 (発行漏れ候補) あり。
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
