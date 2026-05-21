#!/usr/bin/env node
/**
 * compose_slack_message.js
 * 用途: Slack 通知文生成（Notion URL + サマリ抜粋）
 * 入力: --input <intake.json> --notion-url <url> [--output <path>]
 * 出力: Slack 用 mrkdwn テキスト
 * 終了コード: 0=成功, 1=エラー
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

function truncate(s, n) {
  if (!s) return '';
  s = String(s).replace(/\s+/g, ' ').trim();
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}

function compose(data, notionUrl) {
  const fa = data.five_axes || data.four_axes || {};
  const hint = data.skill_name_hint || '(未命名)';
  const open = (data.open_questions || []).length;
  const completion = data.completion_rate != null ? `${Math.round(data.completion_rate * 100)}%` : '不明';

  const lines = [];
  lines.push(`:memo: *新しいスキル要件ヒアリングが完了しました*`);
  lines.push('');
  lines.push(`*スキル名(仮)*: ${hint}`);
  lines.push(`*完了率*: ${completion}　*未解決*: ${open} 件`);
  lines.push('');
  const ka = fa.knowledge_assets || {};
  const kaSummary = ka.needed === false
    ? '不要'
    : [
        Array.isArray(ka.existing_sources) ? `既存${ka.existing_sources.length}` : null,
        Array.isArray(ka.external_inputs) ? `外部${ka.external_inputs.length}` : null,
        Array.isArray(ka.tacit_knowledge) ? `暗黙${ka.tacit_knowledge.length}` : null,
      ].filter(Boolean).join(' / ') || '要設計';
  const get = (v) => (v && typeof v === 'object' ? v.answer || v.summary || '' : v || '');
  lines.push('*5軸サマリ*');
  lines.push(`• 出力先: ${truncate(get(fa.output_target), 80)}`);
  lines.push(`• 情報源: ${truncate(get(fa.info_source || fa.information_source), 80)}`);
  lines.push(`• 共有相手: ${truncate(get(fa.share_target || fa.audience), 80)}`);
  lines.push(`• 真の課題: ${truncate(get(fa.true_problem), 120)}`);
  lines.push(`• ナレッジ資産: ${truncate(kaSummary, 80)}`);
  lines.push('');
  if (notionUrl) lines.push(`:notion: <${notionUrl}|Notion で詳細を見る>`);
  lines.push('');
  lines.push(`次のステップ: skill-creator に引き渡し可能です。`);
  return lines.join('\n');
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    process.stderr.write('Usage: compose_slack_message.js --input <json> [--notion-url <url>] [--output <path>]\n');
    process.exit(1);
  }
  const data = JSON.parse(fs.readFileSync(args.input, 'utf8'));
  const text = compose(data, args['notion-url'] || '');
  if (args.output) fs.writeFileSync(args.output, text);
  else process.stdout.write(text + '\n');
  process.exit(0);
}

if (require.main === module) main();
module.exports = { compose, truncate };
