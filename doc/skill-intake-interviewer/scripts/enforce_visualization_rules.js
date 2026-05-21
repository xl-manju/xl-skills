#!/usr/bin/env node
/**
 * enforce_visualization_rules.js
 * 用途: 非エンジニア対応マスト 8 ルールを機械検証
 * (ノード数、ラベル長、色凡例、絵文字検出 等)
 * 入力: --input <path.mmd> [--caption <text>]
 * 出力: stdout JSON { pass, violations }
 * 終了コード: 0=PASS, 2=FAIL, 1=エラー
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

const EMOJI_RE = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{1F000}-\u{1F2FF}]/u;

function extractNodes(text) {
  const nodes = [];
  const re = /([A-Za-z][A-Za-z0-9_]*)\s*[\[\(\{]([^\]\)\}]+)[\]\)\}]/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    nodes.push({ id: m[1], label: m[2].replace(/^["']|["']$/g, '') });
  }
  return nodes;
}

function checkRules(text, caption) {
  const violations = [];
  const nodes = extractNodes(text);

  // R1: ノード数 7±2 = 上限 9
  if (nodes.length > 9) {
    violations.push({ rule: 'R1_node_count', message: `ノード数 ${nodes.length} > 9 (7±2 上限)` });
  }
  // R2: ノードラベル日本語10文字以内
  for (const n of nodes) {
    const visibleLen = [...n.label].length;
    if (visibleLen > 10) {
      violations.push({ rule: 'R2_label_length', node: n.id, label: n.label, message: `ラベル ${visibleLen} 文字 > 10` });
    }
  }
  // R3: 色凡例（classDef または style があれば legend コメントを要求）
  const hasStyle = /classDef|style\s+\w+\s+(fill|stroke):/.test(text);
  const hasLegend = /%%\s*(legend|凡例)/i.test(text);
  if (hasStyle && !hasLegend) {
    violations.push({ rule: 'R3_color_legend', message: '色を使用しているが凡例コメント (%% legend:) がない' });
  }
  // R4: 絵文字禁止（Font Awesome のみ）
  if (EMOJI_RE.test(text)) {
    violations.push({ rule: 'R4_no_emoji', message: '絵文字が含まれている。Font Awesome (fa:fa-*) を使用すること' });
  }
  // R5: caption（言いたい一言）必須
  if (!caption || caption.trim().length === 0) {
    violations.push({ rule: 'R5_caption_required', message: '図に caption (言いたい一言) が付いていない' });
  }
  // R6: 専門用語（簡易）
  const jargon = ['API', 'SDK', 'OAuth', 'CRUD', 'webhook'].filter(t => new RegExp(`\\b${t}\\b`).test(text));
  if (jargon.length > 0) {
    violations.push({ rule: 'R6_jargon_in_diagram', terms: jargon, message: '専門用語が図解内にある' });
  }
  // R7: direction 明示（flowchart/graph の場合）
  if (/^(flowchart|graph)/m.test(text) && !/(flowchart|graph)\s+(TD|TB|BT|LR|RL)/.test(text)) {
    violations.push({ rule: 'R7_direction_required', message: 'flowchart/graph の direction が明示されていない' });
  }
  // R8: 視覚理解度★1図種の禁止（quadrantChart, sankey 単独使用は警告）
  const head = text.split('\n')[0].trim();
  if (/^(quadrantChart|sankey)/.test(head)) {
    violations.push({ rule: 'R8_low_readability', message: `${head.split(/\s/)[0]} は非エンジニア理解度★1。代替を検討` });
  }

  return { pass: violations.length === 0, violations, node_count: nodes.length };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    process.stderr.write('Usage: enforce_visualization_rules.js --input <path> [--caption <text>]\n');
    process.exit(1);
  }
  const text = fs.readFileSync(args.input, 'utf8');
  const r = checkRules(text, args.caption || '');
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  process.exit(r.pass ? 0 : 2);
}

if (require.main === module) main();
module.exports = { checkRules, extractNodes, EMOJI_RE };
