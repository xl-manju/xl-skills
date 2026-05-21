#!/usr/bin/env node
// validate_sheet.js - Prompt作成シートの全フィールド充足度検証
// Usage: node scripts/validate_sheet.js <hearing-result.json>
// Exit: 0=全充足, 4=未充足あり, 2=引数エラー, 3=ファイル不在

const fs = require("fs");
const path = require("path");

// 必須フィールド定義
const REQUIRED_FIELDS = [
  { key: "prompt_name", label: "プロンプト名", priority: "必須" },
  { key: "target_user", label: "想定利用者", priority: "必須" },
  { key: "purpose", label: "目的", priority: "必須" },
  { key: "background", label: "背景", priority: "必須" },
  { key: "success_criteria", label: "完了条件", priority: "必須" },
  { key: "steps", label: "手順", priority: "必須", isArray: true, minLength: 3 },
  { key: "challenges", label: "課題", priority: "必須", isArray: true, minLength: 1 },
  { key: "required_info", label: "必要情報", priority: "推奨", isArray: true, minLength: 1 },
  { key: "constraints", label: "制約条件", priority: "推奨", isArray: true, minLength: 1 },
  { key: "prompt_issues", label: "プロンプト課題", priority: "推奨" },
  { key: "test_cases", label: "テストケース", priority: "オプション", isArray: true, minLength: 1 },
];

// ステップの出力フォーマット検証
function validateSteps(steps) {
  const issues = [];
  if (!Array.isArray(steps)) {
    issues.push({ field: "steps", message: "配列ではありません" });
    return issues;
  }
  steps.forEach((step, i) => {
    if (!step.description || step.description.trim() === "") {
      issues.push({ field: `steps[${i}].description`, message: `Step${i + 1}の説明が空` });
    }
    if (!step.output_format || step.output_format.trim() === "") {
      issues.push({ field: `steps[${i}].output_format`, message: `Step${i + 1}の出力フォーマットが未定義` });
    }
  });
  return issues;
}

function validate(data) {
  const results = { filled: [], missing: [], warnings: [], stepIssues: [] };

  for (const field of REQUIRED_FIELDS) {
    const value = data[field.key];

    if (value === undefined || value === null || value === "") {
      if (field.priority === "オプション") {
        results.warnings.push({ field: field.key, label: field.label, message: "未入力（オプション）" });
      } else {
        results.missing.push({ field: field.key, label: field.label, priority: field.priority });
      }
      continue;
    }

    if (field.isArray) {
      if (!Array.isArray(value) || value.length < field.minLength) {
        results.missing.push({
          field: field.key,
          label: field.label,
          priority: field.priority,
          message: `最低${field.minLength}件必要（現在: ${Array.isArray(value) ? value.length : 0}件）`,
        });
        continue;
      }
    }

    results.filled.push({ field: field.key, label: field.label });
  }

  // ステップ詳細検証
  if (data.steps && Array.isArray(data.steps)) {
    results.stepIssues = validateSteps(data.steps);
  }

  return results;
}

// メイン処理
function main() {
  if (process.argv.length < 3 || process.argv[2] === "-h" || process.argv[2] === "--help") {
    console.log("Usage: node validate_sheet.js <hearing-result.json>");
    console.log("  Validates Prompt作成シート field completeness.");
    console.log("  Exit codes: 0=OK, 2=args error, 3=file not found, 4=validation failed");
    process.exit(process.argv[2] === "-h" || process.argv[2] === "--help" ? 0 : 2);
  }

  const filePath = path.resolve(process.argv[2]);
  if (!fs.existsSync(filePath)) {
    console.error(`[ERROR] File not found: ${filePath}`);
    process.exit(3);
  }

  let data;
  try {
    data = JSON.parse(fs.readFileSync(filePath, "utf-8"));
  } catch (e) {
    console.error(`[ERROR] Invalid JSON: ${e.message}`);
    process.exit(1);
  }

  const results = validate(data);

  // 出力
  console.log("=== Prompt作成シート 検証結果 ===\n");
  console.log(`充足: ${results.filled.length}/${REQUIRED_FIELDS.length}`);
  console.log(`未充足: ${results.missing.length}`);
  console.log(`警告: ${results.warnings.length}`);
  console.log(`ステップ問題: ${results.stepIssues.length}\n`);

  if (results.missing.length > 0) {
    console.log("--- 未充足フィールド ---");
    results.missing.forEach((m) => {
      console.log(`  [${m.priority}] ${m.label} (${m.field})${m.message ? ": " + m.message : ""}`);
    });
    console.log();
  }

  if (results.warnings.length > 0) {
    console.log("--- 警告 ---");
    results.warnings.forEach((w) => {
      console.log(`  [オプション] ${w.label} (${w.field}): ${w.message}`);
    });
    console.log();
  }

  if (results.stepIssues.length > 0) {
    console.log("--- ステップ詳細問題 ---");
    results.stepIssues.forEach((s) => {
      console.log(`  ${s.field}: ${s.message}`);
    });
    console.log();
  }

  // JSON出力（LLMが解釈用）
  console.log("--- JSON結果 ---");
  console.log(JSON.stringify(results, null, 2));

  // 必須フィールドが全て埋まっているかで終了コード決定
  const requiredMissing = results.missing.filter((m) => m.priority === "必須");
  process.exit(requiredMissing.length > 0 || results.stepIssues.length > 0 ? 4 : 0);
}

main();
