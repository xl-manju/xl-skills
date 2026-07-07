#!/usr/bin/env python3
# /// script
# name: notion_report_sink
# purpose: 月次スナップショット DB を積層する決定論 sink。対象月の DB を指定ページ『請求書発行チェック』
#          直下へ find-or-create し (同一対象月は既存 month_db_id 再利用=二重 DB 0)、
#          分類済みレポート行を非破壊冪等 upsert する (以前 run の行は削除しない=deleted 常時 0)。
# inputs:
#   - argv: --rows FILE (C05 分類済みレポート行 JSON list) --target YYMM [--apply --verified] [--config PATH]
#   - config: mf-kessai-config.default.json (配布既定) + .mf-kessai-config.json (ローカル上書き) の
#             notion.report_parent_page (XLOCAL 共有の配布既定 + 任意上書き)
# outputs:
#   - stdout: upsert 結果 JSON {created, updated, skipped, deleted(=0), collapsed_multi_contract,
#             month_db_id, month_db_reused, placement}
#   - stderr: violation
#   - exit: 0=OK / 1=部分失敗 / 2=fail-closed (target/親ページ未設定・rows 不正)
# contexts: [C, E]
# network: true   # Notion REST (親ページ子ブロック list + DB find-or-create + 行 upsert)。MF へは書かない
# write-scope: notion:monthly-report-db (指定ページ『請求書発行チェック』直下・newest-on-top intended_index/append fallback)
# dependencies: [notion_transport, build_notion_db, mfk_api]
# requires-python: ">=3.11"
# ///
"""月次スナップショット DB を積層する決定論 sink (前月↔今月の発行漏れ比較レポート出力先)。

責務 (C06):
  1. **月次 DB の find-or-create**: 対象月 (target=YYMM) の DB が無ければ、指定ページ
     『請求書発行チェック』(論理キー ``report_parent_page``) の直下の子として ``child_database`` を
     作成する (database の parent は page_id/database_id のみ許容・block_id=トグル見出し不可の
     Notion API 制約による)。DB の一意キー = target_month(YYMM) + logical_parent(report_parent_page)
     + title『請求漏れ比較レポート YYYY-MM』。同一対象月の再実行では既存 month_db_id を再利用し
     二重 DB を作らない (month_db_reused=true)。
  2. **7 列スキーマ (列順 SSOT)**: [取引先名(title), 漏れチェック(checkbox), 商品名(rich_text),
     先月の金額(number/yen), 今月の金額(number/yen), 先月と今月の比較(rich_text), コメント(rich_text)]
     をこの左→右順で固定する。title(=各行=ページ名)プロパティ = 取引先名を先頭に置き Notion の
     title 最左固定と定義順を一致させる。漏れチェックは checkbox (正常=✓ / 要対応=☐)。金額は税抜。
     DB 生成と列型写像は build_notion_db.build_property を再利用する (踏襲元の能力境界を明示=SS-F2:
     notion_reconcile_sink は既存 DB への行 upsert 専用で DB 生成機能を持たないため DB 生成は
     build_notion_db に委譲する)。
  3. **非破壊冪等 upsert**: 当月 DB へレポート行を upsert する。同月内の 2/3 営業日目再実行は
     入力同定 {取引先×契約ID×商品} と stored key (取引先名,商品名) で同一行を 1 行へ収束させる
     (重複行 0)。固定 7 列に契約IDは永続化しないため、契約ID違いは要対応優先で collapse し
     collapsed_multi_contract に計上する。**非破壊マージ = 以前の run で書いた行は今回入力に
     無くても当月 DB から削除しない** (deleted 常時 0・全情報保持・clear-then-insert でない)。
     手動追記運用は無い前提ゆえ frozen 列は設けない (notion_reconcile_sink の人間対応済み凍結は
     踏襲しない)。
  4. **配置順**: target_month の YYYY-MM で newest-on-top の意図位置 (intended_index) を算出し、
     実配置は Notion API 制約により末尾 append する。過去月 --target 後追い時も意図位置を報告し、
     実配置との差を placement で開示する。

GAP-NOTION-DB-PARENT / GAP-NOTION-TOGGLE-PLACEMENT (能力境界の正直な明記):
  当初設計は「トグル見出し2配下へ DB を find-or-create + 任意位置 (先頭) へ insert」だったが、
  **Notion API (2022-06-28) は database の parent に page_id / database_id のみ許容し block_id
  (トグル見出し) を許さない** (POST /databases に block_id 親を送ると 400)。かつ **任意位置 insert
  も存在しない** (child ブロックは末尾 append のみ・child_database の再並べ替え PATCH も無い)。
  よって本実装は Notion API で確立している方式を採る:
    - find-or-create : POST /databases に ``parent={type:"page_id", page_id:<report_parent_page>}``
      で指定ページ『請求書発行チェック』直下の child_database を作成する (トグル見出し配下ではない)。
      既存月 DB の探索は GET /blocks/{report_parent_page}/children でページ直下の子を辿り title 一致で
      見つける (child_database ブロックの id は database_id と一致するので、一致ブロックの id を
      そのまま month_db_id に使う)。``report_toggle_block`` は本 sink では使用しない (Notion API 制約で
      トグル配下配置が不能なため deprecated・config には後方互換で残置)。
    - placement     : newest-on-top / YYYY-MM 安定挿入の**意図位置** (intended_index) を既存
      child_database 群の YYYY-MM から算出して報告するが、API は末尾 append しかできないため
      実配置は append となる (fallback = 末尾 append + title の YYYY-MM で人間が識別)。この
      「意図位置 vs 実配置 (append)」の差は stdout の ``placement`` フィールドで開示する。
  全ての API 経路は notion_transport._req 経由で、テストは req 引数に fake-store を差し替えて
  network 非依存で検証する (既存 test_notion_reconcile_sink の offline 契約踏襲)。fake-store は
  POST /databases の parent.type が page_id であることを検証し、block_id 親の再混入を機械 fail させる。
"""
import argparse
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "lib"))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "skills", "run-mf-invoice-db-setup", "scripts"))

from notion_transport import _req, _notion_token, _rich_text_plain  # noqa: E402
from build_notion_db import build_property  # noqa: E402  DB 生成の列型写像を再利用 (SS-F2)
from mfk_api import load_config  # noqa: E402
from mfk_reconcile import normalize as _normalize_name  # noqa: E402  名寄せ SSOT (NFKC・SKILL Gotcha5)

# Notion rich_text の content は 1 要素あたり 2000 文字上限。超過は切り詰める。
_MAX_RICH_TEXT = 2000

# --- 7 列スキーマ (列順 SSOT: この左→右順で固定する) --------------------------------
PROP_CUSTOMER = "取引先名"                 # title    (= 各行 = ページ名)
PROP_MISSING_CHECK = "漏れチェック"       # checkbox (正常=✓チェックあり / 要対応=☐チェックなし)
PROP_PRODUCT = "商品名"                    # rich_text
PROP_PREV_AMOUNT = "先月の金額"            # number(yen)  税抜
PROP_CURR_AMOUNT = "今月の金額"            # number(yen)  税抜
PROP_COMPARISON = "先月と今月の比較"       # rich_text (テキスト説明)
PROP_COMMENT = "コメント"                  # rich_text

# 列順 SSOT の配列。DB 生成時の properties 構築順 = Notion 上の列の左→右順。
# 取引先名 (title) を先頭に置く: Notion は table view で title 列を最左に固定するため、title を
# COLUMN_ORDER 先頭に定義することで「定義順 = 実表示順」を一致させ、列順を確実に設定通りにする
# (title を非先頭に置くと Notion が最左へ引き上げ定義順と表示順がズレる)。漏れチェック(checkbox)は
# title 直後の 2 列目。
COLUMN_ORDER = [
    PROP_CUSTOMER,
    PROP_MISSING_CHECK,
    PROP_PRODUCT,
    PROP_PREV_AMOUNT,
    PROP_CURR_AMOUNT,
    PROP_COMPARISON,
    PROP_COMMENT,
]

# C05 producer (mfk_period_report.py) が emit する行キー → 本 sink の 7 列への写像 (SEAM SSOT)。
# producer/consumer のキー語彙をここで一元宣言し、seam 断裂 (キー名不一致で列が空になる) を防ぐ。
# _build_row_props はこの producer キー (各値の第一 alias) を読む。ROW_CONTRACT を SSOT として
# 実効化する担保は 2 段: (1) test_row_contract_maps_every_producer_key_to_column が本 dict の
# 各 producer キーを _build_row_props で辿り mapped 列へ着地することを assert し drift を検出する
# (宣言と実装の乖離を機械 fail させる)、(2) test_seam_c05_output_populates_all_seven_columns が
# C05 実出力 → 本 sink を実 pipe で貫通して 7 列全充足を検証する (isolation では捕捉不能)。
ROW_CONTRACT = {
    "gap_check": PROP_MISSING_CHECK,   # 漏れチェック (checkbox: 正常=✓/要対応=☐)
    "customer": PROP_CUSTOMER,         # 取引先名 (title)
    "product": PROP_PRODUCT,           # 商品名
    "prev_amount": PROP_PREV_AMOUNT,   # 先月の金額 (税抜)
    "amount": PROP_CURR_AMOUNT,        # 今月の金額 (税抜・C05 の amount=当月期待/実額)
    "period_diff": PROP_COMPARISON,    # 先月と今月の比較 (テキスト説明)
    "comment": PROP_COMMENT,           # コメント (事情説明)
}

# 漏れチェックは checkbox: 正常=チェックあり(True) / 要対応(発行漏れ候補)=チェックなし(False)。
# チェックの有無だけで直感的に「請求できている(✓)/要対応(☐)」を判別できるようにする。

# 列名 -> build_notion_db.build_property が解釈する型 spec。
_COLUMN_SPECS = {
    PROP_MISSING_CHECK: {"type": "checkbox"},
    PROP_CUSTOMER: {"type": "title"},
    PROP_PRODUCT: {"type": "rich_text"},
    PROP_PREV_AMOUNT: {"type": "number"},
    PROP_CURR_AMOUNT: {"type": "number"},
    PROP_COMPARISON: {"type": "rich_text"},
    PROP_COMMENT: {"type": "rich_text"},
}

# 月次 DB の title。target=YYMM を YYYY-MM へ展開して埋める。
_TITLE_PREFIX = "請求漏れ比較レポート"
_YYYYMM_RE = re.compile(r"(\d{4})-(\d{2})$")


class SinkError(RuntimeError):
    """fail-closed で停止すべき設定/前提エラー (main が exit 2 に写像する)。"""


# ---------------------------------------------------------------------------
# 純関数 (正規化 / タイトル / プロパティ整形)
# ---------------------------------------------------------------------------

def _norm(value):
    """None を '' に、他は str() + strip して返す (キー比較を安定化)。"""
    return "" if value is None else str(value).strip()


def _valid_target(target):
    """target が YYMM (数字 4 桁・月 01-12) かを判定する。"""
    t = _norm(target)
    if len(t) != 4 or not t.isdigit():
        return False
    return 1 <= int(t[2:]) <= 12


def target_to_yyyymm(target):
    """YYMM (例 '2607') を YYYY-MM (例 '2026-07') へ展開する。20xx を前置する。"""
    t = _norm(target)
    return f"20{t[:2]}-{t[2:]}"


def month_db_title(target):
    """月次 DB の title『請求漏れ比較レポート YYYY-MM』を返す。"""
    return f"{_TITLE_PREFIX} {target_to_yyyymm(target)}"


def _parse_report_yyyymm(title):
    """child_database の title から YYYY-MM を取り出す。レポート DB 以外は None。"""
    t = _norm(title)
    if not t.startswith(_TITLE_PREFIX):
        return None
    m = _YYYYMM_RE.search(t)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _child_db_title(block):
    """child_database ブロックの title (plain str) を返す (空/欠落は '')。"""
    if not isinstance(block, dict):
        return ""
    return (block.get("child_database") or {}).get("title") or ""


def _title_plain(prop):
    """Notion title プロパティを plain text へ連結する (空/欠落は '')。"""
    if not isinstance(prop, dict):
        return ""
    return "".join(
        (rt.get("text") or {}).get("content") or rt.get("plain_text") or ""
        for rt in (prop.get("title") or [])
    )


def _rt(value):
    """rich_text プロパティ。content の改行 \\n はそのまま保持する (split しない)。"""
    s = str(value if value is not None else "")
    return {"rich_text": [{"text": {"content": s[:_MAX_RICH_TEXT]}}]}


def _row_customer(row):
    return _norm(row.get("customer") or row.get("取引先名") or row.get("customer_name"))


def _row_product(row):
    return _norm(row.get("product") or row.get("商品名") or row.get("product_name"))


def _row_contract_id(row):
    return _norm(row.get("contract_id") or row.get("契約ID"))


def _amount(row, *keys):
    """row から金額を取り出す (最初に見つかった非 None を返す)。0 は有効値。"""
    for k in keys:
        if k in row and row[k] is not None:
            return row[k]
    return None


def _stored_key(customer, product):
    """当月 DB の既存ページを索引する『回収可能』キー。

    固定 7 列スキーマは contract_id を persist しないため (inventory property_order が 7 列固定・
    契約ID列なし)、当月 DB 内の既存ページから回収できる同定キーは (取引先名, 商品名) に限られる。
    contract_id は C05 が同定に使う論理メタだが本 sink では persist しない (=recoverable でない)。

    設計判断 (記録): 同一対象月・同一取引先・同一商品に契約IDだけ異なる複数契約が同居する場合、
    このキーでは 1 行へ収束する (multi-contract collapse)。多契約×同一商品は稀という前提で
    7 列固定を優先した意思決定であり、collapse 時は要対応を優先保持 (_prefer_action) して
    真の発行漏れが正常行に上書きされる false-negative を防ぐ。collapse 件数は stdout の
    collapsed_multi_contract に計上し常態化を可観測にする (常態化すれば 8 列目 contract_id 追加へ
    の移行トリガ)。

    キーは名寄せ SSOT mfk_reconcile.normalize (NFKC + 敬称/法人格/空白/中黒除去 + lower) で
    正規化する (SKILL Gotcha5)。表示 title は raw のまま・キー算出だけ正規化することで、macOS/MF
    API 由来のカタカナ NFD↔NFC 揺れや全角半角差で同一取引先が別行に割れる (=同月2回実行で重複行が
    出て冪等保証 C7/OUT1 が崩れる) のを防ぐ。新規行キーと既存ページ回収キー (_page_match_key) は
    同じ正規化を通るため索引が一致する。
    """
    return (_normalize_name(customer), _normalize_name(product))


def _severity_rank(row):
    """行の漏れチェック severity。要対応(発行漏れ候補)=1 を正常=0 より優先する。"""
    check = _norm(row.get("gap_check") or row.get("check") or row.get("漏れチェック"))
    return 1 if check == "要対応" else 0


def _prefer_action(a, b):
    """同一 (取引先,商品) 衝突時に残す行を決める (F-α safe guard)。

    要対応(発行漏れ候補)を正常が上書きして漏れを隠す false-negative を防ぐため、severity の
    高い方 (要対応) を保持する。両方が同 severity の要対応 (契約ID違いの複数漏れが 1 行へ
    collapse) の場合は、後着を基に両者の comment を改行連結でマージして片方の漏れ詳細が消えない
    ようにする (F-17: 件数だけ数えて内容を捨てる情報損失を防ぐ)。正常×正常は後着を採る。
    """
    ra, rb = _severity_rank(a), _severity_rank(b)
    if ra != rb:
        return a if ra > rb else b
    if ra == 1:  # 要対応×要対応 → comment をマージした後着行 (情報保全)。
        return _merge_action_comments(b, a)
    return b  # 正常×正常 → 後着 (最新入力)。


def _merge_action_comments(base, other):
    """base を基に other の comment を連結マージした新 row を返す (要対応 collapse の情報保全)。"""
    cb = _norm(base.get("comment") or base.get("コメント"))
    co = _norm(other.get("comment") or other.get("コメント"))
    merged = dict(base)
    cid_b, cid_o = _row_contract_id(base), _row_contract_id(other)
    if cid_b and cid_o and cid_b != cid_o:
        merged["comment"] = f"[複数契約collapse] 契約{cid_b}: {cb} / 契約{cid_o}: {co}".strip()
    elif cb and co and cb != co:
        merged["comment"] = f"{cb} / {co}"
    else:
        merged["comment"] = cb or co
    return merged


def _page_gap_check(page):
    """既存ページの漏れチェック (checkbox) を 正常/要対応 に写像して返す (未設定は '')。

    checkbox True=正常 / False=要対応。cross-run safe guard (前 run の要対応=☐ を新 run の
    正常=✓ で無条件に上書きしない) が既存値を読むのに使う。
    """
    props = (page or {}).get("properties") or {}
    prop = props.get(PROP_MISSING_CHECK) or {}
    if "checkbox" not in prop:
        return ""
    return "正常" if prop.get("checkbox") else "要対応"


def _append_comment(props, note):
    """props のコメント列 rich_text 末尾へ note を追記する (freshly-built/read 両形式に対応)。"""
    prop = props.get(PROP_COMMENT) or {}
    existing = "".join(
        (rt.get("text") or {}).get("content") or rt.get("plain_text") or ""
        for rt in (prop.get("rich_text") or [])
    )
    props[PROP_COMMENT] = _rt(f"{existing} / {note}" if existing else note)


def _page_match_key(page):
    """既存ページの properties から _stored_key を回収する。"""
    props = page.get("properties") or {}
    return _stored_key(_title_plain(props.get(PROP_CUSTOMER)), _rich_text_plain(props.get(PROP_PRODUCT)))


def schema_properties():
    """7 列スキーマの Notion properties dict を列順 SSOT の順で構築する。

    dict は挿入順を保持するので COLUMN_ORDER の順に build_property した結果が Notion 上の
    列の左→右順になる (列順固定)。
    """
    return {name: build_property(_COLUMN_SPECS[name]) for name in COLUMN_ORDER}


def _build_row_props(row, *, creating):
    """row を月次 DB の 7 列プロパティ dict へ整形する。

    creating=True (新規 POST) のときだけ title (= 取引先名) を載せる。更新 (PATCH) では title
    (不変な表示キー) に触れず、入力に無い nullable 事実列は明示クリアして stale を残さない
    (行そのものは削除しない=非破壊マージは行単位で成立)。
    """
    props = {}

    # 漏れチェック: C05 producer は `gap_check` を emit する (SSOT=ROW_CONTRACT)。
    # 別名 check/漏れチェック/missing_check も後方互換で受ける。checkbox へ写像:
    # 正常=✓(True) / 要対応(発行漏れ候補)=☐(False)。checkbox は空状態を持たないため、
    # 値が判明したとき (check 非空) のみ設定し、更新で不明なら既存チェックを温存する。
    check = _norm(row.get("gap_check") or row.get("check")
                  or row.get("漏れチェック") or row.get("missing_check"))
    if check:
        props[PROP_MISSING_CHECK] = {"checkbox": check == "正常"}

    product = _row_product(row)
    if product:
        props[PROP_PRODUCT] = _rt(product)
    elif not creating:
        props[PROP_PRODUCT] = {"rich_text": []}

    prev_amount = _amount(row, "prev_amount", "先月の金額")
    if prev_amount is not None:
        props[PROP_PREV_AMOUNT] = {"number": prev_amount}
    elif not creating:
        props[PROP_PREV_AMOUNT] = {"number": None}

    # 今月の金額: C05 producer は `amount` を emit する。別名 curr_amount/今月の金額も受ける。
    curr_amount = _amount(row, "amount", "curr_amount", "今月の金額")
    if curr_amount is not None:
        props[PROP_CURR_AMOUNT] = {"number": curr_amount}
    elif not creating:
        props[PROP_CURR_AMOUNT] = {"number": None}

    # 先月と今月の比較: C05 producer は `period_diff` を emit する。別名 comparison も受ける。
    comparison = _norm(row.get("period_diff") or row.get("comparison") or row.get("先月と今月の比較"))
    if comparison:
        props[PROP_COMPARISON] = _rt(comparison)
    elif not creating:
        props[PROP_COMPARISON] = {"rich_text": []}

    comment = _norm(row.get("comment") or row.get("コメント"))
    if comment:
        props[PROP_COMMENT] = _rt(comment)
    elif not creating:
        props[PROP_COMMENT] = {"rich_text": []}

    if creating:
        customer = _row_customer(row)[:_MAX_RICH_TEXT]
        props[PROP_CUSTOMER] = {"title": [{"text": {"content": customer}}]}
    return props


# ---------------------------------------------------------------------------
# 配置 (newest-on-top / YYYY-MM 安定挿入)
# ---------------------------------------------------------------------------

def intended_index(existing_yyyymm, new_yyyymm):
    """newest-on-top で new_yyyymm を安定挿入する意図位置 (0=先頭=最新) を返す。

    子は YYYY-MM 降順 (新しい月が上部) に並ぶべきなので、挿入位置 = new より新しい (大きい)
    既存月の数。過去月 --target を後追いしても先頭 (0) に割り込まず、正しい下位位置へ入る
    (単純 prepend が過去月を最上部に置く不具合を避ける)。YYYY-MM 文字列は辞書順=時系列順。
    """
    return sum(1 for m in existing_yyyymm if m and m > new_yyyymm)


def list_block_children(block_id, token, req=None):
    """ブロック/ページの子ブロックを has_more/next_cursor を辿り全件取得する。

    GET /blocks/{id}/children は id がページ (page_id) でもブロックでも子を返す
    (ページは自身が 1 つのブロックであり page_id をそのまま渡せる)。月次 DB を
    ページ直下へ置く Option 1 では id = report_parent_page (page_id) を渡す。
    """
    req = req or _req
    out = []
    cursor = None
    while True:
        path = f"/blocks/{block_id}/children?page_size=100"
        if cursor:
            path += f"&start_cursor={cursor}"
        res = req("GET", path, token)
        out.extend(res.get("results", []))
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return out


def find_or_create_month_db(target, parent_page_id, token, req=None, *, apply=True):
    """対象月の月次 DB を find-or-create する。返り値 (month_db_id, reused, placement)。

    探索: 親ページ (report_parent_page) 直下の child_database を辿り title『請求漏れ比較レポート
    YYYY-MM』一致で既存を探す (child_database ブロックの id は database_id と一致するのでそれを
    month_db_id に使う)。見つかれば再利用 (reused=True・二重 DB を作らない)。見つからず apply=True
    なら POST /databases に parent={type:"page_id", page_id:<report_parent_page>} で child_database
    を作成する。

    Notion API 制約 (GAP-NOTION-TOGGLE-PLACEMENT の解): database の parent は page_id / database_id
    のみで block_id (トグル見出し) は不可 (Notion-Version 2022-06-28)。よって月次 DB は指定ページ
    『請求書発行チェック』直下に child_database として置く (トグル見出し配下ではない)。placement は
    newest-on-top の意図位置 (intended_index) と、API 実配置が末尾 append である旨を開示する。
    """
    req = req or _req
    desired = month_db_title(target)
    new_yyyymm = target_to_yyyymm(target)

    found_id = None
    existing_yyyymm = []
    for block in list_block_children(parent_page_id, token, req):
        if block.get("type") != "child_database":
            continue
        title = _child_db_title(block)
        if title == desired:
            found_id = block.get("id")
            continue
        ym = _parse_report_yyyymm(title)
        if ym:
            existing_yyyymm.append(ym)

    placement = {
        "parent_page_id": parent_page_id,
        "target_yyyymm": new_yyyymm,
        "requested_order": "newest-on-top",          # 新しい月を上部へ
        "intended_index": intended_index(existing_yyyymm, new_yyyymm),
        "sibling_month_dbs": len(existing_yyyymm),
        # Notion API は任意位置 insert 不可。child_database は末尾 append される
        # (fallback = title の YYYY-MM で人間が識別)。意図位置との差は intended_index が示す。
        "api_strategy": "append-child-database",
        # 列順は定義順=実表示順で一致させる (F-10 解消)。Notion table view は title 列を最左固定で
        # 描画するため、COLUMN_ORDER の先頭を title (取引先名) に置くことで定義順と実描画順を一致させた。
        # properties は COLUMN_ORDER 順に build するので実列順は [取引先名, 漏れチェック(checkbox),
        # 商品名, 先月の金額, 今月の金額, 先月と今月の比較, コメント] で確定する。
        "column_order_defined": list(COLUMN_ORDER),
        "column_order_note": (
            "列順は定義順=実表示順で一致 (取引先名=title を先頭に定義)。実列順は "
            "取引先名→漏れチェック(✓)→商品名→先月の金額→今月の金額→先月と今月の比較→コメント。"),
    }

    if found_id:
        placement["reused"] = True
        return found_id, True, placement

    if not apply:
        placement["reused"] = False
        placement["created"] = False
        return None, False, placement

    res = req("POST", "/databases", token, {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"text": {"content": desired}}],
        "properties": schema_properties(),
    })
    placement["reused"] = False
    placement["created"] = True
    return res["id"], False, placement


# ---------------------------------------------------------------------------
# 行 upsert (非破壊冪等)
# ---------------------------------------------------------------------------

def query_month(month_db_id, token, req=None):
    """当月 DB の全行を has_more/next_cursor を辿り取得し page_id で dedup する。

    月次 DB は対象月ごとに独立なので、当該 DB の query がそのまま『当月行だけ』を返す
    (対象年月フィルタ列は不要)。過去月は別 DB ゆえ本 query の射程外 = 構造的に不可侵。
    """
    req = req or _req
    out = {}
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = req("POST", f"/databases/{month_db_id}/query", token, body)
        for page in res.get("results", []):
            pid = page.get("id")
            if pid and pid not in out:
                out[pid] = page
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return list(out.values())


def upsert_report_rows(rows, month_db_id, token, req=None):
    """rows を当月 DB へ **非破壊冪等** upsert する。返り値 {created, updated, skipped, deleted}。

    手順:
      1. query_month で当月既存行を取得し _stored_key (取引先名, 商品名) で索引化する。
      2. 入力 rows を _stored_key で収束させる (同月 2/3 営業日目の同一行再投入は 1 件に畳む・
         最後の値を採用)。取引先名が空の行は skip する (title=取引先名 が必須)。
      3. 既存行あり → PATCH 更新 (title は送らない)。無し → POST 新規作成。
      4. **削除はしない** (今回入力に無い既存行も残す=非破壊マージ・deleted 常時 0)。
      5. 各行は try/except で隔離し個別失敗は skipped に計上して継続する。
    """
    req = req or _req
    existing = query_month(month_db_id, token, req)
    index = {}
    for page in existing:
        key = _page_match_key(page)
        if key[0] and key not in index:  # 取引先名 (title) がある行のみ索引
            index[key] = page

    created = updated = skipped = collapsed_multi = 0
    collapsed = {}
    for row in rows:
        customer = _row_customer(row)
        if not customer:
            skipped += 1
            sys.stderr.write("[notion_report_sink] 取引先名 (title) が空の行を skip しました\n")
            continue
        key = _stored_key(customer, _row_product(row))
        prev = collapsed.get(key)
        if prev is None:
            collapsed[key] = row
            continue
        # 同一 (取引先,商品) 衝突。契約IDが異なる複数契約なら multi-contract collapse を計上し、
        # 要対応を優先保持して漏れ隠蔽 (false-negative) を防ぐ (F-α safe guard)。
        if _row_contract_id(prev) != _row_contract_id(row):
            collapsed_multi += 1
            sys.stderr.write(
                "[notion_report_sink] 同一(取引先,商品)に契約ID違いの複数契約を検出。"
                f"7列に契約ID列が無いため1行へ収束し要対応を優先保持: {key}\n")
        collapsed[key] = _prefer_action(prev, row)

    for key, row in collapsed.items():
        try:
            page = index.get(key)
            if page is not None:
                props = _build_row_props(row, creating=False)
                # cross-run safe guard (F-2): 前 run で立てた要対応を新 run の正常で無条件に
                # 下げると前日フラグした漏れが消える (false-negative)。既存ページが要対応で新行が
                # 正常なら漏れチェックを要対応のまま保持し、正常化した旨を comment へ注記する
                # (intra-run の _prefer_action と cross-run を対称化)。
                if _page_gap_check(page) == "要対応" and _severity_rank(row) == 0:
                    props[PROP_MISSING_CHECK] = {"checkbox": False}  # 要対応を保持 (☐ チェックなし)
                    _append_comment(props, "前 run の要対応を保持 (今 run 入力は正常・cross-run safe guard)")
                req("PATCH", f"/pages/{page['id']}", token, {"properties": props})
                updated += 1
            else:
                props = _build_row_props(row, creating=True)
                req("POST", "/pages", token,
                    {"parent": {"database_id": month_db_id}, "properties": props})
                created += 1
        except Exception:  # noqa: BLE001  個別行の失敗は隔離し残りを継続する
            skipped += 1
            continue
    return {"created": created, "updated": updated, "skipped": skipped,
            "deleted": 0, "collapsed_multi_contract": collapsed_multi}


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------

def _resolve_parent(cfg):
    return _norm((cfg.get("notion") or {}).get("report_parent_page"))


def run(rows, target, cfg, token, req=None, *, apply=True):
    """月次 DB find-or-create → 行 upsert を配線する (テスト可能な orchestration 本体)。

    apply=False (dry-run) は network を一切叩かず、計画のみを返す (書き込まない)。
    """
    if not _valid_target(target):
        raise SinkError(f"--target は YYMM (数字4桁・月01-12) を指定してください: {target!r}")
    # target_month cross-check (F-7): C05 が各行に付けた対象月と --target がズレたまま流すと
    # 誤月 DB へ silent 投入され冪等・非破壊ゆえ誤混入が残存する。不一致は fail-closed で拒否。
    _t = _norm(target)
    for r in rows:
        rt = _norm(r.get("target_month") or r.get("target"))
        if rt and rt != _t:
            raise SinkError(
                f"--target={target} と行の target_month={rt} が不一致です。誤った対象月の DB へ "
                "投入するのを防ぐため中止します (C05 の --target-month と C06 の --target を揃えてください)。")
    valid_rows = [r for r in rows if _row_customer(r)]

    if not apply:
        return {
            "created": 0, "updated": 0, "skipped": len(rows) - len(valid_rows), "deleted": 0,
            "month_db_id": None, "month_db_reused": False, "dry_run": True,
            "planned_rows": len(valid_rows),
            "placement": {
                "target_yyyymm": target_to_yyyymm(target),
                "requested_order": "newest-on-top",
                "api_strategy": "append-child-database",
                "report_parent_page": _resolve_parent(cfg),
                "note": "dry-run: 親ページ未走査 (書き込みなし)",
            },
        }

    parent_page = _resolve_parent(cfg)
    if not parent_page:
        raise SinkError(
            "notion.report_parent_page が未設定です。月次 DB を置くページ『請求書発行チェック』の "
            "page_id を mf-kessai-config.default.json または .mf-kessai-config.json に設定してください "
            "(database の親は page_id/database_id のみ・block_id 不可のため、月次 DB は指定ページ直下へ置く)。")

    req = req or _req
    month_db_id, reused, placement = find_or_create_month_db(target, parent_page, token, req, apply=True)
    placement["report_parent_page"] = parent_page  # 親ページ (論理キー) を証跡に載せる
    counts = upsert_report_rows(rows, month_db_id, token, req)
    counts.update({
        "month_db_id": month_db_id,
        "month_db_reused": reused,
        "placement": placement,
        "dry_run": False,
    })
    return counts


def _load_rows(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SinkError(f"--rows は JSON list を指定してください (先頭型={type(data).__name__})")
    return data


def main(argv=None):
    p = argparse.ArgumentParser(
        description="月次発行漏れ比較レポート DB へ分類済みレポート行を非破壊冪等 upsert する sink")
    p.add_argument("--rows", required=True, help="C05 分類済みレポート行 JSON list ファイル")
    p.add_argument("--target", required=True, help="対象月 YYMM (例 2607)")
    p.add_argument("--apply", action="store_true", help="実際に Notion へ書き込む (無指定は dry-run)")
    p.add_argument("--verified", action="store_true",
                   help="二段確認 (dry-run 内訳確認 + mfk-report-verifier) 完了の明示。--apply 時は必須")
    p.add_argument("--config", help="設定 JSON パス (省略時は既定 + ローカル上書き)")
    a = p.parse_args(argv)

    try:
        # 書込ゲートを機械層で担保 (prose でなく exit2): --apply は --verified 必須。
        if a.apply and not a.verified:
            raise SinkError(
                "--apply には --verified が必須です (二段確認=dry-run 内訳確認 + "
                "mfk-report-verifier のゲート)。dry-run で内訳を確認し、二段確認後に "
                "--apply --verified を付けてください。")
        cfg = load_config(a.config)
        rows = _load_rows(a.rows)
        token = None
        if a.apply:
            # token 欠落は fail-closed=exit2 で担保する (F-15)。_notion_token は欠落時 RuntimeError を
            # 投げるが、これを未捕捉のまま素通しすると exit1 (=manifest 上 非致命/部分成功扱い) になり
            # 「何も書けていないのに継続」する。SinkError へ写像して exit2 に統一する。
            try:
                token = _notion_token(cfg)
            except RuntimeError as e:
                raise SinkError(f"Notion トークンが取得できません (fail-closed): {e}")
        result = run(rows, a.target, cfg, token, apply=a.apply)
    except SinkError as e:
        sys.stderr.write(f"[notion_report_sink] {e}\n")
        return 2
    except Exception as e:  # noqa: BLE001
        # apply 中の想定外失敗 (Notion API 拒否・DB 生成拒否等) を
        # exit1 (=manifest 上 非致命/部分成功) へ落とさず fail-closed=exit2 に統一する。write ツールで
        # 「エラーで何も書けていないのに部分成功」の誤認を防ぐ (F-15/F-B の runtime 失敗モード)。
        sys.stderr.write(f"[notion_report_sink] 想定外エラーで中止 (fail-closed): {e}\n")
        return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 部分失敗 (行 skip) があれば exit 1 (fail-soft)。全成功/ dry-run は 0。
    return 1 if result.get("skipped") else 0


if __name__ == "__main__":
    sys.exit(main())
