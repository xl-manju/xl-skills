#!/usr/bin/env node
// validate_prompt.js — trace JSON / merged prompt の schema 検証 (Node 標準のみ)
// hearing-result.schema.json の required フィールドを最小実装でチェック。
"use strict";
const fs = require("fs");
const path = require("path");

function parseArgs(argv) {
  const args = { input: null, phase: "hearing", schema: null };
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "--input") args.input = argv[++i];
    else if (argv[i] === "--phase") args.phase = argv[++i];
    else if (argv[i] === "--schema") args.schema = argv[++i];
  }
  return args;
}

function loadJson(p) {
  return JSON.parse(fs.readFileSync(p, "utf8"));
}

function checkRequired(obj, required, prefix) {
  const missing = [];
  for (const k of required) {
    if (obj[k] === undefined || obj[k] === null || obj[k] === "") {
      missing.push(`${prefix}.${k}`);
    }
  }
  return missing;
}

function main() {
  const { input, phase, schema } = parseArgs(process.argv);
  if (!input) {
    console.error("usage: validate_prompt.js --input <json> [--phase hearing|merged] [--schema <path>]");
    process.exit(2);
  }
  const data = loadJson(input);
  const schemaPath = schema || path.join(__dirname, "..", "schemas", "hearing-result.schema.json");
  const sch = loadJson(schemaPath);

  let target;
  let required;
  if (phase === "hearing") {
    target = data.phase1 || data;
    required = (sch.properties && sch.properties.phase1 && sch.properties.phase1.required)
      || sch.required || ["role","context","constraints","output_format"];
  } else {
    target = data;
    required = sch.required || [];
  }

  const missing = checkRequired(target, required, `phase1`);
  if (missing.length > 0) {
    console.error("FAIL missing fields:");
    for (const m of missing) console.error(`  - ${m}`);
    process.exit(1);
  }
  console.log(`OK phase=${phase} required=${required.length} fields validated`);
}

main();
