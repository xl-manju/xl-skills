#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

const TEMPLATES = {
  flow: 'flowchart TD\n{{nodes}}\n{{edges}}',
  sequence: 'sequenceDiagram\n{{participants}}\n{{messages}}',
  quadrant: 'quadrantChart\n  title {{title}}\n  x-axis {{x_low}} --> {{x_high}}\n  y-axis {{y_low}} --> {{y_high}}\n{{items}}',
  state: 'stateDiagram-v2\n{{transitions}}',
  graph: 'graph LR\n{{nodes}}\n{{edges}}',
};

function fill(template, vars) {
  return template.replace(/\{\{(\w+)\}\}/g, (_, k) => (vars[k] != null ? String(vars[k]) : ''));
}

function compose(type, vars) {
  const tpl = TEMPLATES[type] || TEMPLATES.flow;
  return fill(tpl, vars || {});
}

function main(argv) {
  const type = argv[2];
  const varsFile = argv[3];
  if (!type) { process.stderr.write('usage: compose_diagram.js <type> [vars.json]\n'); return 2; }
  let vars = {};
  if (varsFile) {
    try { vars = JSON.parse(fs.readFileSync(path.resolve(varsFile), 'utf8')); }
    catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  }
  process.stdout.write(compose(type, vars) + '\n');
  return 0;
}

module.exports = { compose, TEMPLATES };

if (require.main === module) {
  process.exit(main(process.argv));
}
