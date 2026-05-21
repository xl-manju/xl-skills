#!/usr/bin/env node
/**
 * measure_value_realized.js
 * 用途: 利用後フィードバックから「時間短縮実績」を集計
 * 入力: --feedback <json: [{skill, before_minutes, after_minutes, frequency_per_week}]>
 * 出力: stdout JSON { total_saved_per_week, breakdown }
 * 終了コード: 0=成功, 1=エラー
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

function aggregate(items) {
  const breakdown = [];
  let totalPerWeek = 0;
  for (const it of items) {
    const before = Number(it.before_minutes || 0);
    const after = Number(it.after_minutes || 0);
    const freq = Number(it.frequency_per_week || 0);
    const savedPerOp = Math.max(0, before - after);
    const savedPerWeek = savedPerOp * freq;
    totalPerWeek += savedPerWeek;
    breakdown.push({
      skill: it.skill || '(unnamed)',
      saved_per_op_minutes: savedPerOp,
      saved_per_week_minutes: savedPerWeek,
      reduction_rate: before > 0 ? Number((savedPerOp / before).toFixed(2)) : 0,
    });
  }
  return {
    total_saved_per_week_minutes: totalPerWeek,
    total_saved_per_week_hours: Number((totalPerWeek / 60).toFixed(2)),
    total_saved_per_year_hours: Number((totalPerWeek * 52 / 60).toFixed(1)),
    breakdown,
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.feedback) {
    process.stderr.write('Usage: measure_value_realized.js --feedback <json>\n');
    process.exit(1);
  }
  const items = JSON.parse(fs.readFileSync(args.feedback, 'utf8'));
  if (!Array.isArray(items)) {
    process.stderr.write('feedback must be array\n');
    process.exit(1);
  }
  const r = aggregate(items);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  process.exit(0);
}

if (require.main === module) main();
module.exports = { aggregate };
