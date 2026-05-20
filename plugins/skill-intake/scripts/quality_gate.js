#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const { validate } = require('./validate_intake');
const { check } = require('./check_completeness');
const { detect } = require('./detect_contradictions');

function gate(intake) {
  const v = validate(intake);
  const c = check(intake);
  const d = detect(intake);
  const checks = {
    validate_intake: { ok: v.ok, errors: v.errors },
    check_completeness: { ok: c.ok, placeholders: c.placeholders, filled_axes: c.filled_axes },
    detect_contradictions: { ok: d.ok, count: d.count },
  };
  const ok = v.ok && c.ok && d.ok;
  return { status: ok ? 'PASS' : 'FAIL', checks };
}

function main(argv) {
  const file = argv[2];
  const outFile = argv[3];
  if (!file) { process.stderr.write('usage: quality_gate.js <intake.json> [out.json]\n'); return 2; }
  let data;
  try { data = JSON.parse(fs.readFileSync(path.resolve(file), 'utf8')); }
  catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  const r = gate(data);
  const text = JSON.stringify(r, null, 2);
  if (outFile) fs.writeFileSync(path.resolve(outFile), text + '\n');
  else process.stdout.write(text + '\n');
  return r.status === 'PASS' ? 0 : 1;
}

module.exports = { gate };

if (require.main === module) {
  process.exit(main(process.argv));
}
