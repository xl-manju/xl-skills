#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const AXES = ['output_destination', 'info_source', 'share_target', 'true_problem', 'knowledge_assets'];
const PLACEHOLDER_PATTERNS = [/\bTBD\b/i, /未定/, /\?{2,}/, /^\s*[-—]\s*$/, /要確認/, /後で決め/];

function isPlaceholder(s) {
  if (typeof s !== 'string') return true;
  const v = s.trim();
  if (v.length < 4) return true;
  return PLACEHOLDER_PATTERNS.some((re) => re.test(v));
}

function check(intake) {
  const axes = (intake && (intake['5_axes'] || intake.five_axes)) || {};
  const filled = {};
  const placeholders = [];
  let count = 0;
  for (const k of AXES) {
    const val = axes[k];
    const ok = !isPlaceholder(val);
    filled[k] = ok;
    if (ok) count += 1;
    else placeholders.push(k);
  }
  return {
    ok: count === AXES.length,
    filled_axes: count,
    total_axes: AXES.length,
    detail: filled,
    placeholders,
  };
}

function main(argv) {
  const file = argv[2];
  if (!file) {
    process.stderr.write('usage: check_completeness.js <intake.json>\n');
    return 2;
  }
  let data;
  try { data = JSON.parse(fs.readFileSync(path.resolve(file), 'utf8')); }
  catch (e) {
    process.stderr.write(`input error: ${e.message}\n`);
    return 2;
  }
  const r = check(data);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return r.ok ? 0 : 1;
}

module.exports = { check, isPlaceholder };

if (require.main === module) {
  process.exit(main(process.argv));
}
