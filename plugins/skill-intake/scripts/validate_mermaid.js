#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const HEADERS = ['flowchart', 'graph', 'sequenceDiagram', 'classDiagram', 'stateDiagram', 'stateDiagram-v2',
  'erDiagram', 'gantt', 'pie', 'journey', 'mindmap', 'timeline', 'quadrantChart'];

function jaLen(s) {
  let n = 0;
  for (const ch of s) n += ch.charCodeAt(0) > 127 ? 1 : 0.5;
  return n;
}

function extractNodeLabels(src) {
  const labels = [];
  const reBracket = /\[([^\]\n]+)\]/g;
  const reParen = /\(([^)\n]+)\)/g;
  let m;
  while ((m = reBracket.exec(src))) labels.push(m[1]);
  while ((m = reParen.exec(src))) labels.push(m[1]);
  return labels;
}

function validate(src) {
  const errors = [];
  const warnings = [];
  const trimmed = src.trim();
  if (!trimmed) return { ok: false, errors: ['empty diagram'], warnings, node_count: 0 };
  const firstWord = trimmed.split(/\s+/)[0];
  if (!HEADERS.some((h) => firstWord.startsWith(h))) {
    errors.push(`unknown diagram header: ${firstWord}`);
  }
  const lines = trimmed.split(/\n/).filter((l) => l.trim() && !l.trim().startsWith('%%'));
  const bodyLines = lines.slice(1);
  const nodeCount = bodyLines.length;
  if (nodeCount < 5 || nodeCount > 9) {
    warnings.push(`node/line count ${nodeCount} outside 7±2`);
  }
  const labels = extractNodeLabels(trimmed);
  for (const lbl of labels) {
    if (jaLen(lbl) > 10) warnings.push(`label too long: "${lbl}"`);
  }
  return { ok: errors.length === 0, errors, warnings, node_count: nodeCount, label_count: labels.length };
}

function main(argv) {
  const file = argv[2];
  if (!file) { process.stderr.write('usage: validate_mermaid.js <diagram.mmd>\n'); return 2; }
  let src;
  try { src = fs.readFileSync(path.resolve(file), 'utf8'); }
  catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  const r = validate(src);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return r.ok ? 0 : 1;
}

module.exports = { validate, jaLen };

if (require.main === module) {
  process.exit(main(process.argv));
}
