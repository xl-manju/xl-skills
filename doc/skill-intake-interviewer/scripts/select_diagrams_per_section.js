#!/usr/bin/env node
/**
 * select_diagrams_per_section.js
 * 用途: 各セクションの図種リストを決定。section_completeness 1〜3図/セクション
 * 入力: --input <intake.json>
 * 出力: stdout JSON { sections: { A: [type1,type2], B: [...] } }
 * 終了コード: 0=成功, 1=エラー
 */

'use strict';
const fs = require('fs');
const { select: selectType } = require('./select_diagram_type.js');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

function decideCount(secText) {
  const len = secText.length;
  if (len < 200) return 1;
  if (len < 800) return 2;
  return 3;
}

function selectPerSection(data) {
  const result = {};
  const sections = data.sections || {};
  for (const [key, sec] of Object.entries(sections)) {
    const text = JSON.stringify(sec);
    const count = decideCount(text);
    const top = selectType(data, key);
    result[key] = top.slice(0, count).map(t => ({ type: t.type, score: t.score }));
    if (result[key].length < count) {
      const used = new Set(result[key].map(x => x.type));
      const rest = selectType({ sections: { _: sec } }, '_').filter(t => !used.has(t.type));
      result[key] = result[key].concat(rest.slice(0, count - result[key].length).map(t => ({ type: t.type, score: t.score })));
    }
  }
  return { sections: result };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    process.stderr.write('Usage: select_diagrams_per_section.js --input <json>\n');
    process.exit(1);
  }
  const data = JSON.parse(fs.readFileSync(args.input, 'utf8'));
  const r = selectPerSection(data);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  process.exit(0);
}

if (require.main === module) main();
module.exports = { selectPerSection, decideCount };
