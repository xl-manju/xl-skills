#!/usr/bin/env node
// merge_layers.js - 個別生成されたLayer(1-7)ファイルを1つのプロンプトに合算
// Usage: node scripts/merge_layers.js --dir <layers-dir> --output <output-path> [--format yaml|markdown|json|xml]
// Exit: 0=成功, 1=エラー, 2=引数エラー, 3=ファイル/ディレクトリ不在, 4=Layer不足
//
// 目的: LLMが各Layerを個別に高精度で生成した後、Scriptで決定論的にマージ
// 方式: Layer 1-7のファイルを順番に結合、セパレータ挿入、重複除去

const fs = require("fs");
const path = require("path");

function getArg(name) {
  const idx = process.argv.indexOf(`--${name}`);
  return idx !== -1 && process.argv[idx + 1] ? process.argv[idx + 1] : null;
}

// Layer ファイル名パターン
const LAYER_FILES = [
  { layer: 1, patterns: ["layer1", "layer_1", "基本定義"], label: "Layer 1: 基本定義" },
  { layer: 2, patterns: ["layer2", "layer_2", "ドメイン定義"], label: "Layer 2: ドメイン定義" },
  { layer: 3, patterns: ["layer3", "layer_3", "インフラストラクチャ"], label: "Layer 3: インフラストラクチャ" },
  { layer: 4, patterns: ["layer4", "layer_4", "共通ポリシー"], label: "Layer 4: 共通ポリシー" },
  { layer: 5, patterns: ["layer5", "layer_5", "エージェント定義"], label: "Layer 5: エージェント定義" },
  { layer: 6, patterns: ["layer6", "layer_6", "オーケストレーション"], label: "Layer 6: オーケストレーション" },
  { layer: 7, patterns: ["layer7", "layer_7", "ユーザーインタラクション"], label: "Layer 7: ユーザーインタラクション" },
];

// ディレクトリからLayerファイルを探索
function findLayerFiles(dir) {
  const files = fs.readdirSync(dir);
  const found = {};

  for (const layerDef of LAYER_FILES) {
    // 完全一致ファイル名を優先、次にパターンマッチ
    let matchedFile = null;

    // パターン1: layer{N}.yaml, layer{N}.md など
    for (const f of files) {
      const lower = f.toLowerCase();
      for (const pat of layerDef.patterns) {
        if (lower.includes(pat.toLowerCase())) {
          matchedFile = f;
          break;
        }
      }
      if (matchedFile) break;
    }

    if (matchedFile) {
      found[layerDef.layer] = {
        file: path.join(dir, matchedFile),
        label: layerDef.label,
      };
    }
  }

  return found;
}

// YAML用セパレータ
function yamlSeparator(label) {
  return `\n# ${"─".repeat(77)}\n# ${label}\n# ${"─".repeat(77)}\n`;
}

// Markdown用セパレータ
function mdSeparator(label) {
  return `\n---\n\n## ${label}\n\n`;
}

// マージ実行
function mergeLayers(layerFiles, format) {
  const parts = [];
  const missingLayers = [];

  for (let i = 1; i <= 7; i++) {
    if (!layerFiles[i]) {
      missingLayers.push(LAYER_FILES[i - 1].label);
      continue;
    }

    const content = fs.readFileSync(layerFiles[i].file, "utf-8").trim();

    // セパレータ挿入
    switch (format) {
      case "yaml":
        parts.push(yamlSeparator(layerFiles[i].label));
        break;
      case "markdown":
        parts.push(mdSeparator(layerFiles[i].label));
        break;
      case "json":
        // JSONは最終的にオブジェクトとしてマージ
        break;
      case "xml":
        parts.push(`\n  <!-- ${layerFiles[i].label} -->\n`);
        break;
    }

    parts.push(content);
  }

  if (format === "json") {
    // JSON: 各Layerのオブジェクトをマージ
    const merged = {};
    for (let i = 1; i <= 7; i++) {
      if (!layerFiles[i]) continue;
      try {
        const content = fs.readFileSync(layerFiles[i].file, "utf-8");
        const parsed = JSON.parse(content);
        Object.assign(merged, parsed);
      } catch (e) {
        // JSONパースエラーの場合はテキストとして追加
        merged[`layer${i}_raw`] = fs.readFileSync(layerFiles[i].file, "utf-8");
      }
    }
    return { content: JSON.stringify(merged, null, 2), missingLayers };
  }

  return { content: parts.join("\n"), missingLayers };
}

function main() {
  if (process.argv.length < 3 || process.argv[2] === "-h" || process.argv[2] === "--help") {
    console.log("Usage: node merge_layers.js --dir <layers-dir> --output <output-path> [--format yaml]");
    console.log("  Merges individually generated Layer 1-7 files into a single prompt.");
    console.log("  Layer files are detected by name pattern (layer1.yaml, layer_2.md, etc.).");
    console.log("  Exit codes: 0=OK, 1=error, 2=args error, 3=dir not found, 4=layers missing");
    process.exit(process.argv[2] === "-h" || process.argv[2] === "--help" ? 0 : 2);
  }

  const dir = getArg("dir");
  const output = getArg("output");
  const format = getArg("format") || "yaml";

  if (!dir) {
    console.error("[ERROR] --dir required");
    process.exit(2);
  }

  const resolvedDir = path.resolve(dir);
  if (!fs.existsSync(resolvedDir)) {
    console.error(`[ERROR] Directory not found: ${resolvedDir}`);
    process.exit(3);
  }

  const layerFiles = findLayerFiles(resolvedDir);
  const foundCount = Object.keys(layerFiles).length;

  console.log(`\n=== Layer マージ ===\n`);
  console.log(`検出Layer: ${foundCount}/7`);

  // 各Layerの検出状態
  for (let i = 1; i <= 7; i++) {
    if (layerFiles[i]) {
      console.log(`  [OK] ${layerFiles[i].label} → ${path.basename(layerFiles[i].file)}`);
    } else {
      console.log(`  [未検出] ${LAYER_FILES[i - 1].label}`);
    }
  }
  console.log();

  if (foundCount === 0) {
    console.error("[ERROR] No layer files found in directory");
    process.exit(4);
  }

  const { content, missingLayers } = mergeLayers(layerFiles, format);

  if (output) {
    const resolvedOutput = path.resolve(output);
    fs.writeFileSync(resolvedOutput, content, "utf-8");
    console.log(`[OK] マージ完了: ${resolvedOutput}`);
  } else {
    process.stdout.write(content);
  }

  if (missingLayers.length > 0) {
    console.log(`\n[WARNING] 未検出Layer（${missingLayers.length}件）:`);
    missingLayers.forEach(l => console.log(`  - ${l}`));
    process.exit(4);
  }

  // JSON統計出力
  console.log("\n--- JSON結果 ---");
  console.log(JSON.stringify({
    foundLayers: foundCount,
    missingLayers,
    format,
    output: output || "stdout",
  }, null, 2));

  process.exit(0);
}

main();
