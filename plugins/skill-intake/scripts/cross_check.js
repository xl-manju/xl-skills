#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const { convert } = require('./convert_md_to_json');

const AXES = ['output_destination', 'info_source', 'share_target', 'true_problem', 'knowledge_assets'];

function norm(s) { return String(s || '').replace(/\s+/g, ' ').trim(); }

function similarity(a, b) {
  const na = norm(a); const nb = norm(b);
  if (!na && !nb) return 1;
  if (!na || !nb) return 0;
  const sa = new Set(na.split(/[\s、。,.]+/).filter(Boolean));
  const sb = new Set(nb.split(/[\s、。,.]+/).filter(Boolean));
  const inter = [...sa].filter((x) => sb.has(x)).length;
  const union = new Set([...sa, ...sb]).size;
  return union ? inter / union : 0;
}

function cross(md, json) {
  const fromMd = convert(md);
  const mdAxes = fromMd['5_axes'] || {};
  const jsonAxes = json['5_axes'] || json.five_axes || {};
  const mismatches = [];
  for (const k of AXES) {
    const sim = similarity(mdAxes[k], jsonAxes[k]);
    if (sim < 0.4) {
      mismatches.push({ axis: k, similarity: +sim.toFixed(2), md_excerpt: norm(mdAxes[k]).slice(0, 60), json_excerpt: norm(jsonAxes[k]).slice(0, 60) });
    }
  }
  return { ok: mismatches.length === 0, mismatches };
}

function main(argv) {
  const mdFile = argv[2];
  const jsonFile = argv[3];
  if (!mdFile || !jsonFile) { process.stderr.write('usage: cross_check.js <intake.md> <intake.json>\n'); return 2; }
  let md; let json;
  try {
    md = fs.readFileSync(path.resolve(mdFile), 'utf8');
    json = JSON.parse(fs.readFileSync(path.resolve(jsonFile), 'utf8'));
  } catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  const r = cross(md, json);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return r.ok ? 0 : 1;
}

module.exports = { cross, similarity };

if (require.main === module) {
  process.exit(main(process.argv));
}
