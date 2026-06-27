#!/usr/bin/env python3
"""MF掛け払い 発行整合チェック engine (双方向照合・純関数)。

DB1 契約マスタ(当月期待集合)と MF掛け払いの発行実績(参照専用GETで取得済み)を
突合し、各契約×当月の判定(verdict)を返す。さらに逆方向で「MF実績にあり当月マスタに
名寄せできない顧客」を orphan として検出する。

副作用なし・ネットワークなし・I/O なし(verdict-mapping.json の読込だけは SSOT 解決の
ため許容、fail-soft)。pytest で単体テストする (tests/test_mfk_reconcile.py)。
scratchpad/reconcile.py を移植しつつ確定設計(design wi22zpkq2)と buildspec の設計修正
F1/E1/B1/H1/K1/J1 を反映した。

確定仕様(絶対遵守):
  - 年周期 = ANNUAL_MONTHS=12 固定。支払サイクルは契約ごとに DB1『支払サイクル』列で
    明示する(キーワード推測 annual_signal は撤去 = SSOT 一本化)。MECE6値+従量:
    月払い/年間払い/年間一括更新/単発/分割/隔月/従量(都度)。
  - 年間払い(case b): 初年度のみ一括→翌年月額(既存 billing_lifecycle 互換)。
  - 年間一括更新(case a): 毎年更新で再一括(ThinkTank型, elapsed%12==0 で lump)。
  - MF API は参照専用。人間対応済み(=チェック済み)は AI 不可触(本 engine は判定のみ)。

評価順序(classify):
  ① ステータス=保留 → REVIEW_PENDING として行を生成し、確認ポイントへ理由を出す。
  ② 契約終了月 end & T>=end または ステータス=終了 → MF実績なしなら SUPPRESS_ENDED。
     終了月〜終了月+1 の MF実績は MATCH_ENDED_FINAL、終了月+2 以降は REVIEW_ENDED_BUT_BILLED。
  ③ 支払サイクル別展開(K1: 人手設定の列を最優先)。

設計修正の反映箇所(関数 docstring にも個別タグ):
  F1(数量差)  : DB1『期待明細数』を Σ し契約ID境界で MF供給件数と比較 → quantity_downgrade
  E1(年間保留): 年間払い/年間一括更新 & elapsed==0 & lump未検出 → REVIEW_ANNUAL_BILLING_MONTH
                (GAP に落とさない) → _classify_annual / _classify_annual_renewal
  B1(金額差)  : 名寄せMF供給ありで金額のみ不一致 → REVIEW_AMOUNT_MISMATCH、GAP は供給皆無に限定
                → find_mf_match / _classify_monthly_expected
  H1(従量)    : 従量(都度) → REVIEW_METERED(常に要確認) → classify
  K1(優先順位): 支払サイクル列が最優先。人手設定の非月払い&開始日空欄 → REVIEW_DATA_INCOMPLETE。
                支払サイクル列も空欄なら月払いfallback → _resolve_cycle / classify
  J1(名寄せ)  : MF顧客ID優先→fallback(金額+エンドクライアント名NFKC, 取引先境界で供給限定)、
                証跡の取引先不一致は MATCH 扱いせず → find_mf_match 単一入口、全経路が経由
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter, defaultdict

# 既存 SSOT(byte一致維持)からサイクル定数とサイクル別 active 判定を取り込む。
# 月払い/年間払いラベル・ANNUAL_MONTHS・billing_lifecycle は run-mf-invoice-check の
# 年間抑制回帰を壊さないよう mfk_invoice_diff 側を唯一の定義元とする(ここで再定義しない)。
from mfk_invoice_diff import (  # noqa: F401  (定数は再エクスポートして利用側の単一import点にする)
    ANNUAL_MONTHS,
    CADENCE_ANNUAL,
    CADENCE_ANNUAL_RENEWAL,
    CADENCE_BIMONTHLY,
    CADENCE_METERED,
    CADENCE_MONTHLY,
    CADENCE_ONESHOT,
    CADENCE_SPLIT,
    annual_renewal_period,
    bimonthly_active,
    oneshot_active,
    split_active,
)

# 非月払いサイクル(契約開始日 elapsed を必須とする): 開始日空欄なら K1 でデータ不備。
# 従量は期待額が件数依存で常に REVIEW のため elapsed 不要 → ここには含めない。
NON_MONTHLY_CYCLES = frozenset(
    {CADENCE_ANNUAL, CADENCE_ANNUAL_RENEWAL, CADENCE_ONESHOT, CADENCE_SPLIT, CADENCE_BIMONTHLY}
)

# F1 数量差降格(quantity_downgrade)の対象 verdict。月次の当月期待は契約ID境界で
# Σ期待明細数 vs MF供給件数を比較できるが、年額一括(MATCH_ANNUAL)は qty12 等の
# 単一一括明細で『当月の月次件数』概念を持たず、_expected_amounts(月額)も空になり
# 供給0と誤判定して MATCH_ANNUAL を不当降格する。よって月次のみを対象にする
# (実証エンジン reconcile.py も MATCH_MONTHLY のみを数量降格対象としていた)。
_MATCH_VERDICTS = frozenset({"MATCH_MONTHLY"})

# 年間 lump 検出のしきい値(年額一括らしさ)。design の match_annual_lump を踏襲。
_ANNUAL_LUMP_QTY = 10
_ANNUAL_LUMP_AMOUNT = 900000
_ANNUAL_LUMP_CATEGORIES = ("thinktank", "riyo", "init")


# ============================================================================
# 判定語彙 SSOT (verdict-mapping.json) — ハードコードせず単一JSONから派生
# ============================================================================
VERDICT_MAPPING_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "skills",
    "run-mf-invoice-reconcile",
    "schemas",
    "verdict-mapping.json",
)

_VERDICT_CACHE = None


def load_verdict_mapping(path=None):
    """verdict-mapping.json を {internal_verdict: {judge_label, ai_check, warning_class}} で返す。

    SSOT は schemas/verdict-mapping.json(engine と sink が双方これを参照)。CHECK_VERDICTS や
    判定select options はここから派生し、別ファイルへ二重定義しない。読込失敗時は空dictを
    返す fail-soft(import 自体は決して落とさない)。明示 path 指定時はキャッシュしない。
    """
    global _VERDICT_CACHE
    if path is None and _VERDICT_CACHE is not None:
        return _VERDICT_CACHE
    target = path or VERDICT_MAPPING_PATH
    try:
        with open(target, encoding="utf-8") as fh:
            doc = json.load(fh)
        out = {}
        for m in doc.get("mappings", []):
            key = m.get("internal_verdict")
            if key:
                out[key] = {
                    "judge_label": m.get("judge_label", key),
                    "ai_check": bool(m.get("ai_check", False)),
                    "warning_class": m.get("warning_class", "なし"),
                    # 請求確認シート『判定』selectへ片方向ミラーする5値投影(SSOT)。
                    # ORPHAN はシート行が無いため null。キー欠落も None で fail-soft。
                    "sheet_label": m.get("sheet_label"),
                    # 請求確認シート『確認ポイント』へ書く『何を確認すべきか』定型ガイダンス
                    # (確認OK/対象外は空文字)。行固有の警告は書き戻し層で連結する。
                    "action_hint": m.get("action_hint", ""),
                }
    except (OSError, ValueError):
        out = {}
    if path is None:
        _VERDICT_CACHE = out
    return out


def judge_label(verdict, mapping=None):
    """internal_verdict → DB2『判定』日本語ラベル。未定義は verdict 文字列をそのまま返す。"""
    mp = mapping if mapping is not None else load_verdict_mapping()
    return mp.get(verdict, {}).get("judge_label", verdict)


def warning_class(verdict, mapping=None):
    """internal_verdict → 警告クラス(重大>警告>情報>なし)。"""
    mp = mapping if mapping is not None else load_verdict_mapping()
    return mp.get(verdict, {}).get("warning_class", "なし")


def sheet_label(verdict, mapping=None):
    """internal_verdict → 請求確認シート『判定』selectの5値(AIの確認OK/対象外/要確認/発行漏れ)。

    ORPHAN(逆方向・シート行なし)や未定義は None を返し、書き戻し側で投影スキップする。
    DB2『判定』(judge_label・15値)とは別軸の5値投影で、SSOT は verdict-mapping.json の sheet_label。
    """
    mp = mapping if mapping is not None else load_verdict_mapping()
    return mp.get(verdict, {}).get("sheet_label")


def action_hint(verdict, mapping=None):
    """internal_verdict → 請求確認シート『確認ポイント』の定型ガイダンス(何を確認すべきか)。

    確認OK/対象外 (MATCH_*/SUPPRESS_*) は空文字。SSOT は verdict-mapping.json の action_hint。
    行固有の警告詳細 (数量差の想定漏れ額・データ不備の理由等) は書き戻し層で連結する。
    """
    mp = mapping if mapping is not None else load_verdict_mapping()
    return mp.get(verdict, {}).get("action_hint", "")


def is_check_verdict(verdict, mapping=None):
    """ai_check:true(AI が ✓ を付けてよい verdict)か。"""
    mp = mapping if mapping is not None else load_verdict_mapping()
    return mp.get(verdict, {}).get("ai_check", False)


def check_verdicts(mapping=None):
    """ai_check:true の internal_verdict 集合(CHECK_VERDICTS を派生)。"""
    mp = mapping if mapping is not None else load_verdict_mapping()
    return frozenset(k for k, v in mp.items() if v.get("ai_check"))


# import 時に派生(SSOT 由来・ハードコードしない)。読込失敗時は空集合 fail-soft。
CHECK_VERDICTS = check_verdicts()


# ============================================================================
# 正規化・抽出 (scratchpad/reconcile.py から移植)
# ============================================================================
_CORP = [
    "株式会社", "有限会社", "合同会社", "有限責任事業組合", "弁護士法人",
    "医療法人", "一般社団法人", "(株)", "(有)", "（株）", "（有）",
]


def normalize(s):
    """NFKC 正規化 + 敬称/法人格/空白/中黒除去 + lower。名寄せの基準文字列。

    NFKC で濁点/半濁点の合成・全角半角・互換文字を吸収する(macOS/MF API 由来のカタカナは
    NFD のことがあり見た目同一でも != になる罠を防ぐ)。
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = s.replace("様", "").replace("　", "").replace(" ", "")
    s = s.replace("・", "").replace("／", "/")
    for c in _CORP:
        s = s.replace(c, "")
    return s.strip().lower()


def parse_amounts(text):
    """確認内容から金額(円)候補を返す。返り値 = (primary, typo_candidates)。

    primary          : 『NNN,NNN円』として読めた値。
    typo_candidates  : 区切り桁異常(例 50,0000=500000)で /10 した typo 候補(50000)。
                       原 reconcile は primary に混ぜていたが、MATCH と REVIEW_AMOUNT_TYPO を
                       区別できるよう分離する(混ぜると typo が常に MATCH に化け分岐が死ぬ)。
    """
    primary, typo = [], []
    for m in re.finditer(r"([0-9０-９][0-9０-９,，]*)\s*円", text or ""):
        raw = m.group(1).replace(",", "").replace("，", "")
        for z, h in zip("０１２３４５６７８９", "0123456789"):
            raw = raw.replace(z, h)
        if not raw.isdigit():
            continue
        v = int(raw)
        primary.append(v)
        # 50,0000 のような区切り桁異常: 直前カンマ後が4桁
        seg = m.group(1).split(",")[-1].split("，")[-1]
        if len(seg) >= 4 and v >= 100000 and v % 10 == 0:
            typo.append(v // 10)
    return primary, typo


def extract_names(torihiki, kakunin):
    """取引先 + 確認内容内の人名/企業名 候補(正規化前文字列)を返す。"""
    names = [torihiki] if torihiki else []
    text = kakunin or ""
    # 企業名(接尾/接頭)
    for m in re.finditer(r"([^\s　：:、]{1,12}(?:株式会社|合同会社|有限会社|有限責任事業組合))", text):
        names.append(m.group(1))
    for m in re.finditer(r"((?:株式会社|合同会社|有限会社)[^\s　：:、0-9]{1,12})", text):
        names.append(m.group(1))
    # 金額の直後〜stopword 手前を名前候補に(人名想定)
    m = re.search(r"[0-9０-９][0-9０-９,，]*\s*円(?:/件|／件)?\s*(.+)", text)
    if m:
        tail = m.group(1)
        tail = re.split(r"(更新|契約更新|契約期間|期間|請求なし|https?|→|2[0-9]{3}〜)", tail)[0]
        tail = tail.strip(" 　:：")
        if tail and len(tail) <= 20:
            names.append(tail)
    # 重複除去
    seen, uniq = set(), []
    for n in names:
        nn = normalize(n)
        if nn and nn not in seen:
            seen.add(nn)
            uniq.append(n)
    return uniq


def mf_paren_name(desc):
    """MF明細 desc 中の『（NAME様…）』のエンドクライアント名を返す。無ければ None。"""
    m = re.search(r"（(.+?)様", desc or "")
    if m:
        return m.group(1)
    m = re.search(r"\((.+?)様", desc or "")
    return m.group(1) if m else None


def category(text):
    """明細/商品テキストを補助カテゴリへ分類(年間 lump 検出と立替除外に使用)。"""
    t = text or ""
    if "立替" in t:
        return "tatekae"
    if "業務委託" in t:
        return "biz"
    if "初期導入" in t or "初期費用" in t:
        return "init"
    if "トライアル" in t:
        return "trial"
    if "ThinkTank" in t or "100億" in t:
        return "thinktank"
    if "チイキズカン" in t and ("利用料" in t or "サービス利用" in t):
        return "riyo"
    if "講座" in t or "研修" in t:
        return "training"
    if "利用料" in t:
        return "riyo"
    return "other"


def _expected_categories(contract):
    """契約の商品/確認内容から MF 明細 category の期待集合を返す。

    金額だけで同一会社内の別商品を拾うと、ユーザーが求める「商品名/確認内容が含まれるか」
    の検証にならない。既存の category() 語彙を使い、商品列と確認内容から期待カテゴリを
    導出して候補明細を絞る。未知カテゴリは空集合にして従来の会社+金額照合へ fail-soft。
    """
    text = " ".join(str(contract.get(k) or "") for k in ("商品", "確認内容", "備考"))
    cats = set()
    if "業務委託" in text:
        cats.add("biz")
    if "ThinkTank" in text or "100億" in text:
        cats.add("thinktank")
    if "チイキズカン" in text and ("利用料" in text or "サービス利用" in text):
        cats.add("riyo")
    if "初期導入" in text or "初期費用" in text:
        cats.add("init")
    if "講座" in text or "研修" in text:
        cats.add("training")
    return cats


# ============================================================================
# 日付 (月粒度・day破棄。既存 billing_lifecycle と一致)
# ============================================================================
def ym_int(s):
    """YYMM(2606) / YYYY-MM / YYYY-MM-DD を月通し番号(年*12+月)へ。不正は None。"""
    if not s:
        return None
    s = str(s).strip()
    m = re.fullmatch(r"(\d{2})(\d{2})", s)
    if m:
        y, mo = 2000 + int(m.group(1)), int(m.group(2))
        return y * 12 + (mo - 1) if 1 <= mo <= 12 else None
    m = re.match(r"(\d{4})-(\d{1,2})", s)  # YYYY-MM / YYYY-MM-DD の先頭を許容
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        return y * 12 + (mo - 1) if 1 <= mo <= 12 else None
    return None


def months_elapsed(start, target_ym):
    """契約開始日(YYMM/YYYY-MM/YYYY-MM-DD)から対象月までの経過月数。不正なら None。

    I1: 日付は月粒度(day破棄)。丸1年-1日は月粒度へ縮約され既存 billing_lifecycle と一致する。
    """
    a, b = ym_int(start), ym_int(target_ym)
    if a is None or b is None:
        return None
    return b - a


def _int(v):
    """金額/件数を int 化。None/空/カンマ/float文字列に堅牢。不可なら None。"""
    if v in (None, ""):
        return None
    try:
        return int(float(str(v).replace(",", "").replace("，", "")))
    except (TypeError, ValueError):
        return None


def _dedup(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ============================================================================
# MF インデックス (行二重化 dedup・立替/負額/0円 除外)
# ============================================================================
def build_mf_index(mf):
    """MF JSON を {customer_id: {cust, names, services}} へ。

    - billing_id+desc+amount で API二重化(同一明細の重複出現)を dedup。
    - 立替(tatekae)・負額(値引)・0円明細は services から除外(=不課税/相殺分は判定対象外)。
    - names は会社名 + 明細括弧内エンドクライアント名(NFKC)。company 境界判定は cust(会社名)を使う。
    """
    idx = {}
    for cid, c in mf["customers"].items():
        cust = c.get("name") or cid
        seen = set()
        services = []
        names = {normalize(cust)}
        for ln in c.get("lines", []):
            amt = ln.get("amount")
            desc = ln.get("desc") or ""
            cat = category(desc)
            pn = mf_paren_name(desc)
            if pn:
                names.add(normalize(pn))
            if amt is None or amt <= 0 or cat == "tatekae":
                continue
            key = (ln.get("billing_id"), desc, amt)  # API二重化を畳む
            if key in seen:
                continue
            seen.add(key)
            services.append({
                "amount": amt, "unit_price": ln.get("unit_price"),
                "qty": ln.get("qty"), "category": cat, "desc": desc,
                "paren": pn, "billing_id": ln.get("billing_id"),
            })
        idx[cid] = {"cust": cust, "names": names, "services": services}
    return idx


def _company_match(tnorm, cust_norm):
    """会社名(取引先 ↔ MF顧客名)の境界一致(完全一致 or 3文字以上の包含)。

    人名(エンドクライアント名)ではなく会社名のみで境界を決める。これが J1 偽陰性封鎖の核:
    name-global 一致(人名で他社請求に誤接続)を構造的に排除する。

    包含一致は短名の偶発包含(例: 児島株式会社→『児島』が 鹿児島堀口製茶 に含まれ誤MATCH)を
    避けるため、含まれる側を 3 文字以上に限定する(design の orphan法『最短3文字以上を要求し
    短名の偶発包含を抑止』と一致)。完全一致は長さによらず許容する。
    """
    if len(tnorm) < 2 or len(cust_norm) < 2:
        return False
    if tnorm == cust_norm:
        return True
    if len(tnorm) >= 3 and tnorm in cust_norm:
        return True
    if len(cust_norm) >= 3 and cust_norm in tnorm:
        return True
    return False


def name_match(notion_norms, mf_norms):
    """正規化名集合の重なり判定(完全一致 or 2文字以上の包含)。互換用ヘルパ。"""
    for a in notion_norms:
        if len(a) < 2:
            continue
        for b in mf_norms:
            if len(b) < 2:
                continue
            if a == b or a in b or b in a:
                return True
    return False


# ============================================================================
# 契約フィールド抽出 (DB1 形式優先・旧シート 確認内容 へ fail-soft fallback)
# ============================================================================
def _torihiki_norm(contract):
    return normalize(contract.get("取引先", ""))


def _endclient_norms(contract):
    """契約のエンドクライアント名集合(明示『エンドクライアント名』+確認内容抽出)。

    取引先自身は境界(会社)側なので除外する。空集合なら会社内の明細を全許容(=単一endclient想定)。
    """
    norms = set()
    ec = contract.get("エンドクライアント名")
    if ec:
        n = normalize(ec)
        if n:
            norms.add(n)
    tnorm = _torihiki_norm(contract)
    for nm in extract_names(contract.get("取引先", ""), contract.get("確認内容", "")):
        n = normalize(nm)
        if n and n != tnorm:
            norms.add(n)
    return norms


def _expected_amounts(contract):
    """契約の期待金額候補 = (primary, typo_candidates)。

    DB1『現行単価/金額/単価』を最優先(typo無し)。無ければ旧シート 確認内容 を parse。
    """
    primary = []
    for key in ("現行単価", "金額", "単価"):
        iv = _int(contract.get(key))
        if iv is not None:
            primary.append(iv)
    if primary:
        return _dedup(primary), []
    return parse_amounts(contract.get("確認内容", ""))


def _boundary_customers(contract, mf_index):
    """名寄せ境界の MF顧客リストを返す = (list[(cid, cust_entry)], confirmed)。

    J1: ①MF顧客ID 一致(確定境界) ②fallback=取引先の会社名一致(契約=取引先境界)。
    全照合経路(find_mf_match / quantity_downgrade / orphan)がこの単一関数で境界を解決する。
    """
    cid = contract.get("MF顧客ID")
    if cid and cid in mf_index:
        return [(cid, mf_index[cid])], True
    tnorm = _torihiki_norm(contract)
    out = []
    for k, c in mf_index.items():
        if _company_match(tnorm, normalize(c["cust"])):
            out.append((k, c))
    return out, False


def _svc_matches_endclient(svc, ec_norms):
    """境界内 MF明細が当該契約のエンドクライアントに該当するか(多 endclient 会社の分離)。

    ec_norms 空 or 明細に括弧名なし → True(単一 endclient 想定で会社内を許容)。
    """
    if not ec_norms:
        return True
    pn = svc.get("paren")
    if not pn:
        return True
    pnn = normalize(pn)
    return any(e == pnn or e in pnn or pnn in e for e in ec_norms if len(e) >= 2)


def _annual_year_amounts(contract):
    """年間一括の期待年額候補。現行単価×初回年間月数 と 現行単価そのもの(既に年額の場合)。"""
    primary, _ = _expected_amounts(contract)
    months = _int(contract.get("初回年間月数")) or ANNUAL_MONTHS
    out = set(primary)
    for u in primary:
        out.add(u * months)
    return out


# ============================================================================
# 名寄せ単一入口 (find_mf_match) — 全 verdict 経路がここを通る (J1)
# ============================================================================
def find_mf_match(contract, mf_index, mode="monthly"):
    """契約 × MF実績 の照合を行う唯一の入口。境界解決→金額/年額/存在 判定。

    mode:
      'monthly'  : 当月期待(月払い/単発開始月/分割対象月/隔月請求月/年間払い13ヶ月目〜)。
      'annual'   : 年間一括(lump)検出(年間払い elapsed==0 / 年間一括更新 lump月)。
      'presence' : 当該契約の MF実績の有無のみ(REVIEW_ENDED_BUT_BILLED 判定用)。

    返り値 dict:
      status   : 'match'|'typo'|'amount_mismatch'|'cross_client'|'no_supply'
      evidence : 一致した {cust, **svc} or None
      boundary_supply : 境界内(会社/ID)の (cust, svc) 全件
      cross_evidence  : 境界外で同名人物が別会社に請求されている証跡(J1, status=cross_client時)

    status の意味と verdict 対応:
      match           → MATCH_*(完全一致)
      typo            → REVIEW_AMOUNT_TYPO(/10 桁typo 候補が一致)
      amount_mismatch → REVIEW_AMOUNT_MISMATCH(B1: 名寄せ供給ありで金額のみ不一致)
      cross_client    → 別会社で同名請求あり(J1: MATCH 扱いしない。呼出側は GAP+証跡で要確認化)
      no_supply       → GAP(名寄せ供給が皆無)
    """
    boundary, _confirmed = _boundary_customers(contract, mf_index)
    ec_norms = _endclient_norms(contract)
    company_supply = [(c["cust"], svc) for _, c in boundary for svc in c["services"]]
    ec_supply = [(cust, svc) for cust, svc in company_supply if _svc_matches_endclient(svc, ec_norms)]
    candidates = ec_supply if ec_supply else company_supply
    expected_cats = _expected_categories(contract)
    category_candidates = [
        (cust, svc) for cust, svc in candidates
        if not expected_cats or svc.get("category") in expected_cats
    ]
    scoped_candidates = category_candidates if expected_cats else candidates

    if mode == "presence":
        if scoped_candidates:
            cust, svc = scoped_candidates[0]
            return {"status": "match", "evidence": {"cust": cust, **svc},
                    "boundary_supply": company_supply, "cross_evidence": None}
        return {"status": "no_supply", "evidence": None,
                "boundary_supply": company_supply, "cross_evidence": None}

    if mode == "annual":
        year_amounts = _annual_year_amounts(contract)
        for cust, svc in scoped_candidates:
            is_lump = svc["category"] in _ANNUAL_LUMP_CATEGORIES and (
                (svc.get("qty") or 0) >= _ANNUAL_LUMP_QTY or svc["amount"] >= _ANNUAL_LUMP_AMOUNT)
            if is_lump or svc["amount"] in year_amounts:
                return {"status": "match", "evidence": {"cust": cust, **svc},
                        "boundary_supply": company_supply, "cross_evidence": None}
        # lump 未検出 → 呼出側で REVIEW_ANNUAL_BILLING_MONTH(E1, GAPにしない)
        return {"status": "no_supply", "evidence": None,
                "boundary_supply": company_supply, "cross_evidence": None}

    # mode == 'monthly'
    primary, typo = _expected_amounts(contract)
    pset, tset = set(primary), set(typo)
    for cust, svc in scoped_candidates:
        if svc["amount"] in pset:
            return {"status": "match", "evidence": {"cust": cust, **svc},
                    "boundary_supply": company_supply, "cross_evidence": None}
    expected_count = _int(contract.get("期待明細数")) or 1
    if expected_count > 1:
        aggregate_amounts = {amount * expected_count for amount in pset}
        for cust, svc in scoped_candidates:
            if svc["amount"] in aggregate_amounts:
                return {
                    "status": "match",
                    "evidence": {
                        "cust": cust,
                        **svc,
                        "_aggregated_billing": True,
                        "_aggregated_expected_count": expected_count,
                    },
                    "boundary_supply": company_supply,
                    "cross_evidence": None,
                }
    for cust, svc in scoped_candidates:
        if svc["amount"] in tset:
            return {"status": "typo", "evidence": {"cust": cust, **svc},
                    "boundary_supply": company_supply, "cross_evidence": None}
    # B1: 名寄せ供給(会社一致)が存在し金額のみ不一致 → REVIEW_AMOUNT_MISMATCH(GAPにしない)
    if scoped_candidates:
        return {"status": "amount_mismatch", "evidence": None,
                "boundary_supply": company_supply, "cross_evidence": None}
    if company_supply and expected_cats:
        return {"status": "no_supply", "evidence": None,
                "boundary_supply": company_supply, "cross_evidence": None}
    # 境界に会社が無い: J1 — 同名人物が別会社で請求されていないか走査
    cross = _cross_client_evidence(ec_norms, pset | tset, mf_index)
    if cross:
        return {"status": "cross_client", "evidence": None,
                "boundary_supply": company_supply, "cross_evidence": cross}
    return {"status": "no_supply", "evidence": None,
            "boundary_supply": company_supply, "cross_evidence": None}


def _cross_client_evidence(ec_norms, amount_set, mf_index):
    """境界外で、同名エンドクライアント・同額の請求がある証跡を返す(J1 安全網)。無ければ None。"""
    if not ec_norms:
        return None
    for _, c in mf_index.items():
        for svc in c["services"]:
            pn = svc.get("paren")
            if not pn:
                continue
            pnn = normalize(pn)
            if svc["amount"] in amount_set and any(
                    e == pnn or e in pnn or pnn in e for e in ec_norms if len(e) >= 2):
                return {"cust": c["cust"], **svc}
    return None


# ============================================================================
# 契約ID境界キー (F1 数量集計・重複統合の単位)
# ============================================================================
def contract_id_key(contract):
    """契約ID境界キー = (norm取引先, norm エンドクライアント, 商品, 枝番)。

    F1: 数量差は name-bucket でなくこの契約ID境界で集計し偽陽性を回避する。金額は識別キーに
    含めない(effective-dating で改定するため)。エンドクライアント名が空なら確認内容から推定。
    """
    ec = contract.get("エンドクライアント名")
    if not ec:
        extracted = [n for n in extract_names(contract.get("取引先", ""), contract.get("確認内容", ""))
                     if normalize(n) != _torihiki_norm(contract)]
        ec = extracted[0] if extracted else ""
    return (
        _torihiki_norm(contract),
        normalize(ec),
        (contract.get("商品") or "").strip(),
        str(contract.get("枝番") or "").strip(),
    )


# ============================================================================
# classify (行分類・評価順序の本体)
# ============================================================================
def _resolve_cycle(contract):
    """支払サイクルを解決。K1: 人手設定の列が最優先。空欄のときのみ月払いへ fallback。"""
    cycle = (contract.get("支払サイクル") or "").strip()
    if cycle:
        return cycle
    return CADENCE_MONTHLY


def _pending_reason(contract):
    """保留(REVIEW_PENDING)の理由を確認ポイント用に 1 フレーズで返す(契約終了の請求なし注記も含む)。"""
    content = contract.get("備考") or contract.get("確認内容") or ""
    if "未締結" in content or "未確定" in content:
        return "契約書が未締結/未確定"
    if "請求なし" in content:
        return "確認内容に『請求なし』の注記あり"
    if not content.strip():
        return "確認内容が空欄"
    if contract.get("現行単価") is None:
        return "確認内容に金額の記載なし"
    return "金額が月額下限未満で請求条件が未確定"


def _new_row(contract, **computed):
    """contract のコピーに計算済みフィールドと verdict 枠を載せた行を作る。"""
    rec = dict(contract)
    rec.update(computed)
    rec.setdefault("verdict", None)
    rec.setdefault("evidence", None)
    rec.setdefault("warning", "")
    rec.setdefault("direction", "順方向")
    return rec


def _classify_monthly_expected(rec, contract, mf_index, elapsed):
    """月次相当の当月期待を MF と突合し verdict を rec へ書く(B1 金額差分岐を含む)。

    elapsed が負(対象月が契約開始前)なら未開始 → SUPPRESS_OFFMONTH。
    elapsed None(開始日空欄=月払い2年目以降)は常に当月期待とする。
    """
    if elapsed is not None and elapsed < 0:
        rec["verdict"] = "SUPPRESS_OFFMONTH"
        return
    primary, typo = _expected_amounts(contract)
    if not primary and not typo:
        rec["verdict"] = "REVIEW_NO_AMOUNT"
        return
    m = find_mf_match(contract, mf_index, mode="monthly")
    st = m["status"]
    if st == "match":
        rec["verdict"] = "MATCH_MONTHLY"
        rec["evidence"] = m["evidence"]
    elif st == "typo":
        rec["verdict"] = "REVIEW_AMOUNT_TYPO"
        rec["evidence"] = m["evidence"]
    elif st == "amount_mismatch":
        rec["verdict"] = "REVIEW_AMOUNT_MISMATCH"  # B1
        rec["warning"] = "名寄せMF供給ありで金額不一致"
    elif st == "cross_client":
        # J1: 別会社で同名請求あり。MATCH 扱いせず GAP(発行漏れ候補)+証跡で要確認化。
        rec["verdict"] = "GAP"
        rec["evidence"] = m["cross_evidence"]
        rec["_cross_client"] = m["cross_evidence"]
        rec["warning"] = "別取引先で同名請求あり(証跡流用不可・要確認)"
    else:  # no_supply
        rec["verdict"] = "GAP"


def _classify_annual(rec, contract, mf_index, elapsed):
    """年間払い(case b): 初年度に一括1回→開始+12月から月額。E1(当月開始で一括未検出=保留)を反映。

    一括は発行タイミングのズレで「契約開始月の翌月」に発行されることがある(MF 2606 は大半が
    5月分サービスの当月発行)。そのため初年度窓 0<=elapsed<12 の全体で当月MFの年額一括を探し、
    在れば MATCH_ANNUAL とする(実証エンジン reconcile.py の挙動)。当月MFに一括が無い場合は
    elapsed==0(当月開始で一括を当月期待)→ REVIEW_ANNUAL_BILLING_MONTH(E1, GAPにしない)、
    0<elapsed<12(年間前払い期間中で当月の月次請求なしが正常)→ SUPPRESS_ANNUAL、
    elapsed>=12 → 月額へ移行。
    """
    if elapsed is not None and elapsed >= ANNUAL_MONTHS:
        _classify_monthly_expected(rec, contract, mf_index, elapsed)  # 月額へ移行
        return
    if elapsed is not None and 0 <= elapsed < ANNUAL_MONTHS:
        m = find_mf_match(contract, mf_index, mode="annual")
        if m["status"] == "match":
            rec["verdict"] = "MATCH_ANNUAL"
            rec["evidence"] = m["evidence"]
        elif elapsed == 0:
            rec["verdict"] = "REVIEW_ANNUAL_BILLING_MONTH"  # E1: 当月開始だが一括未検出
        else:
            rec["verdict"] = "SUPPRESS_ANNUAL"  # 年間前払い期間中
    else:  # elapsed < 0(未開始)。None は K1 で REVIEW_DATA_INCOMPLETE 済
        rec["verdict"] = "SUPPRESS_ANNUAL"


def _classify_annual_renewal(rec, contract, mf_index, elapsed):
    """年間一括更新(case a): 毎年更新で再一括(ThinkTank型)。月額へは移行しない。E1 を反映。

    更新一括も発行タイミングのズレ(更新月の翌月発行)を許容し、当月MFの年額一括を先に探す。
    在れば MATCH_ANNUAL。当月MFに一括が無い場合は更新月(elapsed%12==0)→
    REVIEW_ANNUAL_BILLING_MONTH(E1, GAPにしない)、前払い期間中(elapsed%12!=0)→ SUPPRESS_ANNUAL。
    """
    m = find_mf_match(contract, mf_index, mode="annual")
    if m["status"] == "match":
        rec["verdict"] = "MATCH_ANNUAL"
        rec["evidence"] = m["evidence"]
        return
    period = annual_renewal_period(elapsed)  # 'lump'|'prepaid'|None
    if period == "lump":
        rec["verdict"] = "REVIEW_ANNUAL_BILLING_MONTH"  # E1: 更新月だが一括未検出
    else:  # 'prepaid'(前払い中) / None(elapsed None は K1 済 / 負は未開始)
        rec["verdict"] = "SUPPRESS_ANNUAL"


def classify(contracts, mf_index, target_ym):
    """有効/終了契約 × 当月の判定行を返す(順方向)。最後に F1 数量差降格を適用。

    評価順序: ①ステータス=保留→REVIEW_PENDING ②契約終了→SUPPRESS_ENDED/REVIEW_ENDED_BUT_BILLED
    ③支払サイクル別展開(K1 列優先・H1 従量・E1 年間保留・B1 金額差)。
    """
    t_idx = ym_int(target_ym)
    rows = []
    for contract in contracts:
        status = (contract.get("ステータス") or "有効").strip()
        start = (contract.get("契約開始日") or "").strip()
        end = (contract.get("契約終了月") or "").strip()
        start_idx = ym_int(start) if start else None
        end_idx = ym_int(end) if end else None
        elapsed = months_elapsed(start, target_ym) if start else None
        cycle = _resolve_cycle(contract)

        rec = _new_row(contract, _start_idx=start_idx, _end_idx=end_idx,
                       _elapsed=elapsed, _cycle=cycle)

        # ① 保留(契約未締結/確認内容空欄/金額未記載で支払サイクル判定不能)。判定なしのまま
        #    だとシート上で不可視になり請求漏れを見落とす恐れがあるため、要確認として可視化し
        #    保留理由を確認ポイント(action_hint+warning)へ書く(ユーザー確定 2026-06-27)。
        if status == "保留":
            rec["verdict"] = "REVIEW_PENDING"
            rec["warning"] = _pending_reason(contract)
            rows.append(rec)
            continue

        # ② 契約終了月以降。役務の請求は翌月に発行される(月またぎ発行)ため、終了月Mの最終請求書は
        #    M+1 に出るのが正常。終了月〜終了月+1(最終請求月)の MF 請求は MATCH_ENDED_FINAL(発行確認OK)で
        #    過剰請求にしない。終了月+2 以降(または終了月不明の status=終了)の MF 請求のみ
        #    REVIEW_ENDED_BUT_BILLED(過剰請求)。MF 無しはどの月でも SUPPRESS_ENDED(対象外)。
        if status == "終了" or (end_idx is not None and t_idx is not None and t_idx >= end_idx):
            pres = find_mf_match(contract, mf_index, mode="presence")
            if pres["status"] != "match":
                rec["verdict"] = "SUPPRESS_ENDED"
            elif end_idx is not None and t_idx is not None and t_idx <= end_idx + 1:
                # 終了月〜翌月の請求 = 最終請求書(月またぎ発行)。過剰請求にしない。
                rec["verdict"] = "MATCH_ENDED_FINAL"
                rec["evidence"] = pres["evidence"]
            else:  # 終了月+2 以降、または終了月不明の終了ステータス = 過剰請求
                rec["verdict"] = "REVIEW_ENDED_BUT_BILLED"
                rec["evidence"] = pres["evidence"]
                rec["warning"] = "契約終了後(最終請求月より後)にMF請求あり(過剰請求)"
            rows.append(rec)
            continue

        # H1: 従量(都度) は期待額不定 → 常に REVIEW(開始日空欄でも可)
        if cycle == CADENCE_METERED:
            rec["verdict"] = "REVIEW_METERED"
            rec["warning"] = "従量(都度)・期待額不定"
            rows.append(rec)
            continue

        # K1: 非月払いサイクル & 開始日空欄(elapsed None) → データ不備(展開不能)
        if cycle in NON_MONTHLY_CYCLES and elapsed is None:
            rec["verdict"] = "REVIEW_DATA_INCOMPLETE"
            rec["warning"] = "非月払いサイクルで契約開始日が空欄(elapsed算出不能)"
            rows.append(rec)
            continue

        # ③ 支払サイクル別展開
        if cycle == CADENCE_ANNUAL:
            _classify_annual(rec, contract, mf_index, elapsed)
        elif cycle == CADENCE_ANNUAL_RENEWAL:
            _classify_annual_renewal(rec, contract, mf_index, elapsed)
        elif cycle == CADENCE_ONESHOT:
            if oneshot_active(elapsed):
                _classify_monthly_expected(rec, contract, mf_index, elapsed)
            else:
                rec["verdict"] = "SUPPRESS_ONESHOT"
        elif cycle == CADENCE_SPLIT:
            n = _int(contract.get("分割回数"))
            if split_active(elapsed, n):
                _classify_monthly_expected(rec, contract, mf_index, elapsed)
            else:
                rec["verdict"] = "SUPPRESS_OFFMONTH"
        elif cycle == CADENCE_BIMONTHLY:
            parity = start_idx if start_idx is not None else 0
            if bimonthly_active(elapsed, parity):
                _classify_monthly_expected(rec, contract, mf_index, elapsed)
            else:
                rec["verdict"] = "SUPPRESS_OFFMONTH"
        else:  # 月払い(明示 or 空欄fallback)
            _classify_monthly_expected(rec, contract, mf_index, elapsed)

        rows.append(rec)

    quantity_downgrade(rows, mf_index)  # F1
    return rows


def quantity_downgrade(rows, mf_index):
    """F1: 契約ID境界で 期待件数(Σ期待明細数) > MF供給件数(dedup後・同名寄せ・同額) を降格。

    presence-based 充足後、数量差があれば REVIEW_QTY_MISMATCH へ降格する(発行済み証跡は
    保持しつつ AI確認済みにはしない)。集計単位は contract_id_key(name-bucket でなく契約ID境界=偽陽性回避)。
    岩本鉄工所/大橋諒祐(期待2 > 取引先自身のMF供給1)の偽陰性を機械的に封鎖する条件。
    """
    buckets = defaultdict(list)
    for rec in rows:
        if rec.get("verdict") in _MATCH_VERDICTS:
            evidence = rec.get("evidence") or {}
            if evidence.get("_aggregated_billing"):
                rec["_expected"] = _int(rec.get("期待明細数")) or 1
                rec["_supply"] = 1
                rec["warning"] = (
                    f"MF 1明細に期待{rec['_expected']}件分が集約されているため"
                    "数量差に降格しない"
                )
                continue
            buckets[contract_id_key(rec)].append(rec)

    for _key, recs in buckets.items():
        # 期待件数 = Σ期待明細数(既定1)
        expected = sum((_int(r.get("期待明細数")) or 1) for r in recs)
        # 期待金額集合(契約ID境界で共通の名寄せ・代表契約で境界解決)
        amount_set = set()
        for r in recs:
            primary, typo = _expected_amounts(r)
            amount_set.update(primary)
            amount_set.update(typo)
        ec_norms = _endclient_norms(recs[0])
        boundary, _ = _boundary_customers(recs[0], mf_index)
        # MF供給件数 = 境界内 dedup明細のうち 同 endclient・同額 の件数
        supply_keys = set()
        for _, c in boundary:
            for svc in c["services"]:
                if svc["amount"] in amount_set and _svc_matches_endclient(svc, ec_norms):
                    supply_keys.add((c["cust"], svc.get("billing_id"), svc["desc"], svc["amount"]))
        supply = len(supply_keys)

        if expected > supply:
            shortfall = expected - supply
            unit = min(amount_set) if amount_set else 0
            for rec in recs:
                rec["verdict"] = "REVIEW_QTY_MISMATCH"
                rec["_expected"] = expected
                rec["_supply"] = supply
                rec["warning"] = f"数量差: 期待{expected}>MF供給{supply}(想定漏れ額 {shortfall * unit:,}円)"


# ============================================================================
# 双方向: orphan 検出 (実績 − 当月期待 = 要マスタ登録)
# ============================================================================
def detect_orphans(contracts, mf_index, target_ym):
    """MF実績(課税)のうち、当月いずれの登録済み契約にも名寄せされない MF顧客を ORPHAN で返す。

    J1: 名寄せ境界(_boundary_customers = MF顧客ID優先→取引先会社名)で被覆集合を作り、
    残りを orphan とする。name-global 照合は使わない(design の name照合 42/82 偽orphan を回避)。
    target_ym は I/F 統一のため受けるが、mf_index は既に当月分で構築されている前提。
    """
    matched_cids = set()
    for contract in contracts:
        status = (contract.get("ステータス") or "有効").strip()
        if status == "保留":
            continue
        boundary, _ = _boundary_customers(contract, mf_index)
        for cid, _c in boundary:
            matched_cids.add(cid)

    orphans = []
    for cid, c in mf_index.items():
        if cid in matched_cids or not c["services"]:
            continue
        amount = sum(svc["amount"] for svc in c["services"])
        rep = max(c["services"], key=lambda s: s["amount"])
        orphans.append({
            "verdict": "ORPHAN",
            "direction": "逆方向orphan",
            "MF顧客ID": cid,
            "cust": c["cust"],
            "amount": amount,
            "desc": rep["desc"],
            "services": c["services"],
            "contract_id": None,
            "warning": "MF実績ありマスタ未登録(要マスタ登録)",
        })
    return orphans


# ============================================================================
# reconcile (双方向の便宜まとめ) + attach_cycle (移行下書き&テスト共用)
# ============================================================================
def reconcile(contracts, mf_index, target_ym):
    """順方向(classify) + 逆方向(detect_orphans) をまとめて返す純関数。

    返り値 dict: {target_ym, rows(順方向), orphans(逆方向), summary(verdict件数)}。
    sink/orchestrator がそのまま DB2 upsert へ渡せる形(I/O は呼出側)。
    """
    rows = classify(contracts, mf_index, target_ym)
    orphans = detect_orphans(contracts, mf_index, target_ym)
    summary = Counter(r["verdict"] for r in rows)
    summary.update(o["verdict"] for o in orphans)
    return {
        "target_ym": target_ym,
        "rows": rows,
        "orphans": orphans,
        "summary": dict(summary),
    }


_CANONICAL_CYCLE_RULES = [
    ("従量", CADENCE_METERED),
    ("都度", CADENCE_METERED),
    # 年間一括の2系を判別(順序で優先): case a『更新も一括』=毎年再一括(ThinkTank型) を先に。
    ("更新も一括", CADENCE_ANNUAL_RENEWAL),
    ("年間一括更新", CADENCE_ANNUAL_RENEWAL),
    # case b『年間一括-初年度のみ→月額』=初年度のみ一括→翌年月額。"年間一括" だけで
    # ANNUAL_RENEWAL に倒すと case b が誤って毎年一括化するため、初年度シグナルを先に拾う。
    ("初年度のみ", CADENCE_ANNUAL),
    ("→月額", CADENCE_ANNUAL),
    ("年間払い", CADENCE_ANNUAL),
    ("年間", CADENCE_ANNUAL),
    ("分割", CADENCE_SPLIT),
    ("隔月", CADENCE_BIMONTHLY),
    ("月払い", CADENCE_MONTHLY),
    ("月額", CADENCE_MONTHLY),
    ("単発", CADENCE_ONESHOT),
]


def _canonical_cycle(raw):
    """棚卸しの inferred_cycle 文字列を MECE6値+従量 の正規ラベルへ写像。未判定は ''。

    年間一括の2系を区別する(順序で優先): 『年間一括-更新も一括』(case a)→年間一括更新、
    『年間一括-初年度のみ→月額』(case b)→年間払い。bare『年間』は case b(年間払い)へ倒す。
    """
    t = str(raw or "")
    for needle, canon in _CANONICAL_CYCLE_RULES:
        if needle in t:
            return canon
    return ""


def _row_dup_key(row):
    """重複統合の単位(原件数退避用)= (norm取引先, 商品, norm確認内容)。"""
    return (
        normalize(row.get("取引先", "")),
        (row.get("商品") or "").strip(),
        normalize(row.get("確認内容", "")),
    )


def attach_cycle(notion_rows, cycle_inventory):
    """旧シート各行に 支払サイクル / 期待明細数 / エンドクライアント名 を付与した行を返す。

    cycle_inventory: 棚卸しJSON の contracts(torihiki/shohin/endclient/amount/inferred_cycle)。
    付与内容:
      支払サイクル  : inferred_cycle を _canonical_cycle で正規化。(取引先,エンドクライアント)で
                      照合し、無ければ取引先のみで fallback。
      期待明細数    : 同 (取引先,商品,確認内容) で重複する行数 = 原件数退避(F1 数量差の元)。
      エンドクライアント名: 確認内容から抽出した先頭人名(未設定時のみ)。
    入力は破壊せず新 dict を返す(移行下書き&テストで共用)。
    """
    by_pair, by_torihiki = {}, {}
    for inv in cycle_inventory:
        canon = _canonical_cycle(inv.get("inferred_cycle", ""))
        tnorm = normalize(inv.get("torihiki", ""))
        ecnorm = normalize(inv.get("endclient", ""))
        by_pair[(tnorm, ecnorm)] = canon
        by_torihiki.setdefault(tnorm, canon)

    counts = Counter(_row_dup_key(r) for r in notion_rows)

    out = []
    for r in notion_rows:
        extracted = [n for n in extract_names(r.get("取引先", ""), r.get("確認内容", ""))
                     if normalize(n) != normalize(r.get("取引先", ""))]
        ec = r.get("エンドクライアント名") or (extracted[0] if extracted else "")
        tnorm = normalize(r.get("取引先", ""))
        cyc = by_pair.get((tnorm, normalize(ec)))
        if not cyc:
            cyc = by_torihiki.get(tnorm, "")
        nr = dict(r)
        nr["支払サイクル"] = cyc
        nr["期待明細数"] = counts[_row_dup_key(r)]
        if ec and not nr.get("エンドクライアント名"):
            nr["エンドクライアント名"] = ec
        out.append(nr)
    return out
