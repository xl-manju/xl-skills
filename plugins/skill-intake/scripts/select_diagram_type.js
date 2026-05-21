#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const RULES = [
  { type: 'sequence', keywords: ['順番', 'やりとり', 'メッセージ', '対話', 'sequence', '会話'] },
  { type: 'flow', keywords: ['手順', '流れ', 'プロセス', 'process', '工程', 'workflow'] },
  { type: 'quadrant', keywords: ['比較', '優先', '位置付け', '象限', 'trade-off', '評価'] },
  { type: 'state', keywords: ['状態', 'ステート', 'ライフサイクル', '遷移'] },
  { type: 'pie', keywords: ['割合', 'シェア', '比率', '構成比'] },
  { type: 'mindmap', keywords: ['分類', '構造', '要素', '体系'] },
  { type: 'class', keywords: ['データ構造', '属性', '関係'] },
  { type: 'er', keywords: ['DB', 'テーブル', 'スキーマ', 'entity'] },
  { type: 'gantt', keywords: ['期間', 'スケジュール', 'タイムライン'] },
  { type: 'journey', keywords: ['体験', 'ユーザー体験', 'journey'] },
  { type: 'timeline', keywords: ['年表', '歴史', 'timeline'] },
  { type: 'graph', keywords: [] },
];

function pick(text) {
  const t = String(text || '');
  for (const r of RULES) {
    if (r.keywords.some((k) => t.includes(k))) return r.type;
  }
  return 'flow';
}

function selectAll(intake) {
  const sections = intake.sections || {};
  const out = {};
  for (const k of Object.keys(sections)) out[k] = pick(sections[k]);
  return out;
}

function main(argv) {
  const file = argv[2];
  if (!file) { process.stderr.write('usage: select_diagram_type.js <intake.json>\n'); return 2; }
  let data;
  try { data = JSON.parse(fs.readFileSync(path.resolve(file), 'utf8')); }
  catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  const r = selectAll(data);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return 0;
}

module.exports = { pick, selectAll };

if (require.main === module) {
  process.exit(main(process.argv));
}
