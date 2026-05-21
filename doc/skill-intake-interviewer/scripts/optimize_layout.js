#!/usr/bin/env node
/**
 * optimize_layout.js
 * 用途: ノード数で direction（TD/LR）切替・グループ化判定
 * 入力: --input <path.mmd>
 * 出力: stdout に最適化後の .mmd
 * 終了コード: 0=成功, 1=エラー
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

function countNodes(text) {
  const ids = new Set();
  const re = /(^|\s)([A-Za-z][A-Za-z0-9_]*)(\[|\(|\{|\>|\b)/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    const id = m[2];
    if (!/^(flowchart|graph|TD|TB|BT|LR|RL|subgraph|end|click|class|classDef|style|direction)$/.test(id)) {
      ids.add(id);
    }
  }
  return ids.size;
}

function chooseDirection(nodeCount) {
  if (nodeCount <= 4) return 'TD';
  if (nodeCount <= 8) return 'LR';
  return 'TB';
}

function optimize(text) {
  const lines = text.split(/\r?\n/);
  if (lines.length === 0) return text;
  const head = lines[0].trim();
  const m = head.match(/^(flowchart|graph)(\s+(TD|TB|BT|LR|RL))?(.*)$/);
  if (!m) return text;
  const nodes = countNodes(text);
  const dir = chooseDirection(nodes);
  const groupHint = nodes > 8 ? '%% suggest: group by subgraph' : '';
  lines[0] = `${m[1]} ${dir}${m[4] || ''}`;
  if (groupHint) lines.splice(1, 0, groupHint);
  return lines.join('\n');
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    process.stderr.write('Usage: optimize_layout.js --input <path>\n');
    process.exit(1);
  }
  const text = fs.readFileSync(args.input, 'utf8');
  const out = optimize(text);
  if (args.output) fs.writeFileSync(args.output, out);
  else process.stdout.write(out);
  process.exit(0);
}

if (require.main === module) main();
module.exports = { optimize, countNodes, chooseDirection };
