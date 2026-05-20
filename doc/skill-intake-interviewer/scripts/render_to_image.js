#!/usr/bin/env node
/**
 * render_to_image.js
 * 用途: SVG → PNG 変換（Notion 添付用）。複数のレンダラを順に試し、1つでも成功すれば PNG を生成
 * 入力: --input <path.svg> --output <path.png> [--width 1600] [--strict]
 * 出力: PNG ファイル + stdout JSON { renderer, output, size_bytes }
 * 終了コード: 0=成功, 1=全レンダラ失敗（--strict 時は必ず exit 1）
 *
 * フォールバック順序:
 *   1. rsvg-convert (librsvg) — 最も忠実
 *   2. magick / convert (ImageMagick)
 *   3. sips (macOS 標準) — SVG 直接対応は限定的だが PDF 経由で可
 *   4. inkscape
 *   5. node sharp（npm i sharp が必要）
 */

'use strict';
const fs = require('fs');
const path = require('path');
const { execSync, spawnSync } = require('child_process');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (!k.startsWith('--')) continue;
    const key = k.replace(/^--/, '');
    const next = argv[i + 1];
    if (!next || next.startsWith('--')) { args[key] = true; }
    else { args[key] = next; i++; }
  }
  return args;
}

function which(cmd) {
  try { execSync(`command -v ${cmd}`, { stdio: 'ignore' }); return true; }
  catch (_) { return false; }
}

const renderers = [
  {
    name: 'rsvg-convert',
    available: () => which('rsvg-convert'),
    run: (input, output, width) => {
      execSync(`rsvg-convert -w ${width} -f png -o "${output}" "${input}"`, { stdio: 'pipe' });
    },
  },
  {
    name: 'magick',
    available: () => which('magick'),
    run: (input, output, width) => {
      execSync(`magick -background none -density 200 "${input}" -resize ${width}x "${output}"`, { stdio: 'pipe' });
    },
  },
  {
    name: 'convert',
    available: () => which('convert'),
    run: (input, output, width) => {
      execSync(`convert -background none -density 200 "${input}" -resize ${width}x "${output}"`, { stdio: 'pipe' });
    },
  },
  {
    name: 'inkscape',
    available: () => which('inkscape'),
    run: (input, output, width) => {
      execSync(`inkscape --export-type=png --export-filename="${output}" --export-width=${width} "${input}"`, { stdio: 'pipe' });
    },
  },
  {
    name: 'sharp',
    available: () => { try { require.resolve('sharp'); return true; } catch (_) { return false; } },
    run: (input, output, width) => {
      const sharp = require('sharp');
      const buf = fs.readFileSync(input);
      // 同期ラッパは無いが execSync 不要。ここは exec で別 node を呼ぶ簡易対応
      const tmpScript = path.join(require('os').tmpdir(), `sharp-render-${Date.now()}.js`);
      fs.writeFileSync(tmpScript, `require('sharp')(${JSON.stringify(buf.toString('base64'))} && Buffer.from(process.argv[2],'base64')).resize(${width}).png().toFile(${JSON.stringify(output)}).then(()=>process.exit(0)).catch(e=>{console.error(e);process.exit(1)});`);
      try { execSync(`node "${tmpScript}" "${buf.toString('base64')}"`, { stdio: 'pipe' }); }
      finally { try { fs.unlinkSync(tmpScript); } catch (_) {} }
    },
  },
  {
    name: 'sips-via-pdf',
    available: () => which('sips') && (which('rsvg-convert') || which('cairosvg') || which('qlmanage')),
    run: (input, output, width) => {
      const tmpPdf = path.join(require('os').tmpdir(), `svg2pdf-${Date.now()}.pdf`);
      if (which('rsvg-convert')) execSync(`rsvg-convert -f pdf -o "${tmpPdf}" "${input}"`, { stdio: 'pipe' });
      else if (which('cairosvg')) execSync(`cairosvg "${input}" -o "${tmpPdf}"`, { stdio: 'pipe' });
      else throw new Error('no svg→pdf converter');
      try { execSync(`sips -s format png --resampleWidth ${width} "${tmpPdf}" --out "${output}"`, { stdio: 'pipe' }); }
      finally { try { fs.unlinkSync(tmpPdf); } catch (_) {} }
    },
  },
];

function detectRenderers() {
  return renderers.filter(r => r.available()).map(r => r.name);
}

function render(input, output, width) {
  if (!fs.existsSync(input)) throw new Error(`input not found: ${input}`);
  fs.mkdirSync(path.dirname(output), { recursive: true });
  const errors = [];
  for (const r of renderers) {
    if (!r.available()) continue;
    try {
      r.run(input, output, width);
      if (fs.existsSync(output) && fs.statSync(output).size > 0) {
        return { renderer: r.name, output, size_bytes: fs.statSync(output).size };
      }
      errors.push(`${r.name}: produced empty file`);
    } catch (e) {
      errors.push(`${r.name}: ${e.message.split('\n')[0]}`);
    }
  }
  const installed = detectRenderers();
  throw new Error(
    `All renderers failed.\n` +
    `Tried: ${errors.join(' | ') || '(none available)'}\n` +
    `Installed: ${installed.length ? installed.join(', ') : 'none'}\n` +
    `Install one of: brew install librsvg | brew install imagemagick | brew install inkscape | npm i sharp`
  );
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.detect) {
    process.stdout.write(JSON.stringify({ available: detectRenderers() }, null, 2) + '\n');
    process.exit(0);
  }
  if (!args.input || !args.output) {
    process.stderr.write('Usage: render_to_image.js --input <svg> --output <png> [--width 1600] [--strict]\n');
    process.stderr.write('       render_to_image.js --detect\n');
    process.exit(1);
  }
  const width = parseInt(args.width || '1600', 10);
  try {
    const r = render(args.input, args.output, width);
    process.stdout.write(JSON.stringify(r, null, 2) + '\n');
    process.exit(0);
  } catch (e) {
    process.stderr.write(`render failed: ${e.message}\n`);
    process.exit(1);
  }
}

if (require.main === module) main();
module.exports = { render, detectRenderers };
