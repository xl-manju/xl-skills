#!/usr/bin/env node
// convert_format.js — YAML → md/json/xml 変換 (Node 標準のみ、簡易 YAML パーサ実装)
// 7 層 YAML は構造が単純 (Layer 見出し + key: value / list) なので簡易パーサで対応。
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

// 簡易 YAML パーサ: # === LN === でセクション分割、key: value と "- item" を抽出
function parseYaml(text) {
  const layers = {};
  const sectionRe = /#\s*===\s*(L[1-7])\s*===([\s\S]*?)(?=#\s*===|$)/g;
  let m;
  while ((m = sectionRe.exec(text)) !== null) {
    const [, name, body] = m;
    const obj = {};
    let currentKey = null;
    for (const rawLine of body.split("\n")) {
      const line = rawLine.replace(/\s+$/, "");
      if (!line.trim() || line.trim().startsWith("#")) continue;
      const kv = line.match(/^(\s*)([A-Za-z_][\w-]*)\s*:\s*(.*)$/);
      const li = line.match(/^\s*-\s+(.+)$/);
      if (kv) {
        currentKey = kv[2];
        const val = kv[3].trim();
        obj[currentKey] = val === "" ? [] : val;
      } else if (li && currentKey && Array.isArray(obj[currentKey])) {
        obj[currentKey].push(li[1].trim());
      } else if (li && currentKey && typeof obj[currentKey] === "string" && obj[currentKey] === "") {
        obj[currentKey] = [li[1].trim()];
      }
    }
    layers[name] = obj;
  }
  return layers;
}

function toMd(layers) {
  const names = { L1: "Role", L2: "Context", L3: "Principles", L4: "Workflow",
                  L5: "Constraints", L6: "Output", L7: "Evaluation" };
  const out = ["# 7-Layer Structured Prompt", ""];
  for (const L of ["L1","L2","L3","L4","L5","L6","L7"]) {
    out.push(`## ${L}: ${names[L]}`);
    const obj = layers[L] || {};
    for (const k of Object.keys(obj)) {
      const v = obj[k];
      if (Array.isArray(v)) {
        out.push(`- **${k}**:`);
        for (const it of v) out.push(`  - ${it}`);
      } else {
        out.push(`- **${k}**: ${v}`);
      }
    }
    out.push("");
  }
  return out.join("\n");
}

function toJson(layers) { return JSON.stringify(layers, null, 2); }

function toXml(layers) {
  const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  const parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<prompt>"];
  for (const L of ["L1","L2","L3","L4","L5","L6","L7"]) {
    parts.push(`  <layer name="${L}">`);
    const obj = layers[L] || {};
    for (const k of Object.keys(obj)) {
      const v = obj[k];
      if (Array.isArray(v)) {
        parts.push(`    <${k}>`);
        for (const it of v) parts.push(`      <item>${esc(it)}</item>`);
        parts.push(`    </${k}>`);
      } else {
        parts.push(`    <${k}>${esc(v)}</${k}>`);
      }
    }
    parts.push(`  </layer>`);
  }
  parts.push("</prompt>");
  return parts.join("\n");
}

function main() {
  const { input, format, output } = parseArgs(process.argv);
  if (!input || !output) {
    console.error("usage: convert_format.js --input <yaml> --format md|json|xml --output <file>");
    process.exit(2);
  }
  const text = fs.readFileSync(input, "utf8");
  const layers = parseYaml(text);
  let out;
  if (format === "md") out = toMd(layers);
  else if (format === "json") out = toJson(layers);
  else if (format === "xml") out = toXml(layers);
  else if (format === "yaml") out = text;
  else { console.error(`unknown format: ${format}`); process.exit(2); }
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, out);
  console.log(`converted → ${output} (${format})`);
}

main();
