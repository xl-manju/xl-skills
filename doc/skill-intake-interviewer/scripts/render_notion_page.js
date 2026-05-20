#!/usr/bin/env node
/**
 * render_notion_page.js
 * 用途: Notion 用 Markdown 整形（heading/toggle/callout 変換）。SVG 埋込含む
 * 入力: --input <intake.md> [--svg-dir <dir>] [--output <path>]
 * 出力: Notion 互換 Markdown
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

function transform(md, svgDir) {
  const lines = md.split(/\r?\n/);
  const out = [];
  let inFrontmatter = false;
  let inMermaid = false;
  let mermaidBuf = [];
  let mermaidIdx = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (i === 0 && line === '---') { inFrontmatter = true; continue; }
    if (inFrontmatter) { if (line === '---') inFrontmatter = false; continue; }

    if (/^```mermaid\s*$/.test(line)) { inMermaid = true; mermaidBuf = []; continue; }
    if (inMermaid && /^```\s*$/.test(line)) {
      inMermaid = false;
      mermaidIdx++;
      const svgPath = svgDir ? path.join(svgDir, `diagram-${mermaidIdx}.svg`) : null;
      if (svgPath && fs.existsSync(svgPath)) {
        out.push(`![diagram-${mermaidIdx}](${svgPath})`);
      } else {
        out.push('```mermaid');
        out.push(...mermaidBuf);
        out.push('```');
      }
      continue;
    }
    if (inMermaid) { mermaidBuf.push(line); continue; }

    // callout: > ⚠️ / > 注意: / > 💡 / > Tip:
    const callout = line.match(/^>\s*(注意|警告|Tip|ヒント|Note|メモ)[:：]?\s*(.*)$/i);
    if (callout) {
      const icon = /注意|警告|warn/i.test(callout[1]) ? '⚠️' : 'ℹ️';
      out.push(`> ${icon} **${callout[1]}**: ${callout[2]}`);
      continue;
    }

    // toggle: <details> → Notion toggle (Markdown では ▶ で表現)
    if (/^<details>/.test(line)) { out.push('▼ Toggle:'); continue; }
    if (/^<\/details>/.test(line)) continue;
    const summary = line.match(/^<summary>(.*)<\/summary>/);
    if (summary) { out.push(`**${summary[1]}**`); continue; }

    out.push(line);
  }
  return out.join('\n');
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    process.stderr.write('Usage: render_notion_page.js --input <md> [--svg-dir <dir>] [--output <path>]\n');
    process.exit(1);
  }
  const md = fs.readFileSync(args.input, 'utf8');
  const result = transform(md, args['svg-dir']);
  if (args.output) fs.writeFileSync(args.output, result);
  else process.stdout.write(result + '\n');
  process.exit(0);
}

if (require.main === module) main();
module.exports = { transform };
