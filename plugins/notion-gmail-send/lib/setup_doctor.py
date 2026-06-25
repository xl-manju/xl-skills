#!/usr/bin/env python3
# /// script
# name: setup_doctor
# purpose: notion-gmail-send のセットアップ状態 (config / Keychain / 送信ログDB ID / 任意の Gmail sendAs 実API probe) を横断診断する。
# inputs:
#   - argv: [--config <path>] [--from <addr>] [--probe] [--json]
# outputs:
#   - stdout: GateResult 一覧 / exit 0=PASS, 1=未充足, 2=設定読み込み失敗
# contexts: [C, E]
# network: true   # --probe 時のみ gmail.googleapis.com
# write-scope: none
# dependencies: ["google-auth"]
# requires-python: ">=3.9"
# ///
"""setup doctor for notion-gmail-send.

本送信は行わず、live-send preflight の前提を単独で点検する薄い入口。
`--probe` を付けた場合だけ Gmail の実 API で sendAs を検証する。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from lib import notion_config, preflight  # noqa: E402


def _result(gate: str, passed: bool, reason: str = "", action: str = "", detail: str = "") -> dict:
    return {"gate": gate, "passed": passed, "reason": reason, "action": action, "detail": detail}


def _print_text(results: list[dict]) -> None:
    print("notion-gmail-send setup-doctor")
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        line = f"[{mark}] {r['gate']}"
        if r.get("reason"):
            line += f" {r['reason']}"
        if r.get("detail"):
            line += f" - {r['detail']}"
        if r.get("action"):
            line += f" (next: {r['action']})"
        print(line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", help=".notion-config.json path")
    ap.add_argument("--from", dest="from_addr", default="", help="sendAs 検証する From。未指定時は sender.impersonate")
    ap.add_argument("--probe", action="store_true", help="Gmail 実APIで DWD/sendAs まで検証する")
    ap.add_argument("--json", action="store_true", help="結果を JSON で出力する")
    args = ap.parse_args()

    results: list[dict] = []
    if args.config and not Path(args.config).is_file():
        results.append(_result("G0.config", False, "config_missing", "create_config",
                               f"指定パスが見つかりません: {args.config}"))
        if args.json:
            print(json.dumps({"passed": False, "results": results}, ensure_ascii=False, indent=2))
        else:
            _print_text(results)
        return 2
    try:
        cfg = notion_config.load_config(args.config)
        config_path = notion_config.find_config_path(args.config)
        results.append(_result("G0.config", True, detail=str(config_path) if config_path else "loaded"))
    except notion_config.ConfigError as e:
        results.append(_result("G0.config", False, "config_missing", "create_config", str(e)))
        if args.json:
            print(json.dumps({"passed": False, "results": results}, ensure_ascii=False, indent=2))
        else:
            _print_text(results)
        return 2

    try:
        log_db_id = notion_config.get_db_id("gmail-send-log", cfg)
        results.append(_result("G2.log_db", True, detail=f"db_id={log_db_id[:8]}..."))
    except notion_config.ConfigError as e:
        results.append(_result("G2.log_db", False, "log_db_id_missing", "db_setup", str(e)))

    sender = notion_config.get_sender(cfg)
    from_addr = args.from_addr or sender.get("impersonate") or ""
    results.extend(preflight.gate_g1_auth(
        cfg,
        from_addr,
        probe_api=args.probe,
        verify_from_addrs=[from_addr] if from_addr else None,
    ))

    passed = preflight.all_passed(results)
    if args.json:
        print(json.dumps({"passed": passed, "results": results}, ensure_ascii=False, indent=2))
    else:
        _print_text(results)
        if not args.probe:
            print("\nGmail の DWD/sendAs 実API確認まで行う場合は --probe を付けてください。")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
