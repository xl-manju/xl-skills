#!/usr/bin/env node
// convert_format.js — 7層正規形YAML → md/json/xml/yaml 変換 (Node 標準のみ)
// 設計方針: 日本語7層・ゴールシーク構造を「構造保存」で変換する。
//   YAML 本文（key: value / リスト / - [ ] チェックリスト / 達成ゴール 等）を捨てず保持し、
//   Layer 見出しのみ提示形式に合わせて書き換える。これにより可逆で、ゴールシーク要素を落とさない。
// マーカーは scaffold_prompt.js / merge_layers.js が出力する「# Layer N: <title>」に一致させる。
"use strict";
const fs = require("fs");
const path = require("path");

function parseArgs(argv) {
  const args = { input: null, format: "md", output: null };
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "--input") args.input = argv[++i];
    else if (argv[i] === "--format") args.format = argv[++i];
    else if (argv[i] === "--output") args.output = argv[++i];
  }
  return args;
}

// 「# Layer N: <title>」マーカーで本文を 7 層に分割し、本文を verbatim 保持する。
function parseLayers(text) {
  const layers = [];
  for (let n = 1; n <= 7; n++) {
    const re = new RegExp(
      `#+\\s*Layer\\s*${n}\\s*[:：]\\s*([^\\n]*)\\n([\\s\\S]*?)(?=#+\\s*Layer\\s*${n + 1}\\s*[:：]|$)`
    );
    const m = text.match(re);
    if (m) {
      layers.push({ n, title: m[1].trim(), body: m[2].replace(/\s+$/g, "") });
    }
  }
  return layers;
}

function toMd(layers) {
  const out = ["# 7層構造プロンプト", ""];
  for (const { n, title, body } of layers) {
    out.push(`## Layer ${n}: ${title}`, "");
    if (body.trim()) out.push(body.trimEnd(), "");
  }
  return out.join("\n");
}

function toJson(layers) {
  return JSON.stringify(
    layers.map(({ n, title, body }) => ({ layer: n, title, body: body.trim() })),
    null,
    2
  );
}

function toXml(layers) {
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<prompt>"];
  for (const { n, title, body } of layers) {
    parts.push(`  <layer n="${n}" title="${esc(title)}"><![CDATA[\n${body}\n]]></layer>`);
  }
  parts.push("</prompt>");
  return parts.join("\n");
}

function main() {
  const { input, format, output } = parseArgs(process.argv);
  if (!input || !output) {
    console.error("usage: convert_format.js --input <yaml> --format md|json|xml|yaml --output <file>");
    process.exit(2);
  }
  const text = fs.readFileSync(input, "utf8");
  let out;
  if (format === "yaml") {
    out = text;
  } else {
    const layers = parseLayers(text);
    if (layers.length === 0) {
      console.error("[ERROR] Layer マーカー (# Layer N:) が見つかりません。正規形YAMLか確認してください。");
      process.exit(1);
    }
    if (format === "md") out = toMd(layers);
    else if (format === "json") out = toJson(layers);
    else if (format === "xml") out = toXml(layers);
    else { console.error(`unknown format: ${format}`); process.exit(2); }
  }
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, out);
  console.log(`converted → ${output} (${format})`);
}

main();
