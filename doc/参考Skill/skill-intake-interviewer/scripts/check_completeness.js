#!/usr/bin/env node
/**
 * check_completeness.js
 * 用途: 必須項目（5軸全部 = 出力先/情報源/共有相手/真の課題/ナレッジ資産、A1/A2/B1/C1/F1/H1）が埋まっているかチェック
 *       ナレッジ資産軸は MUST: needed=false でも verified=true なら PASS。
 *       needed=true の場合は existing_sources / external_inputs / tacit_knowledge のいずれか1つ以上必須。
 *       extraction_pipeline.needed=true なら ingest_format / analysis_method / storage / retrieval 全充足必須。
 * 入力: --input <intake.json>
 * 出力: stdout JSON { complete, missing, completion_rate }
 * 終了コード: 0=成功, 1=エラー, 2=不完全
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) {
    args[argv[i].replace(/^--/, '')] = argv[i + 1];
  }
  return args;
}

const REQUIRED_AXES = ['output_target', 'info_source', 'share_target', 'true_problem', 'knowledge_assets'];
const REQUIRED_ITEMS = [
  { section: 'A', key: 'A1' },
  { section: 'A', key: 'A2' },
  { section: 'B', key: 'B1' },
  { section: 'C', key: 'C1' },
  { section: 'F', key: 'F1' },
  { section: 'H', key: 'H1' },
];

function isFilled(v) {
  if (v == null) return false;
  if (typeof v === 'string') return v.trim().length > 0 && !/^\[\?\]/.test(v.trim());
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === 'object') return Object.keys(v).length > 0;
  return true;
}

function checkKnowledgeAssets(ka) {
  const errs = [];
  if (!ka || typeof ka !== 'object') {
    errs.push('knowledge_assets.missing');
    return errs;
  }
  if (ka.verified !== true) errs.push('knowledge_assets.verified=false');
  if (ka.needed === true) {
    const hasAny =
      (Array.isArray(ka.existing_sources) && ka.existing_sources.length >= 1) ||
      (Array.isArray(ka.external_inputs) && ka.external_inputs.length >= 1) ||
      (Array.isArray(ka.tacit_knowledge) && ka.tacit_knowledge.length >= 1) ||
      (ka.extraction_pipeline && ka.extraction_pipeline.needed === true);
    if (!hasAny) errs.push('knowledge_assets.no_source_filled');
    const ep = ka.extraction_pipeline;
    if (ep && ep.needed === true) {
      for (const f of ['ingest_format', 'analysis_method', 'storage', 'retrieval']) {
        if (!isFilled(ep[f])) errs.push(`knowledge_assets.extraction_pipeline.${f}`);
      }
    }
  }
  return errs;
}

function check(data) {
  const missing = [];
  const axes = data.five_axes || data.four_axes || {};
  for (const k of REQUIRED_AXES) {
    if (k === 'knowledge_assets') {
      missing.push(...checkKnowledgeAssets(axes[k]));
    } else if (!isFilled(axes[k])) {
      missing.push(`five_axes.${k}`);
    }
  }
  const sections = data.sections || {};
  for (const item of REQUIRED_ITEMS) {
    const sec = sections[item.section];
    if (!sec || !isFilled(sec[item.key])) {
      missing.push(`sections.${item.section}.${item.key}`);
    }
  }
  const total = REQUIRED_AXES.length + REQUIRED_ITEMS.length;
  const filled = Math.max(0, total - missing.length);
  return {
    complete: missing.length === 0,
    missing,
    completion_rate: Number((filled / total).toFixed(2)),
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    process.stderr.write('Usage: check_completeness.js --input <path>\n');
    process.exit(1);
  }
  let data;
  try {
    data = JSON.parse(fs.readFileSync(args.input, 'utf8'));
  } catch (e) {
    process.stderr.write(`parse error: ${e.message}\n`);
    process.exit(1);
  }
  const r = check(data);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  process.exit(r.complete ? 0 : 2);
}

if (require.main === module) main();
module.exports = { check, parseArgs };
