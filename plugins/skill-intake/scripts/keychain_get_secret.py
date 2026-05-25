#!/usr/bin/env python3
"""macOS Keychain から Notion トークンを取得する唯一の経路。"""

import argparse
import os
import subprocess
import sys

DEFAULT_SERVICE = 'notion-api-key'
DEFAULT_ACCOUNT = 'skill-intake'


def _default_service():
    """毎呼出 env を再評価 (module-level 定数だと同一プロセスでの repo 切替に追随できない)。
    config 経由の差し替えは notion_http._resolve_token() → notion_config.get_token() を使うこと。
    """
    return os.environ.get('INTAKE_KEYCHAIN_SERVICE', DEFAULT_SERVICE)


def _default_account():
    return os.environ.get('INTAKE_KEYCHAIN_ACCOUNT', DEFAULT_ACCOUNT)


# 後方互換 alias (module 読み込み時の env を反映、後から変更する場合は _default_* を直接呼ぶこと)
SERVICE = _default_service()
ACCOUNT = _default_account()


class KeychainError(Exception):
    def __init__(self, message, exit_code=44):
        super().__init__(message)
        self.exit_code = exit_code


def get_secret(service=None, account=None):
    service = service or _default_service()
    account = account or _default_account()
    if sys.platform != 'darwin':
        raise KeychainError(f'unsupported platform: {sys.platform} (macOS only)')
    res = subprocess.run(
        ['/usr/bin/security', 'find-generic-password', '-s', service, '-a', account, '-w'],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise KeychainError(
            f'Keychain lookup failed (service={service}, account={account}): '
            + (res.stderr or '').strip()
        )
    token = (res.stdout or '').rstrip('\n')
    if not token:
        raise KeychainError('Keychain returned empty token')
    return token


def mask_token(t):
    if not t:
        return '(empty)'
    return f'{t[:4]}... (len={len(t)})'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--service')
    parser.add_argument('--account')
    parser.add_argument('--env-prefix')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--print-unsafe', action='store_true')
    args = parser.parse_args()

    service = args.service or SERVICE
    account = args.account or ACCOUNT
    try:
        t = get_secret(service=service, account=account)
    except KeychainError as e:
        sys.stderr.write(f'[keychain_get_secret] {e}\n')
        return e.exit_code

    if args.check:
        print(f'OK {mask_token(t)}')
    elif args.print_unsafe:
        sys.stdout.write(t)
    else:
        print(f'OK service={service} account={account} {mask_token(t)}')
        print('hint: use --print-unsafe to emit raw token (avoid in shared terminals)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
