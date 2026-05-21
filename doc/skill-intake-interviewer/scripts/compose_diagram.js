#!/usr/bin/env node
/**
 * compose_diagram.js
 * 用途: テンプレに変数を流し込み Mermaid 構文を生成
 * 入力: --template <path> --vars <json>
 * 出力: stdout に .mmd 文字列
 * 終了コード: 0=成功, 1=エラー
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

function render(template, vars) {
  return template.replace(/\{\{\s*([\w.]+)\s*(?:\|\s*(.+?))?\s*\}\}/g, (m, key, fallback) => {
    const path = key.split('.');
    let v = vars;
    for (const p of path) {
      if (v == null) { v = undefined; break; }
      v = v[p];
    }
    if (v == null) return fallback != null ? fallback : '';
    if (Array.isArray(v)) return v.join('\n');
    return String(v);
  });
}

function expandLoops(template, vars) {
  return template.replace(/\{\{#each\s+(\w+)\}\}([\s\S]*?)\{\{\/each\}\}/g, (m, key, body) => {
    const arr = vars[key];
    if (!Array.isArray(arr)) return '';
    return arr.map((item, idx) => {
      const ctx = typeof item === 'object' ? { ...item, '@index': idx } : { '.': item, '@index': idx };
      return render(body, ctx);
    }).join('');
  });
}

function compose(template, vars) {
  const looped = expandLoops(template, vars);
  return render(looped, vars);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.template || !args.vars) {
    process.stderr.write('Usage: compose_diagram.js --template <path> --vars <json>\n');
    process.exit(1);
  }
  const tmpl = fs.readFileSync(args.template, 'utf8');
  const vars = JSON.parse(fs.readFileSync(args.vars, 'utf8'));
  const out = compose(tmpl, vars);
  process.stdout.write(out);
  process.exit(0);
}

if (require.main === module) main();
module.exports = { compose, render, expandLoops };
