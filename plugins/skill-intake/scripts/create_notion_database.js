#!/usr/bin/env node
// create_notion_database.js
// --mode=create : 指定 parent page 配下に新 DB を作成 (期待スキーマで)
// --mode=sync   : 既存 DB のプロパティ定義を期待スキーマへ寄せる (差分 PATCH)
//
// Usage:
//   node create_notion_database.js --mode=create --parent-page <PAGE_ID> [--title "skillインタビュー"]
//   node create_notion_database.js --mode=sync --database-id <DB_ID> [--dry-run]
//
// Exit codes: 0=OK, 1=API error, 2=INPUT_ERROR, 44=KEYCHAIN_ERROR

'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { notionFetch } = require('./notion_http');

const SCHEMA_PATH = path.resolve(
  __dirname,
  '..',
  'skills/run-skill-intake-aggregator/references/notion-db-schema.json'
);

function buildPropertyDef(spec) {
  const def = {};
  switch (spec.type) {
    case 'title':            def.title = {}; break;
    case 'rich_text':        def.rich_text = {}; break;
    case 'number':           def.number = { format: 'number' }; break;
    case 'checkbox':         def.checkbox = {}; break;
    case 'url':              def.url = {}; break;
    case 'people':           def.people = {}; break;
    case 'created_time':     def.created_time = {}; break;
    case 'last_edited_time': def.last_edited_time = {}; break;
    case 'select':
      def.select = { options: (spec.options || []).map(name => ({ name })) };
      break;
    case 'multi_select':
      def.multi_select = { options: (spec.options || []).map(name => ({ name })) };
      break;
    default:
      throw new Error(`unsupported type: ${spec.type}`);
  }
  return def;
}

function buildProperties(schema) {
  const out = {};
  for (const [name, spec] of Object.entries(schema.properties)) {
    out[name] = buildPropertyDef(spec);
  }
  return out;
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--mode=')) out.mode = a.slice('--mode='.length);
    else if (a === '--mode') out.mode = argv[++i];
    else if (a === '--parent-page') out.parentPage = argv[++i];
    else if (a === '--database-id') out.databaseId = argv[++i];
    else if (a === '--title') out.title = argv[++i];
    else if (a === '--dry-run') out.dryRun = true;
  }
  return out;
}

async function createDb({ parentPage, title, schema }) {
  if (!parentPage) {
    console.error('--parent-page is required for --mode=create');
    process.exit(2);
  }
  const body = {
    parent: { type: 'page_id', page_id: parentPage },
    title: [{ type: 'text', text: { content: title || 'skillインタビュー' } }],
    properties: buildProperties(schema),
  };
  const res = await notionFetch('/databases', { method: 'POST', body });
  console.log(`created database id=${res.id}`);
  console.log(`url=${res.url}`);
  return res;
}

async function syncDb({ databaseId, schema, dryRun }) {
  if (!databaseId) {
    console.error('--database-id is required for --mode=sync');
    process.exit(2);
  }
  const current = await notionFetch(`/databases/${databaseId}`);
  const desired = buildProperties(schema);
  const patch = {};
  const expectedTitleName = Object.entries(schema.properties).find(([, s]) => s.type === 'title')?.[0];
  const currentTitleName = Object.entries(current.properties).find(([, p]) => p.type === 'title')?.[0];
  if (expectedTitleName && currentTitleName && expectedTitleName !== currentTitleName) {
    patch[currentTitleName] = { name: expectedTitleName };
    console.log(`title rename: "${currentTitleName}" -> "${expectedTitleName}"`);
  }
  for (const [name, def] of Object.entries(desired)) {
    if (name === expectedTitleName && currentTitleName) continue;
    const cur = current.properties[name];
    if (!cur || cur.type !== schema.properties[name].type) {
      patch[name] = def;
    } else if (schema.properties[name].type === 'select' || schema.properties[name].type === 'multi_select') {
      const curOpts = (cur[cur.type].options || []).map(o => o.name).sort().join(',');
      const expOpts = (schema.properties[name].options || []).slice().sort().join(',');
      if (curOpts !== expOpts) patch[name] = def;
    }
  }
  if (Object.keys(patch).length === 0) {
    console.log('no drift; nothing to sync');
    return;
  }
  console.log(`sync plan: ${Object.keys(patch).join(', ')}`);
  if (dryRun) { console.log('dry-run: no PATCH issued'); return; }
  const res = await notionFetch(`/databases/${databaseId}`, { method: 'PATCH', body: { properties: patch } });
  console.log(`synced ${Object.keys(patch).length} properties`);
  return res;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const schema = JSON.parse(fs.readFileSync(SCHEMA_PATH, 'utf8'));
  try {
    if (args.mode === 'create') await createDb({ ...args, schema });
    else if (args.mode === 'sync') await syncDb({ ...args, schema });
    else { console.error('--mode=create|sync required'); process.exit(2); }
    process.exit(0);
  } catch (e) {
    console.error(`[create_notion_database] ${e.message}`);
    process.exit(e.status === 401 ? 44 : 1);
  }
}

if (require.main === module) main();
module.exports = { buildPropertyDef, buildProperties };
