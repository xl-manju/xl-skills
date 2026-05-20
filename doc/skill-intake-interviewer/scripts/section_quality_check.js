#!/usr/bin/env node
/**
 * section_quality_check.js
 * 用途: セクション必要十分検証（説明文/質問/選択肢/サンプル/アンチパターン/図解の充足）
 * 入力: --input <section.md> [--section-key A]
 * 出力: stdout JSON { pass, missing, present }
 * 終了コード: 0=PASS, 2=不足, 1=エラー
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

const REQUIRED = [
  { key: 'description', regex: /^##?\s*(説明|概要|description)/im, label: '説明文' },
  { key: 'questions', regex: /^##?\s*(質問|問い|questions?)/im, label: '質問' },
  { key: 'options', regex: /^##?\s*(選択肢|候補|options?)/im, label: '選択肢' },
  { key: 'sample', regex: /^##?\s*(サンプル|例|example)/im, label: 'サンプル' },
  { key: 'antipattern', regex: /^##?\s*(アンチパターン|失敗例|anti[_\s-]?pattern)/im, label: 'アンチパターン' },
  { key: 'diagram', regex: /```mermaid|<svg|!\[.*\]\(.*\.(svg|png)\)/i, label: '図解' },
];

function check(text) {
  const present = [];
  const missing = [];
  for (const r of REQUIRED) {
    if (r.regex.test(text)) present.push(r.key);
    else missing.push({ key: r.key, label: r.label });
  }
  return { pass: missing.length === 0, present, missing };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    process.stderr.write('Usage: section_quality_check.js --input <md> [--section-key A]\n');
    process.exit(1);
  }
  const text = fs.readFileSync(args.input, 'utf8');
  const r = check(text);
  if (args['section-key']) r.section = args['section-key'];
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  process.exit(r.pass ? 0 : 2);
}

if (require.main === module) main();
module.exports = { check, REQUIRED };
