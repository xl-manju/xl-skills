#!/usr/bin/env node
/**
 * quality_gate.js
 * 用途: 共通品質ゲート。ルブリック5次元判定 → PASS/FAIL JSON
 * 入力: --agent <name> --output <path> [--threshold 0.8]
 * 出力: stdout JSON { pass, score, dimensions }
 * 終了コード: 0=PASS, 2=FAIL, 1=エラー
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

const DIMENSIONS = ['completeness', 'consistency', 'depth', 'verifiability', 'conciseness'];

function scoreCompleteness(text) {
  const placeholders = (text.match(/\[\?\]|TODO|TBD|XXX/g) || []).length;
  const len = text.length;
  if (len < 100) return 0.2;
  return Math.max(0, 1 - placeholders * 0.1);
}

function scoreConsistency(text) {
  const headerCount = (text.match(/^#{1,6}\s/gm) || []).length;
  const lines = text.split('\n').length;
  if (lines < 10) return 0.5;
  return headerCount > 0 ? Math.min(1, headerCount / 5) : 0.4;
}

function scoreDepth(text) {
  const why = (text.match(/なぜ|理由|because|why/gi) || []).length;
  const example = (text.match(/例[:：]|example|例えば/gi) || []).length;
  return Math.min(1, (why + example) * 0.15);
}

function scoreVerifiability(text) {
  const checkable = (text.match(/- \[[ x]\]|^\d+\.\s/gm) || []).length;
  const refs = (text.match(/references\/|scripts\//g) || []).length;
  return Math.min(1, (checkable * 0.05) + (refs * 0.1));
}

function scoreConciseness(text) {
  const lines = text.split('\n');
  const longLines = lines.filter(l => l.length > 200).length;
  const ratio = lines.length > 0 ? longLines / lines.length : 0;
  return Math.max(0, 1 - ratio * 2);
}

function evaluate(text) {
  const scores = {
    completeness: scoreCompleteness(text),
    consistency: scoreConsistency(text),
    depth: scoreDepth(text),
    verifiability: scoreVerifiability(text),
    conciseness: scoreConciseness(text),
  };
  const total = DIMENSIONS.reduce((a, k) => a + scores[k], 0) / DIMENSIONS.length;
  return { score: Number(total.toFixed(3)), dimensions: scores };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.output) {
    process.stderr.write('Usage: quality_gate.js --agent <name> --output <path> [--threshold 0.8]\n');
    process.exit(1);
  }
  const threshold = Number(args.threshold || 0.8);
  const text = fs.readFileSync(args.output, 'utf8');
  const ev = evaluate(text);
  const result = {
    agent: args.agent || '(unknown)',
    pass: ev.score >= threshold,
    threshold,
    ...ev,
  };
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  process.exit(result.pass ? 0 : 2);
}

if (require.main === module) main();
module.exports = { evaluate, DIMENSIONS };
