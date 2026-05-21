#!/usr/bin/env node
// verify_notion_schema.js
// 期待スキーマ (references/notion-db-schema.json) と現状 DB の properties を突き合わせ、
// 過不足・型不一致を eval-log/notion-conflicts.json に書き出す。
//
// Usage:
//   node verify_notion_schema.js --database-id <ID> [--on-conflict skip-warn|overwrite|fail-stop]
//
// Exit codes: 0=consistent or warnings-only, 1=conflicts under fail-stop, 2=INPUT_ERROR, 44=KEYCHAIN_ERROR

'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { getDatabase } = require('./notion_http');

const SCHEMA_PATH = path.resolve(
  __dirname,
  '..',
  'skills/run-skill-intake-aggregator/references/notion-db-schema.json'
);

// Notion property "type" 文字列を期待 type と比較する正規化
function normalizeType(t) {
  return t; // Notion の type 文字列はスキーマ JSON と同じ語彙 (title/select/rich_text/...)
}

function classifyConflict(expected, actual) {
  const { spec } = expected;
  if (actual === undefined || actual === null) {
    return spec.required
      ? { kind: 'missing', detail: `required property absent (expected type=${spec.type})` }
      : { kind: 'missing_optional', detail: `optional property absent (expected type=${spec.type})` };
  }
  const expType = normalizeType(spec.type);
  const actType = normalizeType(actual.type);
  if (expType !== actType) {
    return { kind: 'type_mismatch', detail: `expected=${expType}, actual=${actType}` };
  }
  if ((expType === 'select' || expType === 'multi_select') && Array.isArray(spec.options)) {
    const actualOptions = ((actual[expType] && actual[expType].options) || []).map(o => o.name);
    const expectedSet = new Set(spec.options);
    const actualSet = new Set(actualOptions);
    const missing = spec.options.filter(o => !actualSet.has(o));
    const extra = actualOptions.filter(o => !expectedSet.has(o));
    if (missing.length || extra.length) {
      const parts = [];
      if (missing.length) parts.push(`missing options: [${missing.join(', ')}]`);
      if (extra.length) parts.push(`extra options: [${extra.join(', ')}]`);
      return { kind: 'options_drift', detail: parts.join('; ') };
    }
  }
  return { kind: 'ok', detail: 'match' };
}

function classifyExtras(expectedNames, actualProps) {
  const out = [];
  for (const name of Object.keys(actualProps)) {
    if (!expectedNames.has(name)) {
      out.push({ name, kind: 'extra', detail: `unexpected property: ${actualProps[name].type}` });
    }
  }
  return out;
}

function parseArgs(argv) {
  const out = { mode: 'skip-warn' };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--database-id') out.databaseId = argv[++i];
    else if (a === '--on-conflict') out.mode = argv[++i];
    else if (a === '--out') out.outPath = argv[++i];
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const schema = JSON.parse(fs.readFileSync(SCHEMA_PATH, 'utf8'));
  const databaseId = args.databaseId
    || process.env.INTAKE_NOTION_DATABASE_ID
    || schema.database_id_default;
  if (!databaseId) {
    console.error('database id is required (--database-id or INTAKE_NOTION_DATABASE_ID)');
    process.exit(2);
  }
  const validModes = new Set(['skip-warn', 'overwrite', 'fail-stop']);
  if (!validModes.has(args.mode)) {
    console.error(`invalid --on-conflict: ${args.mode}`);
    process.exit(2);
  }

  let db;
  try {
    db = await getDatabase(databaseId);
  } catch (e) {
    console.error(`[verify_notion_schema] ${e.message}`);
    process.exit(e.status === 401 ? 44 : 1);
  }

  const expectedNames = new Set(Object.keys(schema.properties));
  const conflicts = [];
  for (const [name, spec] of Object.entries(schema.properties)) {
    const actual = db.properties[name];
    const r = classifyConflict({ name, spec }, actual);
    if (r.kind !== 'ok') conflicts.push({ name, ...r });
  }
  conflicts.push(...classifyExtras(expectedNames, db.properties));

  const outPath = args.outPath || path.resolve('eval-log/notion-conflicts.json');
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  const report = {
    database_id: databaseId,
    database_title: (db.title || []).map(t => t.plain_text).join(''),
    mode: args.mode,
    checked_at: new Date().toISOString(),
    summary: {
      total: conflicts.length,
      by_kind: conflicts.reduce((acc, c) => (acc[c.kind] = (acc[c.kind] || 0) + 1, acc), {}),
    },
    conflicts,
  };
  fs.writeFileSync(outPath, JSON.stringify(report, null, 2));
  console.log(`wrote ${outPath} (${conflicts.length} entries, mode=${args.mode})`);

  const blocking = conflicts.filter(c => c.kind !== 'missing_optional' && c.kind !== 'extra');
  if (args.mode === 'fail-stop' && blocking.length > 0) {
    console.error(`fail-stop: ${blocking.length} blocking conflicts`);
    process.exit(1);
  }
  process.exit(0);
}

if (require.main === module) {
  main().catch(e => { console.error(e); process.exit(1); });
}

module.exports = { classifyConflict, classifyExtras };
