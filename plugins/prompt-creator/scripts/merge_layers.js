#!/usr/bin/env node
// merge_layers.js — tmp/prompt-layers/L{1..7}.yaml を 1 本に合算
// Node 標準のみ (fs/path/手書き YAML 連結)。js-yaml 不使用。
"use strict";
const fs = require("fs");
const path = require("path");

function parseArgs(argv) {
  const args = { layers: null, output: null };
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "--layers") args.layers = argv[++i];
    else if (argv[i] === "--output") args.output = argv[++i];
  }
  return args;
}

function main() {
  const { layers: layersDir, output } = parseArgs(process.argv);
  if (!layersDir || !output) {
    console.error("usage: merge_layers.js --layers <dir> --output <file>");
    process.exit(2);
  }
  // 正準マーカー「# Layer N:」を採用 (verify_completeness.js / convert_format.js と一致)。
  // per-layer ファイルが自前の「# Layer N: title」見出しを持つ場合は重複付与を避ける。
  const layerTitles = {
    1: "基本定義層", 2: "ドメイン定義層", 3: "インフラストラクチャ定義層",
    4: "共通ポリシー層", 5: "エージェント定義層", 6: "オーケストレーション層",
    7: "ユーザーインタラクション層",
  };
  const parts = [];
  for (let n = 1; n <= 7; n++) {
    const p = path.join(layersDir, `L${n}.yaml`);
    if (!fs.existsSync(p)) {
      console.error(`missing layer: ${p}`);
      process.exit(1);
    }
    const body = fs.readFileSync(p, "utf8").trimEnd();
    const hasHeader = new RegExp(`#+\\s*Layer\\s*${n}\\s*[:：]`).test(body);
    if (!hasHeader) parts.push(`# Layer ${n}: ${layerTitles[n]}`);
    parts.push(body);
    parts.push("");
  }
  const layers = [1, 2, 3, 4, 5, 6, 7];
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, parts.join("\n") + "\n");
  console.log(`merged ${layers.length} layers → ${output}`);
}

main();
