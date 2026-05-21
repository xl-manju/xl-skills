#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const AXIS_HEADINGS = {
  output_destination: ['出力先', 'Output Destination'],
  info_source: ['情報源', 'Information Source'],
  share_target: ['共有相手', 'Sharing Target'],
  true_problem: ['真の課題', 'True Problem'],
  knowledge_assets: ['ナレッジ資産', 'Knowledge Assets'],
};

function parseSections(md) {
  const lines = md.split(/\r?\n/);
  const sections = {};
  let current = null;
  let buf = [];
  for (const line of lines) {
    const m = line.match(/^#{1,4}\s+(.*?)\s*$/);
    if (m) {
      if (current) sections[current] = buf.join('\n').trim();
      current = m[1];
      buf = [];
    } else if (current) {
      buf.push(line);
    }
  }
  if (current) sections[current] = buf.join('\n').trim();
  return sections;
}

function pickAxis(sections, keys) {
  for (const k of Object.keys(sections)) {
    if (keys.some((needle) => k.includes(needle))) return sections[k];
  }
  return '';
}

function extractFrontmatter(md) {
  const m = md.match(/^---\n([\s\S]*?)\n---\n/);
  if (!m) return { meta: {}, body: md };
  const meta = {};
  for (const line of m[1].split(/\n/)) {
    const kv = line.match(/^(\w[\w_-]*)\s*:\s*(.*)$/);
    if (kv) meta[kv[1]] = kv[2].trim().replace(/^['"]|['"]$/g, '');
  }
  return { meta, body: md.slice(m[0].length) };
}

function convert(md) {
  const { meta, body } = extractFrontmatter(md);
  const sections = parseSections(body);
  const five_axes = {};
  for (const k of Object.keys(AXIS_HEADINGS)) five_axes[k] = pickAxis(sections, AXIS_HEADINGS[k]);
  const out = {
    skill_name_hint: meta.skill_name_hint || meta.name || '',
    pattern: meta.pattern || 'other',
    user_profile: sections['User Profile'] || sections['利用者プロファイル'] || '',
    '5_axes': five_axes,
    sections,
    open_questions: [],
    integrations: meta.integrations ? meta.integrations.split(/\s*,\s*/) : [],
    raw_meta: meta,
  };
  return out;
}

function main(argv) {
  const file = argv[2];
  const outFile = argv[3];
  if (!file) { process.stderr.write('usage: convert_md_to_json.js <intake.md> [intake.json]\n'); return 2; }
  let md;
  try { md = fs.readFileSync(path.resolve(file), 'utf8'); }
  catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  const json = convert(md);
  const text = JSON.stringify(json, null, 2);
  if (outFile) fs.writeFileSync(path.resolve(outFile), text + '\n');
  else process.stdout.write(text + '\n');
  return 0;
}

module.exports = { convert, parseSections };

if (require.main === module) {
  process.exit(main(process.argv));
}
