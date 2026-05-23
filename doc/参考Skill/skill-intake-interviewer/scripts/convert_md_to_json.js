#!/usr/bin/env node
/**
 * convert_md_to_json.js
 * 用途: Markdown 正本 → JSON 副本変換（決定論）
 * frontmatter / セクション見出し / チェックボックス / 表 を構造化
 * 入力: --input <intake.md> --output <intake.json>
 * 出力: ファイル書き出し or stdout
 * 終了コード: 0=成功, 1=エラー
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

function parseFrontmatter(text) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (!m) return { frontmatter: {}, body: text };
  const fm = {};
  for (const line of m[1].split(/\r?\n/)) {
    const kv = line.match(/^([A-Za-z0-9_\-]+)\s*:\s*(.*)$/);
    if (kv) fm[kv[1]] = kv[2].trim().replace(/^["']|["']$/g, '');
  }
  return { frontmatter: fm, body: m[2] };
}

function parseTable(lines, start) {
  const rows = [];
  let i = start;
  while (i < lines.length && /^\s*\|/.test(lines[i])) {
    rows.push(lines[i]);
    i++;
  }
  if (rows.length < 2) return { table: null, end: start };
  const header = rows[0].split('|').slice(1, -1).map(s => s.trim());
  const data = rows.slice(2).map(r => {
    const cells = r.split('|').slice(1, -1).map(s => s.trim());
    const o = {};
    header.forEach((h, j) => { o[h] = cells[j] || ''; });
    return o;
  });
  return { table: { header, rows: data }, end: i };
}

function parseSections(body) {
  const lines = body.split(/\r?\n/);
  const root = { intro: '', sections: {} };
  let currentH1 = null;
  let currentH2 = null;
  let buffer = [];

  function flush() {
    const text = buffer.join('\n').trim();
    if (!text) { buffer = []; return; }
    if (currentH1 == null) {
      root.intro += (root.intro ? '\n' : '') + text;
    } else {
      const sec = root.sections[currentH1] = root.sections[currentH1] || { title: currentH1, content: '', subsections: {} };
      if (currentH2 == null) sec.content += (sec.content ? '\n' : '') + text;
      else {
        sec.subsections[currentH2] = sec.subsections[currentH2] || { title: currentH2, content: '', items: [] };
        sec.subsections[currentH2].content += (sec.subsections[currentH2].content ? '\n' : '') + text;
      }
    }
    buffer = [];
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const h1 = line.match(/^#\s+(.+)/);
    const h2 = line.match(/^##\s+(.+)/);
    const h3 = line.match(/^###\s+(.+)/);
    if (h1) { flush(); currentH1 = h1[1].trim(); currentH2 = null; continue; }
    if (h2) { flush(); currentH2 = h2[1].trim(); continue; }
    if (h3) { flush(); currentH2 = h3[1].trim(); continue; }
    if (/^\s*\|/.test(line)) {
      flush();
      const { table, end } = parseTable(lines, i);
      if (table) {
        const target = currentH2
          ? (root.sections[currentH1].subsections[currentH2] = root.sections[currentH1].subsections[currentH2] || { items: [] })
          : (currentH1 ? root.sections[currentH1] : root);
        target.tables = target.tables || [];
        target.tables.push(table);
        i = end - 1;
        continue;
      }
    }
    const cb = line.match(/^\s*-\s*\[([ xX])\]\s*(.+)/);
    if (cb) {
      const item = { checked: cb[1].toLowerCase() === 'x', text: cb[2].trim() };
      if (currentH1) {
        const sec = root.sections[currentH1] = root.sections[currentH1] || { title: currentH1, subsections: {}, content: '' };
        if (currentH2) {
          sec.subsections[currentH2] = sec.subsections[currentH2] || { items: [], content: '' };
          sec.subsections[currentH2].items = sec.subsections[currentH2].items || [];
          sec.subsections[currentH2].items.push(item);
        } else {
          sec.items = sec.items || [];
          sec.items.push(item);
        }
      }
      continue;
    }
    buffer.push(line);
  }
  flush();
  return root;
}

function convert(mdText) {
  const { frontmatter, body } = parseFrontmatter(mdText);
  const parsed = parseSections(body);
  return {
    skill_name_hint: frontmatter.skill_name_hint || frontmatter.name || '',
    created_at: frontmatter.created_at || new Date().toISOString(),
    frontmatter,
    intro: parsed.intro,
    sections: parsed.sections,
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    process.stderr.write('Usage: convert_md_to_json.js --input <md> [--output <json>]\n');
    process.exit(1);
  }
  const md = fs.readFileSync(args.input, 'utf8');
  const json = convert(md);
  const out = JSON.stringify(json, null, 2) + '\n';
  if (args.output) fs.writeFileSync(args.output, out);
  else process.stdout.write(out);
  process.exit(0);
}

if (require.main === module) main();
module.exports = { convert, parseFrontmatter, parseSections, parseTable };
