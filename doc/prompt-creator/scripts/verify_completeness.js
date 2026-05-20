#!/usr/bin/env node
// verify_completeness.js - ヒアリングJSON vs 生成プロンプトの網羅性検証
// Usage: node scripts/verify_completeness.js <hearing-result.json> <prompt-file> [--pass N]
// Exit: 0=全項目反映, 4=未反映あり, 2=引数エラー, 3=ファイル不在
//
// 目的: Prompt作成シートの全項目が7層プロンプトに漏れなく反映されているか検証
// 方式: キーワード重複率 + フィールド存在チェック（決定論的）
//       意味的一致はreview-prompt.md（LLM）が補完

const fs = require("fs");
const path = require("path");

function getArg(name) {
  const idx = process.argv.indexOf(`--${name}`);
  return idx !== -1 && process.argv[idx + 1] ? process.argv[idx + 1] : null;
}

// 日本語テキストからキーワードを抽出（助詞・接続詞を除去）
function extractKeywords(text) {
  if (!text || typeof text !== "string") return [];
  // 句読点・記号で分割、2文字以上の語を抽出
  const words = text
    .replace(/[、。！？「」『』（）\[\]{}#\-=_*`~|<>\/\\:;@$%^&+,."']/g, " ")
    .split(/\s+/)
    .filter(w => w.length >= 2)
    // 一般的な助詞・接続詞を除外
    .filter(w => !["こと", "ため", "もの", "それ", "これ", "この", "その",
                   "する", "した", "して", "なる", "ある", "いる", "できる",
                   "ない", "なく", "から", "まで", "として", "について",
                   "における", "による", "に対し", "に関する"].includes(w));
  return [...new Set(words)];
}

// キーワード重複率を計算（source のキーワードが target に含まれる割合）
function keywordOverlap(sourceText, targetText) {
  const sourceKw = extractKeywords(sourceText);
  const targetKw = extractKeywords(targetText);
  if (sourceKw.length === 0) return { rate: 1.0, matched: [], missing: [] };

  const targetJoined = targetText.toLowerCase();
  const matched = sourceKw.filter(kw => targetJoined.includes(kw.toLowerCase()));
  const missing = sourceKw.filter(kw => !targetJoined.includes(kw.toLowerCase()));

  return {
    rate: matched.length / sourceKw.length,
    matched,
    missing,
  };
}

// ヒアリングJSONの各フィールドが7層プロンプトに反映されているか検証
function verifyCompleteness(hearingData, promptContent) {
  const results = {
    fields: [],
    summary: { total: 0, reflected: 0, partial: 0, missing: 0 },
    overallRate: 0,
  };

  // フィールドと期待されるLayerのマッピング
  const fieldChecks = [
    { key: "prompt_name", label: "プロンプト名", layer: "Layer 1", priority: "必須" },
    { key: "purpose", label: "目的", layer: "Layer 1", priority: "必須" },
    { key: "background", label: "背景", layer: "Layer 1", priority: "必須" },
    { key: "success_criteria", label: "完了条件", layer: "Layer 1", priority: "必須" },
    { key: "target_user", label: "想定利用者", layer: "Layer 1/7", priority: "必須" },
  ];

  // 配列フィールド（各要素を個別チェック）
  const arrayFieldChecks = [
    { key: "steps", subKey: "description", label: "手順", layer: "Layer 5", priority: "必須" },
    { key: "steps", subKey: "output_format", label: "出力フォーマット", layer: "Layer 5", priority: "必須" },
    { key: "challenges", label: "課題", layer: "Layer 2/4", priority: "必須" },
    { key: "constraints", label: "制約条件", layer: "Layer 4", priority: "推奨" },
    { key: "required_info", label: "必要情報", layer: "Layer 7", priority: "推奨" },
    { key: "test_cases", subKey: "input", label: "テストケース入力", layer: "Layer 7", priority: "オプション" },
    { key: "test_cases", subKey: "expected_output", label: "テストケース出力", layer: "Layer 7", priority: "オプション" },
  ];

  // 単一フィールドチェック
  for (const check of fieldChecks) {
    const value = hearingData[check.key];
    if (!value || value === "") {
      results.fields.push({
        ...check,
        status: "SKIP",
        message: "ヒアリングデータなし",
        rate: null,
      });
      continue;
    }

    results.summary.total++;
    const overlap = keywordOverlap(value, promptContent);

    let status;
    if (overlap.rate >= 0.7) {
      status = "REFLECTED";
      results.summary.reflected++;
    } else if (overlap.rate >= 0.3) {
      status = "PARTIAL";
      results.summary.partial++;
    } else {
      status = "MISSING";
      results.summary.missing++;
    }

    results.fields.push({
      ...check,
      status,
      rate: Math.round(overlap.rate * 100),
      missingKeywords: overlap.missing.slice(0, 5),
    });
  }

  // 配列フィールドチェック
  for (const check of arrayFieldChecks) {
    const arr = hearingData[check.key];
    if (!arr || !Array.isArray(arr) || arr.length === 0) {
      results.fields.push({
        key: check.key,
        label: check.label,
        layer: check.layer,
        priority: check.priority,
        status: "SKIP",
        message: "ヒアリングデータなし",
        rate: null,
      });
      continue;
    }

    // 各要素を個別にチェック
    for (let i = 0; i < arr.length; i++) {
      const item = check.subKey ? arr[i][check.subKey] : arr[i];
      if (!item || item === "") continue;

      results.summary.total++;
      const overlap = keywordOverlap(item, promptContent);

      let status;
      if (overlap.rate >= 0.6) {
        status = "REFLECTED";
        results.summary.reflected++;
      } else if (overlap.rate >= 0.25) {
        status = "PARTIAL";
        results.summary.partial++;
      } else {
        status = "MISSING";
        results.summary.missing++;
      }

      results.fields.push({
        key: `${check.key}[${i}]${check.subKey ? "." + check.subKey : ""}`,
        label: `${check.label}[${i + 1}]`,
        layer: check.layer,
        priority: check.priority,
        status,
        rate: Math.round(overlap.rate * 100),
        missingKeywords: overlap.missing.slice(0, 3),
      });
    }
  }

  // 全体反映率
  results.overallRate = results.summary.total > 0
    ? Math.round((results.summary.reflected / results.summary.total) * 100)
    : 100;

  return results;
}

function main() {
  if (process.argv.length < 4 || process.argv[2] === "-h" || process.argv[2] === "--help") {
    console.log("Usage: node verify_completeness.js <hearing-result.json> <prompt-file> [--pass N]");
    console.log("  Verifies hearing data is fully reflected in generated prompt.");
    console.log("  Exit codes: 0=OK, 2=args error, 3=file not found, 4=incomplete");
    process.exit(process.argv[2] === "-h" || process.argv[2] === "--help" ? 0 : 2);
  }

  const hearingPath = path.resolve(process.argv[2]);
  const promptPath = path.resolve(process.argv[3]);
  const passNum = getArg("pass") || "1";

  if (!fs.existsSync(hearingPath)) {
    console.error(`[ERROR] Hearing file not found: ${hearingPath}`);
    process.exit(3);
  }
  if (!fs.existsSync(promptPath)) {
    console.error(`[ERROR] Prompt file not found: ${promptPath}`);
    process.exit(3);
  }

  let hearingData;
  try {
    hearingData = JSON.parse(fs.readFileSync(hearingPath, "utf-8"));
  } catch (e) {
    console.error(`[ERROR] Invalid hearing JSON: ${e.message}`);
    process.exit(1);
  }

  const promptContent = fs.readFileSync(promptPath, "utf-8");
  const results = verifyCompleteness(hearingData, promptContent);

  // 出力
  console.log(`\n=== 網羅性検証結果（Pass ${passNum}） ===\n`);
  console.log(`全体反映率: ${results.overallRate}%`);
  console.log(`反映済み: ${results.summary.reflected}/${results.summary.total}`);
  console.log(`部分反映: ${results.summary.partial}`);
  console.log(`未反映: ${results.summary.missing}\n`);

  // 未反映・部分反映の項目を表示
  const issues = results.fields.filter(f => f.status === "MISSING" || f.status === "PARTIAL");
  if (issues.length > 0) {
    console.log("--- 要修正項目 ---");
    for (const item of issues) {
      const icon = item.status === "MISSING" ? "[未反映]" : "[部分反映]";
      console.log(`  ${icon} ${item.label} (${item.key}) → 期待Layer: ${item.layer} | 反映率: ${item.rate}%`);
      if (item.missingKeywords && item.missingKeywords.length > 0) {
        console.log(`         不足キーワード: ${item.missingKeywords.join(", ")}`);
      }
    }
    console.log();
  }

  // 反映済み項目
  const reflected = results.fields.filter(f => f.status === "REFLECTED");
  if (reflected.length > 0) {
    console.log("--- 反映済み項目 ---");
    for (const item of reflected) {
      console.log(`  [OK] ${item.label} → ${item.layer} (${item.rate}%)`);
    }
    console.log();
  }

  // JSON出力（LLMが解釈用）
  console.log("--- JSON結果 ---");
  console.log(JSON.stringify(results, null, 2));

  // 必須項目に未反映があれば失敗
  const criticalMissing = results.fields.filter(
    f => f.priority === "必須" && (f.status === "MISSING" || f.status === "PARTIAL")
  );
  process.exit(criticalMissing.length > 0 ? 4 : 0);
}

main();
