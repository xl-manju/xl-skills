#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');

function loadBank(p) {
  if (!fs.existsSync(p)) return '';
  return fs.readFileSync(p, 'utf8');
}

function append(bank, sessionId, questions) {
  const stamp = new Date().toISOString();
  const lines = [`\n## Session ${sessionId} — ${stamp}`];
  for (const q of questions) {
    const text = typeof q === 'string' ? q : q.text || JSON.stringify(q);
    const tags = (typeof q === 'object' && q.tags) ? ` <!-- ${q.tags.join(',')} -->` : '';
    lines.push(`- ${text}${tags}`);
  }
  return bank.replace(/\s*$/, '') + lines.join('\n') + '\n';
}

function main(argv) {
  const bankFile = argv[2];
  const sessionFile = argv[3];
  if (!bankFile || !sessionFile) {
    process.stderr.write('usage: update_question_bank.js <question-bank.md> <session.json>\n');
    return 2;
  }
  let session;
  try { session = JSON.parse(fs.readFileSync(path.resolve(sessionFile), 'utf8')); }
  catch (e) { process.stderr.write(`input error: ${e.message}\n`); return 2; }
  const sessionId = session.session_id || session.id || `s-${Date.now()}`;
  const questions = session.questions || session.used_questions || [];
  const bank = loadBank(path.resolve(bankFile));
  const next = append(bank, sessionId, questions);
  fs.writeFileSync(path.resolve(bankFile), next);
  process.stdout.write(JSON.stringify({ ok: true, appended: questions.length, session_id: sessionId }) + '\n');
  return 0;
}

module.exports = { append };

if (require.main === module) {
  process.exit(main(process.argv));
}
