#!/usr/bin/env python3
# /// script
# name: build_plan
# purpose: dry-run。DB1/DB2 を取得し本文true×宛先true の直積を生成、件名/本文の{{}}置換・MIME組立・content_hash/plan_hash を算出して plan.json と全件プレビューを出力する。Gmail API は呼ばない。
# inputs:
#   - argv: --out <plan.json> / --db1 / --db2 / --config / --canary N
#   - keychain: notion-api-key.xl-skills
# outputs:
#   - plan.json (本文全文含む・ローカル作業領域) + stdout 全件プレビュー + 第1段件数
#   - exit: 0=plan生成成功 / 2=接続/設定エラー
# contexts: [E, C]
# network: true   # api.notion.com への HTTPS のみ (Gmail は呼ばない)
# write-scope: local-workspace   # plan.json をローカルに書く (git管理外)
# dependencies: []
# requires-python: ">=3.9"
# ///
"""dry-run plan 構築 (仕様書 §4/§5/§6/§8 step1-4)。

送信ログDB が未確定でも第1段件数 (本文true×宛先true) と plan_hash まで作成する (G0)。
plan.json は本文全文を含むためローカル作業領域のみに書き、Notion ログには保存しない (§12 PII)。
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT))
from lib import (  # noqa: E402
    notion_client, notion_config, secrets,
    render_substitute as rs, message_assemble as ma, plan_build as pb,
)


def _combine_cc(body_cc_raw: str, hisho_email: str) -> str:
    """本文CC + 秘書CC を結合した cc_raw 文字列にする (重複/To除外は assemble が正規化)。

    結合は dry-run でここ1回だけ確定し plan.json の cc_list に焼く。live-send は再結合しない
    (content_hash の決定論を二重ロジックで壊さないため。仕様書 §6)。
    """
    return ",".join(p for p in (body_cc_raw or "", hisho_email or "") if p.strip())


def _classify_unit(body: dict, recip: dict) -> tuple[dict | None, str | None]:
    """1組(本文×宛先)を送信単位に変換する。skip 時は (None, reason_code)。

    To=プロ人材メール、CC=本文CC + 秘書(cc秘書)メール (仕様書 §6)。
    """
    values = notion_client.values_for_recipient(recip)
    if rs.unsafe_value_keys(values):
        return None, "unsafe_header"
    subject_out, un_s = rs.substitute(body["subject"], values)
    body_out, un_b = rs.substitute(body["body"], values)
    unresolved = list(dict.fromkeys(un_s + un_b))
    if unresolved:
        return None, "unresolved_token"
    cc_raw = _combine_cc(body["cc_raw"], recip.get("hisho_email", ""))
    asm = ma.assemble(subject_out, body_out, body["from_addr"], recip["pro_email"], cc_raw)
    if asm["invalid_addrs"]:
        reason = "invalid_cc" if all(a.startswith("cc:") for a in asm["invalid_addrs"]) else "invalid_to"
        return None, reason
    # To と重複して CC から除外されたアドレス (秘書addr==プロ人材To 等) を可視化する。
    # 除外自体は normalize_cc の安全側挙動 (同一人物2通回避) で変えない。プレビュー警告のみ。
    cc_suppressed = ma.cc_suppressed_by_to(ma.parse_comma_addrs(cc_raw), asm["to_list"])
    unit = {
        "subject": subject_out,
        "body": body_out,
        "from_addr": body["from_addr"],
        "to_list": asm["to_list"],
        "cc_list": asm["cc_list"],
        "raw": asm["raw"],
        "multi_to_visible": asm["multi_to_visible"],
        "cc_suppressed_due_to_to_overlap": cc_suppressed,
        "body_page_id": body["page_id"],
        "recipient_page_id": recip["page_id"],
    }
    unit["content_hash"] = pb.content_hash(unit)
    return unit, None


def _stable_units(units: list[dict]) -> list[dict]:
    return sorted(units, key=lambda u: (u["content_hash"], u.get("body_page_id", ""), u.get("recipient_page_id", "")))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="plan.json 出力先 (既定: eval-log/notion-gmail-send/plan-<campaign>.json)")
    ap.add_argument("--db1", help="メール本文DB id (override)")
    ap.add_argument("--db2", help="メール送信先_DB id (override)")
    ap.add_argument("--config", help=".notion-config.json パス")
    ap.add_argument("--canary", "--limit", dest="canary", type=int,
                    help="送信可能 unit を安定順の先頭 N 件に限定した plan を作る (少数検品用)")
    args = ap.parse_args()
    if args.canary is not None and args.canary < 1:
        print("[ERROR] --canary/--limit は 1 以上を指定してください", file=sys.stderr)
        return 2

    try:
        cfg = notion_config.load_config(args.config)
        source = (cfg.get("notion_gmail_send") or {}).get("source") or {}
        db1 = args.db1 or source.get("body_db")
        db2 = args.db2 or source.get("recipient_db")
        if not db1 or not db2:
            print("[ERROR] body_db / recipient_db が未解決 (config notion_gmail_send.source または --db1/--db2)", file=sys.stderr)
            return 2
        client = notion_client.NotionClient(secrets.get_notion_api_key())
        bodies, body_skipped = notion_client.fetch_bodies_true(client, db1)
        resolution = notion_client.fetch_recipients_true(client, db2)
    except (notion_config.ConfigError, secrets.KeychainError, notion_client.NotionError) as e:
        print(f"[ERROR] dry-run preflight 失敗: {e}", file=sys.stderr)
        return 2

    recips = resolution["recipients"]            # 送信可能・dedup後
    recip_skipped = resolution["skipped"]        # プロ人材メール空
    suppressed = resolution["suppressed"]        # メールを送らない=✅ (送信対象より優先)
    duplicate_dropped = resolution["duplicate_dropped"]  # プロ人材重複で除外された古い行

    first_stage = len(bodies) * len(recips)
    campaign_id = pb.generate_campaign_id()
    units: list[dict] = []
    skipped: list[dict] = []
    for body in bodies:
        for recip in recips:
            unit, reason = _classify_unit(body, recip)
            if reason:
                skipped.append({"body_page_id": body["page_id"], "recipient_page_id": recip["page_id"],
                                "subject": body["subject"], "to": recip["pro_email"], "reason_code": reason})
                continue
            # dedup キーは content ベース (campaign_id 非依存) で別実行の二重送信も機構で防ぐ。
            unit["idempotency_key"] = pb.dedup_key(unit["body_page_id"], unit["recipient_page_id"], unit["content_hash"])
            units.append(unit)

    available_units = len(units)
    if args.canary is not None and args.canary < available_units:
        units = _stable_units(units)[:args.canary]
    plan = pb.finalize_plan(campaign_id, units)
    plan.update({
        "generated_at": datetime.datetime.now().astimezone().isoformat(),
        "first_stage_count": first_stage,
        "body_true_count": len(bodies),       # 本文 true(メッセージ対象✅かつ非空) 行数。G2.body の正しい母数
        "recipient_true_count": len(recips),  # 宛先(送信対象✅かつ送らない☐かつプロ人材非空・dedup後) 行数
        "available_unit_count": available_units,
        "canary_limit": args.canary,
        "canary_applied": args.canary is not None and args.canary < available_units,
        "source": {"body_db": db1, "recipient_db": db2},
        "skipped": skipped,
        "suppressed": suppressed,                # メールを送らない=✅ で抑制した宛先
        "duplicate_dropped": duplicate_dropped,  # プロ人材重複で除外した古い行
        "body_skipped": body_skipped,
        "recipient_skipped": recip_skipped,
    })

    config_path = notion_config.find_config_path(args.config)
    out = args.out or str(Path(config_path.parent if config_path else ".")
                          / "eval-log" / "notion-gmail-send" / f"plan-{campaign_id}.json")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 全件プレビュー (本文全文含めてよい §12) ----
    print(f"campaign_id : {campaign_id}")
    print(f"plan_hash   : {plan['plan_hash']}")
    print(f"第1段 計画送信単位 = 本文true({len(bodies)}) × 宛先true({len(recips)}) = {first_stage}")
    print(f"  宛先 = 送信対象✅かつ送らない☐の dedup後 {len(recips)} 件 "
          f"(抑制 {len(suppressed)} / 重複除外 {len(duplicate_dropped)} / メール空 {len(recip_skipped)})")
    print(f"送信可能 (plan) : {plan['count']} 通 / skip : {len(skipped)} 件")
    if plan["canary_applied"]:
        print(f"canary      : 有効 (送信可能 {available_units} 通のうち先頭 {plan['count']} 通だけを plan 化)")
        print("              検品後は Notion の ✅ 対象を広げるか --canary なしで dry-run を再作成してください。")
    elif args.canary is not None:
        print(f"canary      : 指定 {args.canary} / 送信可能 {available_units} 通のため限定なし")
    print(f"先頭To (承認echo): {plan['first_to']}")
    # 承認確認語 (nonce): 該当単位のプレビューを目視確認しないと得られない (blind approve 防止)。
    nonce_idx, nonce_code = pb.approval_nonce(plan["plan_hash"], plan["units"])
    nonce_unit_no = (nonce_idx + 1) if nonce_idx is not None else None
    if plan["count"] > 0:
        print(f"\n--- 承認文字列 ---")
        print(f"プレビュー単位[{nonce_unit_no}] の行末に表示される【確認語】を読み取り、末尾に付けて入力してください:")
        print(f"APPROVE {plan['plan_hash']} {plan['count']} {plan['first_to']} <確認語>\n")
    for i, u in enumerate(plan["units"], 1):
        warn = " ⚠️multi_to_visible" if u["multi_to_visible"] else ""
        mark = f"  【確認語: {nonce_code}】" if (i - 1) == nonce_idx else ""
        print(f"[{i}] To={u['to_list']} CC={u['cc_list']}{warn}{mark}")
        if u.get("cc_suppressed_due_to_to_overlap"):
            # 秘書addr がプロ人材To と同一でCC除外された (同一人物2通回避)。届かないわけではない旨を明示。
            print(f"    ⚠️cc_suppressed_due_to_to_overlap: {u['cc_suppressed_due_to_to_overlap']} "
                  f"は To と同一のため CC から除外 (To で届くので二重送信回避・正常)")
        print(f"    件名: {u['subject']}")
        print(f"    本文: {u['body'][:120]}{'…' if len(u['body'])>120 else ''}")
    if skipped:
        print("\n--- skipped_validation ---")
        for s in skipped:
            print(f"    [{s['reason_code']}] {s['subject']} → {s['to']}")
    if suppressed:
        print("\n--- 送信抑制 (メールを送らない=✅ ・送信対象より優先) ---")
        for s in suppressed:
            print(f"    {s['name']} <{s['pro_email']}>")
    if duplicate_dropped:
        print("\n--- 重複除外 (同一プロ人材は最新created_timeの1件のみ送信・同時刻はpage_id降順) ---")
        for d in duplicate_dropped:
            print(f"    {d['name']} <{d['pro_email']}> 会社={d['company']} created={d['created_time']}"
                  f" → 採用 page={d['kept_page_id'][-6:]} のため除外")
    if recip_skipped:
        print("\n--- 宛先除外 (送信対象✅だがプロ人材メール空) ---")
        for s in recip_skipped:
            print(f"    [{s['reason_code']}] {s['name']}")
    if body_skipped:
        print("\n--- 本文除外 (メッセージ対象✅だが本文不備) ---")
        for s in body_skipped:
            print(f"    [{s['reason_code']}] {s['subject']}")
    print(f"\nplan.json: {out}")
    if plan["count"] == 0:
        if suppressed or duplicate_dropped or recip_skipped:
            print(f"\n送信可能0通: 抑制 {len(suppressed)} / 重複除外 {len(duplicate_dropped)} / "
                  f"メール空 {len(recip_skipped)} 件のため宛先が残りませんでした。Notion の宛先設定を確認してください。")
        else:
            print("\n本文0通: メッセージ対象=✅ かつ {{}}入り本文 を記入してから再実行してください。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
