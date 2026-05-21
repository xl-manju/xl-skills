#!/usr/bin/env node
// verify_completeness.js — merged prompt.yaml が 7 Layer 全てに最低 1 要素を持つか検証
"use strict";
const fs = require("fs");

function parseArgs(argv) {
  const args = { input: null };
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "--input") args.input = argv[++i];
  }
  return args;
}

function main() {
  const { input } = parseArgs(process.argv);
  if (!input) {
    console.error("usage: verify_completeness.js --input <prompt.yaml>");
    process.exit(2);
  }
  const text = fs.readFileSync(input, "utf8");
  const layers = ["L1","L2","L3","L4","L5","L6","L7"];
  const missing = [];
  for (const L of layers) {
    const re = new RegExp(`#\\s*===\\s*${L}\\s*===([\\s\\S]*?)(?=#\\s*===|$)`);
    const m = text.match(re);
    if (!m) { missing.push(`${L}: section missing`); continue; }
    const body = m[1].trim();
    const nonEmptyLines = body.split("\n").filter(l => {
      const s = l.trim();
      return s.length > 0 && !s.startsWith("#");
    });
    if (nonEmptyLines.length === 0) missing.push(`${L}: empty body`);
  }
  if (missing.length > 0) {
    console.error("FAIL incomplete:");
    for (const m of missing) console.error(`  - ${m}`);
    process.exit(1);
  }
  console.log(`OK 7 layers verified`);
}

main();
