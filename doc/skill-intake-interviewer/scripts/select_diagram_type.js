#!/usr/bin/env node
/**
 * select_diagram_type.js
 * 用途: 入力データから最適図種を上位2つ選定
 * 入力: --input <intake.json> [--section <key>]
 * 出力: stdout JSON [{type, score, reason}]
 * 終了コード: 0=成功, 1=エラー
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

const CATALOG = [
  { type: 'flowchart', signals: ['フロー', '流れ', '手順', 'ステップ', 'process', 'step'] },
  { type: 'sequenceDiagram', signals: ['順序', 'やりとり', '応答', 'request', 'response', 'API'] },
  { type: 'stateDiagram', signals: ['状態', 'ステート', '遷移', 'state'] },
  { type: 'erDiagram', signals: ['データ', 'モデル', 'スキーマ', 'テーブル', 'entity'] },
  { type: 'classDiagram', signals: ['クラス', 'オブジェクト', '構造', 'class'] },
  { type: 'gantt', signals: ['期間', 'スケジュール', '日程', 'timeline'] },
  { type: 'pie', signals: ['比率', '割合', '構成比', 'percent'] },
  { type: 'mindmap', signals: ['発散', 'アイデア', '分類', 'mindmap'] },
  { type: 'timeline', signals: ['時系列', '歴史', '推移'] },
  { type: 'journey', signals: ['ユーザー体験', 'カスタマー', 'journey'] },
  { type: 'quadrantChart', signals: ['4象限', '優先度', 'matrix'] },
  { type: 'gitGraph', signals: ['ブランチ', 'バージョン', 'git'] },
  { type: 'numbered-steps', signals: ['1番目', '2番目', '①', '②', '段階'] },
  { type: 'persona-card', signals: ['ペルソナ', 'プロフィール', 'persona', 'ターゲット'] },
  { type: 'before-after', signals: ['ビフォー', 'アフター', '改善前', '改善後', 'before', 'after'] },
  { type: 'comparison-table', signals: ['比較', '違い', 'vs', '対比'] },
  { type: 'traffic-light', signals: ['優先度', '緊急度', 'OK/NG', 'ステータス'] },
  { type: 'progress-bar', signals: ['進捗', '達成率', 'progress'] },
  { type: 'icon-grid', signals: ['機能一覧', 'カテゴリ', 'icon'] },
  { type: 'sankey', signals: ['流量', '配分', 'sankey'] },
];

function score(text, signals) {
  const t = String(text).toLowerCase();
  let s = 0;
  for (const sig of signals) {
    if (t.includes(String(sig).toLowerCase())) s += 1;
  }
  return s;
}

function select(data, section) {
  const target = section && data.sections && data.sections[section]
    ? JSON.stringify(data.sections[section])
    : JSON.stringify(data);
  const scored = CATALOG.map(c => ({
    type: c.type,
    score: score(target, c.signals),
    reason: c.signals.filter(s => target.toLowerCase().includes(String(s).toLowerCase())).slice(0, 3),
  })).sort((a, b) => b.score - a.score);
  const top = scored.filter(x => x.score > 0).slice(0, 2);
  if (top.length === 0) return [{ type: 'flowchart', score: 0, reason: ['default fallback'] }];
  return top;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    process.stderr.write('Usage: select_diagram_type.js --input <json> [--section <key>]\n');
    process.exit(1);
  }
  const data = JSON.parse(fs.readFileSync(args.input, 'utf8'));
  const result = select(data, args.section);
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  process.exit(0);
}

if (require.main === module) main();
module.exports = { select, CATALOG };
