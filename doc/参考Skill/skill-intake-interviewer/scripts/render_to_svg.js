#!/usr/bin/env node
/**
 * render_to_svg.js
 * 用途: .mmd → .svg。@mermaid-js/mermaid-cli (mmdc) が利用可能なら呼ぶ、無ければ警告して停止
 * 入力: --input <path.mmd> --output <path.svg> [--theme default|dark]
 * 出力: SVG ファイル
 * 終了コード: 0=成功, 1=エラー（mmdc未導入含む）
 */

'use strict';
const fs = require('fs');
const { execSync } = require('child_process');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

function hasMmdc() {
  try { execSync('which mmdc', { stdio: 'ignore' }); return true; }
  catch (_) { return false; }
}

function render(input, output, theme) {
  if (!hasMmdc()) {
    throw new Error('mmdc (@mermaid-js/mermaid-cli) is not installed. Install via: npm install -g @mermaid-js/mermaid-cli');
  }
  if (!fs.existsSync(input)) throw new Error(`input not found: ${input}`);
  const t = theme || 'default';
  execSync(`mmdc -i "${input}" -o "${output}" -t ${t} -b transparent`, { stdio: 'pipe' });
  if (!fs.existsSync(output)) throw new Error('mmdc completed but output missing');
  return { input, output, theme: t, size_bytes: fs.statSync(output).size };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input || !args.output) {
    process.stderr.write('Usage: render_to_svg.js --input <mmd> --output <svg> [--theme default|dark]\n');
    process.exit(1);
  }
  try {
    const r = render(args.input, args.output, args.theme);
    process.stdout.write(JSON.stringify(r, null, 2) + '\n');
    process.exit(0);
  } catch (e) {
    process.stderr.write(`render failed: ${e.message}\n`);
    process.exit(1);
  }
}

if (require.main === module) main();
module.exports = { render, hasMmdc };
