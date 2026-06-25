#!/usr/bin/env python3
# /// script
# name: audit_mail_dbs
# purpose: メール本文DB(DB1)/メール送信先_DB(DB2) のデータ品質を監査し、送信前に直すべき問題を行単位でレポートする。本文が使うトークンと宛先値のクロス検査で送信時 skip 予測も出す。read-only。
# inputs:
#   - argv: --db1 <id> / --db2 <id> / --config / --json
#   - keychain: notion-api-key.xl-skills
# outputs:
#   - stdout: 改善レポート (issues 一覧 + 送信時 skip 予測) / --json で機械可読
#   - exit: 0=問題なし / 1=改善推奨あり / 2=接続/設定エラー
# contexts: [E, C]
# network: true   # api.notion.com への HTTPS GET のみ
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""メールソース2DB データ品質監査 (run-notion-gmail-source-audit 本体)。

送信ログDB ではなく、送信元の本文DB/宛先DB の品質を改善するための監査。Notion へは書き込まず
(改善は人が行う領域)、何を直せば送信成功率が上がるかを行単位で提示する。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN_ROOT))
from lib import notion_client, notion_config, secrets, mail_db_audit as audit  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db1", help="メール本文DB id (override)")
    ap.add_argument("--db2", help="メール送信先_DB id (override)")
    ap.add_argument("--config")
    ap.add_argument("--json", action="store_true", help="機械可読 JSON で出力")
    args = ap.parse_args()

    try:
        cfg = notion_config.load_config(args.config)
        source = (cfg.get("notion_gmail_send") or {}).get("source") or {}
        db1 = args.db1 or source.get("body_db")
        db2 = args.db2 or source.get("recipient_db")
        if not db1 or not db2:
            print("[ERROR] body_db / recipient_db 未解決 (config notion_gmail_send.source または --db1/--db2)", file=sys.stderr)
            return 2
        client = notion_client.NotionClient(secrets.get_notion_api_key())
        body_rep = audit.audit_body_db(client, db1)
        recip_rep = audit.audit_recipient_db(client, db2)
        recip_schema = audit.audit_recipient_db_schema(client, db2)  # DB2 schema 層 (廃止列残存・要件1(d))
        cross = audit.cross_audit(body_rep["used_tokens"], recip_rep["recipients"])
    except (notion_config.ConfigError, secrets.KeychainError, notion_client.NotionError) as e:
        print(f"[ERROR] 監査失敗: {e}", file=sys.stderr)
        return 2

    all_issues = body_rep["issues"] + recip_rep["issues"] + recip_schema["issues"] + cross
    high = [i for i in all_issues if i.get("severity") == "high"]

    if args.json:
        print(json.dumps({
            "body_db": {"db_id": db1, **{k: v for k, v in body_rep.items() if k != "issues"}},
            "recipient_db": {"db_id": db2, "total_target": recip_rep["total_target"], "sendable": recip_rep["sendable"],
                             "schema_properties": recip_schema["properties"]},
            "issues": all_issues,
            "high_severity_count": len(high),
        }, ensure_ascii=False, indent=2))
        return 1 if all_issues else 0

    # ---- 人間向けレポート ----
    print("===== メールソース2DB データ品質監査 =====")
    print(f"DB1 メール本文_DB ({db1[:8]}…): 送信対象 {body_rep['total_target']} 件 / 本文OK {body_rep['sendable']} 件")
    print(f"  本文が使うトークン: {body_rep['used_tokens'] or '(なし)'}")
    print(f"DB2 送信先_DB ({db2[:8]}…): 対象母集団 {recip_rep['total_target']} 件 / 送信可能(dedup後) {recip_rep['sendable']} 件")
    print(f"  送信抑制 (メールを送らない✅): {len(recip_rep['suppressed'])} 件 / "
          f"重複除外 (プロ人材最新created_time1件): {len(recip_rep['duplicate_dropped'])} 件")
    # 送信時 skip 予測 (この宛先への全本文が落ちる組)
    cross_skip = len({i["page_id"] for i in cross})
    print(f"\n送信時 skip 予測: 未置換になる宛先 {cross_skip} 件")

    if not all_issues:
        print("\n✅ 改善が必要な問題は見つかりませんでした。dry-run へ進めます。")
        return 0

    print(f"\n--- 改善推奨 {len(all_issues)} 件 (high {len(high)}) ---")
    for i in all_issues:
        loc = i.get("subject") or i.get("name") or i.get("page_id") or ""
        print(f"  [{i['severity']}][{i['code']}] {i['db']}: {loc}")
        print(f"      → {i['detail']}")
    print("\n改善は Notion 上で人が行ってください (本スキルは検出のみ・書込しません)。")
    print("修正後に再度 audit → run-notion-gmail-dry-run で送信計画を確認してください。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
