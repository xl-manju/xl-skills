#!/usr/bin/env node
// publish_notion_page.js — intake.json と (任意で) blocks.json を入力に
// Notion DB へページを実投稿する。
//
// Usage:
//   node publish_notion_page.js --intake <path/to/intake.json> [--blocks <blocks.json>] \
//     [--database-id <ID>] [--md-url <URL>] [--json-url <URL>] [--dry-run]
//
// Exit codes: 0=OK, 1=API error, 2=INPUT_ERROR, 44=KEYCHAIN_ERROR

'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { notionFetch } = require('./notion_http');

function rt(s) { return [{ type: 'text', text: { content: String(s || '').slice(0, 2000) } }]; }

function buildProperties(intake, args) {
  const axes = intake.five_axes || intake['5_axes'] || {};
  const props = {
    '名前': { title: rt(intake.skill_name_hint || intake.skill_name || 'untitled') },
    'ステータス': { select: { name: intake.status || '下書き' } },
    'パターン': { select: { name: intake.pattern || 'その他' } },
    '出力先': { rich_text: rt(axes.output_destination) },
    '情報源': { rich_text: rt(axes.info_source) },
    '共有相手': { rich_text: rt(axes.share_target) },
    '真の課題': { rich_text: rt(axes.true_problem) },
    'ナレッジ資産': { rich_text: rt(axes.knowledge_assets) },
  };
  if (intake.user_profile) props['ユーザープロファイル'] = { rich_text: rt(typeof intake.user_profile === 'string' ? intake.user_profile : JSON.stringify(intake.user_profile)) };
  if (Array.isArray(intake.open_questions) && intake.open_questions.length) {
    props['未解決事項'] = { rich_text: rt('- ' + intake.open_questions.join('\n- ')) };
  }
  if (Array.isArray(intake.integrations) && intake.integrations.length) {
    props['外部連携'] = { multi_select: intake.integrations.map(name => ({ name })) };
  }
  if (args.mdUrl)   props['Markdown 正本'] = { url: args.mdUrl };
  if (args.jsonUrl) props['JSON 副本']     = { url: args.jsonUrl };
  if (typeof intake.handoff_to_creator === 'boolean') props['Creator 引き渡し'] = { checkbox: intake.handoff_to_creator };
  if (typeof intake.viz_count === 'number')           props['図解枚数']         = { number: intake.viz_count };
  if (typeof intake.value_score === 'number')         props['価値実現スコア']   = { number: intake.value_score };
  return props;
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--intake') out.intake = argv[++i];
    else if (a === '--blocks') out.blocks = argv[++i];
    else if (a === '--database-id') out.databaseId = argv[++i];
    else if (a === '--md-url') out.mdUrl = argv[++i];
    else if (a === '--json-url') out.jsonUrl = argv[++i];
    else if (a === '--dry-run') out.dryRun = true;
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.intake) { console.error('--intake is required'); process.exit(2); }
  const databaseId = args.databaseId
    || process.env.INTAKE_NOTION_DATABASE_ID
    || '36607a0cd18c80bf9effc74aa736645c';
  const intake = JSON.parse(fs.readFileSync(path.resolve(args.intake), 'utf8'));
  const body = {
    parent: { database_id: databaseId },
    properties: buildProperties(intake, args),
  };
  if (args.blocks) {
    const blocks = JSON.parse(fs.readFileSync(path.resolve(args.blocks), 'utf8'));
    body.children = blocks.children || blocks;
  }
  if (args.dryRun) {
    console.log(JSON.stringify({ dry_run: true, parent: body.parent, prop_count: Object.keys(body.properties).length, has_children: !!body.children }, null, 2));
    process.exit(0);
  }
  try {
    const res = await notionFetch('/pages', { method: 'POST', body });
    const out = { id: res.id, url: res.url, created_time: res.created_time };
    console.log(JSON.stringify(out, null, 2));
    process.exit(0);
  } catch (e) {
    console.error(`[publish_notion_page] ${e.message}`);
    process.exit(e.status === 401 ? 44 : 1);
  }
}

if (require.main === module) main();
module.exports = { buildProperties };
