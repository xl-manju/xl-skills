#!/usr/bin/env node
/**
 * verify_notion_assets.js
 * 用途: Notion 公開前の MUST ゲート。マニフェストの全 image_upload 項目について
 *       - image_path が存在
 *       - サイズ > 0
 *       - PNG マジックナンバー（89 50 4E 47）一致
 *       を確認。1つでも欠けたら exit 1。
 * 入力: --manifest <manifest.json>
 * 出力: stdout JSON { ok, total, verified, failures: [...] }
 * 終了コード: 0=全PASS, 1=失敗あり（公開停止）
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (!k.startsWith('--')) continue;
    const key = k.replace(/^--/, '');
    const next = argv[i + 1];
    if (!next || next.startsWith('--')) { args[key] = true; }
    else { args[key] = next; i++; }
  }
  return args;
}

function isPng(filePath) {
  try {
    const fd = fs.openSync(filePath, 'r');
    const buf = Buffer.alloc(8);
    fs.readSync(fd, buf, 0, 8, 0);
    fs.closeSync(fd);
    return buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4E && buf[3] === 0x47;
  } catch (_) { return false; }
}

function verify(manifestPath) {
  const m = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const failures = [];
  let verified = 0;
  for (const item of m.items || []) {
    if (item.route !== 'image_upload') { verified++; continue; }
    const p = item.image_path;
    if (!p) { failures.push({ id: item.id, reason: 'image_path missing' }); continue; }
    if (!fs.existsSync(p)) { failures.push({ id: item.id, reason: `not found: ${p}` }); continue; }
    const size = fs.statSync(p).size;
    if (size === 0) { failures.push({ id: item.id, reason: `empty: ${p}` }); continue; }
    if (p.toLowerCase().endsWith('.png') && !isPng(p)) {
      failures.push({ id: item.id, reason: `not a valid PNG: ${p}` }); continue;
    }
    verified++;
  }
  return {
    ok: failures.length === 0,
    total: (m.items || []).length,
    verified,
    failures,
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.manifest) {
    process.stderr.write('Usage: verify_notion_assets.js --manifest <manifest.json>\n');
    process.exit(1);
  }
  try {
    const r = verify(args.manifest);
    process.stdout.write(JSON.stringify(r, null, 2) + '\n');
    process.exit(r.ok ? 0 : 1);
  } catch (e) {
    process.stderr.write(`verify failed: ${e.message}\n`);
    process.exit(1);
  }
}

if (require.main === module) main();
module.exports = { verify };
