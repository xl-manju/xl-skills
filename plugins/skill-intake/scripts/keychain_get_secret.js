#!/usr/bin/env node
// keychain_get_secret.js
// macOS Keychain から Notion トークンを取得する唯一の経路。
// 他の script / agent はこのモジュール経由でのみトークンに触れること。
// exit codes: 0=OK, 2=INPUT_ERROR, 44=KEYCHAIN_ERROR

'use strict';

const { spawnSync } = require('node:child_process');

const SERVICE = process.env.INTAKE_KEYCHAIN_SERVICE || 'notion-api-key';
const ACCOUNT = process.env.INTAKE_KEYCHAIN_ACCOUNT || 'skill-intake-interviewer';

function getSecret({ service = SERVICE, account = ACCOUNT } = {}) {
  if (process.platform !== 'darwin') {
    const err = new Error(`unsupported platform: ${process.platform} (macOS only)`);
    err.code = 'PLATFORM_UNSUPPORTED';
    err.exit = 44;
    throw err;
  }
  const res = spawnSync('/usr/bin/security', [
    'find-generic-password', '-s', service, '-a', account, '-w',
  ], { encoding: 'utf8' });

  if (res.status !== 0) {
    const err = new Error(
      `Keychain lookup failed (service=${service}, account=${account}): ` +
      (res.stderr || '').trim()
    );
    err.code = 'KEYCHAIN_NOT_FOUND';
    err.exit = 44;
    throw err;
  }
  const token = (res.stdout || '').replace(/\n$/, '');
  if (!token) {
    const err = new Error('Keychain returned empty token');
    err.code = 'KEYCHAIN_EMPTY';
    err.exit = 44;
    throw err;
  }
  return token;
}

function maskToken(t) {
  if (!t) return '(empty)';
  const prefix = t.slice(0, 4);
  return `${prefix}... (len=${t.length})`;
}

module.exports = { getSecret, maskToken, SERVICE, ACCOUNT };

if (require.main === module) {
  const args = new Set(process.argv.slice(2));
  try {
    const t = getSecret();
    if (args.has('--check')) {
      console.log(`OK ${maskToken(t)}`);
    } else if (args.has('--print-unsafe')) {
      process.stdout.write(t);
    } else {
      console.log(`OK service=${SERVICE} account=${ACCOUNT} ${maskToken(t)}`);
      console.log('hint: use --print-unsafe to emit raw token (avoid in shared terminals)');
    }
    process.exit(0);
  } catch (e) {
    console.error(`[keychain_get_secret] ${e.message}`);
    process.exit(e.exit || 1);
  }
}
