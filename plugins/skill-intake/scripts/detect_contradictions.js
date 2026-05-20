#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const NEG = ['ない', '不要', '無し', 'なし', '使わない', '使用しない', '対象外'];
const POS = ['必要', '使う', '対象', '欲しい', 'する', '実施'];

function flatten(obj, prefix = '', acc = []) {
  if (obj == null) return acc;
  if (typeof obj === 'string') { acc.push({ path: prefix, value: obj }); return acc; }
  if (Array.isArray(obj)) { obj.forEach((v, i) => flatten(v, `${prefix}[${i}]`, acc)); return acc; }
  if (typeof obj === 'object') {
    for (const k of Object.keys(obj)) flatten(obj[k], prefix ? `${prefix}.${k}` : k, acc);
  }
  return acc;
}

function tokenize(s) {
  return s.split(/[、。\s,.;]+/).map((t) => t.trim()).filter(Boolean);
}

function detect(intake) {
  const statements = flatten(intake);
  const contradictions = [];
  for (let i = 0; i < statements.length; i += 1) {
    for (let j = i + 1; j < statements.length; j += 1) {
      const a = statements[i].value;
      const b = statements[j].value;
      const aNeg = NEG.some((n) => a.includes(n));
      const bPos = POS.some((p) => b.includes(p));
      const bNeg = NEG.some((n) => b.includes(n));
      const aPos = POS.some((p) => a.includes(p));
      if (!((aNeg && bPos) || (aPos && bNeg))) continue;
      const aToks = new Set(tokenize(a));
      const bToks = new Set(tokenize(b));
      const shared = [...aToks].filter((t) => bToks.has(t) && t.length >= 2);
      if (shared.length >= 1) {
        contradictions.push({
          a_path: statements[i].path, b_path: statements[j].path,
          shared_terms: shared, a_excerpt: a.slice(0, 80), b_excerpt: b.slice(0, 80),
        });
      }
    }
  }
  return { ok: contradictions.length === 0, count: contradictions.length, contradictions };
}

function main(argv) {
  const file = argv[2];
  if (!file) { process.stderr.write('usage: detect_contradictions.js <intake.json>\n'); return 2; }
  let data;
  try { data = JSON.parse(fs.readFileSync(path.resolve(file), 'utf8')); }
  catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  const r = detect(data);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return r.ok ? 0 : 1;
}

module.exports = { detect };

if (require.main === module) {
  process.exit(main(process.argv));
}
