#!/usr/bin/env node
/**
 * extract_open_questions.js
 * 用途: [?] を全シートから抽出して未解決リスト化
 * 入力: --input <intake.json|intake.md>
 * 出力: stdout JSON { open_questions: [{path, text}] }
 * 終了コード: 0=成功, 1=エラー
 */

'use strict';
const fs = require('fs');
const path = require('path');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

function walk(node, pathStr, out) {
  if (node == null) return;
  if (typeof node === 'string') {
    if (/\[\?\]/.test(node)) {
      out.push({ path: pathStr, text: node.trim() });
    }
    return;
  }
  if (Array.isArray(node)) {
    node.forEach((v, i) => walk(v, `${pathStr}[${i}]`, out));
    return;
  }
  if (typeof node === 'object') {
    for (const k of Object.keys(node)) {
      walk(node[k], pathStr ? `${pathStr}.${k}` : k, out);
    }
  }
}

function fromMarkdown(text) {
  const out = [];
  const lines = text.split(/\r?\n/);
  let currentHeading = '';
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const h = line.match(/^#{1,6}\s+(.+)$/);
    if (h) currentHeading = h[1].trim();
    if (/\[\?\]/.test(line)) {
      out.push({ path: currentHeading || `line:${i + 1}`, text: line.trim() });
    }
  }
  return out;
}

function extract(input, isMarkdown) {
  if (isMarkdown) return fromMarkdown(input);
  const out = [];
  walk(input, '', out);
  return out;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    process.stderr.write('Usage: extract_open_questions.js --input <path>\n');
    process.exit(1);
  }
  const ext = path.extname(args.input).toLowerCase();
  const raw = fs.readFileSync(args.input, 'utf8');
  let qs;
  if (ext === '.md' || ext === '.markdown') {
    qs = extract(raw, true);
  } else {
    qs = extract(JSON.parse(raw), false);
  }
  process.stdout.write(JSON.stringify({ open_questions: qs, count: qs.length }, null, 2) + '\n');
  process.exit(0);
}

if (require.main === module) main();
module.exports = { extract, fromMarkdown, walk };
