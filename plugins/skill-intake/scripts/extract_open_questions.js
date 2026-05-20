#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const MARKERS = [/\?$/, /要確認/, /未定/, /\bTBD\b/i, /わからない/, /検討中/, /後で/];

function walk(obj, prefix = '', acc = []) {
  if (obj == null) return acc;
  if (typeof obj === 'string') {
    if (MARKERS.some((re) => re.test(obj))) acc.push({ path: prefix, text: obj.trim() });
    return acc;
  }
  if (Array.isArray(obj)) { obj.forEach((v, i) => walk(v, `${prefix}[${i}]`, acc)); return acc; }
  if (typeof obj === 'object') {
    for (const k of Object.keys(obj)) walk(obj[k], prefix ? `${prefix}.${k}` : k, acc);
  }
  return acc;
}

function extract(intake) {
  const detected = walk(intake);
  const existing = Array.isArray(intake.open_questions) ? intake.open_questions : [];
  const merged = [...existing];
  for (const d of detected) {
    if (!merged.some((m) => (typeof m === 'string' ? m : m.text) === d.text)) merged.push(d);
  }
  return { count: merged.length, open_questions: merged };
}

function main(argv) {
  const file = argv[2];
  if (!file) { process.stderr.write('usage: extract_open_questions.js <intake.json>\n'); return 2; }
  let data;
  try { data = JSON.parse(fs.readFileSync(path.resolve(file), 'utf8')); }
  catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  const r = extract(data);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return 0;
}

module.exports = { extract };

if (require.main === module) {
  process.exit(main(process.argv));
}
