#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const ALLOWED = new Set(['.png', '.svg', '.jpg', '.jpeg', '.gif']);

function walk(dir, acc = []) {
  if (!fs.existsSync(dir)) return acc;
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(p, acc);
    else acc.push(p);
  }
  return acc;
}

function hash(filePath) {
  const buf = fs.readFileSync(filePath);
  return crypto.createHash('sha256').update(buf).digest('hex').slice(0, 16);
}

function prepare(srcDir, destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  const items = [];
  const skipped = [];
  for (const file of walk(srcDir)) {
    const ext = path.extname(file).toLowerCase();
    if (!ALLOWED.has(ext)) { skipped.push({ path: file, reason: 'ext' }); continue; }
    const rel = path.relative(srcDir, file);
    const dest = path.join(destDir, rel);
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(file, dest);
    const stat = fs.statSync(dest);
    items.push({
      path: rel,
      absolute: dest,
      size: stat.size,
      sha256_16: hash(dest),
      ext,
    });
  }
  const summary = {
    total: items.length,
    by_ext: items.reduce((a, it) => { a[it.ext] = (a[it.ext] || 0) + 1; return a; }, {}),
  };
  return { items, skipped, summary, src: srcDir, dest: destDir };
}

function main(argv) {
  const src = argv[2];
  const dest = argv[3];
  const out = argv[4];
  if (!src || !dest) { process.stderr.write('usage: prepare_notion_assets.js <src> <dest> [manifest.json]\n'); return 2; }
  const manifest = prepare(path.resolve(src), path.resolve(dest));
  const text = JSON.stringify(manifest, null, 2);
  const manifestPath = out ? path.resolve(out) : path.join(path.resolve(dest), 'manifest.json');
  fs.writeFileSync(manifestPath, text + '\n');
  process.stdout.write(JSON.stringify({ ok: true, manifest: manifestPath, total: manifest.summary.total }) + '\n');
  return 0;
}

module.exports = { prepare };

if (require.main === module) {
  process.exit(main(process.argv));
}
