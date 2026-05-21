#!/usr/bin/env node
/**
 * validate_mermaid.js
 * 用途: Mermaid 構文検証（基本ルール: 図種ヘッダ、エッジ表記、ノードラベル）
 * mermaid-cli が無ければ手書き検証で fallback
 * 入力: --input <path.mmd>
 * 出力: stdout JSON { valid, errors, warnings }
 * 終了コード: 0=成功, 1=エラー, 2=検証失敗
 */

'use strict';
const fs = require('fs');
const { execSync } = require('child_process');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

const VALID_HEADERS = [
  'flowchart', 'graph', 'sequenceDiagram', 'classDiagram', 'stateDiagram',
  'stateDiagram-v2', 'erDiagram', 'gantt', 'pie', 'mindmap', 'timeline',
  'journey', 'quadrantChart', 'gitGraph', 'requirementDiagram', 'C4Context',
];

function tryCli(filePath) {
  try {
    execSync('which mmdc', { stdio: 'ignore' });
  } catch (_) { return null; }
  try {
    const tmp = `/tmp/mermaid-validate-${process.pid}.svg`;
    execSync(`mmdc -i "${filePath}" -o "${tmp}" -q 2>&1`, { stdio: 'pipe' });
    try { fs.unlinkSync(tmp); } catch (_) {}
    return { valid: true, errors: [], warnings: [], engine: 'mmdc' };
  } catch (e) {
    return { valid: false, errors: [String(e.stderr || e.message)], warnings: [], engine: 'mmdc' };
  }
}

function fallbackValidate(text) {
  const errors = [];
  const warnings = [];
  const lines = text.split(/\r?\n/).map(l => l.replace(/%%.*$/, '')).filter(l => l.trim());
  if (lines.length === 0) {
    errors.push('empty diagram');
    return { valid: false, errors, warnings, engine: 'fallback' };
  }
  const header = lines[0].trim();
  const headWord = header.split(/\s+/)[0];
  if (!VALID_HEADERS.includes(headWord)) {
    errors.push(`invalid diagram header: "${headWord}". expected one of ${VALID_HEADERS.join(', ')}`);
  }
  // flowchart / graph: direction
  if (/^(flowchart|graph)/.test(header)) {
    if (!/(TD|TB|BT|LR|RL)/.test(header)) {
      warnings.push('flowchart direction not specified (TD/LR推奨)');
    }
    // edge syntax check
    let hasEdge = false;
    for (const l of lines.slice(1)) {
      if (/-->|---|==>|-\.->|\.->/.test(l)) hasEdge = true;
    }
    if (!hasEdge) warnings.push('no edges found in flowchart');
  }
  // unbalanced brackets
  const openCount = (text.match(/[\[\(\{]/g) || []).length;
  const closeCount = (text.match(/[\]\)\}]/g) || []).length;
  if (openCount !== closeCount) {
    errors.push(`unbalanced brackets: open=${openCount}, close=${closeCount}`);
  }
  return { valid: errors.length === 0, errors, warnings, engine: 'fallback' };
}

function validate(text, filePath) {
  const cli = filePath ? tryCli(filePath) : null;
  if (cli) return cli;
  return fallbackValidate(text);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    process.stderr.write('Usage: validate_mermaid.js --input <path>\n');
    process.exit(1);
  }
  const text = fs.readFileSync(args.input, 'utf8');
  const r = validate(text, args.input);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  process.exit(r.valid ? 0 : 2);
}

if (require.main === module) main();
module.exports = { validate, fallbackValidate, VALID_HEADERS };
