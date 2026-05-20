#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const DEFAULT_TEMPLATE = `## {{title}}

**ねらい**: {{purpose}}

**現状**: {{current}}

**期待**: {{expected}}

{{diagram_block}}

**未解決**: {{open_questions}}
`;

function fill(tpl, vars) {
  return tpl.replace(/\{\{(\w+)\}\}/g, (_, k) => (vars[k] != null ? String(vars[k]) : ''));
}

function diagramBlock(diagrams) {
  if (!Array.isArray(diagrams) || diagrams.length === 0) return '';
  return diagrams.map((d) => `\n\`\`\`mermaid\n${d.trim()}\n\`\`\`\n`).join('');
}

function apply(template, vars) {
  const v = { ...vars };
  if (Array.isArray(v.diagrams)) v.diagram_block = diagramBlock(v.diagrams);
  return fill(template || DEFAULT_TEMPLATE, v);
}

function main(argv) {
  const varsFile = argv[2];
  const templateFile = argv[3];
  if (!varsFile) { process.stderr.write('usage: apply_section_template.js <vars.json> [template.md]\n'); return 2; }
  let vars; let tpl = DEFAULT_TEMPLATE;
  try {
    vars = JSON.parse(fs.readFileSync(path.resolve(varsFile), 'utf8'));
    if (templateFile) tpl = fs.readFileSync(path.resolve(templateFile), 'utf8');
  } catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  process.stdout.write(apply(tpl, vars));
  return 0;
}

module.exports = { apply, DEFAULT_TEMPLATE };

if (require.main === module) {
  process.exit(main(process.argv));
}
