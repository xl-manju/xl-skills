#!/usr/bin/env node
// validate_prompt.js — hearing JSON / trace JSON / generated prompt の最小検証 (Node 標準のみ)
"use strict";
const fs = require("fs");
const path = require("path");

function parseArgs(argv) {
  const args = { input: null, phase: null, schema: null };
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

function defaultSchemaFor(phase) {
  const root = path.join(__dirname, "..");
  if (phase === "hearing") {
    return path.join(root, "skills", "run-prompt-elicit", "schemas", "hearing-result.schema.json");
  }
  if (phase === "sheet") {
    return path.join(root, "skills", "run-prompt-creator-7layer", "schemas", "hearing-result.schema.json");
  }
  if (phase === "trace") {
    return path.join(root, "skills", "run-prompt-create", "schemas", "build-trace.schema.json");
  }
  return null;
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

function detectPhase(input, explicitPhase) {
  if (explicitPhase) return explicitPhase;
  const ext = path.extname(input).toLowerCase();
  if (ext === ".json") return "trace";
  return "prompt";
}

function validateJsonBySchema(input, phase, schemaPath) {
  const data = loadJson(input);
  const sch = loadJson(schemaPath);
  let target = data;
  let required = sch.required || [];

  if (phase === "hearing") {
    target = data.phase1 || data;
    required = (sch.properties && sch.properties.phase1 && sch.properties.phase1.required)
      || sch.required || ["session_id", "timestamp", "answers"];
  }

  const missing = checkRequired(target, required, phase);
  if (missing.length > 0) {
    console.error("FAIL missing fields:");
    for (const m of missing) console.error(`  - ${m}`);
    process.exit(1);
  }
  console.log(`OK phase=${phase} schema=${schemaPath} required=${required.length} fields validated`);
}

function validatePromptText(input) {
  const text = fs.readFileSync(input, "utf8");
  const problems = [];
  for (let n = 1; n <= 7; n++) {
    const re = new RegExp(`#+\\s*Layer\\s*${n}\\s*[:：]`);
    if (!re.test(text)) problems.push(`Layer ${n}: marker missing`);
  }
  if (/\{\{[^}]+\}\}/.test(text)) problems.push("unexpanded placeholder remains");
  if (/TODO(?!\(human\))/i.test(text)) problems.push("TODO remains without TODO(human)");
  if (problems.length > 0) {
    console.error("FAIL prompt validation:");
    for (const p of problems) console.error(`  - ${p}`);
    process.exit(1);
  }
  console.log(`OK phase=prompt layers=7 file=${input}`);
}

function main() {
  const { input, phase, schema } = parseArgs(process.argv);
  if (!input) {
    console.error("usage: validate_prompt.js --input <file> [--phase hearing|sheet|trace|prompt] [--schema <path>]");
    process.exit(2);
  }
  const resolvedPhase = detectPhase(input, phase);
  if (resolvedPhase === "prompt") {
    validatePromptText(input);
    return;
  }
  const schemaPath = schema || defaultSchemaFor(resolvedPhase);
  if (!schemaPath || !fs.existsSync(schemaPath)) {
    console.error(`schema not found for phase=${resolvedPhase}: ${schemaPath || "(none)"}`);
    process.exit(2);
  }
  validateJsonBySchema(input, resolvedPhase, schemaPath);
}

main();
