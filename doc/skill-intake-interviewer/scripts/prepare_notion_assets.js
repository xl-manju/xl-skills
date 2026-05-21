#!/usr/bin/env node
/**
 * prepare_notion_assets.js
 * 用途: visuals/ 配下を走査し Notion 公開用マニフェストを作る。
 *       - .mmd  → mermaid_block ルート（Notion の code block で表示）
 *       - .svg  → image_upload ルート（必ず PNG を生成）
 *       - .png  → image_upload ルート（そのまま）
 * 入力: --visuals <dir> --output <manifest.json> [--width 1600] [--mermaid-fallback svg|png]
 * 出力: manifest.json
 *   {
 *     items: [
 *       { id, source, kind: "mermaid"|"svg"|"png", route: "mermaid_block"|"image_upload",
 *         block_text?: "...", image_path?: "...", section_hint?: "..." }
 *     ],
 *     summary: { total, mermaid_blocks, image_uploads, png_generated }
 *   }
 * 終了コード: 0=全て準備完了, 1=1つでも変換失敗（マスト失敗）
 */

'use strict';
const fs = require('fs');
const path = require('path');
const { render } = require('./render_to_image');

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

function walk(dir) {
  const out = [];
  if (!fs.existsSync(dir)) return out;
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
}

function classify(file) {
  const ext = path.extname(file).toLowerCase();
  if (ext === '.mmd') return 'mermaid';
  if (ext === '.svg') return 'svg';
  if (ext === '.png') return 'png';
  return null;
}

function sectionHint(file, visualsRoot) {
  const rel = path.relative(visualsRoot, file);
  const parts = rel.split(path.sep);
  if (parts.length >= 2) return parts[0];
  return path.basename(file, path.extname(file));
}

function prepare(visualsDir, outputPath, width) {
  const files = walk(visualsDir).filter(f => classify(f));
  files.sort();

  const items = [];
  const errors = [];
  let pngGenerated = 0;

  for (const f of files) {
    const kind = classify(f);
    const id = path.relative(visualsDir, f).replace(/[\\/]/g, '_').replace(/\.[^.]+$/, '');
    const hint = sectionHint(f, visualsDir);

    if (kind === 'mermaid') {
      const text = fs.readFileSync(f, 'utf8');
      items.push({
        id,
        source: f,
        kind,
        route: 'mermaid_block',
        block_text: text,
        section_hint: hint,
      });
    } else if (kind === 'svg') {
      const png = f.replace(/\.svg$/i, '.png');
      try {
        if (!fs.existsSync(png) || fs.statSync(png).size === 0) {
          render(f, png, width);
          pngGenerated++;
        }
        items.push({
          id,
          source: f,
          kind,
          route: 'image_upload',
          image_path: png,
          section_hint: hint,
        });
      } catch (e) {
        errors.push({ file: f, error: e.message });
      }
    } else if (kind === 'png') {
      items.push({
        id,
        source: f,
        kind,
        route: 'image_upload',
        image_path: f,
        section_hint: hint,
      });
    }
  }

  const summary = {
    total: items.length,
    mermaid_blocks: items.filter(i => i.route === 'mermaid_block').length,
    image_uploads: items.filter(i => i.route === 'image_upload').length,
    png_generated: pngGenerated,
    errors: errors.length,
  };

  const manifest = { generated_at: new Date().toISOString(), visuals_dir: visualsDir, items, summary, errors };

  if (outputPath) {
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, JSON.stringify(manifest, null, 2));
  }

  return manifest;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.visuals || !args.output) {
    process.stderr.write('Usage: prepare_notion_assets.js --visuals <dir> --output <manifest.json> [--width 1600]\n');
    process.exit(1);
  }
  const width = parseInt(args.width || '1600', 10);
  try {
    const manifest = prepare(args.visuals, args.output, width);
    process.stdout.write(JSON.stringify(manifest.summary, null, 2) + '\n');
    if (manifest.errors.length > 0) {
      process.stderr.write(`FAIL: ${manifest.errors.length} SVG could not be converted to PNG.\n`);
      for (const er of manifest.errors) process.stderr.write(`  - ${er.file}: ${er.error.split('\n')[0]}\n`);
      process.exit(1);
    }
    process.exit(0);
  } catch (e) {
    process.stderr.write(`prepare failed: ${e.message}\n`);
    process.exit(1);
  }
}

if (require.main === module) main();
module.exports = { prepare };
