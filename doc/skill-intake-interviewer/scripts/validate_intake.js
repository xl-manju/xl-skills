#!/usr/bin/env node
/**
 * validate_intake.js
 * 用途: intake.json が handoff-contract.md のスキーマに準拠しているか検証
 * 入力: --input <intake.json>
 * 出力: stdout JSON { valid, errors }
 * 終了コード: 0=成功, 1=エラー, 2=検証失敗
 */

'use strict';
const fs = require('fs');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) {
    const k = argv[i].replace(/^--/, '');
    args[k] = argv[i + 1];
  }
  return args;
}

const SCHEMA = {
  required: ['skill_name_hint', 'sections', 'open_questions', 'created_at'],
  five_axes: ['output_target', 'info_source', 'share_target', 'true_problem', 'knowledge_assets'],
  sections_required: ['A', 'B', 'C', 'F', 'H'],
};

function isString(v) { return typeof v === 'string' && v.length > 0; }
function isObject(v) { return v && typeof v === 'object' && !Array.isArray(v); }
function isArray(v) { return Array.isArray(v); }

function validate(data) {
  const errors = [];
  if (!isObject(data)) {
    errors.push('root must be object');
    return errors;
  }
  for (const k of SCHEMA.required) {
    if (!(k in data)) errors.push(`missing required field: ${k}`);
  }
  if (data.skill_name_hint && !isString(data.skill_name_hint)) {
    errors.push('skill_name_hint must be non-empty string');
  }
  const axes = data.five_axes || data.four_axes;
  if (!axes) {
    errors.push('missing required field: five_axes (or legacy four_axes)');
  } else if (!isObject(axes)) {
    errors.push('five_axes must be object');
  } else {
    for (const k of SCHEMA.five_axes) {
      if (!(k in axes)) {
        errors.push(`five_axes.${k} missing`);
        continue;
      }
      if (k === 'knowledge_assets') {
        const ka = axes[k];
        if (!isObject(ka)) {
          errors.push('five_axes.knowledge_assets must be object');
        } else {
          if (typeof ka.needed !== 'boolean') errors.push('knowledge_assets.needed must be boolean');
          if (ka.verified !== true) errors.push('knowledge_assets.verified must be true');
          if (ka.needed === true) {
            const hasAny =
              (Array.isArray(ka.existing_sources) && ka.existing_sources.length >= 1) ||
              (Array.isArray(ka.external_inputs) && ka.external_inputs.length >= 1) ||
              (Array.isArray(ka.tacit_knowledge) && ka.tacit_knowledge.length >= 1) ||
              (ka.extraction_pipeline && ka.extraction_pipeline.needed === true);
            if (!hasAny) errors.push('knowledge_assets.needed=true but no source filled');
            if (ka.extraction_pipeline && ka.extraction_pipeline.needed === true) {
              for (const f of ['ingest_format', 'analysis_method', 'storage', 'retrieval']) {
                if (!isString(ka.extraction_pipeline[f])) {
                  errors.push(`knowledge_assets.extraction_pipeline.${f} required`);
                }
              }
            }
          }
        }
      } else {
        const a = axes[k];
        if (!isObject(a) && !isString(a)) {
          errors.push(`five_axes.${k} must be object or non-empty string`);
        }
      }
    }
  }
  if (data.sections) {
    if (!isObject(data.sections)) {
      errors.push('sections must be object');
    } else {
      for (const k of SCHEMA.sections_required) {
        if (!(k in data.sections)) errors.push(`sections.${k} missing`);
      }
    }
  }
  if (data.open_questions && !isArray(data.open_questions)) {
    errors.push('open_questions must be array');
  }
  if (data.created_at && !isString(data.created_at)) {
    errors.push('created_at must be ISO string');
  }
  return errors;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    process.stderr.write('Usage: validate_intake.js --input <path>\n');
    process.exit(1);
  }
  let data;
  try {
    data = JSON.parse(fs.readFileSync(args.input, 'utf8'));
  } catch (e) {
    process.stderr.write(`failed to read/parse: ${e.message}\n`);
    process.exit(1);
  }
  const errors = validate(data);
  const result = { valid: errors.length === 0, errors };
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  process.exit(result.valid ? 0 : 2);
}

if (require.main === module) main();
module.exports = { validate, parseArgs };
