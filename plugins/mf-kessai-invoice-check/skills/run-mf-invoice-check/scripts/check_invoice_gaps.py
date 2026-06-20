#!/usr/bin/env python3
"""月次発行漏れチェック実行スクリプト。

  --collect  : 前月/今月の発行済み請求を取得→差集合→商品名/金額/企業名突合→未検証候補JSON出力
  --finalize : verify(subagent)が確定した結果を確定リストへ昇格 (誤検出 customer_id を除外)
  --sink     : 確定リストを Notion DB に冪等 upsert (確定リスト不在なら fail-closed で停止)

月は --month YYYY-MM (既定: 実行日の月)。前月は自動算出。
全て GET (参照専用)。MF APIへの POST/PATCH/DELETE は PreToolUse hook で遮断される。

出力先は install パス非依存に解決する (F2 ポータビリティ)。lib import に使う _PLUGIN_ROOT は
__file__ 相対なので任意 install パスで安定するが、成果物(候補/確定 JSON)の置き場は repo 構造に
依存させず、base_url の env-first 思想と同型の優先順位 env > Claude project > CWD で解決する。
"""
import argparse
import calendar
import datetime
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "lib"))
from mfk_api import get, iter_all, load_config  # noqa: E402
from mfk_invoice_diff import amount_changed, detect_gaps  # noqa: E402
import notion_invoice_sink  # noqa: E402

GAP_VERDICT = "発行漏れ候補"
_VERDICT_ENUM = ("発行漏れ候補", "継続発行", "今月新規")


def eval_log_dir():
    """成果物の出力ディレクトリを install パス非依存に解決する。

    優先順位 (base_url の env-first 思想を出力先へ横展開):
      1. MFK_OUTPUT_DIR (env, 明示上書き)
      2. CLAUDE_PROJECT_DIR (Claude Code 注入の project root)
      3. os.getcwd() (実行 CWD。prompts/agent の裸相対 eval-log/ と基準一致)
    """
    base = os.environ.get("MFK_OUTPUT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return os.path.join(base, "eval-log")


def candidates_path():
    """collect が出力する未検証候補 JSON のパス。"""
    return os.path.join(eval_log_dir(), "mfk-gap-candidates.json")


def verified_path():
    """finalize が出力し sink が消費する確定 JSON のパス (二段確認の物理境界)。"""
    return os.path.join(eval_log_dir(), "mfk-gap-verified.json")


def validate_rows(rows):
    """sink/finalize 入口の最小 schema 検証 (F4)。違反メッセージのリストを返す (空なら OK)。

    invoice-gap-result.schema.json の必須制約 (customer_id 非空 / period_ym=YYYY-MM /
    verdict enum) を冪等キー破綻前に機械強制する。
    """
    errs = []
    if not isinstance(rows, list):
        return ["入力が配列でない"]
    for i, r in enumerate(rows):
        cid = r.get("customer_id")
        ym = r.get("period_ym")
        v = r.get("verdict")
        if not (isinstance(cid, str) and cid.strip()):
            errs.append(f"[{i}] customer_id が空/非文字列: {cid!r}")
        if not (isinstance(ym, str) and re.fullmatch(r"\d{4}-\d{2}", ym or "")):
            errs.append(f"[{i}] period_ym が YYYY-MM でない: {ym!r}")
        if v not in _VERDICT_ENUM:
            errs.append(f"[{i}] verdict が enum 外: {v!r}")
    return errs


def month_range(ym):
    y, m = map(int, ym.split("-"))
    last = calendar.monthrange(y, m)[1]
    return f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{last:02d}"


def prev_month(ym):
    y, m = map(int, ym.split("-"))
    m -= 1
    if m == 0:
        y -= 1
        m = 12
    return f"{y:04d}-{m:02d}"


def fetch_issued(ym):
    first, last = month_range(ym)
    return list(iter_all("/billings/qualified", {
        "issue_date_from": first, "issue_date_to": last, "status": "invoice_issued",
    }))


def by_customer(billings):
    out = {}
    for b in billings:
        out.setdefault(b["customer_id"], b)
    return out


def resolve_names(customer_ids):
    names = {}
    ids = list(customer_ids)
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        data = get("/customers", {"ids": chunk, "limit": 200})
        for c in data.get("items", []):
            names[c["id"]] = c.get("name", "")
    if ids and not names:  # 全件解決失敗 = パラメータ形式の疑い。空欄で黙って進めない
        sys.stderr.write(
            f"[check] 警告: 顧客ID {len(ids)}件に対し企業名が1件も解決できませんでした。"
            "/customers?ids= の形式を実APIで確認してください (このままだと企業名が空欄になります)。\n")
    return names


def detail_of(billing_id):
    """billing の商品名(先頭3明細)と更新日を返す。

    MF API に updated_at は存在しない (ref-mf-kessai-api 参照)。更新日は transactions.created_at の
    最新値で代替し、内部キー名 `updated_at` は『更新日列の値』の意味で用いる (取得元は created_at)。
    """
    if not billing_id:
        return {"product_name": "", "updated_at": None}
    data = get("/transactions", {"billing_id": billing_id, "limit": 5})
    descs, updated = [], None
    for t in data.get("items", []):
        ca = t.get("created_at")
        if ca and (updated is None or ca > updated):
            updated = ca
        for d in t.get("transaction_details", []):
            if d.get("description"):
                descs.append(d["description"])
    return {"product_name": " / ".join(descs[:3]), "updated_at": updated}


def collect(ym):
    prev_ym = prev_month(ym)
    prev_b = fetch_issued(prev_ym)
    curr_b = fetch_issued(ym)
    res = detect_gaps(prev_b, curr_b)
    prev_by, curr_by = by_customer(prev_b), by_customer(curr_b)
    changed = set(amount_changed(res["continuing"], res["prev_amount"], res["curr_amount"]))
    targets = set(res["gap_candidates"]) | changed
    names = resolve_names(targets)
    rows = []
    for cid in res["gap_candidates"]:
        b = prev_by.get(cid, {})
        det = detail_of(b.get("id"))
        rows.append({
            "customer_id": cid, "period_ym": ym, "company_name": names.get(cid, ""),
            "verdict": "発行漏れ候補", "product_name": det["product_name"],
            "prev_amount": res["prev_amount"].get(cid), "curr_amount": None,
            "issue_date": b.get("issue_date"), "updated_at": det["updated_at"],
        })
    for cid in res["continuing"]:
        if cid not in changed:
            continue
        b = curr_by.get(cid, {})
        det = detail_of(b.get("id"))
        rows.append({
            "customer_id": cid, "period_ym": ym, "company_name": names.get(cid, ""),
            "verdict": "継続発行", "product_name": det["product_name"],
            "prev_amount": res["prev_amount"].get(cid), "curr_amount": res["curr_amount"].get(cid),
            "issue_date": b.get("issue_date"), "updated_at": det["updated_at"],
        })
    return res, rows


def _print_summary(ym, res, rows):
    # 月次サマリ行(notion_invoice_sink._summary_row)の changed_count は「継続発行のうち
    # 金額変動した件数」のみを数える。画面の「継続発行(全件)」とは定義が異なるため、
    # 同じ「継続発行」の語で別の数を示して運用者を誤認させないよう内訳まで明示する。
    changed = len([r for r in rows if r.get("verdict") == "継続発行"])
    print(f"== 発行漏れチェック {prev_month(ym)} → {ym} ==")
    print(f"発行漏れ候補: {len(res['gap_candidates'])}件 / "
          f"継続発行(全件): {len(res['continuing'])}件 (うち金額変動: {changed}件) / "
          f"今月新規: {len(res['new_this_month'])}件")
    for r in rows:
        amt = f"前月{r['prev_amount']}→今月{r['curr_amount']}"
        print(f"  [{r['verdict']}] {r['company_name']}({r['customer_id']}) {r['product_name']} {amt}")


def finalize(exclude_ids, in_path, out_path):
    """verify(subagent)の確定結果を確定リストへ昇格する (二段確認の物理境界を作る, F1)。

    exclude_ids: 誤検出として除外する customer_id 集合 (発行漏れ候補のみ除外対象)。
    確定リストの存在自体が『verify を通過した』証跡となり、sink はこれを fail-closed で要求する。
    """
    with open(in_path, encoding="utf-8") as f:
        rows = json.load(f)
    errs = validate_rows(rows)
    if errs:
        sys.stderr.write("[finalize] 候補JSONが schema 違反:\n  " + "\n  ".join(errs) + "\n")
        return 2
    excl = {c for c in exclude_ids if c}
    kept = [r for r in rows if not (r.get("verdict") == GAP_VERDICT and r.get("customer_id") in excl)]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"確定リストを {out_path} に出力 ({len(kept)}件 / 誤検出除外 {len(rows) - len(kept)}件)。"
          "--sink で Notion 投入してください。")
    return 0


def main():
    p = argparse.ArgumentParser(description="MF掛け払い 月次発行漏れチェック (collect→verify→finalize→sink)")
    p.add_argument("--collect", action="store_true", help="未検証候補を取得・出力")
    p.add_argument("--finalize", action="store_true", help="verify確定結果を確定リストへ昇格")
    p.add_argument("--sink", action="store_true", help="確定リストを Notion へ冪等 upsert")
    p.add_argument("--month", help="対象月 YYYY-MM (既定: 実行日の月)")
    p.add_argument("--exclude-ids", help="finalize: 誤検出として除外する customer_id (カンマ区切り)")
    p.add_argument("--input", help="finalize/sink の入力 JSON path")
    p.add_argument("--out", help="collect/finalize の出力先 path")
    p.add_argument("--force-unverified", action="store_true",
                   help="sink: 確定リスト無しで未検証候補を直接投入 (二段確認スキップ・非推奨)")
    a = p.parse_args()

    if a.finalize:
        in_path = a.input or candidates_path()
        out_path = a.out or verified_path()
        return finalize((a.exclude_ids or "").split(","), in_path, out_path)

    if a.sink:
        if a.input:
            path = a.input
        elif a.force_unverified:
            path = candidates_path()
            sys.stderr.write("[check] 警告: --force-unverified。二段確認を経ない未検証候補を投入します。\n")
        else:
            path = verified_path()
            if not os.path.exists(path):
                sys.stderr.write(
                    f"[check] 確定リスト {path} が不在です。collect→verify(subagent)→finalize の後に "
                    "--sink してください (二段確認をスキップして投入するなら --force-unverified)。\n")
                return 2
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
        errs = validate_rows(rows)
        if errs:
            sys.stderr.write("[check] sink 入力が schema 違反:\n  " + "\n  ".join(errs) + "\n")
            return 2
        cfg = load_config()
        db_id = (cfg.get("notion") or {}).get("database_id")
        if not db_id:
            sys.stderr.write("[check] notion.database_id 未設定。先に run-mf-invoice-db-setup を実行してください。\n")
            return 2
        ym = a.month or (rows[0]["period_ym"] if rows else datetime.date.today().strftime("%Y-%m"))
        r = notion_invoice_sink.upsert(db_id, rows, period_ym=ym)
        print(f"Notion upsert: created={r['created']} updated={r['updated']} "
              f"period={r['period_ym']} run_id={r['run_id']} (月次サマリ行とページ履歴を含む)")
        return 0

    # 既定は collect
    ym = a.month or datetime.date.today().strftime("%Y-%m")
    res, rows = collect(ym)
    _print_summary(ym, res, rows)
    out = a.out or candidates_path()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"\n候補を {out} に出力 ({len(rows)}件)。subagent(mfk-gap-verifier)検証→--finalize→--sink の順で投入してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
