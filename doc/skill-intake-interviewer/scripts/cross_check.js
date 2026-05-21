#!/usr/bin/env node
/**
 * cross_check.js
 * 用途: 全 agent 出力間の整合検証
 * (例: user-profiler が「非技術者」判定なのに interviewer が技術用語を使ってる)
 * 入力: --outputs <json: {agent_name: path, ...}>
 * 出力: stdout JSON { consistent, issues }
 * 終了コード: 0=一貫, 1=エラー, 2=矛盾
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

const TECH_TERMS = ['API', 'SDK', 'OAuth', 'CLI', 'webhook', 'endpoint', 'payload', 'JSON', 'YAML', 'CRUD'];

function loadAll(map) {
  const out = {};
  for (const [k, p] of Object.entries(map)) {
    if (!fs.existsSync(p)) continue;
    out[k] = fs.readFileSync(p, 'utf8');
  }
  return out;
}

function checkNonTechConsistency(outputs) {
  const issues = [];
  const profiler = outputs['user-profiler'] || '';
  const isNonTech = /非エンジニア|非技術者|初心者|non[_-]?tech/i.test(profiler);
  if (!isNonTech) return issues;
  for (const [name, text] of Object.entries(outputs)) {
    if (name === 'user-profiler') continue;
    const found = TECH_TERMS.filter(t => new RegExp(`\\b${t}\\b`).test(text));
    if (found.length > 0) {
      issues.push({
        type: 'jargon_for_nontech',
        agent: name,
        terms: found,
        message: `user-profiler が非技術者と判定したが、${name} で専門用語が使用されている`,
      });
    }
  }
  return issues;
}

function checkFourAxesAlignment(outputs) {
  const issues = [];
  const handoff = outputs['handoff'] || '';
  const interviewer = outputs['interviewer'] || '';
  const fa = ['出力先', '情報源', '共有相手', '真の課題'];
  for (const axis of fa) {
    const inHandoff = handoff.includes(axis);
    const inInterviewer = interviewer.includes(axis);
    if (inHandoff && !inInterviewer) {
      issues.push({
        type: 'axis_missing_in_interviewer',
        axis,
        message: `handoff に ${axis} があるが interviewer 出力に痕跡がない`,
      });
    }
  }
  return issues;
}

function checkSummarizerCovers(outputs) {
  const issues = [];
  const summary = outputs['summarizer'] || '';
  if (!summary) return issues;
  const required = ['出力先', '情報源', '共有相手', '真の課題'];
  for (const r of required) {
    if (!summary.includes(r)) {
      issues.push({ type: 'summary_missing_axis', axis: r });
    }
  }
  return issues;
}

function crossCheck(outputs) {
  const issues = [
    ...checkNonTechConsistency(outputs),
    ...checkFourAxesAlignment(outputs),
    ...checkSummarizerCovers(outputs),
  ];
  return { consistent: issues.length === 0, issues };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.outputs) {
    process.stderr.write('Usage: cross_check.js --outputs <json>\n');
    process.exit(1);
  }
  const map = JSON.parse(fs.readFileSync(args.outputs, 'utf8'));
  const all = loadAll(map);
  const r = crossCheck(all);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  process.exit(r.consistent ? 0 : 2);
}

if (require.main === module) main();
module.exports = { crossCheck, TECH_TERMS };
