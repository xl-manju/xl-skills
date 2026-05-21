#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const AXES = ['output_destination', 'info_source', 'share_target', 'true_problem', 'knowledge_assets'];

function score(intake, manifest) {
  const axes = intake['5_axes'] || intake.five_axes || {};
  let filled = 0;
  for (const k of AXES) if (typeof axes[k] === 'string' && axes[k].trim().length >= 4) filled += 1;
  const axisScore = filled / AXES.length;
  const visCount = manifest && manifest.summary && typeof manifest.summary.total === 'number'
    ? manifest.summary.total
    : (manifest && Array.isArray(manifest.items) ? manifest.items.length : 0);
  const visScore = Math.min(visCount / 12, 1);
  const openQ = Array.isArray(intake.open_questions) ? intake.open_questions.length : 0;
  const openPenalty = Math.max(0, 1 - openQ * 0.05);
  const total = +(0.55 * axisScore + 0.35 * visScore + 0.10 * openPenalty).toFixed(3);
  return { score: total, components: { axisScore, visScore, openPenalty }, axes_filled: filled, visualization_count: visCount };
}

function main(argv) {
  const intakeFile = argv[2];
  const manifestFile = argv[3];
  if (!intakeFile) { process.stderr.write('usage: measure_value_realized.js <intake.json> [manifest.json]\n'); return 2; }
  let intake; let manifest = null;
  try {
    intake = JSON.parse(fs.readFileSync(path.resolve(intakeFile), 'utf8'));
    if (manifestFile && fs.existsSync(manifestFile)) manifest = JSON.parse(fs.readFileSync(path.resolve(manifestFile), 'utf8'));
  } catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  const r = score(intake, manifest);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return 0;
}

module.exports = { score };

if (require.main === module) {
  process.exit(main(process.argv));
}
