#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const MIN = 1;
const MAX = 3;

function enforce(perSection) {
  const out = {};
  const violations = [];
  for (const sec of Object.keys(perSection)) {
    const arr = Array.isArray(perSection[sec]) ? perSection[sec] : [perSection[sec]];
    if (arr.length < MIN) violations.push({ section: sec, count: arr.length, rule: `min ${MIN}` });
    if (arr.length > MAX) violations.push({ section: sec, count: arr.length, rule: `max ${MAX}` });
    out[sec] = arr.slice(0, MAX);
  }
  return { ok: violations.length === 0, result: out, violations };
}

function main(argv) {
  const file = argv[2];
  if (!file) { process.stderr.write('usage: select_diagrams_per_section.js <map.json>\n'); return 2; }
  let data;
  try { data = JSON.parse(fs.readFileSync(path.resolve(file), 'utf8')); }
  catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  const r = enforce(data);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return r.ok ? 0 : 1;
}

module.exports = { enforce, MIN, MAX };

if (require.main === module) {
  process.exit(main(process.argv));
}
