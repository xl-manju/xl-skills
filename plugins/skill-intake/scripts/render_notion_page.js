#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const MAX_RT = 1900;

function rt(text) {
  return [{ type: 'text', text: { content: String(text == null ? '' : text).slice(0, MAX_RT) } }];
}

function heading(level, text) {
  const key = `heading_${Math.min(Math.max(level, 1), 3)}`;
  return { object: 'block', type: key, [key]: { rich_text: rt(text) } };
}

function paragraph(text) {
  return { object: 'block', type: 'paragraph', paragraph: { rich_text: rt(text) } };
}

function bullet(text) {
  return { object: 'block', type: 'bulleted_list_item', bulleted_list_item: { rich_text: rt(text) } };
}

function image(url) {
  return { object: 'block', type: 'image', image: { type: 'external', external: { url } } };
}

function code(text, language) {
  return {
    object: 'block',
    type: 'code',
    code: { rich_text: rt(text), language: language || 'plain text' },
  };
}

function divider() {
  return { object: 'block', type: 'divider', divider: {} };
}

function callout(text, emoji) {
  return {
    object: 'block',
    type: 'callout',
    callout: { rich_text: rt(text), icon: emoji ? { type: 'emoji', emoji } : undefined },
  };
}

function pushIfText(blocks, text, factory) {
  if (text == null) return;
  const s = typeof text === 'string' ? text : JSON.stringify(text);
  if (!s.trim()) return;
  blocks.push(factory(s));
}

function renderKeyValueList(blocks, obj) {
  if (!obj || typeof obj !== 'object') return;
  for (const [k, v] of Object.entries(obj)) {
    const val = typeof v === 'string' ? v : JSON.stringify(v);
    blocks.push(bullet(`${k}: ${val}`));
  }
}

function renderArray(blocks, arr, formatter) {
  if (!Array.isArray(arr)) return;
  for (const item of arr) {
    const text = formatter ? formatter(item) : (typeof item === 'string' ? item : JSON.stringify(item));
    if (text && text.trim()) blocks.push(bullet(text));
  }
}

function loadMermaidSource(item) {
  if (item.mermaid_source) return item.mermaid_source;
  if (item.path && /\.mmd$/i.test(item.path)) {
    try {
      return fs.readFileSync(path.resolve(item.path), 'utf8');
    } catch { return null; }
  }
  return null;
}

function renderDiagram(blocks, item) {
  if (item.caption) blocks.push(paragraph(item.caption));
  const mermaid = loadMermaidSource(item);
  if (mermaid) {
    blocks.push(code(mermaid, 'mermaid'));
    return;
  }
  if (item.public_url) {
    blocks.push(image(item.public_url));
    return;
  }
  blocks.push(paragraph(`[asset pending] ${item.path || '(no path)'}`));
}

function render(intake, assets) {
  const blocks = [];
  const title = intake.skill_name_hint || intake.skill_name || 'Skill Intake';

  blocks.push(heading(1, title));
  if (intake.description || intake.purpose) {
    blocks.push(callout(intake.description || intake.purpose, '📝'));
  }

  blocks.push(heading(2, '5 軸'));
  const axes = intake['5_axes'] || intake.five_axes || {};
  const axisLabels = {
    output_destination: '出力先',
    info_source: '情報源',
    share_target: '共有相手',
    true_problem: '真の課題',
    knowledge_assets: 'ナレッジ資産',
  };
  for (const k of Object.keys(axisLabels)) {
    blocks.push(heading(3, axisLabels[k]));
    blocks.push(paragraph(axes[k] || '(未充足)'));
  }

  if (intake.user_profile) {
    blocks.push(heading(2, 'User Profile'));
    if (typeof intake.user_profile === 'string') {
      blocks.push(paragraph(intake.user_profile));
    } else {
      renderKeyValueList(blocks, intake.user_profile);
    }
  }

  if (intake.pattern || intake.pattern_classification) {
    blocks.push(heading(2, 'パターン分類'));
    const p = intake.pattern || intake.pattern_classification;
    if (typeof p === 'string') blocks.push(paragraph(p));
    else renderKeyValueList(blocks, p);
  }

  if (intake.integrations || intake.external_integrations) {
    blocks.push(heading(2, '外部連携'));
    const list = intake.integrations || intake.external_integrations;
    if (Array.isArray(list)) {
      renderArray(blocks, list, (i) => typeof i === 'string' ? i : `${i.name || i.service || ''}${i.purpose ? ' — ' + i.purpose : ''}`);
    } else {
      renderKeyValueList(blocks, list);
    }
  }

  if (intake.value_kpi || intake.outcome || intake.value_realization) {
    blocks.push(heading(2, '価値・KPI'));
    const v = intake.value_kpi || intake.outcome || intake.value_realization;
    if (typeof v === 'string') blocks.push(paragraph(v));
    else if (Array.isArray(v)) renderArray(blocks, v);
    else renderKeyValueList(blocks, v);
  }

  if (intake.anti_patterns) {
    blocks.push(heading(2, 'アンチパターン'));
    if (Array.isArray(intake.anti_patterns)) renderArray(blocks, intake.anti_patterns);
    else pushIfText(blocks, intake.anti_patterns, paragraph);
  }

  if (intake.completion_criteria || intake.completeness) {
    blocks.push(heading(2, '完了条件'));
    const c = intake.completion_criteria || intake.completeness;
    if (Array.isArray(c)) renderArray(blocks, c);
    else if (typeof c === 'string') blocks.push(paragraph(c));
    else renderKeyValueList(blocks, c);
  }

  if (Array.isArray(intake.open_questions) && intake.open_questions.length) {
    blocks.push(heading(2, 'Open Questions'));
    renderArray(blocks, intake.open_questions, (q) => typeof q === 'string' ? q : (q.text || q.question || JSON.stringify(q)));
  }

  if (assets && Array.isArray(assets.items) && assets.items.length) {
    blocks.push(heading(2, '図解'));
    for (const a of assets.items) renderDiagram(blocks, a);
  }

  if (intake.next_action || intake.next_actions) {
    blocks.push(divider());
    blocks.push(heading(2, 'Next Action (skill-creator 引き渡し)'));
    const n = intake.next_action || intake.next_actions;
    if (typeof n === 'string') blocks.push(paragraph(n));
    else if (Array.isArray(n)) renderArray(blocks, n);
    else renderKeyValueList(blocks, n);
  }

  if (intake.handoff_candidates || intake.handoff) {
    blocks.push(heading(2, 'Handoff 候補'));
    const h = intake.handoff_candidates || intake.handoff;
    if (Array.isArray(h)) renderArray(blocks, h);
    else if (typeof h === 'string') blocks.push(paragraph(h));
    else renderKeyValueList(blocks, h);
  }

  if (intake.skill_construction_brief || intake.skill_creator_brief) {
    blocks.push(heading(2, 'スキル構築 brief サマリ'));
    const b = intake.skill_construction_brief || intake.skill_creator_brief;
    if (typeof b === 'string') blocks.push(paragraph(b));
    else renderKeyValueList(blocks, b);
  }

  return { children: blocks };
}

function main(argv) {
  const intakeFile = argv[2];
  const assetsFile = argv[3];
  const outFile = argv[4];
  if (!intakeFile) {
    process.stderr.write('usage: render_notion_page.js <intake.json> [manifest.json] [out.json]\n');
    return 2;
  }
  let intake; let assets = null;
  try {
    intake = JSON.parse(fs.readFileSync(path.resolve(intakeFile), 'utf8'));
    if (assetsFile && fs.existsSync(assetsFile)) {
      assets = JSON.parse(fs.readFileSync(path.resolve(assetsFile), 'utf8'));
    }
  } catch (e) {
    process.stderr.write(`input error: ${e.message}\n`);
    return 2;
  }
  const out = render(intake, assets);
  const text = JSON.stringify(out, null, 2);
  if (outFile) fs.writeFileSync(path.resolve(outFile), text + '\n');
  else process.stdout.write(text + '\n');
  return 0;
}

module.exports = { render };

if (require.main === module) {
  process.exit(main(process.argv));
}
