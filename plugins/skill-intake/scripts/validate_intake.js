#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const REQUIRED_AXES = ['output_destination', 'info_source', 'share_target', 'true_problem', 'knowledge_assets'];

function validate(intake) {
  const errors = [];
  if (!intake || typeof intake !== 'object') {
    return { ok: false, errors: ['intake is not an object'] };
  }
  if (!('5_axes' in intake) && !('five_axes' in intake)) {
    errors.push('missing top-level key: 5_axes (or five_axes)');
  }
  if (!('user_profile' in intake)) {
    errors.push('missing top-level key: user_profile');
  }
  const axes = intake['5_axes'] || intake.five_axes;
  if (!axes || typeof axes !== 'object') {
    errors.push('5_axes missing or not an object');
  } else {
    for (const k of REQUIRED_AXES) {
      if (!(k in axes)) errors.push(`5_axes.${k} missing`);
      else if (typeof axes[k] !== 'string' || axes[k].trim() === '') {
        errors.push(`5_axes.${k} empty`);
      }
    }
  }
  if (intake.user_profile && typeof intake.user_profile !== 'object' && typeof intake.user_profile !== 'string') {
    errors.push('user_profile invalid type');
  }
  return { ok: errors.length === 0, errors };
}

function loadJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function main(argv) {
  const file = argv[2];
  if (!file) {
    process.stderr.write('usage: validate_intake.js <intake.json>\n');
    return 2;
  }
  let intake;
  try { intake = loadJson(path.resolve(file)); }
  catch (e) {
    process.stderr.write(`input error: ${e.message}\n`);
    return 2;
  }
  const r = validate(intake);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return r.ok ? 0 : 1;
}

module.exports = { validate };

if (require.main === module) {
  process.exit(main(process.argv));
}
