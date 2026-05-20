#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function hasMmdc() {
  const r = spawnSync('mmdc', ['--version'], { encoding: 'utf8' });
  return r.status === 0;
}

function placeholderPng(outputPath, note) {
  const txt = `# mmdc not installed\n# placeholder for ${path.basename(outputPath)}\n# note: ${note || ''}\n`;
  fs.writeFileSync(outputPath + '.placeholder.txt', txt);
}

function render(inputPath, outputPath, opts) {
  const fmt = opts && opts.format ? opts.format : (outputPath.endsWith('.svg') ? 'svg' : 'png');
  if (!hasMmdc()) {
    placeholderPng(outputPath, `format=${fmt}`);
    return { ok: true, mode: 'placeholder', output: outputPath };
  }
  const args = ['-i', inputPath, '-o', outputPath, '-b', 'white'];
  if (opts && opts.width) args.push('-w', String(opts.width));
  if (opts && opts.height) args.push('-H', String(opts.height));
  const r = spawnSync('mmdc', args, { encoding: 'utf8' });
  if (r.status !== 0) return { ok: false, mode: 'mmdc', stderr: r.stderr };
  return { ok: true, mode: 'mmdc', output: outputPath, format: fmt };
}

function main(argv) {
  const input = argv[2];
  const output = argv[3];
  if (!input || !output) { process.stderr.write('usage: render_to_image.js <input.mmd> <output.png>\n'); return 2; }
  if (!fs.existsSync(input)) { process.stderr.write(`input missing: ${input}\n`); return 2; }
  const r = render(path.resolve(input), path.resolve(output), { width: 1200 });
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return r.ok ? 0 : 3;
}

module.exports = { render, hasMmdc };

if (require.main === module) {
  process.exit(main(process.argv));
}
