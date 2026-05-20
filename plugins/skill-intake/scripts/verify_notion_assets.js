#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

function hash(filePath) {
  const buf = fs.readFileSync(filePath);
  return crypto.createHash('sha256').update(buf).digest('hex').slice(0, 16);
}

function verify(manifestPath) {
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const baseDir = manifest.dest || path.dirname(manifestPath);
  const missing = [];
  const corrupted = [];
  for (const item of manifest.items || []) {
    const abs = item.absolute || path.join(baseDir, item.path);
    if (!fs.existsSync(abs)) { missing.push(item.path); continue; }
    if (item.sha256_16) {
      const h = hash(abs);
      if (h !== item.sha256_16) corrupted.push({ path: item.path, expected: item.sha256_16, actual: h });
    }
  }
  const ok = missing.length === 0 && corrupted.length === 0;
  return { ok, missing, corrupted, total: (manifest.items || []).length };
}

function main(argv) {
  const manifestFile = argv[2];
  if (!manifestFile) { process.stderr.write('usage: verify_notion_assets.js <manifest.json>\n'); return 2; }
  if (!fs.existsSync(manifestFile)) { process.stderr.write(`manifest missing: ${manifestFile}\n`); return 2; }
  const r = verify(path.resolve(manifestFile));
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return r.ok ? 0 : 1;
}

module.exports = { verify };

if (require.main === module) {
  process.exit(main(process.argv));
}
