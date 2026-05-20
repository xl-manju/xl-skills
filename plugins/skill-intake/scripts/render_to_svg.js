#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function hasMmdc() {
  const r = spawnSync('mmdc', ['--version'], { encoding: 'utf8' });
  return r.status === 0;
}

function render(inputPath, outputPath) {
  if (!hasMmdc()) {
    const placeholder = `<?xml version="1.0"?>\n<!-- mmdc not installed; placeholder for ${path.basename(inputPath)} -->\n<svg xmlns="http://www.w3.org/2000/svg" width="320" height="80"><text x="10" y="40">mermaid placeholder</text></svg>\n`;
    fs.writeFileSync(outputPath, placeholder);
    return { ok: true, mode: 'placeholder', output: outputPath };
  }
  const r = spawnSync('mmdc', ['-i', inputPath, '-o', outputPath, '-b', 'transparent'], { encoding: 'utf8' });
  if (r.status !== 0) {
    return { ok: false, mode: 'mmdc', stderr: r.stderr };
  }
  return { ok: true, mode: 'mmdc', output: outputPath };
}

function main(argv) {
  const input = argv[2];
  const output = argv[3];
  if (!input || !output) { process.stderr.write('usage: render_to_svg.js <input.mmd> <output.svg>\n'); return 2; }
  if (!fs.existsSync(input)) { process.stderr.write(`input missing: ${input}\n`); return 2; }
  const r = render(path.resolve(input), path.resolve(output));
  process.stdout.write(JSON.stringify(r, null, 2) + '\n');
  return r.ok ? 0 : 3;
}

module.exports = { render, hasMmdc };

if (require.main === module) {
  process.exit(main(process.argv));
}
