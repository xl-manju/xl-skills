#!/usr/bin/env node
// prompt-creator usage logger
// Usage: node scripts/log_usage.js --result success|failure [--phase "Phase N"] [--format yaml|markdown|json|xml] [--error "ErrorMessage"]

const fs = require("fs");
const path = require("path");

const args = process.argv.slice(2);
const getArg = (name) => {
  const idx = args.indexOf(`--${name}`);
  return idx !== -1 && args[idx + 1] ? args[idx + 1] : null;
};

const result = getArg("result") || "unknown";
const phase = getArg("phase") || "unknown";
const format = getArg("format") || "not_specified";
const error = getArg("error") || "";

const logDir = path.resolve(__dirname, "..");
const logFile = path.join(logDir, "LOGS.md");

const timestamp = new Date().toISOString();
const entry = `| ${timestamp} | ${result} | ${phase} | ${format} | ${error} |`;

if (!fs.existsSync(logFile)) {
  const header = `# Prompt Creator Usage Logs

| Timestamp | Result | Phase | Format | Error |
|-----------|--------|-------|--------|-------|
`;
  fs.writeFileSync(logFile, header + entry + "\n", "utf-8");
} else {
  fs.appendFileSync(logFile, entry + "\n", "utf-8");
}

console.log(`[prompt-creator] Logged: ${result} at ${phase} (format: ${format})`);
