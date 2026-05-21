#!/usr/bin/env node
// generate_sheet.js - ヒアリング結果JSONからPrompt作成シートMarkdownを生成
// Usage: node scripts/generate_sheet.js <hearing-result.json> [--output <path>]
// Exit: 0=成功, 1=一般エラー, 2=引数エラー, 3=ファイル不在

const fs = require("fs");
const path = require("path");

function getArg(name) {
  const idx = process.argv.indexOf(`--${name}`);
  return idx !== -1 && process.argv[idx + 1] ? process.argv[idx + 1] : null;
}

function generateSheet(data) {
  const steps = (data.steps || [])
    .map((s, i) => `${i + 1}. ${s.description || "未定義"}`)
    .join("\n");

  const outputFormats = (data.steps || [])
    .map(
      (s, i) =>
        `## Step${i + 1}\n\`\`\`\n${s.output_format || "未定義"}\n\`\`\``
    )
    .join("\n\n");

  const challenges = (data.challenges || [])
    .map((c) => `- ${c}`)
    .join("\n") || "- 未定義";

  const requiredInfo = (data.required_info || [])
    .map((r) => `- ${r}`)
    .join("\n") || "- 未定義";

  const constraints = [
    "- 各ステップ毎に成果物を出力して、ユーザーに確認する",
    ...(data.constraints || []).map((c) => `- ${c}`),
  ].join("\n");

  const testCases = (data.test_cases || [])
    .map(
      (tc, i) =>
        `# 想定するユーザー入力${i + 1}\n\`\`\`\n${tc.input || "未定義"}\n\`\`\`\n\n# 期待される出力${i + 1}\n\`\`\`\n${tc.expected_output || "未定義"}\n\`\`\``
    )
    .join("\n\n");

  return `# Prompt作成シート

# Next Action
- [ ] フォーマットを具体的な内容で埋める

# プロンプト名
> 素人でもこれを見ただけで分かるこのプロンプトを命名
- ${data.prompt_name || "未定義"}

# プロンプトの想定利用者
> このプロンプトを実際に使う人物像や役割
- ${data.target_user || "未定義"}

# プロンプト作成の目的
> このプロンプトを作ることで達成したい最終ゴール
- ${data.purpose || "未定義"}

# プロンプト作成の背景
> なぜこのプロンプトが必要になったのか、その経緯や状況
- ${data.background || "未定義"}

# 完了条件（成功基準）
> どのような状態になれば「このプロンプトは完成した」と判断できるか
- ${data.success_criteria || "未定義"}

# 目的達成のための手順
> プロンプトを使用する際の大まかな流れやステップ
${steps || "1. 未定義"}

# 出力フォーマット
> 成果物として、出力してほしい形式

${outputFormats || "## Step1\n```\n未定義\n```"}

# 解決すべき課題
> プロンプトが解消するべき問題点や現状の不便
${challenges}

# 目的を達成するために必要な情報
> プロンプトが高品質な出力を行うために、事前に準備・入力しておくべき具体的な情報。
${requiredInfo}

# 注意点・制約条件
> プロンプト設計時に守るべき条件や避けたい出力
${constraints}

# プロンプトに対する課題
- ${data.prompt_issues || "未定義"}

${testCases || "# 想定するユーザー入力1\n```\n未定義\n```\n\n# 期待される出力1\n```\n未定義\n```"}
`;
}

function main() {
  if (process.argv.length < 3 || process.argv[2] === "-h" || process.argv[2] === "--help") {
    console.log("Usage: node generate_sheet.js <hearing-result.json> [--output <path>]");
    console.log("  Generates Prompt作成シート Markdown from hearing result JSON.");
    console.log("  If --output is not specified, prints to stdout.");
    console.log("  Exit codes: 0=OK, 1=error, 2=args error, 3=file not found");
    process.exit(process.argv[2] === "-h" || process.argv[2] === "--help" ? 0 : 2);
  }

  const inputPath = path.resolve(process.argv[2]);
  if (!fs.existsSync(inputPath)) {
    console.error(`[ERROR] File not found: ${inputPath}`);
    process.exit(3);
  }

  let data;
  try {
    data = JSON.parse(fs.readFileSync(inputPath, "utf-8"));
  } catch (e) {
    console.error(`[ERROR] Invalid JSON: ${e.message}`);
    process.exit(1);
  }

  const sheet = generateSheet(data);
  const outputPath = getArg("output");

  if (outputPath) {
    const resolvedOutput = path.resolve(outputPath);
    fs.writeFileSync(resolvedOutput, sheet, "utf-8");
    console.log(`[OK] Prompt作成シートを出力: ${resolvedOutput}`);
  } else {
    process.stdout.write(sheet);
  }

  process.exit(0);
}

main();
