#!/usr/bin/env python3
# /// script
# name: reconcile_invoices
# purpose: 月次1コマンド orchestrator。請求確認シート→契約マスタ同期→MF照合→DB2非破壊upsert を
#          対象月指定で一気通貫実行する。既存 lib (sheet_to_master / mfk_reconcile /
#          notion_reconcile_sink / mfk_api / notion_transport) を配線するだけの薄い指揮層。
# inputs:
#   - argv: --target YYMM [--apply] [--steps ...] [--sheet-db/--db1/--db2] [--config]
#   - config: .mf-kessai-config.json (notion.sheet_db_id / reconcile_db1_id / reconcile_db2_id)
# outputs:
#   - stdout: 各 step の件数・判定内訳サマリ
#   - exit: 0=OK / 2=fail-closed (target/DB id 欠落・依存違反)
# contexts: [C, E]
# network: true   # MF掛け払い GET (参照専用) + Notion REST (read + apply時のみ write)
# write-scope: notion(DB1 契約マスタ / DB2 月次チェック) ※ --apply 時のみ。MF は参照のみ
# dependencies: [sheet_to_master, mfk_reconcile, notion_reconcile_sink, mfk_api, notion_transport]
# requires-python: ">=3.11"
# ///
"""月次照合 orchestrator (請求確認シート → 契約マスタ → MF照合 → 月次チェックDB)。

本スクリプトは **新しい業務ロジックを持たない**。確定済み・テスト済みの純関数 lib を
対象月指定で順に呼び出して配線するだけの指揮層 (二層分離: 再現性は lib/lint/test が担保し、
ここは I/O の orchestration に徹する)。

フロー (canonical 実行順):
  collect      : MF掛け払いを対象月で参照取得 (GET 専用) → raw mf → build_mf_index。
                 sync-master の支払サイクル推定シグナル + reconcile の名寄せ実績の双方に使う。
  sync-master  : 請求確認シート (sheet_db) 全行を query (page_id dedup) → build_contracts
                 (mf シグナルでサイクル推定) → (--apply) upsert_master(db1) 冪等。
  reconcile    : build_contracts 結果 × mf_index で reconcile → 順方向 rows + 逆方向 orphans。
  sink         : 各 row に contract_page_id を解決 (--apply 時 DB1 を query して 契約ID→page_id)
                 → sink row へ整形 → (--apply) upsert_monthly(db2) 履歴非破壊。

設計上の実行順の注記: collect を sync-master より先に走らせる。build_contracts は MF 実績
シグナル (分割注記 / 利用料の年額一括 vs 月次) で支払サイクルを推定するため、シグナルが
無い (mf_index=None) と DB1 の支払サイクル列が劣化し reconcile の判定精度が落ちる。よって
両方が active なときは必ず MF を先に取得して build_contracts へ渡す (collect 単独・
sync-master 単独でも安全に動く)。

安全弁 (fail-closed):
  - --target 未指定 / YYMM 不正 → exit 2。
  - active step が要求する DB id が解決できない → exit 2 (どの id が欠落かを明示)。
  - step 依存違反 (reconcile に sync-master+collect が無い / sink に reconcile が無い) → exit 2。
  - 既定は dry-run (集計サマリのみ・書き込みゼロ)。sink を含む --apply は --verified を要求する。
  - MF API は GET のみ (本 orchestrator から POST/PATCH/DELETE は一切発行しない)。
  - Notion 書き込みは全て notion_transport._req 経由 (書き込み系レート間隔 MFK_NOTION_WRITE_GAP)。
"""
import argparse
import calendar
import json
import os
import re
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "lib"))

import mfk_api  # noqa: E402
import mfk_reconcile  # noqa: E402
import notion_reconcile_sink  # noqa: E402
import notion_sheet_writeback  # noqa: E402
import notion_transport  # noqa: E402
import sheet_to_master  # noqa: E402

ALL_STEPS = ("collect", "sync-master", "reconcile", "sink")

# 請求確認シート (sheet_db) の列名 → build_contracts が読む行キー (SSOT は sheet_to_master)。
SHEET_FIELDS = ("取引先", "商品", "確認内容", "契約開始日", "契約終了月")


# ---------------------------------------------------------------------------
# 設定 / DB id 解決 (fail-closed)
# ---------------------------------------------------------------------------
def _find_local_config(start_dir):
    """start_dir から親方向へ `.mf-kessai-config.json` を探索する (見つからなければ None)。"""
    d = os.path.abspath(start_dir)
    while True:
        cand = os.path.join(d, ".mf-kessai-config.json")
        if os.path.exists(cand):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def load_orchestrator_config(explicit_path=None):
    """配布既定 (mf-kessai-config.default.json) + ローカル上書きを 2 層で読む。

    ローカルは明示 path > plugin ルートから親探索した `.mf-kessai-config.json`。空文字は
    既定を上書きしない (mfk_api._deep_merge と同一規則)。
    """
    cfg = {}
    default_path = os.path.join(_PLUGIN_ROOT, "mf-kessai-config.default.json")
    if os.path.exists(default_path):
        with open(default_path, encoding="utf-8") as f:
            cfg = json.load(f)
    local = explicit_path or _find_local_config(_PLUGIN_ROOT)
    if local and os.path.exists(local):
        with open(local, encoding="utf-8") as f:
            cfg = mfk_api._deep_merge(cfg, json.load(f))
    return cfg


def resolve_db_ids(cfg, args):
    """DB id を 引数 > 環境変数 > config(notion.*) の順で解決する (空欄は未設定扱い)。"""
    notion = cfg.get("notion") or {}

    def pick(arg_val, env_name, cfg_key):
        return (arg_val or os.environ.get(env_name) or notion.get(cfg_key) or "").strip()

    return (
        pick(args.sheet_db, "MFK_SHEET_DB_ID", "sheet_db_id"),
        pick(args.db1, "MFK_RECONCILE_DB1_ID", "reconcile_db1_id"),
        pick(args.db2, "MFK_RECONCILE_DB2_ID", "reconcile_db2_id"),
    )


def required_db_ids(steps, apply):
    """active step 集合が必要とする DB id 種別を返す (apply 依存)。

    sync-master : sheet_db (シート読取・dry-run でも必須)。db1 (契約マスタ upsert)
                  は --apply 時のみ — dry-run の sync-master は query_sheet_rows +
                  build_contracts のみで DB1 に書かない (run() L344-361 参照)。
    sink        : db1 (契約ID→page_id query) + db2 (月次チェック upsert) は --apply
                  時のみ — dry-run の sink は page_id 未解決・書込ゼロで DB を触らない
                  (run() L380-397 参照)。
    collect / reconcile : Notion DB id を要さない (MF API / 純関数。reconcile の
                  シート再読取は sync-master が要求する sheet_db に含まれる)。

    dry-run で db1/db2 まで要求すると、書き込みゼロの判定内訳を見るだけでも 3 DB の
    配線を強制し起動できない過剰制約になる。実際に DB を触る --apply 時のみ要求する。
    """
    need = set()
    if "sync-master" in steps:
        need |= {"sheet_db"}
        if apply:
            need |= {"db1"}
    if "sink" in steps and apply:
        need |= {"db1", "db2"}
    return need


# ---------------------------------------------------------------------------
# Notion 読み取りヘルパ (請求確認シート行の抽出)
# ---------------------------------------------------------------------------
def _prop_to_text(prop):
    """Notion property を素のテキストへ落とす (title/rich_text/select/date/number/checkbox)。"""
    if not isinstance(prop, dict):
        return ""
    for kind in ("title", "rich_text"):
        if kind in prop:
            return "".join(
                (rt.get("text") or {}).get("content") or rt.get("plain_text") or ""
                for rt in (prop.get(kind) or [])
            )
    if "select" in prop:
        return ((prop.get("select") or {}).get("name")) or ""
    if "date" in prop:
        return ((prop.get("date") or {}).get("start")) or ""
    if "number" in prop:
        n = prop.get("number")
        return "" if n is None else str(n)
    return ""


def _extract_sheet_row(page):
    """Notion ページを build_contracts が読む請求確認シート行 dict へ変換する。"""
    props = page.get("properties") or {}
    row = {field: _prop_to_text(props.get(field)) for field in SHEET_FIELDS}
    row["page_id"] = page.get("id")
    return row


def query_sheet_rows(sheet_db, token, req, target_ym=None):
    """請求確認シート DB を query し page_id dedup。target_ym 指定時は当月(年月)のみ取得。

    月次照合は対象月のシート行のみが期待集合。全月を渡すと同一契約の複数月行が
    期待明細数に積算され誤 REVIEW_QTY_MISMATCH を生むため、当月にスコープする。
    """
    seen = set()
    rows = []
    cursor = None
    while True:
        body = {"page_size": 100}
        if target_ym:
            body["filter"] = {"property": "年月", "select": {"equals": target_ym}}
        if cursor:
            body["start_cursor"] = cursor
        res = req("POST", f"/databases/{sheet_db}/query", token, body)
        for page in res.get("results", []):
            pid = page.get("id")
            if pid in seen:
                continue
            seen.add(pid)
            rows.append(_extract_sheet_row(page))
        if not res.get("has_more"):
            break
        cursor = res.get("next_cursor")
    return rows


# ---------------------------------------------------------------------------
# MF 取得 (参照専用 GET) → raw mf JSON
# ---------------------------------------------------------------------------
def _month_range_iso(target_ym):
    """YYMM ('2606') → MF取得用 issue_date 窓 (issue_date_from, issue_date_to)。

    月帰属は **取引日 (transaction.date, 月末締め) 基準**。当月取引分 (例 6月分=取引日
    2026/06/30) の請求書は翌月月初に発行される (発行日=翌月) ため、issue_date を当月内に
    絞ると当月取引分を取りこぼす。よって取得窓を [当月初 .. 翌月末] へ広げて over-fetch し、
    collect_mf が transaction.date で当月取引分のみへ厳格フィルタする (帰属確定は取引日)。
    """
    year = 2000 + int(target_ym[:2])
    month = int(target_ym[2:])
    first = f"{year:04d}-{month:02d}-01"
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    nlast = calendar.monthrange(ny, nm)[1]
    return first, f"{ny:04d}-{nm:02d}-{nlast:02d}"


def _iso_to_ym(iso_date):
    """ISO 日付 (YYYY-MM-DD / YYYY-MM) → YYMM ('2606')。空/不正は None。"""
    m = re.match(r"\s*(\d{4})-(\d{2})", str(iso_date or ""))
    if not m:
        return None
    return f"{int(m.group(1)) % 100:02d}{m.group(2)}"


def _resolve_customer_names(customer_ids, cfg):
    """/customers?ids= を 200 件ずつ叩いて {customer_id: name} を返す (GET 専用)。"""
    names = {}
    ids = [c for c in customer_ids if c]
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        data = mfk_api.get("/customers", {"ids": chunk, "limit": 200}, cfg=cfg)
        for c in data.get("items", []):
            names[c.get("id")] = c.get("name", "")
    return names


def collect_mf(target_ym, cfg):
    """対象月の MF掛け払い発行実績を raw mf JSON へ畳む (参照専用・副作用なし)。

    返り値 = {"customers": {customer_id: {"name", "lines": [{desc, amount, unit_price, qty,
    billing_id, txn_date}]}}}。build_mf_index / build_contracts の双方が消費する形。

    月帰属は **取引日 (transaction.date, 月末締め) 基準**。issue_date 窓を [当月初 .. 翌月末]
    へ広げて /billings/qualified (status=invoice_issued) を over-fetch し、各 billing の
    /transactions を取得して **transaction.date が当月 (target_ym) の取引のみ** を line 化する
    (当月分=取引日6/30・発行7月 を捕捉し、前月分=取引日5/31・発行6月 を除外する)。
    transaction.date が欠落する場合のみ transaction.issue_date → billing.issue_date の順へ
    縮退する。この場合だけ発行日基準となるため、当月取引でも date 欠落かつ翌月発行だと翌月へ
    帰属し当月集合から外れうる (縮退は取りこぼしを防ぐ向きとは限らない)。縮退が起きた件数は
    stderr に1行警告する (silent ではなく可視化。FAIL にはしない)。
    """
    first, last = _month_range_iso(target_ym)
    billings = list(mfk_api.iter_all(
        "/billings/qualified",
        {"issue_date_from": first, "issue_date_to": last, "status": "invoice_issued"},
        cfg=cfg,
    ))
    customers = {}
    fallback_count = 0
    for b in billings:
        cid = b.get("customer_id")
        bid = b.get("id")
        if not cid:
            continue
        for t in mfk_api.iter_all("/transactions", {"billing_id": bid}, cfg=cfg):
            # 月帰属 = 取引日。date 欠落時のみ発行日基準へ縮退 (当月取引が翌月へ帰属しうる)。
            txn_ym = _iso_to_ym(t.get("date"))
            if txn_ym is None:
                fallback_count += 1
                txn_ym = _iso_to_ym(t.get("issue_date")) or _iso_to_ym(b.get("issue_date"))
            if txn_ym is not None and txn_ym != target_ym:
                continue
            entry = customers.setdefault(cid, {"name": None, "lines": []})
            for d in t.get("transaction_details", []):
                entry["lines"].append({
                    "desc": d.get("description"),
                    "amount": d.get("amount"),
                    "unit_price": d.get("unit_price"),
                    "qty": d.get("quantity"),
                    "billing_id": bid,
                    "txn_date": t.get("date"),
                })
    if fallback_count:
        sys.stderr.write(
            f"[collect] 警告: {target_ym} で transaction.date 欠落により発行日基準へ縮退した取引 "
            f"{fallback_count}件 (当月取引が翌月へ帰属し当月集合から外れる恐れ)。\n")
    names = _resolve_customer_names(customers.keys(), cfg)
    for cid, entry in customers.items():
        entry["name"] = names.get(cid) or cid
    return {"customers": customers}


# ---------------------------------------------------------------------------
# reconcile 行 → DB2 sink 行 への橋渡し (loader)
# ---------------------------------------------------------------------------
def _ev(evidence, key):
    return evidence.get(key) if isinstance(evidence, dict) else None


def build_sink_rows(result, page_id_by_cid):
    """reconcile 結果 (順方向 rows + 逆方向 orphans) を notion_reconcile_sink が読む行へ整形。

    順方向: contract_id=契約ID, contract_page_id=DB1 page_id (解決済みマップから), 期待金額=
    現行単価, 突合金額=evidence.amount, 期待件数/MF供給件数 (数量差降格時), judge_label は
    verdict-mapping.json (SSOT) で導出。orphan: relation 無し・mf_customer_id を自然キーに。
    """
    mapping = mfk_reconcile.load_verdict_mapping()
    if not mapping:
        raise RuntimeError("verdict-mapping.json could not be loaded")
    sink_rows = []
    for row in result.get("rows", []):
        verdict = row.get("verdict")
        cid = row.get("契約ID")
        evidence = row.get("evidence")
        sink_rows.append({
            "direction": row.get("direction") or "順方向",
            "contract_id": cid,
            "contract_page_id": page_id_by_cid.get(cid),
            "mf_customer_id": row.get("MF顧客ID"),
            "judge_label": mfk_reconcile.judge_label(verdict, mapping),
            "expected_amount": row.get("現行単価"),
            "matched_amount": _ev(evidence, "amount"),
            "expected_count": row.get("_expected") or row.get("期待明細数"),
            "supply_count": row.get("_supply"),
            "ai_check": mfk_reconcile.is_check_verdict(verdict, mapping),
            "mf_billing_id": _ev(evidence, "billing_id"),
            "warning": row.get("warning") or "",
        })
    for orphan in result.get("orphans", []):
        services = orphan.get("services") or []
        rep = max(services, key=lambda s: s.get("amount") or 0) if services else {}
        sink_rows.append({
            "direction": orphan.get("direction") or "逆方向orphan",
            "contract_id": None,
            "contract_page_id": None,
            "mf_customer_id": orphan.get("MF顧客ID"),
            "judge_label": mfk_reconcile.judge_label(orphan.get("verdict"), mapping),
            "matched_amount": orphan.get("amount"),
            "ai_check": mfk_reconcile.is_check_verdict(orphan.get("verdict"), mapping),
            "mf_billing_id": rep.get("billing_id"),
            "warning": orphan.get("warning") or "",
        })
    return sink_rows


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------
def _validate_target(target):
    return bool(target) and bool(re.fullmatch(r"\d{4}", target)) and 1 <= int(target[2:]) <= 12


def _parse_steps(raw):
    """--steps をパースして検証済み set を返す (不正なら ValueError)。"""
    if not raw:
        return set(ALL_STEPS)
    steps = {s.strip() for s in raw.split(",") if s.strip()}
    unknown = steps - set(ALL_STEPS)
    if unknown:
        raise ValueError(f"未知の step: {sorted(unknown)} (有効: {list(ALL_STEPS)})")
    if "reconcile" in steps and not {"sync-master", "collect"} <= steps:
        raise ValueError("reconcile には sync-master と collect が必要です")
    if "sink" in steps and "reconcile" not in steps:
        raise ValueError("sink には reconcile が必要です")
    return steps


def run(target, steps, apply, sheet_db, db1, db2, cfg):
    """active step を canonical 順で実行し各 step のサマリを stdout へ出す。"""
    mode = "APPLY (実書き込み)" if apply else "DRY-RUN (集計のみ・書き込みなし)"
    print(f"== 月次照合 orchestrator target={target} steps={sorted(steps)} mode={mode} ==")

    token = notion_transport._notion_token() if _needs_notion(steps, apply) else None
    fatal_apply_failure = False

    mf_raw = None
    mf_index = None
    if "collect" in steps:
        mf_raw = collect_mf(target, cfg)
        mf_index = mfk_reconcile.build_mf_index(mf_raw)
        lines = sum(len(c["lines"]) for c in mf_raw["customers"].values())
        print(f"[collect] MF顧客 {len(mf_raw['customers'])}社 / 明細 {lines}行 を取得 (参照専用GET)")

    contracts = None
    if "sync-master" in steps:
        sheet_rows = query_sheet_rows(sheet_db, token, notion_transport._req, target)
        contracts = sheet_to_master.build_contracts(
            sheet_rows, mf_index=mf_raw, target_ym=target)
        print(f"[sync-master] シート {len(sheet_rows)}行 → 契約 {len(contracts)}件 を生成")
        if apply:
            r = sheet_to_master.upsert_master(
                contracts, db1, token, req=notion_transport._req)
            print(f"[sync-master] DB1 upsert: created={r['created']} "
                  f"updated={r['updated']} failed={len(r['failed'])}")
            # 個別失敗は握りつぶさず必ず可視化する (silent cap 禁止: 1 件の欠損で
            # 契約マスタが不完全になり後段の発行漏れ判定が崩れるため)。
            for f in r["failed"]:
                sys.stderr.write(
                    f"[sync-master] DB1 失敗: 契約ID={f.get('契約ID')!r} "
                    f"error={f.get('error')}\n")
            if r["failed"]:
                fatal_apply_failure = True

    result = None
    if "reconcile" in steps:
        result = mfk_reconcile.reconcile(contracts, mf_index, target)
        # 順方向(期待/GAP/MATCH/QTY)は当月契約。orphan名寄せのみ全月契約で行い、
        # 年間前払い等で当月シートに無いが他月に登録済みの継続契約を誤 orphan しない。
        all_rows = query_sheet_rows(sheet_db, token, notion_transport._req)
        contracts_all = sheet_to_master.build_contracts(
            all_rows, mf_index=mf_raw, target_ym=target)
        result["orphans"] = mfk_reconcile.detect_orphans(contracts_all, mf_index, target)
        summ = dict(Counter(r.get("verdict") for r in result["rows"]))
        summ["ORPHAN"] = len(result["orphans"])
        result["summary"] = summ
        print(f"[reconcile] 順方向 {len(result['rows'])}行 / 逆方向orphan "
              f"{len(result['orphans'])}件")
        for verdict, n in sorted(result["summary"].items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"    {verdict}: {n}")
        # 健全性検知 (read-only): 確認内容に終了根拠が無いのに契約終了月が入っている行を月次
        # フローで可視化する。検知のみで列クリア(write)は行わず clear_unsupported_end_dates.py
        # --apply へ委譲する (責務分離・fail-soft: exit code は変えない)。当月契約なら engine が
        # REVIEW_ENDED_NO_BASIS(要確認)で行ごと可視化するが、当月シートに無い他月行の残存も
        # 全シート横断 (all_rows) で件数告知し、根拠なき終了月による発行漏れ隠蔽の温存を断つ。
        end_health = notion_sheet_writeback.plan_unsupported_end_date_clear(all_rows)
        unsupported = end_health["stats"]["unsupported"]
        if unsupported:
            print(f"    [健全性] 根拠なき契約終了月: {unsupported}件 "
                  "(継続契約の発行漏れを隠す恐れ・要是正)")
            sys.stderr.write(
                f"[reconcile] 警告: 確認内容に終了根拠が無いのに契約終了月が入っている行 "
                f"{unsupported}件。継続契約を終了扱いにして発行漏れを隠す恐れがあります。"
                "`python3 scripts/clear_unsupported_end_dates.py --apply` で是正できます。\n")

    if "sink" in steps:
        if fatal_apply_failure:
            sys.stderr.write("[sink] DB1 upsert failed; DB2 sink skipped to avoid relation gaps.\n")
            return 2
        if apply and not mfk_reconcile.load_verdict_mapping():
            sys.stderr.write("[sink] verdict-mapping.json could not be loaded; apply aborted.\n")
            return 2
        page_id_by_cid = {}
        if apply:
            page_id_by_cid = sheet_to_master._existing_contract_ids(
                db1, token, notion_transport._req)
        try:
            sink_rows = build_sink_rows(result, page_id_by_cid)
        except RuntimeError as e:
            sys.stderr.write(f"[sink] {e}; sink skipped.\n")
            return 2
        resolved = sum(1 for r in sink_rows if r.get("contract_page_id"))
        print(f"[sink] DB2 投入対象 {len(sink_rows)}行 (contract_page_id 解決 {resolved}件)")
        if apply:
            r = notion_reconcile_sink.upsert_monthly(
                sink_rows, db2, target, token, req=notion_transport._req)
            print(f"[sink] DB2 upsert: created={r['created']} updated={r['updated']} "
                  f"frozen={r['frozen']} failed={r['failed']}")
            if r["failed"] or r["frozen"]:
                sys.stderr.write(
                    "[sink] DB2 upsert had failed/frozen rows; sheet writeback skipped "
                    "to keep DB2 as SoR.\n")
                return 2
            # シート書き戻し (片方向ミラー): 判定/AI確認/確認ポイントを投影し、契約開始日の
            # 空欄だけを派生値で自動補完する。契約終了月は誤推定防止のため触れない。
            # current_dates=当月シートの現値で空欄セルだけ書く (非空値・チェック済み等は不可侵)。
            current_dates = {
                row["page_id"]: {"契約開始日": row.get("契約開始日"),
                                 "契約終了月": row.get("契約終了月")}
                for row in query_sheet_rows(sheet_db, token, notion_transport._req, target)
                if row.get("page_id")
            }
            wb = notion_sheet_writeback.writeback(
                result.get("rows", []), sheet_db, token, notion_transport._req,
                current_dates=current_dates)
            print(f"[sink] シート書き戻し: 判定列={wb['schema']} / 更新={wb['updated']}行 "
                  f"(対象{wb['targeted']}) failed={len(wb['failed'])}")
            for f in wb["failed"]:
                sys.stderr.write(
                    f"[sink] シート書き戻し失敗: page_id={f['page_id']} error={f['error']}\n")
        else:
            print("[sink] dry-run のため DB2 への書き込み・シート書き戻しは行いません (--apply で実行)")
    return 0


def _needs_notion(steps, apply):
    """Notion トークンが要るか (シート読取 or 書き込み or page_id 解決のいずれか)。"""
    if "sync-master" in steps:
        return True
    if "sink" in steps and apply:
        return True
    return False


def main(argv=None):
    p = argparse.ArgumentParser(
        description="月次照合 orchestrator (シート→契約マスタ→MF照合→月次チェックDB)")
    p.add_argument("--target", help="対象月 YYMM (例: 2606)")
    p.add_argument("--apply", action="store_true",
                   help="実書き込みを行う (既定は dry-run・集計のみ)")
    p.add_argument("--verified", action="store_true",
                   help="dry-run と二段確認が完了済みであることを明示する。sink を含む --apply では必須")
    p.add_argument("--steps",
                   help="実行 step をカンマ区切りで指定 (既定: 全て)。"
                        f"有効値: {','.join(ALL_STEPS)}")
    p.add_argument("--sheet-db", dest="sheet_db", help="請求確認シート DB id (config 上書き)")
    p.add_argument("--db1", help="契約マスタ DB1 id (config 上書き)")
    p.add_argument("--db2", help="月次チェック DB2 id (config 上書き)")
    p.add_argument("--config", help="ローカル設定 JSON path (省略時は親探索)")
    a = p.parse_args(argv)

    if not _validate_target(a.target):
        sys.stderr.write(
            f"[reconcile] --target が YYMM 形式の実在月でありません: {a.target!r} "
            "(例: --target 2606)\n")
        return 2

    try:
        steps = _parse_steps(a.steps)
    except ValueError as e:
        sys.stderr.write(f"[reconcile] --steps エラー: {e}\n")
        return 2
    if a.apply and "sink" in steps and not a.verified:
        sys.stderr.write(
            "[reconcile] sink を含む --apply には --verified が必要です。"
            "先に dry-run の判定内訳を subagent で二段確認してから再実行してください。\n")
        return 2

    cfg = load_orchestrator_config(a.config)
    sheet_db, db1, db2 = resolve_db_ids(cfg, a)
    available = {"sheet_db": sheet_db, "db1": db1, "db2": db2}
    missing = sorted(k for k in required_db_ids(steps, a.apply) if not available[k])
    if missing:
        sys.stderr.write(
            f"[reconcile] DB id が解決できません: {missing}。"
            ".mf-kessai-config.json の notion.{sheet_db_id,reconcile_db1_id,reconcile_db2_id} "
            "を設定するか --sheet-db/--db1/--db2 で指定してください。\n")
        return 2

    return run(a.target, steps, a.apply, sheet_db, db1, db2, cfg)


if __name__ == "__main__":
    sys.exit(main())
