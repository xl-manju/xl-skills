#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

function checkSection(name, body) {
  const text = String(body || '').trim();
  const wordCount = text.split(/\s+/).filter(Boolean).length;
  const hasHeading = /^#{1,4}\s/m.test(text) || true;
  const hasContent = wordCount >= 20;
  const hasPlaceholder = /(TBD|未定|要確認|\?{2,})/i.test(text);
  const ok = hasContent && !hasPlaceholder;
  return { section: name, ok, word_count: wordCount, has_heading: hasHeading, has_placeholder: hasPlaceholder };
}

function checkAll(sections) {
  const results = Object.keys(sections).map((k) => checkSection(k, sections[k]));
  const failed = results.filter((r) => !r.ok);
  return { ok: failed.length === 0, results, failed_count: failed.length };
}

function main(argv) {
  const file = argv[2];
  if (!file) { process.stderr.write('usage: section_quality_check.js <intake.json>\n'); return 2; }
  let data;
  try { data = JSON.parse(fs.readFileSync(path.resolve(file), 'utf8')); }
  catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  const sections = data.sections || {};
  const r = checkAll(sections);
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return r.ok ? 0 : 1;
}

module.exports = { checkAll, checkSection };

if (require.main === module) {
  process.exit(main(process.argv));
}
