#!/usr/bin/env python3
# /// script
# name: send_campaign
# purpose: 承認済み plan.json を入力に live-send preflight(G1/G2/G3) を通し、各送信単位を Notion へ reserved 事前予約→send_guard内蔵 Gmail 送信→sent/unknown 更新する。quota安全停止・部分再開・日本語レポートを行う。
# inputs:
#   - argv: --plan <plan.json> --approved-plan-hash <h> --approved-count <n> --approved-first-to <to> [--config]
#   - keychain: notion-api-key.xl-skills / Google SA鍵
# outputs:
#   - Notion 送信ログDB 更新 + Gmail 送信 + stdout 日本語レポート
#   - exit: 0=完了(全送信orスキップ) / 1=preflight中断 / 2=設定/接続エラー / 3=quota安全停止(部分送信)
# contexts: [E, C]
# network: true   # api.notion.com + gmail.googleapis.com への HTTPS
# write-scope: external-email   # 不可逆送信。send_guard 通過時のみ
# dependencies: ["google-auth"]
# requires-python: ">=3.9"
# ///
"""live-send オーケストレーション (仕様書 §8 step5-11/§10/§11)。

人間承認 (APPROVE <plan_hash> <count> <first_to>) を orchestrator(LLM) が受領し、本 script に
--approved-* として渡す。preflight 全充足まで送信フェーズへ進まない。send_guard は gmail_client
内部で必ず呼ばれるため、本 script が guard を呼び忘れても送信に到達しない。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT))
from lib import (  # noqa: E402
    notion_client, notion_config, secrets, preflight,
    idempotent_log as ilog, gmail_client,
    render_substitute as rs, plan_build as pb, message_assemble as ma,
    send_guard as sg,
)


def _abort(results: list[dict]) -> int:
    print("\n❌ preflight 未充足。1通も送信していません。")
    for r in results:
        if not r["passed"]:
            print(f"  [{r['gate']}] {r['reason']} → 対応: {r['action']}  {r['detail']}")
            if r["action"] == "gcp_setup":
                print("    → doc/GCP-Gmail送信設定手順.md を参照")
            elif r["action"] == "db_setup":
                print("    → /run-notion-gmail-sendlog-setup で送信ログDBを構築")
            elif r["action"] == "fill_body":
                print("    → メッセージ対象=✅ かつ {{}}入り本文 を記入")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="dry-run が生成した plan.json")
    ap.add_argument("--approved-plan-hash", required=True)
    ap.add_argument("--approved-count", required=True, type=int)
    ap.add_argument("--approved-first-to", required=True)
    ap.add_argument("--approved-nonce", default="", help="承認確認語 (プレビュー該当単位で目視確認した値)")
    ap.add_argument("--allow-resend", action="store_true",
                    help="同一内容の既送信を意図的に再送する (既定はクロス実行の二重送信を機構で防止)")
    ap.add_argument("--config")
    args = ap.parse_args()

    try:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        cfg = notion_config.load_config(args.config)
    except (OSError, json.JSONDecodeError, notion_config.ConfigError) as e:
        print(f"[ERROR] plan/config 読み込み失敗: {e}", file=sys.stderr)
        return 2

    units = plan.get("units", [])

    # ---- 決定論セルフチェック (F2: guard を fork/人間に依存させない正本検証) ----
    # plan.json の自己申告スカラ (count/first_to/plan_hash) を信じず、units から再計算して
    # 承認文字列・plan 宣言値の三者一致を fail-closed で確認する。1つでも崩れたら1通も送らない。
    det_errors: list[str] = []
    recomputed_ph = pb.plan_hash(units) if units else ""
    recomputed_first_to = units[0]["to_list"][0] if units and units[0].get("to_list") else ""
    expected_nonce_idx, expected_nonce = pb.approval_nonce(plan.get("plan_hash", ""), units)
    if recomputed_ph != plan.get("plan_hash"):
        det_errors.append("units から再計算した plan_hash が plan.json の値と不一致 (plan 改竄/破損)")
    if plan.get("plan_hash") != args.approved_plan_hash:
        det_errors.append("plan.json の plan_hash が承認 plan_hash と不一致")
    if len(units) != plan.get("count"):
        det_errors.append(f"units 実数({len(units)}) が plan.count({plan.get('count')}) と不一致")
    if len(units) != args.approved_count:
        det_errors.append(f"units 実数({len(units)}) が承認件数({args.approved_count}) と不一致")
    if recomputed_first_to != (args.approved_first_to or ""):
        det_errors.append("units 先頭 To が承認先頭 To と不一致")
    if expected_nonce and args.approved_nonce != expected_nonce:
        det_errors.append("承認確認語(nonce)が plan から計算した値と不一致 (プレビュー未確認の疑い)")
    if det_errors:
        print("\n❌ 決定論セルフチェック失敗。1通も送信していません:")
        for e in det_errors:
            print(f"  - {e}")
        return 1
    # ---- G2 依存実体 ----
    # 本文 true 行数は plan が保持する値を正本とする。len(units) は本文×宛先の直積後件数で、
    # 宛先0件や全skip時に「本文無し(no_body)」と誤誘導するため母数に使わない (plan が無い旧版のみ fallback)。
    bodies_true = plan.get("body_true_count", len(units))
    g2 = preflight.gate_g2_dependencies(cfg, bodies_true_count=bodies_true)
    # ---- G1 認証 (実API probe) ----
    from_addr0 = units[0]["from_addr"] if units else (notion_config.get_sender(cfg).get("impersonate") or "")
    # 複数本文が異なる From を持ちうるため、先頭だけでなく全 distinct From を sendAs 検証する (preflight 網羅性)。
    distinct_from = list(dict.fromkeys(u["from_addr"] for u in units)) or [from_addr0]
    g1 = preflight.gate_g1_auth(cfg, from_addr0, probe_api=True, verify_from_addrs=distinct_from)
    # ---- G3 キャンペーン整合 (self-report でなく units 実体から) ----
    g3 = preflight.gate_g3_presend(
        approved_plan_hash=args.approved_plan_hash, plan_hash=recomputed_ph,
        approved_count=args.approved_count, actual_count=len(units),
        approved_first_to=args.approved_first_to, actual_first_to=recomputed_first_to,
    )
    all_results = g1 + g2 + [g3]
    if not preflight.all_passed(all_results):
        return _abort(all_results)

    try:
        log_db_id = notion_config.get_db_id("gmail-send-log", cfg)
        client = notion_client.NotionClient(secrets.get_notion_api_key())
        sender = notion_config.get_sender(cfg)
        sa = sender.get("sa_keychain") or {}
        sa_key = secrets.get_google_sa_key(sa.get("service"), sa.get("account"))
        impersonate = sender.get("impersonate") or from_addr0
        gclient = gmail_client.GmailClient(sa_key, impersonate)
        # 送信時 suppress 再検証 (C-1): dry-run 承認後に Notion で「メールを送らない=✅」や
        # 「送信対象=☐」に変えられた宛先へ追い越し送信しないよう、plan の宛先 page を再取得して
        # 現在の送信可否を引く。subtract-only (承認件数を超えて送ることは決してない)。
        recipient_db = ((cfg.get("notion_gmail_send") or {}).get("source") or {}).get("recipient_db")
        suppress_state = notion_client.fetch_recipient_send_state(client, recipient_db) if recipient_db else None
    except (notion_config.ConfigError, secrets.KeychainError, gmail_client.GmailUnavailable, notion_client.NotionError) as e:
        print(f"[ERROR] live-send 初期化失敗: {e}", file=sys.stderr)
        return 2

    verified_from: dict[str, bool] = {}
    tally: Counter = Counter()
    details: list[str] = []

    resend_cid = plan["campaign_id"] if args.allow_resend else None
    for u in units:
        # 送信単位の自己検証 (F2/F8): content_hash を再計算し plan の宣言値と照合、
        # 送信バイト列 raw は plan の値を信用せずフィールドから都度再生成する。
        recomputed_ch = pb.content_hash(u)
        # dedup キーは content ベース (campaign_id 非依存)。再計算 content_hash で再導出する。
        key = pb.dedup_key(u["body_page_id"], u["recipient_page_id"], recomputed_ch, resend_campaign_id=resend_cid)
        fields = {
            "idempotency_key": key, "campaign_id": plan["campaign_id"], "plan_hash": plan["plan_hash"],
            "content_hash": recomputed_ch, "body_page_id": u["body_page_id"],
            "recipient_page_id": u["recipient_page_id"], "from_addr": u["from_addr"],
            "to_list": u["to_list"], "cc_list": u["cc_list"], "subject": u["subject"],
        }
        # 送信時 suppress 再検証 (C-1): 承認後に「メールを送らない=✅」or「送信対象=☐」へ変更された宛先は送らない。
        if suppress_state is not None:
            st = suppress_state.get(u["recipient_page_id"])
            if st is None or st["do_not_send"] or not st["send_target"]:
                ilog.mark_skipped(client, log_db_id, fields, "send_suppressed")
                tally["skipped_validation"] += 1
                reason = "宛先削除/取得不可" if st is None else ("メールを送らない=✅" if st["do_not_send"] else "送信対象=☐")
                details.append(f"[send_suppressed] {u['subject']} → {u['to_list']} (承認後に{reason}・送信せず)")
                continue
        if recomputed_ch != u.get("content_hash"):
            # plan 内の content_hash と再計算が不一致 = plan 改変。送信せず skipped_validation で記録。
            ilog.mark_skipped(client, log_db_id, {**fields, "content_hash": u.get("content_hash", "")}, "content_hash_mismatch")
            tally["skipped_validation"] += 1
            details.append(f"[content_hash_mismatch] {u['subject']} → {u['to_list']} (plan 改変の疑い・送信せず)")
            continue
        # 送信バイト列を都度再生成 (raw を plan に依存させない)
        asm = ma.assemble(u["subject"], u["body"], u["from_addr"],
                          ", ".join(u["to_list"]), ", ".join(u["cc_list"]))
        if asm["raw"] is None:
            ilog.mark_skipped(client, log_db_id, fields, "invalid_addr_at_send")
            tally["skipped_validation"] += 1
            details.append(f"[invalid_addr] {u['subject']} → {u['to_list']} ({asm['invalid_addrs']})")
            continue
        raw = asm["raw"]

        # 事前予約
        try:
            rsv = ilog.reserve(client, log_db_id, fields)
        except notion_client.NotionError as e:
            tally["error"] += 1
            details.append(f"[error] {key[:40]}… reserve失敗: {e}")
            continue
        if rsv["action"] == "duplicate":
            tally["duplicate_log_key"] += 1
            details.append(f"[duplicate_log_key] {u['subject']} → {u['to_list']} (ログ行 {rsv['matched']} 件・自動送信せず)")
            continue
        if rsv["action"] == "skip":
            tally["skipped_idempotent"] += 1
            continue
        if rsv["action"] == "skip_manual":
            tally["needs_reconcile" if rsv["status"] == ilog.UNKNOWN else "skipped_existing"] += 1
            details.append(f"[{rsv['status']}] {u['subject']} → {u['to_list']} (自動再送せず)")
            continue

        reserved_id = rsv["page_id"]
        # 送信直前の二段確認(決定論版): 未置換トークン再検査 + sendAs 検証 + 承認 nonce
        unresolved = rs.find_unresolved_tokens(u["subject"]) + rs.find_unresolved_tokens(u["body"])
        fa = u["from_addr"]
        if fa not in verified_from:
            verified_from[fa] = gclient.verify_sendas(fa)
        guard_kwargs = dict(
            approved_plan_hash=args.approved_plan_hash, plan_hash=recomputed_ph,
            approved_count=args.approved_count, actual_count=len(units),
            approved_first_to=args.approved_first_to, actual_first_to=recomputed_first_to,
            reserved_log_id=reserved_id, unresolved_tokens=unresolved,
            from_verified=verified_from[fa],
            approved_nonce=args.approved_nonce, actual_nonce=expected_nonce,
        )
        # F13: guard を mark_sending の前に明示実行し、guard 違反では SENDING を作らない。
        try:
            sg.check(**guard_kwargs)
        except gmail_client.SendGuardError as e:
            ilog.mark_error(client, reserved_id, e.code, str(e))
            tally["skipped_validation"] += 1
            details.append(f"[guard:{e.code}] {u['subject']} → {u['to_list']}")
            continue

        try:
            ilog.mark_sending(client, reserved_id)
            message_id = gclient.send_unit(raw, **guard_kwargs)  # send_unit 内で guard 再実行 (多層防御)
        except gmail_client.SendGuardError as e:  # 多層防御で再検出した場合
            ilog.mark_error(client, reserved_id, e.code, str(e))
            tally["skipped_validation"] += 1
            details.append(f"[guard:{e.code}] {u['subject']} → {u['to_list']}")
            continue
        except gmail_client.QuotaStopped as e:
            # サーバ拒否=未送信確定。当該単位を reserved へ戻し次回自動再開 (F4)。
            ilog.mark_reserved(client, reserved_id, reason_code="quota_stopped")
            ilog.append_journal(plan["campaign_id"], {"event": "quota_stopped", "key": key})
            tally["quota_stopped"] += 1
            details.append(f"[quota_stopped] {e} — 当該単位を reserved へ戻し次回再開")
            break
        except gmail_client.SendOutcomeUnknown as e:
            # 送信成否不明。自動再送禁止 → unknown_needs_reconcile (F3/F9)。
            ilog.append_journal(plan["campaign_id"], {"event": "send_outcome_unknown", "key": key, "detail": str(e)})
            ilog.mark_unknown(client, reserved_id, f"send outcome unknown: {type(e).__name__}")
            tally["unknown_needs_reconcile"] += 1
            details.append(f"[unknown_needs_reconcile] {u['subject']} → {u['to_list']} (送信成否不明・手動照合要)")
            continue
        except Exception as e:  # 送信前にサーバ拒否が確定した 4xx 等 → 未送信扱い
            ilog.mark_error(client, reserved_id, "send_failed", type(e).__name__)
            tally["error"] += 1
            details.append(f"[error] {u['subject']} → {u['to_list']}: {type(e).__name__}")
            continue

        # 送信成功 → ログ更新。失敗時は unknown_needs_reconcile + journal
        try:
            ilog.mark_sent(client, reserved_id, message_id)
            tally["sent"] += 1
        except notion_client.NotionError:
            ilog.append_journal(plan["campaign_id"], {"event": "send_success_log_failed", "key": key, "messageId": message_id, "plan_hash": plan["plan_hash"]})
            try:
                ilog.mark_unknown(client, reserved_id, "sent but log update failed")
            except notion_client.NotionError:
                pass
            tally["unknown_needs_reconcile"] += 1
            details.append(f"[unknown_needs_reconcile] {u['subject']} → 送信済だがログ更新失敗。手動照合要")

    # ---- レポート ----
    plan_skipped = len(plan.get("skipped", []))
    plan_suppressed = len(plan.get("suppressed", []))
    plan_dup_dropped = len(plan.get("duplicate_dropped", []))
    print("\n===== 送信レポート =====")
    print(f"campaign_id : {plan['campaign_id']}")
    print(f"送信 (sent) : {tally['sent']}")
    print(f"dry-run 抑制 (メールを送らない): {plan_suppressed} / 重複除外 (プロ人材最新created_time1件): {plan_dup_dropped}")
    print(f"冪等スキップ (skipped_idempotent): {tally['skipped_idempotent']}")
    print(f"検証スキップ (dry-run skipped_validation): {plan_skipped}")
    print(f"送信前ガード除外 (skipped_validation): {tally['skipped_validation']}")
    print(f"既存予約・自動再送せず: {tally['skipped_existing']}")
    print(f"失敗 (error) : {tally['error'] + tally['duplicate_log_key']}")
    print(f"要照合 (unknown_needs_reconcile): {tally['unknown_needs_reconcile'] + tally['needs_reconcile']}")
    if tally["quota_stopped"]:
        print("⚠️ quota 安全停止しました。再実行で残件 (reserved) を継続します。")
    if details:
        print("\n--- 内訳 ---")
        for d in details:
            print(" " + d)
    print("\n注意: status=sent は Gmail API 受理であり受信者への到達保証ではありません。")
    return 3 if tally["quota_stopped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
