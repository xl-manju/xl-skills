#!/usr/bin/env python3
"""macOS Keychain から Notion トークンを取得する唯一の経路。"""

import argparse
import os
import subprocess
import sys

SERVICE = os.environ.get('INTAKE_KEYCHAIN_SERVICE', 'notion-api-key')
ACCOUNT = os.environ.get('INTAKE_KEYCHAIN_ACCOUNT', 'skill-intake')


class KeychainError(Exception):
    def __init__(self, message, exit_code=44):
        super().__init__(message)
        self.exit_code = exit_code


def get_secret(service=None, account=None):
    service = service or SERVICE
    account = account or ACCOUNT
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
