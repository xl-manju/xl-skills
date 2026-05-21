#!/usr/bin/env node
// validate_prompt.js - 7層構造プロンプトの完全性検証
// Usage: node scripts/validate_prompt.js <prompt-file> [--format yaml|markdown|json|xml]
// Exit: 0=OK, 4=検証失敗, 2=引数エラー, 3=ファイル不在

const fs = require("fs");
const path = require("path");

function getArg(name) {
  const idx = process.argv.indexOf(`--${name}`);
  return idx !== -1 && process.argv[idx + 1] ? process.argv[idx + 1] : null;
}

// YAML/Markdownでの7層検出パターン
const LAYER_PATTERNS = {
  yaml: [
    { layer: 1, pattern: /layer_?1|基本定義|最上位目的/, label: "Layer 1: 基本定義" },
    { layer: 2, pattern: /layer_?2|ドメイン定義|用語集/, label: "Layer 2: ドメイン定義" },
    { layer: 3, pattern: /layer_?3|インフラストラクチャ|ツール定義/, label: "Layer 3: インフラストラクチャ" },
    { layer: 4, pattern: /layer_?4|共通ポリシー|セキュリティ/, label: "Layer 4: 共通ポリシー" },
    { layer: 5, pattern: /layer_?5|エージェント定義|エージェント/, label: "Layer 5: エージェント定義" },
    { layer: 6, pattern: /layer_?6|オーケストレーション|実行フロー/, label: "Layer 6: オーケストレーション" },
    { layer: 7, pattern: /layer_?7|ユーザーインタラクション|初回メッセージ/, label: "Layer 7: ユーザーインタラクション" },
  ],
  markdown: [
    { layer: 1, pattern: /#+\s*(Layer\s*1|基本定義|最上位目的)/i, label: "Layer 1: 基本定義" },
    { layer: 2, pattern: /#+\s*(Layer\s*2|ドメイン定義|用語集)/i, label: "Layer 2: ドメイン定義" },
    { layer: 3, pattern: /#+\s*(Layer\s*3|インフラストラクチャ|ツール定義)/i, label: "Layer 3: インフラストラクチャ" },
    { layer: 4, pattern: /#+\s*(Layer\s*4|共通ポリシー|セキュリティ)/i, label: "Layer 4: 共通ポリシー" },
    { layer: 5, pattern: /#+\s*(Layer\s*5|エージェント定義)/i, label: "Layer 5: エージェント定義" },
    { layer: 6, pattern: /#+\s*(Layer\s*6|オーケストレーション|実行フロー)/i, label: "Layer 6: オーケストレーション" },
    { layer: 7, pattern: /#+\s*(Layer\s*7|ユーザーインタラクション|初回メッセージ)/i, label: "Layer 7: ユーザーインタラクション" },
  ],
  json: [
    { layer: 1, pattern: /"layer_?1"|"基本定義"/, label: "Layer 1: 基本定義" },
    { layer: 2, pattern: /"layer_?2"|"ドメイン定義"/, label: "Layer 2: ドメイン定義" },
    { layer: 3, pattern: /"layer_?3"|"インフラストラクチャ"/, label: "Layer 3: インフラストラクチャ" },
    { layer: 4, pattern: /"layer_?4"|"共通ポリシー"/, label: "Layer 4: 共通ポリシー" },
    { layer: 5, pattern: /"layer_?5"|"エージェント定義"/, label: "Layer 5: エージェント定義" },
    { layer: 6, pattern: /"layer_?6"|"オーケストレーション"/, label: "Layer 6: オーケストレーション" },
    { layer: 7, pattern: /"layer_?7"|"ユーザーインタラクション"/, label: "Layer 7: ユーザーインタラクション" },
  ],
  xml: [
    { layer: 1, pattern: /<layer1|<基本定義/, label: "Layer 1: 基本定義" },
    { layer: 2, pattern: /<layer2|<ドメイン定義/, label: "Layer 2: ドメイン定義" },
    { layer: 3, pattern: /<layer3|<インフラストラクチャ/, label: "Layer 3: インフラストラクチャ" },
    { layer: 4, pattern: /<layer4|<共通ポリシー/, label: "Layer 4: 共通ポリシー" },
    { layer: 5, pattern: /<layer5|<エージェント定義/, label: "Layer 5: エージェント定義" },
    { layer: 6, pattern: /<layer6|<オーケストレーション/, label: "Layer 6: オーケストレーション" },
    { layer: 7, pattern: /<layer7|<ユーザーインタラクション/, label: "Layer 7: ユーザーインタラクション" },
  ],
};

// 変数テンプレート検証
function checkVariables(content) {
  const variables = content.match(/\{\{[^}]+\}\}/g) || [];
  const emptyVars = variables.filter((v) => v === "{{}}");
  return {
    total: variables.length,
    unique: [...new Set(variables)].length,
    empty: emptyVars.length,
    list: [...new Set(variables)],
  };
}

// コメント・セパレータ検証
function checkFormatting(content) {
  const issues = [];
  if (/^====+$/m.test(content)) {
    issues.push("セパレータ '====' が検出されました（'#' コメントのみ使用してください）");
  }
  if (/^----+$/m.test(content)) {
    issues.push("セパレータ '----' が検出されました（'#' コメントのみ使用してください）");
  }
  return issues;
}

function detectFormat(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  const map = { ".yaml": "yaml", ".yml": "yaml", ".md": "markdown", ".json": "json", ".xml": "xml" };
  return map[ext] || null;
}

function validate(content, format) {
  const patterns = LAYER_PATTERNS[format];
  if (!patterns) {
    return { error: `未対応フォーマット: ${format}` };
  }

  const results = {
    format,
    layers: { found: [], missing: [] },
    variables: checkVariables(content),
    formatting: checkFormatting(content),
  };

  for (const p of patterns) {
    if (p.pattern.test(content)) {
      results.layers.found.push(p.label);
    } else {
      results.layers.missing.push(p.label);
    }
  }

  return results;
}

function main() {
  if (process.argv.length < 3 || process.argv[2] === "-h" || process.argv[2] === "--help") {
    console.log("Usage: node validate_prompt.js <prompt-file> [--format yaml|markdown|json|xml]");
    console.log("  Validates 7-layer structured prompt completeness.");
    console.log("  Format is auto-detected from extension if not specified.");
    console.log("  Exit codes: 0=OK, 2=args error, 3=file not found, 4=validation failed");
    process.exit(process.argv[2] === "-h" || process.argv[2] === "--help" ? 0 : 2);
  }

  const filePath = path.resolve(process.argv[2]);
  if (!fs.existsSync(filePath)) {
    console.error(`[ERROR] File not found: ${filePath}`);
    process.exit(3);
  }

  const content = fs.readFileSync(filePath, "utf-8");
  const format = getArg("format") || detectFormat(filePath);

  if (!format) {
    console.error("[ERROR] Format not detected. Use --format yaml|markdown|json|xml");
    process.exit(2);
  }

  const results = validate(content, format);

  if (results.error) {
    console.error(`[ERROR] ${results.error}`);
    process.exit(1);
  }

  // 出力
  console.log("=== 7層構造プロンプト 検証結果 ===\n");
  console.log(`フォーマット: ${results.format}`);
  console.log(`Layer検出: ${results.layers.found.length}/7`);
  console.log(`変数: ${results.variables.unique}種類（${results.variables.total}箇所）`);
  console.log(`フォーマット問題: ${results.formatting.length}\n`);

  if (results.layers.missing.length > 0) {
    console.log("--- 未検出Layer ---");
    results.layers.missing.forEach((l) => console.log(`  [未検出] ${l}`));
    console.log();
  }

  if (results.layers.found.length > 0) {
    console.log("--- 検出済みLayer ---");
    results.layers.found.forEach((l) => console.log(`  [OK] ${l}`));
    console.log();
  }

  if (results.variables.empty > 0) {
    console.log(`--- 警告: 空の変数テンプレート {{}} が${results.variables.empty}箇所あります ---\n`);
  }

  if (results.formatting.length > 0) {
    console.log("--- フォーマット問題 ---");
    results.formatting.forEach((f) => console.log(`  [NG] ${f}`));
    console.log();
  }

  // JSON出力
  console.log("--- JSON結果 ---");
  console.log(JSON.stringify(results, null, 2));

  // Layer不足またはフォーマット問題があれば失敗
  process.exit(results.layers.missing.length > 0 || results.formatting.length > 0 ? 4 : 0);
}

main();
