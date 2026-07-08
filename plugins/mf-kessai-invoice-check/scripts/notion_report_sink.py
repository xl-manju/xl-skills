#!/usr/bin/env python3
# /// script
# name: notion_report_sink
# purpose: 前月↔今月の発行漏れ比較レポートを単一の恒久 DB へ非破壊冪等 upsert する決定論 sink
#          (Design D)。report_toggle_block は歴史的キー名のまま出力先ブロック/見出しとして扱い、
#          トグル内 DB (in-block) または見出し2直下 DB (under-heading) を最優先で更新対象にする。
#          API は block_id 親 DB を『作成』できないが既存 DB の『更新』はできる。既存 DB が無ければ
#          親ページ直下へ新規作成する (page-created)。単一 DB に複数月
#          を保持し、同一 (対象月,取引先,商品) の再実行のみ上書き・以前月の行は削除しない (deleted 0)。
# inputs:
#   - argv: --rows FILE (C05 分類済みレポート行 JSON list) --target YYMM [--apply --verified] [--config PATH]
#   - config: mf-kessai-config.default.json (配布既定) + .mf-kessai-config.json (ローカル上書き) の
#             notion.report_toggle_block (出力先ブロック/見出し) + notion.report_parent_page (新規作成/探索先ページ)
# outputs:
#   - stdout: upsert 結果 JSON {created, updated, skipped, deleted(=0), collapsed_multi_contract,
#             report_db_id, db_location(in-block/under-heading/page/page-created), db_created, placement}
#   - stderr: violation
#   - exit: 0=OK / 1=部分失敗 / 2=fail-closed (target/親ページ未設定・rows 不正)
# contexts: [C, E]
# network: true   # Notion REST (ブロック/ページ子ブロック list + DB 探索/作成/列 PATCH + 行 upsert)。MF へは書かない
# write-scope: notion:report-db-in-toggle (report_toggle_block に紐づく単一恒久レポート DB へ列 PATCH + 行 upsert・既存 DB が無ければ report_parent_page 直下へ)
# dependencies: [notion_transport, build_notion_db, mfk_api]
# requires-python: ">=3.11"
# ///
"""前月↔今月の発行漏れ比較レポートを単一恒久 DB へ非破壊冪等 upsert する決定論 sink (Design D)。

責務 (C06):
  1. **出力先 DB の解決 (指定ブロック/見出し優先・表示名非依存)**: ``report_toggle_block`` がトグル
     ならその中の child_database、プレーン見出し2ならその見出し直下 (次見出しまで) の child_database を
     最優先で更新対象にする。**指定トグル/見出しはこのレポート専用ゆえ、配下 DB は表示名に依存せず
     構造的位置で同定する** (ユーザーが『請求漏れ確認レポート』等どんな名前で手作りしても認識する・
     title 前方一致 _TITLE_PREFIX は同点解消/後方互換のヒントに留める)。無ければ親ページ
     (``report_parent_page``) 直下の既存 report DB (ここは無関係 DB が同居しうるので title 前方一致で
     限定)、どれも無ければ見出しの下 (ページ直下) へ新規作成する。**Notion API は database を block_id
     (トグル) 親で『作成』できないが、UI で作られたトグル内 DB の『更新』(行 upsert・列 PATCH) はできる**
     ため、ユーザーがトグル内に作った DB をそのまま更新できる。既存 DB の title 列名が『取引先名』でなく
     Notion 既定の『名前』等でも、_ensure_db_schema が title 型プロパティの実名を検出し行 upsert が正しい
     列へ書く。db_location (in-block/under-heading/page/page-created) を stdout で開示する。
  2. **8 列スキーマ (列順 SSOT)**: [取引先名(title), 対象月(rich_text/YYYY-MM), 漏れチェック(checkbox),
     商品名(rich_text), 先月の金額(number/yen), 今月の金額(number/yen), 先月と今月の比較(rich_text),
     コメント(rich_text)] をこの左→右順で固定する。title(=各行=ページ名)=取引先名を先頭に置き
     Notion の title 最左固定と定義順を一致させる。**対象月列**は単一 DB で複数月を区別する。既存 DB に
     対象月列が無ければ _ensure_db_schema が PATCH で後付けする (非破壊)。漏れチェックは checkbox
     (正常=✓ / 要対応=☐)。金額は税抜。列型写像は build_notion_db.build_property を再利用する。
  3. **非破壊冪等 upsert**: 単一 DB へレポート行を upsert する。行同定キー = (対象月 YYYY-MM,
     取引先名, 商品名)。同月内の 2/3 営業日目再実行は同一キーで 1 行へ収束させる (重複行 0)。固定列に
     契約IDは永続化しないため、契約ID違いは要対応優先で collapse し collapsed_multi_contract に計上する。
     **非破壊マージ = 以前 run で書いた行も別月の行も今回入力に無くても削除しない** (deleted 常時 0・
     全情報保持・clear-then-insert でない)。手動追記運用は無い前提ゆえ frozen 列は設けない。
  4. **折り返し (wrap)**: 全列の折り返し表示はビュー format 設定で API 非公開ゆえ、placement の
     view_format_note で UI 手順を毎回開示する (列順は properties 定義順で反映できるが wrap/幅は不能)。

設計背景 (Design B/C からの是正):
  当初は『月次スナップショット DB=毎月新規 DB をページ直下へ』(Design B)、次に『ページ直下 DB +
  トグル内 link_to_page 索引』(Design C) を採ったが、実運用でユーザーは Notion UI でトグル内に
  report DB を作って運用しており (API は block_id 親 DB を作成できないだけで更新はできる)、Design B/C は
  そのトグル内 DB を更新せず別 DB を作る乖離があった。Design D は出力先をトグル内 DB へ一本化し、
  複数月を『毎月新規 DB』でなく『単一 DB + 対象月列』で保持することで、API 制約 (block_id 親 DB を
  作れない) と『トグル内に反映』要件を両立する。トグル内に DB が無い新規セットアップ時のみ、見出しの
  下 (ページ直下) へ新規作成し、ユーザーが UI でトグルへドラッグすれば以後は自動更新される。
  全ての API 経路は notion_transport._req 経由で、テストは req 引数に fake-store を差し替えて
  network 非依存で検証する (既存 test_notion_reconcile_sink の offline 契約踏襲)。
"""
import argparse
import json
import os
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

# --- 8 列スキーマ (列順 SSOT: この左→右順で固定する) --------------------------------
# Design D (単一恒久 DB・対象月列で複数月を保持): トグル配下に置いた 1 つの DB を毎回上書き更新
# するため、月をまたいで行が共存する。対象月 (YYYY-MM) 列で月を区別し、以前月の行を非破壊保持する。
PROP_CUSTOMER = "取引先名"                 # title    (= 各行 = ページ名)
PROP_TARGET_MONTH = "対象月"               # rich_text (YYYY-MM・単一 DB で月を区別する)
PROP_MISSING_CHECK = "漏れチェック"       # checkbox (正常=✓チェックあり / 要対応=☐チェックなし)
PROP_PRODUCT = "商品名"                    # rich_text
PROP_PREV_AMOUNT = "先月の金額"            # number(yen)  税抜
PROP_CURR_AMOUNT = "今月の金額"            # number(yen)  税抜
PROP_COMPARISON = "先月と今月の比較"       # rich_text (テキスト説明)
PROP_COMMENT = "コメント"                  # rich_text

# 列順 SSOT の配列。DB 生成時の properties 構築順 = Notion 上の列の左→右順。
# 取引先名 (title) を先頭に置く: Notion は table view で title 列を最左に固定するため、title を
# COLUMN_ORDER 先頭に定義することで「定義順 = 実表示順」を一致させ、列順を確実に設定通りにする
# (title を非先頭に置くと Notion が最左へ引き上げ定義順と表示順がズレる)。対象月を title 直後の
# 2 列目に置き月でグルーピング/フィルタしやすくする。漏れチェック(checkbox)は 3 列目。
COLUMN_ORDER = [
    PROP_CUSTOMER,
    PROP_TARGET_MONTH,
    PROP_MISSING_CHECK,
    PROP_PRODUCT,
    PROP_PREV_AMOUNT,
    PROP_CURR_AMOUNT,
    PROP_COMPARISON,
    PROP_COMMENT,
]

# C05 producer (mfk_period_report.py) が emit する行キー → 本 sink の 8 列への写像 (SEAM SSOT)。
# producer/consumer のキー語彙をここで一元宣言し、seam 断裂 (キー名不一致で列が空になる) を防ぐ。
# _build_row_props はこの producer キー (各値の第一 alias) を読む。ROW_CONTRACT を SSOT として
# 実効化する担保は 2 段: (1) test_row_contract_maps_every_producer_key_to_column が本 dict の
# 各 producer キーを _build_row_props で辿り mapped 列へ着地することを assert し drift を検出する
# (宣言と実装の乖離を機械 fail させる)、(2) test_seam_c05_output_populates_all_seven_columns が
# C05 実出力 → 本 sink を実 pipe で貫通して 8 列全充足を検証する (isolation では捕捉不能)。
ROW_CONTRACT = {
    "gap_check": PROP_MISSING_CHECK,   # 漏れチェック (checkbox: 正常=✓/要対応=☐)
    "customer": PROP_CUSTOMER,         # 取引先名 (title)
    "target_month": PROP_TARGET_MONTH, # 対象月 (YYYY-MM・単一 DB で月を区別)
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
    PROP_TARGET_MONTH: {"type": "rich_text"},
    PROP_PRODUCT: {"type": "rich_text"},
    PROP_PREV_AMOUNT: {"type": "number"},
    PROP_CURR_AMOUNT: {"type": "number"},
    PROP_COMPARISON: {"type": "rich_text"},
    PROP_COMMENT: {"type": "rich_text"},
}

# レポート DB の title 前方一致キー (『請求漏れ比較レポート』で始まる child_database を報告 DB とみなす)。
_TITLE_PREFIX = "請求漏れ比較レポート"

# 折り返し(wrap)/列幅はビュー format 設定で Notion 公開 API (2022-06-28) は操作不能
# (列順は DB 作成時の properties 定義順で既定ビューへ反映できるが、wrap/幅はビュー format ゆえ
# API 非公開=placement の append 制約と同じ能力境界)。placement で UI 手順を毎回開示する SSOT。
_VIEW_FORMAT_NOTE = (
    "全列の折り返し表示 (wrap) はプロパティ(スキーマ)設定でなくビュー表示設定で、"
    "Notion 公開 API では設定できない。Notion UI でこの DB ビューの『…』メニュー→"
    "『すべての列を折り返す (Wrap all columns)』を一度トグルすると以後ビューに永続する。")


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


def _stored_key(target_month, customer, product):
    """単一恒久 DB の既存ページを索引する『回収可能』キー (対象月, 取引先名, 商品名)。

    Design D では 1 つの DB に複数月の行が共存するため、同定キーの先頭に対象月 (YYYY-MM) を含める。
    これにより 2026-06 の行と 2026-07 の行は別行として保持され (非破壊)、同一月・同一取引先・同一
    商品の再実行のみ 1 行へ収束する (月内冪等)。target_month は _norm で正規化する (空は '')。

    固定スキーマは contract_id を persist しないため (property_order に契約ID列なし)、既存ページから
    回収できる同定キーは (対象月, 取引先名, 商品名) に限られる。contract_id は C05 が同定に使う論理
    メタだが本 sink では persist しない (=recoverable でない)。

    設計判断 (記録): 同一対象月・同一取引先・同一商品に契約IDだけ異なる複数契約が同居する場合、
    このキーでは 1 行へ収束する (multi-contract collapse)。多契約×同一商品は稀という前提で
    8 列固定を優先した意思決定であり、collapse 時は要対応を優先保持 (_prefer_action) して
    真の発行漏れが正常行に上書きされる false-negative を防ぐ。collapse 件数は stdout の
    collapsed_multi_contract に計上し常態化を可観測にする (常態化すれば 8 列目 contract_id 追加へ
    の移行トリガ)。

    キーは名寄せ SSOT mfk_reconcile.normalize (NFKC + 敬称/法人格/空白/中黒除去 + lower) で
    正規化する (SKILL Gotcha5)。表示 title は raw のまま・キー算出だけ正規化することで、macOS/MF
    API 由来のカタカナ NFD↔NFC 揺れや全角半角差で同一取引先が別行に割れる (=同月2回実行で重複行が
    出て冪等保証 C7/OUT1 が崩れる) のを防ぐ。新規行キーと既存ページ回収キー (_page_match_key) は
    同じ正規化を通るため索引が一致する。
    """
    return (_norm(target_month), _normalize_name(customer), _normalize_name(product))


def _severity_rank(row):
    """行の漏れチェック severity。要対応(発行漏れ候補)=1 を正常=0 より優先する。"""
    check = _norm(row.get("gap_check") or row.get("check") or row.get("漏れチェック"))
    return 1 if check == "要対応" else 0


# C05 が構造的正常事由 (年契約周期/契約完了/トライアル完了/対象外) で正常化した行の period_diff 標識。
# これらは「バグ由来 false-positive の権威ある訂正」であり、cross-run safe guard が前 run の
# 要対応を無条件保持して打ち消してはならない (例: 金子金物が C05 annual fix 前に 要対応 で
# persist 済みでも、fix 後の 年契約周期 正常化を反映する=elegant-review F-D 是正)。
_STRUCTURAL_NORMAL_MARKERS = ("年契約周期", "契約完了", "トライアル完了", "対象外")


def _is_structural_normal(row):
    """行が構造的正常事由による正常化か (正常 かつ period_diff が上記標識を含む)。

    bare な 正常 (単に今月発行あり等) とは区別する: bare 正常は cross-run guard で前 run の
    要対応を保持するが、構造的正常事由は非請求が正常である積極的根拠ゆえ訂正を許す。
    """
    if _severity_rank(row) != 0:
        return False
    pd = _norm(row.get("period_diff") or row.get("先月と今月の比較") or row.get("comparison"))
    return any(m in pd for m in _STRUCTURAL_NORMAL_MARKERS)


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


def _title_prop_value(props):
    """props から title 型プロパティ値を **列名非依存**で返す (無ければ None)。

    Notion は DB あたり title 列を必ず 1 つだけ持ち、その page プロパティ値 dict のみ "title" キーを
    持つ。ゆえに title 列名が『取引先名』でも Notion 既定の『名前』/『Name』でも同定できる
    (ユーザー手作り DB のタイトル列名ドリフトを吸収する)。
    """
    for v in (props or {}).values():
        if isinstance(v, dict) and "title" in v:
            return v
    return None


def _page_match_key(page):
    """既存ページの properties から _stored_key を回収する (対象月, 取引先名, 商品名)。

    取引先名 (title) は列名非依存で拾う (_title_prop_value)。
    """
    props = page.get("properties") or {}
    return _stored_key(
        _rich_text_plain(props.get(PROP_TARGET_MONTH)),
        _title_plain(_title_prop_value(props)),
        _rich_text_plain(props.get(PROP_PRODUCT)))


def schema_properties():
    """8 列スキーマの Notion properties dict を列順 SSOT の順で構築する。

    dict は挿入順を保持するので COLUMN_ORDER の順に build_property した結果が Notion 上の
    列の左→右順になる (列順固定)。
    """
    return {name: build_property(_COLUMN_SPECS[name]) for name in COLUMN_ORDER}


def _build_row_props(row, target=None, *, creating, title_prop=PROP_CUSTOMER):
    """row を単一恒久 DB の 8 列プロパティ dict へ整形する。

    creating=True (新規 POST) のときだけ title (= 取引先名) を載せる。title_prop は DB の title 列の
    実名 (既定『取引先名』・ユーザー手作り DB では『名前』等でありうるので呼出側が検出した実名を渡す)。
    更新 (PATCH) では title (不変な表示キー) に触れず、入力に無い nullable 事実列は明示クリアして stale を残さない
    (行そのものは削除しない=非破壊マージは行単位で成立)。対象月 (YYYY-MM) は行同定キーの一部
    ゆえ更新でも stale クリアせず、target (呼出側の対象月) or 行の target_month を書く。
    """
    props = {}

    # 対象月 (YYYY-MM): 単一 DB で月を区別する。target (run の --target 由来 YYYY-MM) を優先し、
    # 無ければ行の target_month を YYYY-MM 化して使う。同定キーの一部ゆえ空クリアはしない。
    tm = _norm(target) or _norm(row.get("対象月") or row.get("target_yyyymm"))
    if not tm:
        raw_tm = _norm(row.get("target_month") or row.get("target"))
        tm = target_to_yyyymm(raw_tm) if _valid_target(raw_tm) else raw_tm
    if tm:
        props[PROP_TARGET_MONTH] = _rt(tm)

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
        props[title_prop] = {"title": [{"text": {"content": customer}}]}
    return props


# ---------------------------------------------------------------------------
# 子ブロック取得 (トグル/ページの child_database 探索に使う)
# ---------------------------------------------------------------------------

def list_block_children(block_id, token, req=None):
    """ブロック/ページの子ブロックを has_more/next_cursor を辿り全件取得する。

    GET /blocks/{id}/children は id がページ (page_id) でもブロックでも子を返す
    (ページは自身が 1 つのブロックであり page_id をそのまま渡せる)。Design D の探索/新規作成では
    指定見出しブロック ID または report_parent_page (page_id) を渡す。
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


_HEADING_TYPES = {"heading_1", "heading_2", "heading_3"}


def _is_report_db(block):
    """block が report DB (title が『請求漏れ比較レポート』で始まる child_database) か。

    page-level fallback (無関係 DB が同居しうる親ページ直下・step3) の限定にのみ使う。指定トグル/見出し
    配下 (step1/2) は専用領域ゆえ表示名非依存の _select_report_db で選ぶ。
    """
    return (block.get("type") == "child_database"
            and _child_db_title(block).startswith(_TITLE_PREFIX))


def _select_report_db(db_blocks):
    """指定トグル/見出し配下の child_database ブロック list から report DB の db_id を **表示名非依存**で選ぶ。

    指定トグル/見出しはこのレポート専用の器ゆえ、配下の child_database はその名前が何であれレポート DB と
    みなせる (ユーザーが『請求漏れ確認レポート』等どんな名前で手作りしても認識する=要件『有れば更新』の要)。
    優先順:
      1. title が _TITLE_PREFIX で始まる DB があればそれ (ツール作成 DB・後方互換で最優先=決定論の同点解消)。
      2. 無ければ child_database が配下に 1 つだけならそれを採用 (ユーザー命名 DB)。
      3. 複数あって一意に選べないときは先頭を採るが stderr へ警告する (silent 誤選択を可視化・姉妹
         notion_invoice_sink の ambiguity 安全弁に倣う)。
    child_database が無ければ None。
    """
    if not db_blocks:
        return None
    prefixed = [b for b in db_blocks if _child_db_title(b).startswith(_TITLE_PREFIX)]
    pool = prefixed or db_blocks
    if len(pool) > 1:
        sys.stderr.write(
            "[notion_report_sink] 指定トグル/見出し配下に report DB 候補が複数あります "
            f"(候補数={len(pool)})。先頭を採用しますが、1 つに整理することを推奨します。\n")
    return pool[0].get("id")


def _child_databases_in(container_id, token, req):
    """container (トグル見出し or ページ) 直下の child_database ブロック list を返す。"""
    return [b for b in list_block_children(container_id, token, req)
            if b.get("type") == "child_database"]


def _find_report_db_in(container_id, token, req):
    """親ページ直下 (step3・非スコープ) の report DB を title 前方一致で探し db_id を返す (無ければ None)。

    親ページには無関係な DB が同居しうるので、ここは表示名非依存でなく title 前方一致で限定する
    (トグル/見出し配下の表示名非依存な同定は _select_report_db が担う)。月サフィックス付き
    『… 2026-06』でも prefix 一致で拾う。
    """
    for block in list_block_children(container_id, token, req):
        if _is_report_db(block):
            return block.get("id")
    return None


def _find_report_db_below_heading(page_id, anchor_block_id, token, req):
    """ページ直下で anchor 見出しの直後〜次の見出しまでの区間にある report DB を返す (無ければ None)。

    トグル見出しをプレーン見出しに変えると、配下 DB はページ直下の兄弟 (見出しの下) へ移動する。
    その『見出しの下の DB』を、ページ子ブロックを順に辿り anchor の後ろから次セクション見出しの
    手前までの区間の child_database として集め、表示名非依存で選ぶ (_select_report_db)。この区間
    限定により、ページ上に別の report DB (旧重複等) があってもこの見出しに属する DB だけを拾える。
    """
    children = list_block_children(page_id, token, req)
    ids = [b.get("id") for b in children]
    if anchor_block_id not in ids:
        return None
    region = []
    for block in children[ids.index(anchor_block_id) + 1:]:
        if block.get("type") in _HEADING_TYPES:
            break  # 次セクション見出しに入った=この見出しの範囲外 → 打ち切り
        if block.get("type") == "child_database":
            region.append(block)
    return _select_report_db(region)


def _detect_title_prop(properties):
    """DB properties dict から title 型プロパティの実名を返す (無ければ既定 PROP_CUSTOMER)。

    Notion は DB あたり title 列を必ず 1 つ持つ。ツール作成 DB では『取引先名』だが、ユーザーが UI で
    手作りした DB は既定の『名前』/『Name』でありうる。その実名を検出して行 upsert の title 書込先に使う。
    判定は spec の "title" キー有無を主とする — GET /databases (実 Notion) の property は
    {"type":"title","title":{}}、build_property 生成物は {"title":{}} で、いずれも "title" キーを持つため
    両形式に忠実 (type だけを見ると build_property 形に type が無く取りこぼす)。
    """
    for name, spec in (properties or {}).items():
        if isinstance(spec, dict) and ("title" in spec or spec.get("type") == "title"):
            return name
    return PROP_CUSTOMER


def _ensure_db_schema(db_id, token, req):
    """既存 DB に不足プロパティ (特に 対象月) を PATCH で追加する (非破壊)。返り値=(追加列名 list, title列実名)。

    UI 手動作成 DB や旧 7 列スキーマ DB を単一恒久 DB 契約 (対象月を含む列) へ寄せる。既存プロパティは
    触らず、COLUMN_ORDER のうち DB に無い**非 title** 列だけを追加する (title 列は既存 DB に必ず在り、
    DB は title を 1 つしか持てないため追加対象から除く)。同時に GET したスキーマから title 列の実名
    (『取引先名』/『名前』等) を検出し返す — 行 upsert が title を正しい列名で書けるようにする。
    """
    db = req("GET", f"/databases/{db_id}", token)
    properties = db.get("properties") or {}
    have = set(properties.keys())
    title_prop = _detect_title_prop(properties)
    add_props = {name: build_property(_COLUMN_SPECS[name])
                 for name in COLUMN_ORDER if name not in have and name != PROP_CUSTOMER}
    if add_props:
        req("PATCH", f"/databases/{db_id}", token, {"properties": add_props})
    return list(add_props.keys()), title_prop


def resolve_report_db(anchor_block_id, parent_page_id, token, req=None, *, apply=True):
    """単一恒久レポート DB を解決する (Design D)。返り値 (db_id, location, created, placement)。

    anchor_block_id = config の report_toggle_block。**トグル見出しでもプレーン見出し2でも受ける**
    (ユーザーがトグル→見出し2 に変えても対応する)。出力先の優先順:
      1. **anchor の子の report DB** = anchor がトグル見出し (is_toggleable=true) で DB を配下に持つ場合。
         API は block_id 親 DB を『作成』できないが既存 DB の『更新』(行 upsert・列 PATCH) はできる。
         location='in-block'。
      2. **anchor 見出しの直下 (ページ兄弟) の report DB** = anchor がプレーン見出しで、配下 DB が
         ページ直下の『見出しの下』へ移動している場合 (トグル→見出し2 変換時の実状態)。次セクション
         見出しの手前までで探し、ページ上の別 report DB (旧重複等) と区別する。location='under-heading'。
      3. **ページ直下の任意の既存 report DB** (どの見出しにも紐づかない既存)。location='page'。
      4. どれも無く apply=True なら **見出しの下 (ページ直下) へ新規作成**。location='page-created'。
      5. dry-run で未発見なら (None, 'none', False)。
    見つかった/作った DB は 対象月 列を含むスキーマへ揃える (_ensure_db_schema・apply 時のみ)。単一 DB
    に複数月を保持し、同一 (対象月,取引先,商品) の再実行のみ上書き=非破壊冪等。
    """
    req = req or _req
    placement = {
        "report_anchor_block": anchor_block_id,
        "report_parent_page": parent_page_id,
        "column_order_defined": list(COLUMN_ORDER),
        "view_format_note": _VIEW_FORMAT_NOTE,
        "wrap_all_columns_via_api": False,
    }

    def _resolved(db_id, location, note):
        # apply=True のときだけスキーマ列を PATCH で補い title 列実名を検出する
        # (dry-run は読み取り専用=列追加せず title 列は既定名を仮定)。
        if apply:
            schema_added, title_prop = _ensure_db_schema(db_id, token, req)
        else:
            schema_added, title_prop = [], PROP_CUSTOMER
        placement.update({"location": location, "created": False,
                          "schema_added": schema_added, "title_prop": title_prop,
                          "note": note})
        return db_id, location, False, placement

    # 1. anchor (トグル見出し) の子の report DB (表示名非依存・指定トグルはレポート専用)。
    db_id = (_select_report_db(_child_databases_in(anchor_block_id, token, req))
             if anchor_block_id else None)
    if db_id:
        return _resolved(db_id, "in-block",
                         "指定見出し (トグル) 配下の既存 DB を表示名非依存で更新対象にする (単一恒久 DB・対象月列で複数月を非破壊保持)")

    # 2. anchor 見出しの直下 (ページ兄弟) の report DB (トグル→プレーン見出し変換後の実配置)。
    db_id = (_find_report_db_below_heading(parent_page_id, anchor_block_id, token, req)
             if anchor_block_id else None)
    if db_id:
        return _resolved(db_id, "under-heading",
                         "指定見出しの直下 (ページ兄弟) の既存 DB を更新対象にする (見出しの下=次セクションまでで同定・重複 DB と区別)")

    # 3. ページ直下の任意の既存 report DB。
    db_id = _find_report_db_in(parent_page_id, token, req)
    if db_id:
        return _resolved(db_id, "page",
                         "指定見出しの直下には無く、ページ直下の既存 report DB を更新対象にする (見出しの下に置きたい場合は Notion UI で見出し直後へ移動)")

    # 4/5. 新規作成 (API は block_id 親 DB を作れないため見出しの下=ページ直下へ作る)。
    if not apply:
        placement.update({"location": "none", "created": False,
                          "note": "dry-run: 既存 report DB 未発見 (apply 時は見出しの下=ページ直下へ新規作成)"})
        return None, "none", False, placement

    res = req("POST", "/databases", token, {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"text": {"content": _TITLE_PREFIX}}],
        "properties": schema_properties(),
    })
    placement.update({
        "location": "page-created", "created": True, "schema_added": list(COLUMN_ORDER),
        "title_prop": PROP_CUSTOMER,   # ツール作成 DB の title 列は schema_properties で『取引先名』
        "note": ("既存 report DB が無かったため見出しの下 (ページ直下) へ新規作成した (API は database を "
                 "block_id=見出し親で作れないため=トグル内に直接は作れない)。**初回のみ Notion UI で "
                 "この DB を指定トグル/見出しの直下へドラッグ移動**すれば、以後 in-block/under-heading "
                 "で表示名に関係なく自動更新される")})
    return res["id"], "page-created", True, placement


# ---------------------------------------------------------------------------
# 行 upsert (非破壊冪等)
# ---------------------------------------------------------------------------

def query_month(report_db_id, token, req=None):
    """単一恒久 report DB の全行を has_more/next_cursor を辿り取得し page_id で dedup する。

    Design D では同じ DB に複数月が共存するため、この query は全月の行を返す。呼び出し側は
    _page_match_key の対象月を含むキーで同月だけを更新対象にする。
    """
    req = req or _req
    out = {}
    cursor = None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        res = req("POST", f"/databases/{report_db_id}/query", token, body)
        for page in res.get("results", []):
            pid = page.get("id")
            if pid and pid not in out:
                out[pid] = page
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return list(out.values())


def upsert_report_rows(rows, report_db_id, target, token, req=None, *, title_prop=PROP_CUSTOMER):
    """rows を単一恒久 DB へ **非破壊冪等** upsert する。返り値 {created, updated, skipped, deleted}。

    target = 対象月 YYMM (この run が書く月)。行同定キーは (対象月 YYYY-MM, 取引先名, 商品名) で、
    別の月の行 (以前 run) は同キーに衝突しないため非破壊で共存する (単一 DB に複数月を保持)。
    title_prop = DB の title 列の実名 (既定『取引先名』・ユーザー手作り DB は『名前』等)。新規行 POST の
    title 書込先に使う (既定のままだとツール作成 DB の列名前提で、手作り DB は全行 skip になるのを防ぐ)。

    手順:
      1. query_month で DB 全行を取得し _page_match_key (対象月, 取引先名, 商品名) で索引化する。
      2. 入力 rows を _stored_key で収束させる (同月 2/3 営業日目の同一行再投入は 1 件に畳む・
         最後の値を採用)。取引先名が空の行は skip する (title=取引先名 が必須)。
      3. 既存行あり → PATCH 更新 (title は送らない)。無し → POST 新規作成。
      4. **削除はしない** (今回入力に無い既存行も・別月の行も残す=非破壊マージ・deleted 常時 0)。
      5. 各行は try/except で隔離し個別失敗は skipped に計上して継続する。
    """
    req = req or _req
    target_yyyymm = target_to_yyyymm(target) if _valid_target(target) else _norm(target)
    existing = query_month(report_db_id, token, req)
    index = {}
    migrate_fallback = {}   # (取引先名, 商品名) -> 対象月が空の既存行 (旧 DB/手作り DB 移行時の backfill 用)
    for page in existing:
        key = _page_match_key(page)   # (対象月, 取引先名, 商品名)
        if not key[1]:                # title (取引先名) がある行のみ対象
            continue
        if key[0]:                    # 対象月あり=通常の同定キーで索引
            index.setdefault(key, page)
        else:                         # 対象月が空=旧 DB/手作り DB の未 backfill 行。当月行の照合先候補にする
            migrate_fallback.setdefault((key[1], key[2]), page)

    created = updated = skipped = collapsed_multi = 0
    collapsed = {}
    for row in rows:
        customer = _row_customer(row)
        if not customer:
            skipped += 1
            sys.stderr.write("[notion_report_sink] 取引先名 (title) が空の行を skip しました\n")
            continue
        key = _stored_key(target_yyyymm, customer, _row_product(row))
        prev = collapsed.get(key)
        if prev is None:
            collapsed[key] = row
            continue
        # 同一 (対象月,取引先,商品) 衝突。契約IDが異なる複数契約なら multi-contract collapse を計上し、
        # 要対応を優先保持して漏れ隠蔽 (false-negative) を防ぐ (F-α safe guard)。
        if _row_contract_id(prev) != _row_contract_id(row):
            collapsed_multi += 1
            sys.stderr.write(
                "[notion_report_sink] 同一(取引先,商品)に契約ID違いの複数契約を検出。"
                f"固定列に契約ID列が無いため1行へ収束し要対応を優先保持: {key}\n")
        collapsed[key] = _prefer_action(prev, row)

    for key, row in collapsed.items():
        try:
            page = index.get(key)
            if page is None:
                # 対象月が空の既存行 (旧 DB/手作り DB からの移行) を当月行として backfill 更新し、
                # 同一 (取引先,商品) の二重作成を防ぐ (update が対象月列を書き込み以後は通常キーで一致)。
                # pop で 1 行につき 1 回だけ採用 (複数当月行が同じ空行を奪い合わないようにする)。
                page = migrate_fallback.pop((key[1], key[2]), None)
            if page is not None:
                props = _build_row_props(row, target_yyyymm, creating=False)
                # cross-run safe guard (F-2): 前 run で立てた要対応を新 run の正常で無条件に
                # 下げると前日フラグした漏れが消える (false-negative)。既存ページが要対応で新行が
                # 正常なら漏れチェックを要対応のまま保持し、正常化した旨を comment へ注記する
                # (intra-run の _prefer_action と cross-run を対称化)。
                if _page_gap_check(page) == "要対応" and _severity_rank(row) == 0:
                    if _is_structural_normal(row):
                        # 構造的正常事由 (年契約周期/契約完了等) は権威ある訂正ゆえ guard を bypass し
                        # 正常へ更新する (C05 annual fix を cross-run guard が打ち消さない・F-D)。
                        # props の checkbox は _build_row_props で既に True (正常) が入っている。
                        _append_comment(
                            props, "前 run の要対応を構造的正常事由で訂正 (年契約/契約完了等・cross-run override)")
                    else:
                        props[PROP_MISSING_CHECK] = {"checkbox": False}  # 要対応を保持 (☐ チェックなし)
                        _append_comment(props, "前 run の要対応を保持 (今 run 入力は正常・cross-run safe guard)")
                req("PATCH", f"/pages/{page['id']}", token, {"properties": props})
                updated += 1
            else:
                props = _build_row_props(row, target_yyyymm, creating=True, title_prop=title_prop)
                req("POST", "/pages", token,
                    {"parent": {"database_id": report_db_id}, "properties": props})
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


def _resolve_toggle(cfg):
    """report_toggle_block (Design D: 出力先 report DB を紐づける指定見出し) の block_id。

    キー名は歴史的に toggle だが、トグル見出しでもプレーン見出し2でも受ける。
    """
    return _norm((cfg.get("notion") or {}).get("report_toggle_block"))


def run(rows, target, cfg, token, req=None, *, apply=True):
    """単一恒久 report DB 解決 → 行 upsert を配線する (テスト可能な orchestration 本体)。

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

    parent_page = _resolve_parent(cfg)
    toggle_block = _resolve_toggle(cfg)

    if not apply:
        return {
            "created": 0, "updated": 0, "skipped": len(rows) - len(valid_rows), "deleted": 0,
            "report_db_id": None, "db_location": None, "db_created": False, "dry_run": True,
            "planned_rows": len(valid_rows),
            "placement": {
                "target_yyyymm": target_to_yyyymm(target),
                "report_parent_page": parent_page,
                "report_toggle_block": toggle_block,
                "column_order_defined": list(COLUMN_ORDER),
                "view_format_note": _VIEW_FORMAT_NOTE,     # dry-run でも折り返し UI 手順を開示
                "wrap_all_columns_via_api": False,
                "note": ("dry-run (書き込みなし)。apply 時の出力先: 指定トグル内の既存 DB があれば更新 / "
                         "無ければ見出しの下 (ページ直下) の既存 DB / どちらも無ければ見出しの下へ新規作成 "
                         "(単一恒久 DB・対象月列で複数月を非破壊保持)"),
            },
        }

    if not parent_page:
        raise SinkError(
            "notion.report_parent_page が未設定です。レポート DB を置く/探すページ『請求書発行チェック』の "
            "page_id を mf-kessai-config.default.json または .mf-kessai-config.json に設定してください "
            "(トグル内に DB が無いときの新規作成先=見出しの下=このページ直下)。")

    req = req or _req
    report_db_id, location, created, placement = resolve_report_db(
        toggle_block, parent_page, token, req, apply=True)
    placement["target_yyyymm"] = target_to_yyyymm(target)
    counts = upsert_report_rows(rows, report_db_id, target, token, req,
                                title_prop=placement.get("title_prop", PROP_CUSTOMER))

    counts.update({
        "report_db_id": report_db_id,
        "db_location": location,        # in-block / under-heading / page / page-created
        "db_created": created,
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
