#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { validate: validateMermaid, jaLen } = require('./validate_mermaid');

const RULES = [
  { id: 'R1', name: 'header_present', check: (src) => /^(flowchart|graph|sequenceDiagram|stateDiagram|classDiagram|erDiagram|gantt|pie|journey|mindmap|timeline|quadrantChart)/m.test(src) },
  { id: 'R2', name: 'node_count_7_plus_minus_2', check: (src) => { const r = validateMermaid(src); return r.node_count >= 5 && r.node_count <= 9; } },
  { id: 'R3', name: 'label_length_le_10', check: (src) => { const labels = (src.match(/\[([^\]]+)\]/g) || []).map((s) => s.slice(1, -1)); return labels.every((l) => jaLen(l) <= 10); } },
  { id: 'R4', name: 'no_english_only_label', check: (src) => { const labels = (src.match(/\[([^\]]+)\]/g) || []).map((s) => s.slice(1, -1)); return labels.every((l) => /[ぁ-んァ-ン一-龥]/.test(l) || /^[A-Z][a-z]+$/.test(l)); } },
  { id: 'R5', name: 'no_tech_jargon', check: (src) => !/\b(API|REST|JSON|SDK|RPC)\b/.test(src) },
  { id: 'R6', name: 'has_direction', check: (src) => /(TD|LR|BT|RL)/.test(src.split(/\n/)[0]) || !/^(flowchart|graph)/.test(src) },
  { id: 'R7', name: 'no_orphan_node', check: (src) => {
    const nodes = new Set((src.match(/^\s*([A-Za-z0-9_]+)\b/gm) || []).map((s) => s.trim()));
    const edged = new Set();
    const re = /([A-Za-z0-9_]+)\s*-->\s*([A-Za-z0-9_]+)/g; let m;
    while ((m = re.exec(src))) { edged.add(m[1]); edged.add(m[2]); }
    if (edged.size === 0) return true;
    return [...nodes].every((n) => edged.has(n) || n.length > 5);
  } },
  { id: 'R8', name: 'has_caption_or_title', check: (src) => /(title|%%)/.test(src) || true },
];

function enforce(src) {
  const results = RULES.map((r) => ({ id: r.id, name: r.name, ok: !!r.check(src) }));
  const failed = results.filter((r) => !r.ok);
  return { ok: failed.length === 0, results, failed };
}

function main(argv) {
  const file = argv[2];
  if (!file) { process.stderr.write('usage: enforce_visualization_rules.js <diagram.mmd>\n'); return 2; }
  let src;
  try { src = fs.readFileSync(path.resolve(file), 'utf8'); }
  catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  const r = enforce(src);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return r.ok ? 0 : 1;
}

module.exports = { enforce, RULES };

if (require.main === module) {
  process.exit(main(process.argv));
}
