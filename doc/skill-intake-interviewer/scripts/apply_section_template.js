#!/usr/bin/env node
/**
 * apply_section_template.js
 * 用途: assets/skillヒアリングシート/ の全シートにセクション統一テンプレを一括適用
 * 入力: --sheet-dir <dir> --template <path> [--dry-run]
 * 出力: 各シートに不足セクションを追加
 * 終了コード: 0=成功, 1=エラー
 */

'use strict';
const fs = require('fs');
const path = require('path');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--dry-run') { args['dry-run'] = true; continue; }
    args[argv[i].replace(/^--/, '')] = argv[i + 1]; i++;
  }
  return args;
}

const REQUIRED_SECTIONS = ['説明', '質問', '選択肢', 'サンプル', 'アンチパターン', '図解'];

function listMarkdownFiles(dir) {
  const out = [];
  const stack = [dir];
  while (stack.length) {
    const d = stack.pop();
    if (!fs.existsSync(d)) continue;
    for (const name of fs.readdirSync(d)) {
      const p = path.join(d, name);
      const st = fs.statSync(p);
      if (st.isDirectory()) stack.push(p);
      else if (/\.md$/i.test(name)) out.push(p);
    }
  }
  return out;
}

function findMissingSections(text) {
  const missing = [];
  for (const sec of REQUIRED_SECTIONS) {
    const re = new RegExp(`^##?\\s*${sec}`, 'im');
    if (!re.test(text)) missing.push(sec);
  }
  return missing;
}

function buildTemplateBlock(template, missing) {
  const blocks = [];
  for (const sec of missing) {
    const re = new RegExp(`(^##\\s*${sec}[\\s\\S]*?)(?=\\n##\\s|$)`, 'im');
    const m = template.match(re);
    if (m) blocks.push(m[1].trimEnd());
    else blocks.push(`## ${sec}\n\n[?] 未記入\n`);
  }
  return blocks.join('\n\n');
}

function apply(filePath, template, dryRun) {
  const text = fs.readFileSync(filePath, 'utf8');
  const missing = findMissingSections(text);
  if (missing.length === 0) return { file: filePath, action: 'skip', missing: [] };
  const block = buildTemplateBlock(template, missing);
  const updated = text.replace(/\s*$/, '') + '\n\n' + block + '\n';
  if (!dryRun) fs.writeFileSync(filePath, updated);
  return { file: filePath, action: dryRun ? 'preview' : 'updated', missing };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args['sheet-dir'] || !args.template) {
    process.stderr.write('Usage: apply_section_template.js --sheet-dir <dir> --template <md> [--dry-run]\n');
    process.exit(1);
  }
  const tmpl = fs.readFileSync(args.template, 'utf8');
  const files = listMarkdownFiles(args['sheet-dir']);
  const results = files.map(f => apply(f, tmpl, !!args['dry-run']));
  process.stdout.write(JSON.stringify({ count: files.length, results }, null, 2) + '\n');
  process.exit(0);
}

if (require.main === module) main();
module.exports = { apply, findMissingSections, listMarkdownFiles, REQUIRED_SECTIONS };
