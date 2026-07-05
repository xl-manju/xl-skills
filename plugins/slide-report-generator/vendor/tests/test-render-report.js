/**
 * test-render-report.js — render-report.js の最小テスト (node 実行)。
 *
 * サンプル (sample-report-structure.json) は report-structure.schema.json に valid。
 * 検証:
 *   (a) 例外なく HTML を生成する
 *   (b) 出力に必須要素が含まれる:
 *       - <!DOCTYPE html> / </html>
 *       - 各 section の heading (schema: section.heading)
 *       - theme CSS var (--bg-dark 等 Kanagawa トークン)・theme-name=kanagawa-lotus
 *       - svg visual: <svg viewBox + variant 由来のノードラベル + visual.caption
 *       - mermaid visual: <pre class="mermaid"> + CDN 初期化 + spec.definition テキスト
 *       - codex-image visual: <img src=spec.asset>
 *       - none visual: fallback を誤爆しない
 *       - reportType バッジ
 *   (c) 決定論: 同一入力→byte 一致
 *
 * 失敗時 exit 1、成功時 exit 0。
 *   実行: node test-render-report.js
 */

import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { renderReport } from '../scripts/render-report.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
let failed = 0;
function check(name, cond) {
  if (cond) {
    console.log(`  ok   - ${name}`);
  } else {
    console.error(`  FAIL - ${name}`);
    failed++;
  }
}

const structure = JSON.parse(readFileSync(join(__dirname, 'sample-report-structure.json'), 'utf-8'));

let html = '';
let threw = null;
try {
  html = renderReport(structure);
} catch (e) {
  threw = e;
}

check('(a) 例外なく HTML を生成', threw === null && typeof html === 'string' && html.length > 0);
if (threw) console.error('     ', threw.stack);

// (b) 文書骨格
check('(b) <!DOCTYPE html> を含む', html.startsWith('<!DOCTYPE html>'));
check('(b) 終端 </html> を含む', html.trimEnd().endsWith('</html>'));

// (b) 各 section heading (schema: section.heading)
for (const sec of structure.sections) {
  check(`(b) section heading "${sec.heading}" を含む`, html.includes(`>${sec.heading}</h2>`));
}
// (b) 各 section id (schema: ^section-)
for (const sec of structure.sections) {
  check(`(b) section id "${sec.id}" を含む`, html.includes(`id="${sec.id}"`));
}

// (b) theme CSS var (Kanagawa トークン)
check('(b) theme CSS var --bg-dark を含む', html.includes('--bg-dark:'));
check('(b) theme CSS var --accent-blue-vivid を含む', html.includes('--accent-blue-vivid:'));
check('(b) theme-name meta が kanagawa-lotus', html.includes('content="kanagawa-lotus"'));

// --- visual: schema 語彙で各サンプル section を検証 ---
const bySection = Object.fromEntries(structure.sections.map((s) => [s.id, s]));

// svg (variant=flow, nodes[].label / visual.caption)
const svgFlow = bySection['section-background'];
check('(b) svg <svg viewBox を含む', html.includes('<svg viewBox='));
check('(b) svg visual.caption を含む', html.includes(svgFlow.visual.caption));
check('(b) svg ノードラベルを含む', html.includes(svgFlow.visual.spec.nodes[0].label));

// svg (variant=cycle) も描画される
const svgCycle = bySection['section-next-action'];
check('(b) svg cycle caption を含む', html.includes(svgCycle.visual.caption));

// mermaid (spec.definition / diagramType / CDN 初期化)
const mm = bySection['section-analysis'];
check('(b) mermaid <pre class="mermaid"> を含む', html.includes('<pre class="mermaid">'));
check('(b) mermaid CDN 初期化 script を含む', html.includes('mermaid.initialize'));
check('(b) mermaid 定義テキスト(系統判定)が埋込まれている', html.includes('系統判定'));
check('(b) mermaid visual.caption を含む', html.includes(mm.visual.caption));

// codex-image (spec.asset → <img>)
const codex = bySection['section-findings'];
check('(b) codex-image <img src=asset> を含む', html.includes(`<img src="${codex.visual.spec.asset}"`));
check('(b) codex-image alt を含む', html.includes(codex.visual.alt));

// none (fallback を誤爆しない)
check('(b) none section で fallback を出さない', !html.includes('report-visual--fallback'));

// reportType バッジ / meta
check('(b) reportType バッジ(社内報告分析)を含む', html.includes('社内報告分析'));
check('(b) meta.audience を含む', html.includes(structure.meta.audience));
check('(b) meta.keyMessage を含む', html.includes(structure.meta.keyMessage));

// section 要素数
const sectionCount = (html.match(/class="report-section"/g) || []).length;
check(`(b) section 要素数 = ${structure.sections.length}`, sectionCount === structure.sections.length);

// (c) 決定論
const html2 = renderReport(structure);
check('(c) 決定論: 2回の生成が byte 一致', html === html2);

console.log('');
if (failed > 0) {
  console.error(`test-render-report: ${failed} 件 FAIL (${html.length} bytes)`);
  process.exit(1);
}
console.log(`test-render-report: 全 PASS (${Buffer.byteLength(html)} bytes, ${structure.sections.length} sections)`);
process.exit(0);
