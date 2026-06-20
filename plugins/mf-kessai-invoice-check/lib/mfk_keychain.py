#!/usr/bin/env python3
# /// script
# name: mfk_keychain
# purpose: macOS Keychain からマネーフォワード掛け払い API キーを取得する唯一の経路。
# inputs:
#   - argv: --service --account --check
#   - env: MFK_KEYCHAIN_SERVICE / MFK_KEYCHAIN_ACCOUNT / MFK_API_KEY(fallback)
# outputs:
#   - stdout: マスク表示のみ (生値は出力しない)
#   - exit: 0=OK / 44=Keychain lookup 失敗 / 9=非macOS かつ env fallback 無し
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""macOS Keychain からマネーフォワード掛け払い (MF KESSAI) API キーを取得する唯一の経路。

命名規約: service=mfkessai-api-key.xl-skills / account=xl-skills。
既存の notion-api-key.xl-skills (notion_config.py) と同じ命名規約に揃える。
実装パターンは plugins/contract-generator/lib/keychain_get_secret.py に準拠。

優先順位:
  1. macOS Keychain (service/account) ← 通常はこちら
  2. 環境変数 MFK_API_KEY ← CI / 非macOS のフォールバックのみ

取得した生値はログ出力・print してはならない。HTTP ヘッダ `apikey` にのみ載せる。
"""

import argparse
import os
import subprocess
import sys

DEFAULT_SERVICE = "mfkessai-api-key.xl-skills"
DEFAULT_ACCOUNT = "xl-skills"


def _service(cfg=None):
    """env > config(keychain_service) > DEFAULT の優先順で service 名を解決する。"""
    return os.environ.get("MFK_KEYCHAIN_SERVICE") or (cfg or {}).get("keychain_service") or DEFAULT_SERVICE


def _account(cfg=None):
    """env > config(keychain_account) > DEFAULT の優先順で account 名を解決する。"""
    return os.environ.get("MFK_KEYCHAIN_ACCOUNT") or (cfg or {}).get("keychain_account") or DEFAULT_ACCOUNT


class KeychainError(Exception):
    def __init__(self, message, exit_code=44):
        super().__init__(message)
        self.exit_code = exit_code


def _from_keychain(service, account):
    """Keychain から取得。見つからなければ None を返す (例外は投げない)。"""
    if sys.platform != "darwin":
        return None
    res = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-s", service, "-a", account, "-w"],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return None
    token = (res.stdout or "").rstrip("\n")
    return token or None


def get_api_key(service=None, account=None, cfg=None):
    """MF 掛け払い API キーを取得して生値を返す。

    service/account は env > config(cfg.keychain_service/account) > DEFAULT の優先順で解決する。
    呼び出し側は戻り値をログ・標準出力に出さないこと。
    """
    service = service or _service(cfg)
    account = account or _account(cfg)

    token = _from_keychain(service, account)
    if token:
        return token

    env_key = os.environ.get("MFK_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    if sys.platform != "darwin":
        raise KeychainError(
            f"unsupported platform: {sys.platform} (macOS only). "
            "非macOS では環境変数 MFK_API_KEY を設定してください",
            exit_code=9,
        )
    raise KeychainError(
        f"Keychain lookup failed (service={service}, account={account}). "
        "未登録なら README の Keychain 登録手順を実施してください"
    )


def mask(t):
    if not t:
        return "(empty)"
    if len(t) <= 6:
        return f"(len={len(t)})"
    return f"{t[:4]}...{t[-2:]} (len={len(t)})"


def main():
    p = argparse.ArgumentParser(description="MF掛け払い APIキーの Keychain 取得確認 (本体は表示しない)")
    p.add_argument("--service")
    p.add_argument("--account")
    p.add_argument("--check", action="store_true", help="取得可否のみ確認 (マスク表示)")
    a = p.parse_args()
    service = a.service or _service()
    account = a.account or _account()
    try:
        t = get_api_key(service=service, account=account)
    except KeychainError as e:
        sys.stderr.write(f"[mfk_keychain] {e}\n")
        return e.exit_code
    print(f"OK service={service} account={account} {mask(t)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
