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
  const layers = ["L1","L2","L3","L4","L5","L6","L7"];
  const parts = [];
  for (const L of layers) {
    const p = path.join(layersDir, `${L}.yaml`);
    if (!fs.existsSync(p)) {
      console.error(`missing layer: ${p}`);
      process.exit(1);
    }
    parts.push(`# === ${L} ===`);
    parts.push(fs.readFileSync(p, "utf8").trimEnd());
    parts.push("");
  }
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, parts.join("\n") + "\n");
  console.log(`merged ${layers.length} layers → ${output}`);
}

main();
