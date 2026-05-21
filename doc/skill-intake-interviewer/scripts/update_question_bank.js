#!/usr/bin/env node
/**
 * update_question_bank.js
 * 用途: ヒアリング後、不足質問を references/question-bank.md に追記
 * 入力: --bank <question-bank.md> --new-questions <json: [{category,question}]> [--dry-run]
 * 出力: 追記後のファイル / dry-run 時は diff
 * 終了コード: 0=成功, 1=エラー
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--dry-run') { args['dry-run'] = true; continue; }
    args[argv[i].replace(/^--/, '')] = argv[i + 1]; i++;
  }
  return args;
}

function loadExisting(bankText) {
  const set = new Set();
  for (const line of bankText.split(/\r?\n/)) {
    const m = line.match(/^\s*-\s+(.+)$/);
    if (m) set.add(m[1].trim());
  }
  return set;
}

function appendQuestions(bankText, newQs) {
  const existing = loadExisting(bankText);
  const byCategory = new Map();
  for (const q of newQs) {
    if (existing.has(q.question.trim())) continue;
    const cat = q.category || 'その他';
    if (!byCategory.has(cat)) byCategory.set(cat, []);
    byCategory.get(cat).push(q.question.trim());
  }
  if (byCategory.size === 0) return { text: bankText, added: 0 };

  const lines = bankText.replace(/\s+$/, '').split(/\r?\n/);
  const stamp = new Date().toISOString().slice(0, 10);
  lines.push('', `## 自動追記 ${stamp}`, '');
  let added = 0;
  for (const [cat, qs] of byCategory) {
    lines.push(`### ${cat}`);
    for (const q of qs) { lines.push(`- ${q}`); added++; }
    lines.push('');
  }
  return { text: lines.join('\n') + '\n', added };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.bank || !args['new-questions']) {
    process.stderr.write('Usage: update_question_bank.js --bank <md> --new-questions <json> [--dry-run]\n');
    process.exit(1);
  }
  const bankText = fs.readFileSync(args.bank, 'utf8');
  const newQs = JSON.parse(fs.readFileSync(args['new-questions'], 'utf8'));
  const { text, added } = appendQuestions(bankText, newQs);
  if (args['dry-run']) {
    process.stdout.write(JSON.stringify({ added, preview: text.slice(-500) }, null, 2) + '\n');
  } else {
    fs.writeFileSync(args.bank, text);
    process.stdout.write(JSON.stringify({ added, path: args.bank }, null, 2) + '\n');
  }
  process.exit(0);
}

if (require.main === module) main();
module.exports = { appendQuestions, loadExisting };
