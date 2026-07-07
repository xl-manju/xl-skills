/**
 * render-report.js — report-structure.json → report.html (決定論生成)
 *
 * 契約: report-structure.schema.json (正本) / BUILD CONTRACT §F・§E・§D。
 *   実行: node render-report.js <report-structure.json> <out.html>
 *
 * schema 語彙で読む (consumer は正本 schema に conform):
 *   - meta: title/reportType/audience/keyMessage/subtitle/length(brief|standard|deep)/author…
 *   - section: id(^section-)/heading/paragraphs[]/role/visual/readingOrder(視線方向 enum・任意)/callouts
 *   - visual: {kind, spec, caption, alt, rationale}  ← caption/alt は visual 直下 (spec 内でない)
 *       kind=svg         → svgSpec {variant, nodes[](^n-), edges?, groups?} を svg-builder.cjs へ dispatch
 *       kind=mermaid     → mermaidSpec {diagramType, definition} を mermaid-render.js へ
 *       kind=codex-image → aiVisualSpec {pattern, backgroundSource, asset?, slug, overlayText…} を <img>/composite へ
 *       kind=none        → spec 省略・テキストのみ
 *
 * 意匠トークン (Kanagawa Lotus 配色 / フォント / spacing / 最小サイズ) は
 * vendored `style-builder.cjs` の SPEC を **唯一のソース** として流用する
 * (slide と同一 SSOT・新規発明しない)。report は A4 縦向き・縦スクロールの読み物レイアウト。
 *
 * ESM (vendor/package.json type=module)。vendored .cjs は createRequire で require。
 * CLI と import (renderReport) の両対応。決定論・fail-soft (visual 失敗は fallback、render は落ちない)。
 */

import { readFileSync, writeFileSync } from 'fs';
import { createRequire } from 'module';
import { pathToFileURL } from 'url';
import { renderMermaidFragment, mermaidInitScript } from './mermaid-render.js';

// vendored CommonJS primitives を ESM から require する (共有意匠 SSOT の流用)
const require = createRequire(import.meta.url);
const { SPEC } = require('./style-builder.cjs');
const { escapeHtml } = require('./template-engine.cjs');
const svg = require('./svg-builder.cjs');

// reportType (§D の 4 enum) → アクセント色。読み物の視覚的アイデンティティ付与。
const REPORT_TYPE_ACCENT = {
  'internal-analysis': 'accent-blue-vivid',
  'client-proposal': 'accent-aqua-vivid',
  'tech-doc': 'accent-violet-vivid',
  learning: 'accent-yellow-vivid',
};

// svgSpec.variant (schema enum) → svg-builder.cjs のノードベース図解ビルダーへ写像。
// 単一配列引数 (items|events|circles|quadrants, opts) のビルダーはここで統一 dispatch。
// mindmap/comparison/network は多引数のため renderSvgVisual 内で個別処理。
const VARIANT_SINGLE_ARG = {
  flow: 'buildHorizontalFlow',
  stepper: 'buildVerticalFlow',
  'wave-step': 'buildSnake',
  snake: 'buildSnake',
  cycle: 'buildCycle',
  pyramid: 'buildPyramid',
  tree: 'buildHierarchy',
  org: 'buildHierarchy',
  matrix: 'buildMatrix',
  venn: 'buildVenn',
  timeline: 'buildVerticalTimeline',
  roadmap: 'buildVerticalTimeline',
  chevron: 'buildChevron',
  funnel: 'buildFunnel',
  concentric: 'buildConcentric',
  'value-stack': 'buildValueStack',
};

/** theme を string|object の両方許容し正規化 (schema: kanagawa-lotus 固定) */
function themeName(theme) {
  if (!theme) return 'kanagawa-lotus';
  if (typeof theme === 'string') return theme;
  return theme.name || 'kanagawa-lotus';
}

/**
 * 共有意匠 SSOT (SPEC) から report 用 :root と読み物レイアウト CSS を生成。
 * 色/フォント/spacing の値は SPEC が唯一のソース。単位は rem/mm (縦スクロール文書)。
 */
function buildReportCss(spec = SPEC) {
  const c = spec.colors;
  const fs = spec.fontScale;
  const spacingVars = spec.spacing.map((v, i) => `  --space-${i + 1}: ${v};`).join('\n');
  return `:root {
  /* §2 Kanagawa Lotus パレット (style-builder SPEC を流用 = 共有意匠 SSOT) */
  --bg-dark: ${c.bgDark};
  --fg: ${c.fg};
  --fg-dim: ${c.fgDim};
  --fg-muted: #54546d;
  --wave-blue: ${c.waveBlue};
  --spring-violet: ${c.springViolet};
  --sakura-pink: ${c.sakuraPink};
  --wave-aqua: ${c.waveAqua};
  --autumn-yellow: ${c.autumnYellow};
  --fuji-gray: ${c.fujiGray};
  --accent-blue-vivid: ${c.accentBlueVivid};
  --accent-pink-vivid: ${c.accentPinkVivid};
  --accent-aqua-vivid: ${c.accentAquaVivid};
  --accent-violet-vivid: ${c.accentVioletVivid};
  --accent-yellow-vivid: ${c.accentYellowVivid};
  --shadow-subtle: 0 1px 3px rgba(0,0,0,0.06);
  --shadow-medium: 0 3px 10px rgba(0,0,0,0.10);
  /* §3 フォント (SPEC 流用) */
  --font-scale: ${fs};
  --font-base: ${spec.fonts.base};
  --font-mono: ${spec.fonts.mono};
  --fs-title: calc(2.6rem * var(--font-scale));
  --fs-heading: calc(1.7rem * var(--font-scale));
  --fs-subheading: calc(1.3rem * var(--font-scale));
  --fs-body: calc(1.05rem * var(--font-scale));   /* 読み物本文・最小サイズは SPEC 準拠 */
  --fs-small: calc(0.9rem * var(--font-scale));
${spacingVars}
  /* report ページ幅 (A4 縦) */
  --report-width: 190mm;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 16px; }
body {
  background: var(--bg-dark);
  color: var(--fg);
  font-family: var(--font-base);
  font-size: var(--fs-body);
  line-height: 1.85;
  -webkit-font-smoothing: antialiased;
}

/* ===== 読み物レイアウト (縦スクロール・A4 縦) ===== */
.report {
  max-width: var(--report-width);
  margin: 0 auto;
  padding: var(--space-7, 3rem) var(--space-6, 2rem) var(--space-8, 4rem);
}
.report-header { margin-bottom: var(--space-7, 3rem); border-bottom: 3px solid var(--report-accent, var(--accent-blue-vivid)); padding-bottom: var(--space-4, 1rem); }
.report-title { font-size: var(--fs-title); font-weight: 800; line-height: 1.25; color: var(--fg); }
.report-subtitle { margin-top: var(--space-2, 0.5rem); font-size: var(--fs-subheading); color: var(--fg-dim); font-weight: 500; }
.report-keymessage { margin-top: var(--space-3, 0.75rem); font-size: var(--fs-body); color: var(--fg); font-weight: 500; border-left: 0.3rem solid var(--report-accent, var(--accent-blue-vivid)); padding-left: var(--space-3, 0.75rem); }
.report-meta { margin-top: var(--space-3, 0.75rem); font-size: var(--fs-small); color: var(--fg-dim); display: flex; flex-wrap: wrap; gap: var(--space-4, 1rem); align-items: center; }
.report-meta .report-type-badge {
  display: inline-block; padding: 0.2rem 0.7rem; border-radius: 999px;
  background: var(--report-accent, var(--accent-blue-vivid)); color: #fff; font-weight: 700;
}

/* ===== section ===== */
.report-section { margin-bottom: var(--space-7, 3rem); }
.report-section > h2 {
  font-size: var(--fs-heading); font-weight: 700; line-height: 1.35;
  color: var(--fg);
  padding-left: var(--space-3, 0.75rem);
  border-left: 0.35rem solid var(--section-accent, var(--accent-blue-vivid));
  margin-bottom: var(--space-4, 1rem);
}
.report-section p { font-size: var(--fs-body); margin-bottom: var(--space-4, 1rem); }
.report-section strong { color: var(--section-accent, var(--accent-blue-vivid)); font-weight: 700; }
.report-section code { font-family: var(--font-mono); font-size: 0.92em; background: rgba(59,125,216,0.10); padding: 0.1em 0.35em; border-radius: 0.25rem; }
.report-section a { color: var(--accent-blue-vivid); }
.report-section ul { margin: 0 0 var(--space-4, 1rem) var(--space-5, 1.5rem); }
.report-section li { font-size: var(--fs-body); margin-bottom: var(--space-2, 0.5rem); }

/* ===== callouts (注記/警告/ヒント) ===== */
.report-callout { display: block; margin: var(--space-3, 0.75rem) 0; padding: var(--space-3, 0.75rem); border-radius: 0.5rem; font-size: var(--fs-small); border-left: 0.3rem solid var(--accent-blue-vivid); background: rgba(59,125,216,0.06); }
.report-callout--warning, .report-callout--caution { border-left-color: var(--accent-pink-vivid); background: rgba(217,75,110,0.07); }
.report-callout--tip { border-left-color: var(--accent-yellow-vivid); background: rgba(245,166,35,0.08); }

/* ===== 1 section 1 visual ===== */
.report-visual { margin: var(--space-5, 1.5rem) 0; text-align: center; }
.report-visual svg { width: 100%; max-width: var(--report-width); height: auto; }
.report-visual img { max-width: 100%; height: auto; border-radius: 0.5rem; box-shadow: var(--shadow-medium); }
.report-visual figcaption { margin-top: var(--space-2, 0.5rem); font-size: var(--fs-small); color: var(--fg-dim); }
.report-visual--mermaid pre.mermaid {
  display: block; text-align: left; font-family: var(--font-mono); font-size: var(--fs-small);
  background: rgba(59,125,216,0.06); border: 1px solid rgba(67,67,108,0.14);
  border-radius: 0.5rem; padding: var(--space-3, 0.75rem); overflow-x: auto; white-space: pre;
}
.report-visual--image .composite-overlay { list-style: none; margin: var(--space-2, 0.5rem) 0 0; padding: 0; font-size: var(--fs-small); color: var(--fg-dim); }

.report-footer { margin-top: var(--space-8, 4rem); padding-top: var(--space-3, 0.75rem); border-top: 1px solid rgba(67,67,108,0.15); font-size: var(--fs-small); color: var(--fg-dim); text-align: center; }

/* ===== 印刷 (A4 縦・読み物) ===== */
@page { size: A4 portrait; margin: 18mm; }
@media print {
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
  body { background: #fff; }
  .report { max-width: 100%; padding: 0; }
  .report-section { break-inside: avoid-page; }
  .report-visual { break-inside: avoid; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; }
}`;
}

/**
 * 最小 Markdown → HTML (決定論・安全)。
 * 先に escapeHtml して注入を防いだ上で、安全なパターンのみ再装飾する。
 * ブロック配列の各要素を段落 or 箇条書きへ変換。
 */
function renderParagraphs(paragraphs) {
  const blocks = Array.isArray(paragraphs) ? paragraphs : paragraphs ? [String(paragraphs)] : [];
  return blocks
    .map((raw) => {
      const block = String(raw == null ? '' : raw);
      const lines = block.split('\n').map((l) => l.trimEnd());
      const isList = lines.length > 0 && lines.every((l) => l.trim() === '' || /^\s*[-*]\s+/.test(l));
      if (isList && lines.some((l) => l.trim() !== '')) {
        const items = lines
          .filter((l) => l.trim() !== '')
          .map((l) => `    <li>${inlineMd(l.replace(/^\s*[-*]\s+/, ''))}</li>`)
          .join('\n');
        return `  <ul>\n${items}\n  </ul>`;
      }
      const html = lines.map((l) => inlineMd(l)).join('<br>\n    ');
      return `  <p>${html}</p>`;
    })
    .join('\n');
}

/** インライン装飾 (escape 後の安全な文字列に対してのみ適用) */
function inlineMd(text) {
  let s = escapeHtml(text);
  // [label](url) → <a> (url は http/https/相対のみ許可)
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+|\/[^\s)]*|[^\s):]+)\)/g, '<a href="$2">$1</a>');
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  return s;
}

/**
 * visual (schema §visual: {kind, spec, caption, alt, rationale}) → HTML 片。
 * caption/alt は visual 直下から読む (spec 内ではない)。例外は fallback へ (render は落ちない)。
 * @returns {{ html: string, usesMermaid: boolean }}
 */
function renderVisual(visual) {
  if (!visual || !visual.kind || visual.kind === 'none') return { html: '', usesMermaid: false };
  const spec = visual.spec || {};
  const caption = visual.caption || '';
  const alt = visual.alt || '';
  try {
    if (visual.kind === 'mermaid') {
      const def = spec.definition || '';
      return { html: renderMermaidFragment(def, { caption, ariaLabel: alt || spec.diagramType }), usesMermaid: true };
    }
    if (visual.kind === 'codex-image') {
      return { html: renderCodexImage(spec, { caption, alt }), usesMermaid: false };
    }
    if (visual.kind === 'svg') {
      return { html: renderSvgVisual(spec, { caption, alt }), usesMermaid: false };
    }
  } catch (e) {
    return { html: fallbackVisual(`ビジュアル生成に失敗: ${e.message}`, caption), usesMermaid: false };
  }
  return { html: '', usesMermaid: false };
}

/** diagramNode[] → svg-builder が食う item 配列に射影 (label/subtext を保持) */
function nodesToItems(nodes) {
  const arr = Array.isArray(nodes) ? nodes : [];
  return arr.map((n, i) => {
    if (n == null) return { label: '', number: i + 1 };
    if (typeof n === 'string') return { label: n, number: i + 1 };
    return { label: n.label || '', desc: n.subtext || '', number: i + 1, date: n.subtext || '' };
  });
}

/** svgSpec {variant, nodes[], groups?} → svg-builder への dispatch (決定論) */
function renderSvgVisual(spec, meta) {
  const variant = spec.variant || 'flow';
  const opts = {};
  const items = nodesToItems(spec.nodes);
  let inner = '';

  if (variant === 'mindmap' && typeof svg.buildMindmap === 'function') {
    const center = items.length ? items[0].label : '';
    inner = svg.buildMindmap(center, items.slice(1).map((it) => it.label), opts);
  } else if (variant === 'network' && typeof svg.buildMindmap === 'function') {
    const center = items.length ? items[0].label : '';
    inner = svg.buildMindmap(center, items.slice(1).map((it) => it.label), opts);
  } else if (variant === 'comparison' && typeof svg.buildVs === 'function') {
    // nodes を左右へ決定論分割 (group 指定があれば group で二分、無ければ半々)
    const { left, right } = splitForComparison(spec.nodes || []);
    inner = svg.buildVs(nodesToItems(left).map((i) => i.label), nodesToItems(right).map((i) => i.label), opts);
  } else if (VARIANT_SINGLE_ARG[variant] && typeof svg[VARIANT_SINGLE_ARG[variant]] === 'function') {
    inner = svg[VARIANT_SINGLE_ARG[variant]](items, opts);
  } else {
    return fallbackVisual(`未対応の svg variant: ${variant}`, meta.caption);
  }
  const caption = meta.caption ? `\n  <figcaption>${escapeHtml(meta.caption)}</figcaption>` : '';
  const label = meta.alt ? ` aria-label="${escapeHtml(meta.alt)}"` : '';
  return `<figure class="report-visual report-visual--svg" role="img"${label}>\n  ${inner}${caption}\n</figure>`;
}

/** comparison 用に nodes を左右へ決定論分割 (group 優先、無ければ半々) */
function splitForComparison(nodes) {
  const groups = [...new Set(nodes.map((n) => (n && n.group) || '').filter(Boolean))];
  if (groups.length >= 2) {
    return {
      left: nodes.filter((n) => n && n.group === groups[0]),
      right: nodes.filter((n) => n && n.group !== groups[0]),
    };
  }
  const mid = Math.ceil(nodes.length / 2);
  return { left: nodes.slice(0, mid), right: nodes.slice(mid) };
}

/**
 * aiVisualSpec → <img> (asset/slug) or composite プレースホルダ。
 * asset (WebP/PNG) 明示 or slug から images/<slug>.png を導出し <img> 参照埋込。
 * 双方無い場合 (backgroundSource=none 等) は overlayText を並べた決定論プレースホルダ。
 */
function renderCodexImage(spec, meta) {
  const alt = escapeHtml(meta.alt || spec.alt || (Array.isArray(spec.overlayText) ? spec.overlayText[0] : '') || '図');
  const caption = meta.caption ? `\n  <figcaption>${escapeHtml(meta.caption)}</figcaption>` : '';
  const src = spec.asset || (spec.slug ? `images/${spec.slug}.png` : '');
  if (src) {
    return `<figure class="report-visual report-visual--image">\n  <img src="${escapeHtml(src)}" alt="${alt}">${caption}\n</figure>`;
  }
  const overlays = Array.isArray(spec.overlayText) ? spec.overlayText : [];
  const overlayHtml = overlays.map((t) => `    <li>${escapeHtml(t)}</li>`).join('\n');
  return `<figure class="report-visual report-visual--image" role="img" aria-label="${alt}">
  <svg viewBox="0 0 960 320" role="img" xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="960" height="320" fill="rgba(46,168,143,0.08)" rx="10"/><text x="480" y="60" text-anchor="middle" fill="var(--accent-aqua-vivid, #2EA88F)" font-size="20" font-weight="700" font-family="'Noto Sans JP', sans-serif">Codex Image (${escapeHtml(spec.pattern || 'image')})</text><text x="480" y="170" text-anchor="middle" fill="var(--fg-dim, #727169)" font-size="16" font-family="'Noto Sans JP', sans-serif">${alt}</text></svg>
  <ul class="composite-overlay">
${overlayHtml}
  </ul>${caption}
</figure>`;
}

/** 決定論フォールバック (render を落とさない) */
function fallbackVisual(msg, caption) {
  const cap = caption ? `\n  <figcaption>${escapeHtml(caption)}</figcaption>` : '';
  return `<figure class="report-visual report-visual--fallback">\n  <svg viewBox="0 0 960 200" role="img" aria-label="placeholder" xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="960" height="200" fill="rgba(59,125,216,0.06)" rx="8"/><text x="480" y="105" text-anchor="middle" fill="var(--fg-dim, #727169)" font-size="18" font-family="'Noto Sans JP', sans-serif">${escapeHtml(msg)}</text></svg>${cap}\n</figure>`;
}

/** callouts[] → HTML (任意) */
function renderCallouts(callouts) {
  if (!Array.isArray(callouts) || callouts.length === 0) return '';
  return callouts
    .map((c) => {
      const kind = (c && c.kind) || 'note';
      return `  <aside class="report-callout report-callout--${escapeHtml(kind)}">${inlineMd((c && c.text) || '')}</aside>`;
    })
    .join('\n');
}

/**
 * report-structure オブジェクト → report.html 全文 (決定論)。
 * section は配列順でレンダ (readingOrder は視線方向ヒントであり並び替えキーではない)。
 * @param {object} structure report-structure.schema.json 準拠オブジェクト
 * @returns {string} 完結した HTML 文書
 */
export function renderReport(structure) {
  const meta = (structure && structure.meta) || {};
  const reportType = meta.reportType || 'internal-analysis';
  const accent = REPORT_TYPE_ACCENT[reportType] || 'accent-blue-vivid';
  const title = escapeHtml(meta.title || 'レポート');
  const sections = Array.isArray(structure && structure.sections) ? structure.sections : [];

  let usesMermaid = false;
  const sectionHtml = sections
    .map((sec) => {
      const heading = escapeHtml((sec && sec.heading) || '');
      const secAccent = REPORT_TYPE_ACCENT[(sec && sec.reportType) || reportType] || accent;
      const vis = renderVisual(sec && sec.visual);
      if (vis.usesMermaid) usesMermaid = true;
      const paras = renderParagraphs(sec && sec.paragraphs);
      const callouts = renderCallouts(sec && sec.callouts);
      const idAttr = sec && sec.id ? ` id="${escapeHtml(sec.id)}"` : '';
      const roleAttr = sec && sec.role ? ` data-role="${escapeHtml(sec.role)}"` : '';
      const orderAttr = sec && sec.readingOrder ? ` data-reading-order="${escapeHtml(sec.readingOrder)}"` : '';
      return `<section class="report-section"${idAttr}${roleAttr}${orderAttr} style="--section-accent: var(--${secAccent});">
  <h2>${heading}</h2>
${paras}
${callouts ? callouts + '\n' : ''}  ${vis.html}
</section>`;
    })
    .join('\n');

  // meta 行 (schema 準拠: audience/keyMessage/author/length。date/reader は無い)
  const metaBits = [];
  metaBits.push(`<span class="report-type-badge">${escapeHtml(reportTypeLabel(reportType))}</span>`);
  if (meta.audience) metaBits.push(`<span>読者: ${escapeHtml(meta.audience)}</span>`);
  if (meta.author) metaBits.push(`<span>著者: ${escapeHtml(meta.author)}</span>`);
  if (meta.length) metaBits.push(`<span>分量: ${escapeHtml(lengthLabel(meta.length))}</span>`);
  if (meta.createdAt) metaBits.push(`<span>作成: ${escapeHtml(meta.createdAt)}</span>`);

  const subtitle = meta.subtitle ? `\n    <p class="report-subtitle">${escapeHtml(meta.subtitle)}</p>` : '';
  const keyMessage = meta.keyMessage ? `\n    <p class="report-keymessage">${escapeHtml(meta.keyMessage)}</p>` : '';

  const head = [
    '<!DOCTYPE html>',
    '<html lang="' + escapeHtml(meta.language || 'ja') + '">',
    '<head>',
    '<meta charset="UTF-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
    '<meta name="generator" content="slide-report-generator/render-report">',
    `<meta name="report-type" content="${escapeHtml(reportType)}">`,
    `<meta name="theme-name" content="${escapeHtml(themeName(structure && structure.theme))}">`,
    `<title>${title}</title>`,
    '<link rel="preconnect" href="https://fonts.googleapis.com">',
    '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;800&display=swap" rel="stylesheet">',
    `<style>\n${buildReportCss(SPEC)}\n</style>`,
    usesMermaid ? mermaidInitScript() : '',
    '</head>',
  ]
    .filter(Boolean)
    .join('\n');

  return `${head}
<body style="--report-accent: var(--${accent});">
<main class="report">
  <header class="report-header">
    <h1 class="report-title">${title}</h1>${subtitle}${keyMessage}
    <div class="report-meta">
      ${metaBits.join('\n      ')}
    </div>
  </header>
${sectionHtml}
  <footer class="report-footer">slide-report-generator · report mode · theme: ${escapeHtml(themeName(structure && structure.theme))}</footer>
</main>
</body>
</html>
`;
}

/** reportType enum → 日本語ラベル (§D) */
function reportTypeLabel(rt) {
  return (
    {
      'internal-analysis': '社内報告分析',
      'client-proposal': '顧客提案',
      'tech-doc': '技術ドキュメント',
      learning: '学習解説',
    }[rt] || rt
  );
}

/** length enum → 日本語ラベル */
function lengthLabel(len) {
  return { brief: '短報', standard: '標準', deep: '精読' }[len] || len;
}

// ---- CLI ----
function isMain() {
  return process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
}

if (isMain()) {
  const [inPath, outPath] = process.argv.slice(2);
  if (!inPath || !outPath) {
    console.error('usage: node render-report.js <report-structure.json> <out.html>');
    process.exit(2);
  }
  try {
    const structure = JSON.parse(readFileSync(inPath, 'utf-8'));
    const html = renderReport(structure);
    writeFileSync(outPath, html, 'utf-8');
    console.log(`render-report: wrote ${outPath} (${Buffer.byteLength(html)} bytes, ${(structure.sections || []).length} sections)`);
  } catch (e) {
    console.error(`render-report error: ${e.message}`);
    process.exit(1);
  }
}
