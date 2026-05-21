#!/usr/bin/env node
/**
 * detect_contradictions.js
 * 用途: シート内矛盾検出（例: 「連携なし」+「OAuth設定」）。ルール表で判定
 * 入力: --input <intake.json>
 * 出力: stdout JSON { contradictions: [...] }
 * 終了コード: 0=矛盾なし, 1=エラー, 2=矛盾あり
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) args[argv[i].replace(/^--/, '')] = argv[i + 1];
  return args;
}

const RULES = [
  {
    id: 'integration_none_but_oauth',
    description: '連携なしと宣言しているのにOAuth/APIトークン設定が存在する',
    check: (d) => {
      const flat = JSON.stringify(d).toLowerCase();
      const noIntegration = /連携なし|integration[_:\s]*none|外部連携.*なし/.test(flat);
      const hasOauth = /oauth|api[_\s]?token|client[_\s]?secret/.test(flat);
      return noIntegration && hasOauth;
    },
  },
  {
    id: 'non_tech_user_with_jargon',
    description: '非エンジニア向けと宣言しているのに専門用語が出力に含まれる',
    check: (d) => {
      const profile = (d.user_profile && d.user_profile.tech_level) || '';
      const out = JSON.stringify(d.sections || {}).toLowerCase();
      const isNonTech = /非エンジニア|non[_-]?tech|初心者/.test(profile);
      const hasJargon = /\b(api|sdk|cli|webhook|endpoint|payload)\b/.test(out);
      return isNonTech && hasJargon;
    },
  },
  {
    id: 'output_target_mismatch',
    description: '出力先がNotionなのに共有相手がSlackチャンネルだけ',
    check: (d) => {
      const fa = d.five_axes || d.four_axes || {};
      const get = (v) => (v && typeof v === 'object' ? v.answer || '' : v || '');
      const out = get(fa.output_target).toLowerCase();
      const aud = get(fa.share_target || fa.audience).toLowerCase();
      return /notion/.test(out) && /^slack/.test(aud) && !/notion/.test(aud);
    },
  },
  {
    id: 'info_source_unspecified',
    description: '情報源が「なし」だが処理対象データが存在する',
    check: (d) => {
      const fa = d.five_axes || d.four_axes || {};
      const get = (v) => (v && typeof v === 'object' ? v.answer || '' : v || '');
      const src = get(fa.info_source || fa.information_source).toLowerCase();
      const hasData = JSON.stringify(d.sections || {}).length > 200;
      return /^(なし|none|不明)$/.test(src.trim()) && hasData;
    },
  },
  {
    id: 'true_problem_too_shallow',
    description: '真の課題が表層要望と同一（深掘り未実施）',
    check: (d) => {
      const fa = d.five_axes || d.four_axes || {};
      const get = (v) => (v && typeof v === 'object' ? v.answer || '' : v || '');
      const tp = get(fa.true_problem).trim();
      const hint = (d.skill_name_hint || '').trim();
      return tp.length > 0 && hint.length > 0 && tp === hint;
    },
  },
  {
    id: 'knowledge_assets_unverified',
    description: 'ナレッジ資産軸（MUST）が未確認のままハンドオフ',
    check: (d) => {
      const fa = d.five_axes || d.four_axes || {};
      const ka = fa.knowledge_assets;
      if (!ka || typeof ka !== 'object') return true;
      return ka.verified !== true;
    },
  },
  {
    id: 'knowledge_needed_but_empty',
    description: 'ナレッジ資産が必要(needed=true)なのに source/inputs/tacit いずれも未充足',
    check: (d) => {
      const fa = d.five_axes || d.four_axes || {};
      const ka = fa.knowledge_assets;
      if (!ka || ka.needed !== true) return false;
      const hasAny =
        (Array.isArray(ka.existing_sources) && ka.existing_sources.length >= 1) ||
        (Array.isArray(ka.external_inputs) && ka.external_inputs.length >= 1) ||
        (Array.isArray(ka.tacit_knowledge) && ka.tacit_knowledge.length >= 1) ||
        (ka.extraction_pipeline && ka.extraction_pipeline.needed === true);
      return !hasAny;
    },
  },
];

function detect(data) {
  const found = [];
  for (const r of RULES) {
    try {
      if (r.check(data)) {
        found.push({ id: r.id, description: r.description });
      }
    } catch (_) { /* skip */ }
  }
  return found;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    process.stderr.write('Usage: detect_contradictions.js --input <path>\n');
    process.exit(1);
  }
  let data;
  try {
    data = JSON.parse(fs.readFileSync(args.input, 'utf8'));
  } catch (e) {
    process.stderr.write(`parse error: ${e.message}\n`);
    process.exit(1);
  }
  const contradictions = detect(data);
  process.stdout.write(JSON.stringify({ contradictions }, null, 2) + '\n');
  process.exit(contradictions.length === 0 ? 0 : 2);
}

if (require.main === module) main();
module.exports = { detect, RULES, parseArgs };
