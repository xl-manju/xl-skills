#!/usr/bin/env node
// Source: doc/prompt-creator/scripts/scaffold_prompt.js
// scaffold_prompt.js - ヒアリングJSONから7層構造プロンプトの骨格を決定論的に生成
// Usage: node scripts/scaffold_prompt.js <hearing-result.json> --format yaml|markdown|json|xml [--agents <N>] [--output <path>]
// Exit: 0=成功, 1=エラー, 2=引数エラー, 3=ファイル不在

const fs = require("fs");
const path = require("path");

function getArg(name) {
  const idx = process.argv.indexOf(`--${name}`);
  return idx !== -1 && process.argv[idx + 1] ? process.argv[idx + 1] : null;
}

// 7層マッピングテーブル（generate-prompt.md 4.2 を決定論的に実装）
// Prompt作成シート項目 → 7層構造の配置先
const LAYER_MAPPING = {
  prompt_name:      { layer: 1, path: "基本定義.メタ情報.プロジェクトID" },
  target_user:      { layer: 1, path: "基本定義.プロジェクト概要.想定利用者" },
  purpose:          { layer: 1, path: "基本定義.プロジェクト概要.最上位目的" },
  background:       { layer: 1, path: "基本定義.プロジェクト概要.背景コンテキスト" },
  success_criteria:  { layer: 1, path: "基本定義.プロジェクト概要.成功基準" },
  // Layer 2: ドメイン定義 - steps内の専門用語・ルールから抽出（LLM判断必要）
  challenges:        { layer: 2, path: "ドメイン定義.ビジネスルール.課題" },
  // Layer 3: インフラストラクチャ - ツール情報から抽出（LLM判断必要）
  constraints:       { layer: 4, path: "共通ポリシー.セキュリティ/品質" },
  steps:             { layer: 5, path: "エージェント定義.エージェント.実行仕様.思考プロセス" },
  // steps.output_format → Layer 5 出力テンプレート
  // 全体フロー → Layer 6 オーケストレーション
  test_cases:        { layer: 7, path: "ユーザーインタラクション" },
  required_info:     { layer: 7, path: "ユーザーインタラクション.初回質問の設計材料" },
};

// === YAML骨格生成 ===
function scaffoldYAML(data, agentCount) {
  const steps = data.steps || [];
  const constraints = data.constraints || [];
  const challenges = data.challenges || [];
  const requiredInfo = data.required_info || [];
  const testCases = data.test_cases || [];

  // Layer 4 制約条件をYAML形式に
  const constraintLines = constraints
    .map((c, i) => `      - ID: "CONST_${String(i + 1).padStart(3, "0")}"\n        内容: "${c}"`)
    .join("\n");

  // Layer 2 課題をYAML形式に
  const challengeLines = challenges
    .map((c, i) => `      - ID: "CHAL_${String(i + 1).padStart(3, "0")}"\n        内容: "${c}"`)
    .join("\n");

  // Layer 5 エージェントブロック生成
  const agentBlocks = [];
  for (let i = 0; i < agentCount; i++) {
    const stepSlice = agentCount === 1
      ? steps
      : steps.slice(
          Math.floor(i * steps.length / agentCount),
          Math.floor((i + 1) * steps.length / agentCount)
        );

    const thoughtSteps = stepSlice
      .map((s, j) => `          - ステップ${j + 1}: "${s.description || "{{LLM_FILL}}"}"`)
      .join("\n");

    const outputTemplates = stepSlice
      .filter(s => s.output_format)
      .map((s, j) => `          - 成果物名: "Step${j + 1}出力"\n            出力テンプレート: |\n              ${(s.output_format || "{{LLM_FILL}}").replace(/\n/g, "\n              ")}`)
      .join("\n");

    agentBlocks.push(`    - 番号: ${i + 1}
      名前: "{{LLM_FILL: 実在する専門家の名前}}"

      プロフィール:
        背景: |
          {{LLM_FILL: なぜこの人物が適しているか}}
        目的: |
          {{LLM_FILL: 達成すべき具体的なゴール}}
        責務: |
          {{LLM_FILL: 責任範囲と成果物}}

      知識ベース:
        参考文献:
          - 書籍: "{{LLM_FILL: 書籍名1}}"
            適用方法: |
              {{LLM_FILL: 適用方法}}

      実行仕様:
        思考プロセス:
${thoughtSteps}

        チェックリスト:
          - 項目: "出力検証: すべての必須項目が含まれているか"
            基準: "{{LLM_FILL: 必須フィールドをリスト化}}"
          - 項目: "事実確認: 推測を事実として述べていないか"
            基準: "不確実な情報には限定詞を使用"

        ビジネスルール:
${constraintLines || '          - ID: "CONST_001"\n            内容: "{{LLM_FILL}}"'}

      インターフェース:
        入力:
          - データ名: "{{LLM_FILL}}"
            提供元: "${i === 0 ? '外部' : '{{LLM_FILL: 前エージェント名}}'}"
            検証ルール: |
              {{LLM_FILL}}

        出力:
${outputTemplates || '          - 成果物名: "{{LLM_FILL}}"\n            出力テンプレート: "{{LLM_FILL}}"'}

      依存関係:
        前提エージェント:
          - 名前: "${i === 0 ? 'なし' : '{{LLM_FILL: 前エージェント名}}'}"
        後続エージェント:
          - 名前: "${i === agentCount - 1 ? 'なし' : '{{LLM_FILL: 後続エージェント名}}'}"

      ポリシー:
        セキュリティ:
          許可アクション: ["{{LLM_FILL}}"]
          禁止アクション: ["{{LLM_FILL}}"]
          データアクセス: "read_write"
        品質基準:
          必須フィールド: ["{{LLM_FILL}}"]
          信頼度スコア閾値: 0.8`);
  }

  // Layer 7 テストケース
  const testCaseLines = testCases.length > 0
    ? testCases.map((tc, i) =>
        `      - "${tc.input || "{{LLM_FILL}}"}"`
      ).join("\n")
    : '      - "{{LLM_FILL: ユーザー入力例}}"';

  const requiredInfoLines = requiredInfo.length > 0
    ? requiredInfo.map(r => `      - "${r}"`).join("\n")
    : '      - "{{LLM_FILL}}"';

  // 課題からLayer 2 ビジネスルールのヒントを生成
  const challengeHints = challenges.length > 0
    ? challenges.map(c => `    # 課題: ${c}`).join("\n")
    : "    # {{LLM_FILL: 課題から用語・ルールを抽出}}";

  return `# ${data.prompt_name || "{{プロンプト名}}"}
# ${data.purpose ? data.purpose.substring(0, 60) : "{{1行で概要説明}}"}

# Layer 1: 基本定義層（最上位の不変定義）
基本定義:
  メタ情報:
    プロジェクトID: "${data.prompt_name || "{{プロジェクトID}}"}"

  プロジェクト概要:
    想定利用者: |
      ${data.target_user || "{{LLM_FILL: 想定利用者}}"}
    最上位目的: |
      ${data.purpose || "{{LLM_FILL: 最上位目的}}"}
    背景コンテキスト: |
      ${data.background || "{{LLM_FILL: 背景}}"}
    期待される成果: |
      {{LLM_FILL: 期待される成果物・結果}}
    成功基準: |
      ${data.success_criteria || "{{LLM_FILL: 成功基準}}"}
    スコープ:
      含む: [{{LLM_FILL: スコープ}}]
      含まない: [{{LLM_FILL: 除外範囲}}]

# Layer 2: ドメイン定義層（ビジネスロジックの定義）
ドメイン定義:
${challengeHints}
  用語集:
    "{{LLM_FILL: 用語名}}":
      定義: |
        {{LLM_FILL: 定義}}
      使用コンテキスト: ["{{LLM_FILL}}"]

  ビジネスルール:
    プロセス制約:
${constraintLines || '      - ID: "CONST_001"\n        内容: "{{LLM_FILL}}"'}
    課題:
${challengeLines || '      - ID: "CHAL_001"\n        内容: "{{LLM_FILL}}"'}
    出力制約:
      ID: "OUTPUT_CONST"
      内容: |
        各エージェントの出力タイミングと確認方法を記述

# Layer 3: インフラストラクチャ定義層（外部システムとの接続）
インフラストラクチャ:
  ツール:
    "{{LLM_FILL: ツール名}}":
      説明: |
        {{LLM_FILL: ツールの機能と用途}}
      実行条件:
        トリガー条件: ["{{LLM_FILL}}"]
        スキップ条件: ["{{LLM_FILL}}"]
      インターフェース:
        パラメータ:
          "{{LLM_FILL}}":
            既定値: "{{LLM_FILL}}"
            説明: "{{LLM_FILL}}"
      エラーハンドリング:
        最大リトライ数: 3
        フォールバック処理: "{{LLM_FILL}}"

# Layer 4: 共通ポリシー層（横断的関心事）
共通ポリシー:
  システム設定:
    信頼度スコア閾値: 0.8
    最大リトライ回数: 3

  セキュリティ:
    許可アクション:
      グローバル: ["{{LLM_FILL}}"]
    禁止アクション:
      グローバル: ["{{LLM_FILL}}"]

  品質基準:
    事実確認:
      ルール: |
        {{LLM_FILL: 推測と事実を区別する方法}}
      検証方法: ["{{LLM_FILL}}"]

  エスカレーション:
    共通条件:
      - "{{LLM_FILL}}"
    通知先: "ユーザー"

# Layer 5: エージェント定義層（実行単位の定義）
エージェント定義:
  共通構造:
    - プロフィール
    - 知識ベース
    - 実行仕様
    - インターフェース
    - 依存関係
    - ツール利用
    - ポリシー

  エージェント:
${agentBlocks.join("\n\n")}

# Layer 6: オーケストレーション層（自律的動的実行制御）
オーケストレーション:
  実行原則: |
    AIは入力・状況・目的に基づき、Layer 5のエージェント群から
    最適な組み合わせを自律的に選択・実行・評価し、
    Layer 1の成功基準達成まで反復する。

  選択基準:
    参照元: "Layer 5 各エージェントの「目的」「責務」"
    判断方式: "現在の課題との適合度が最も高いエージェントを選択"
    実行形態: "依存関係に応じて順次/並列/反復を自動決定"

  制約:
    参照元: "Layer 4 共通ポリシー"
    追加制約:
      最大反復回数: 5
      必須経由: "{{LLM_FILL: 必須エージェント}}"

  完了判定:
    参照元: "Layer 1 成功基準"
    判定方式: "成功基準の全項目を満たした時点で完了"
    未達時: "不足要素を特定し、該当エージェントを再選択"

# Layer 7: ユーザーインタラクション層（初回入力の取得）
ユーザーインタラクション:
  初回質問:
    概要: |
      {{LLM_FILL: 初回質問の説明}}

    質問:
${requiredInfoLines}

    回答例:
      - |
        {{LLM_FILL: 回答例}}
`;
}

// === Markdown骨格生成 ===
function scaffoldMarkdown(data, agentCount) {
  // YAML生成してからMarkdownに変換指示を付加
  return `<!-- scaffold_prompt.js auto-generated: Markdown format -->
<!-- LLM_FILL マーカーの箇所をLLMが埋めてください -->

# ${data.prompt_name || "{{プロンプト名}}"}

## Layer 1: 基本定義層

### メタ情報
- プロジェクトID: ${data.prompt_name || "{{LLM_FILL}}"}

### プロジェクト概要
- **想定利用者**: ${data.target_user || "{{LLM_FILL}}"}
- **最上位目的**: ${data.purpose || "{{LLM_FILL}}"}
- **背景コンテキスト**: ${data.background || "{{LLM_FILL}}"}
- **成功基準**: ${data.success_criteria || "{{LLM_FILL}}"}
- **期待される成果**: {{LLM_FILL}}

## Layer 2: ドメイン定義層

### 用語集
| 用語 | 定義 | 使用コンテキスト |
|------|------|-----------------|
| {{LLM_FILL}} | {{LLM_FILL}} | {{LLM_FILL}} |

### ビジネスルール
${(data.constraints || []).map((c, i) => `- CONST_${String(i+1).padStart(3,"0")}: ${c}`).join("\n") || "- {{LLM_FILL}}"}

### 課題
${(data.challenges || []).map((c, i) => `- CHAL_${String(i+1).padStart(3,"0")}: ${c}`).join("\n") || "- {{LLM_FILL}}"}

## Layer 3: インフラストラクチャ定義層

### ツール定義
| ツール名 | 説明 | トリガー条件 |
|---------|------|-------------|
| {{LLM_FILL}} | {{LLM_FILL}} | {{LLM_FILL}} |

## Layer 4: 共通ポリシー層

### セキュリティ
- 許可アクション: {{LLM_FILL}}
- 禁止アクション: {{LLM_FILL}}

### 品質基準
- 事実確認ルール: {{LLM_FILL}}

## Layer 5: エージェント定義層

${Array.from({length: agentCount}, (_, i) => {
  const stepSlice = agentCount === 1
    ? (data.steps || [])
    : (data.steps || []).slice(
        Math.floor(i * (data.steps || []).length / agentCount),
        Math.floor((i + 1) * (data.steps || []).length / agentCount)
      );
  return `### エージェント${i+1}: {{LLM_FILL: 名前}}

**プロフィール**: {{LLM_FILL}}

**思考プロセス**:
${stepSlice.map((s, j) => `${j+1}. ${s.description || "{{LLM_FILL}}"}`).join("\n")}

**出力テンプレート**:
\`\`\`
${stepSlice.filter(s => s.output_format).map(s => s.output_format).join("\n---\n") || "{{LLM_FILL}}"}
\`\`\`
`;
}).join("\n")}

## Layer 6: オーケストレーション層

- **実行原則**: 自律的選択・実行・評価
- **選択基準**: Layer 5エージェントの目的・責務との適合度
- **完了判定**: Layer 1成功基準の全項目充足

## Layer 7: ユーザーインタラクション層

### 初回質問
${(data.required_info || []).map(r => `- ${r}`).join("\n") || "- {{LLM_FILL}}"}

### 回答例
\`\`\`
{{LLM_FILL: 回答例}}
\`\`\`
`;
}

// === JSON骨格生成 ===
function scaffoldJSON(data, agentCount) {
  const scaffold = {
    layer1_基本定義: {
      メタ情報: { プロジェクトID: data.prompt_name || "{{LLM_FILL}}" },
      プロジェクト概要: {
        想定利用者: data.target_user || "{{LLM_FILL}}",
        最上位目的: data.purpose || "{{LLM_FILL}}",
        背景コンテキスト: data.background || "{{LLM_FILL}}",
        成功基準: data.success_criteria || "{{LLM_FILL}}",
        期待される成果: "{{LLM_FILL}}",
      },
    },
    layer2_ドメイン定義: {
      用語集: { "{{LLM_FILL: 用語名}}": { 定義: "{{LLM_FILL}}", 使用コンテキスト: ["{{LLM_FILL}}"] } },
      ビジネスルール: (data.constraints || []).map((c, i) => ({
        ID: `CONST_${String(i+1).padStart(3,"0")}`,
        内容: c,
      })),
      課題: (data.challenges || []).map((c, i) => ({
        ID: `CHAL_${String(i+1).padStart(3,"0")}`,
        内容: c,
      })),
    },
    layer3_インフラストラクチャ: {
      ツール: { "{{LLM_FILL: ツール名}}": { 説明: "{{LLM_FILL}}", トリガー条件: ["{{LLM_FILL}}"] } },
    },
    layer4_共通ポリシー: {
      セキュリティ: { 許可アクション: ["{{LLM_FILL}}"], 禁止アクション: ["{{LLM_FILL}}"] },
      品質基準: { 事実確認: "{{LLM_FILL}}" },
    },
    layer5_エージェント定義: {
      エージェント: Array.from({ length: agentCount }, (_, i) => ({
        番号: i + 1,
        名前: "{{LLM_FILL}}",
        プロフィール: "{{LLM_FILL}}",
        思考プロセス: (data.steps || []).map(s => s.description || "{{LLM_FILL}}"),
        出力テンプレート: "{{LLM_FILL}}",
      })),
    },
    layer6_オーケストレーション: {
      実行原則: "自律的選択・実行・評価",
      完了判定: "Layer 1成功基準の全項目充足",
    },
    layer7_ユーザーインタラクション: {
      初回質問: data.required_info || ["{{LLM_FILL}}"],
      回答例: ["{{LLM_FILL}}"],
    },
  };
  return JSON.stringify(scaffold, null, 2);
}

// === XML骨格生成 ===
function scaffoldXML(data, agentCount) {
  const esc = (s) => (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const steps = data.steps || [];
  const constraints = data.constraints || [];

  return `<?xml version="1.0" encoding="UTF-8"?>
<prompt name="${esc(data.prompt_name || "{{プロンプト名}}")}">

  <layer1 name="基本定義層">
    <meta>
      <project-id>${esc(data.prompt_name || "{{LLM_FILL}}")}</project-id>
    </meta>
    <overview>
      <target-user><![CDATA[${data.target_user || "{{LLM_FILL}}"}]]></target-user>
      <purpose><![CDATA[${data.purpose || "{{LLM_FILL}}"}]]></purpose>
      <background><![CDATA[${data.background || "{{LLM_FILL}}"}]]></background>
      <success-criteria><![CDATA[${data.success_criteria || "{{LLM_FILL}}"}]]></success-criteria>
      <expected-outcome><![CDATA[{{LLM_FILL}}]]></expected-outcome>
    </overview>
  </layer1>

  <layer2 name="ドメイン定義層">
    <glossary>
      <term name="{{LLM_FILL}}">
        <definition><![CDATA[{{LLM_FILL}}]]></definition>
      </term>
    </glossary>
    <business-rules>
${constraints.map((c, i) => `      <rule id="CONST_${String(i+1).padStart(3,"0")}"><![CDATA[${esc(c)}]]></rule>`).join("\n") || '      <rule id="CONST_001"><![CDATA[{{LLM_FILL}}]]></rule>'}
    </business-rules>
    <challenges>
${(data.challenges || []).map((c, i) => `      <challenge id="CHAL_${String(i+1).padStart(3,"0")}"><![CDATA[${esc(c)}]]></challenge>`).join("\n") || '      <challenge id="CHAL_001"><![CDATA[{{LLM_FILL}}]]></challenge>'}
    </challenges>
  </layer2>

  <layer3 name="インフラストラクチャ定義層">
    <tools>
      <tool name="{{LLM_FILL}}">
        <description><![CDATA[{{LLM_FILL}}]]></description>
      </tool>
    </tools>
  </layer3>

  <layer4 name="共通ポリシー層">
    <security>
      <allowed-actions>{{LLM_FILL}}</allowed-actions>
      <prohibited-actions>{{LLM_FILL}}</prohibited-actions>
    </security>
    <quality>
      <fact-check><![CDATA[{{LLM_FILL}}]]></fact-check>
    </quality>
  </layer4>

  <layer5 name="エージェント定義層">
${Array.from({length: agentCount}, (_, i) => `    <agent number="${i+1}" name="{{LLM_FILL}}">
      <profile><![CDATA[{{LLM_FILL}}]]></profile>
      <thought-process>
${steps.map((s, j) => `        <step number="${j+1}"><![CDATA[${esc(s.description || "{{LLM_FILL}}")}]]></step>`).join("\n")}
      </thought-process>
      <output-template><![CDATA[{{LLM_FILL}}]]></output-template>
    </agent>`).join("\n")}
  </layer5>

  <layer6 name="オーケストレーション層">
    <execution-principle><![CDATA[自律的選択・実行・評価]]></execution-principle>
    <completion-criteria><![CDATA[Layer 1成功基準の全項目充足]]></completion-criteria>
  </layer6>

  <layer7 name="ユーザーインタラクション層">
    <initial-questions>
${(data.required_info || ["{{LLM_FILL}}"]).map(r => `      <question><![CDATA[${esc(r)}]]></question>`).join("\n")}
    </initial-questions>
    <answer-examples>
      <example><![CDATA[{{LLM_FILL}}]]></example>
    </answer-examples>
  </layer7>

</prompt>
`;
}

const SCAFFOLDERS = {
  yaml: scaffoldYAML,
  markdown: scaffoldMarkdown,
  json: scaffoldJSON,
  xml: scaffoldXML,
};

function main() {
  if (process.argv.length < 3 || process.argv[2] === "-h" || process.argv[2] === "--help") {
    console.log("Usage: node scaffold_prompt.js <hearing-result.json> --format yaml|markdown|json|xml [--agents N] [--output path]");
    console.log("  Generates 7-layer prompt scaffold from hearing result JSON.");
    console.log("  {{LLM_FILL}} markers indicate sections requiring LLM creative input.");
    console.log("  Exit codes: 0=OK, 1=error, 2=args error, 3=file not found");
    process.exit(process.argv[2] === "-h" || process.argv[2] === "--help" ? 0 : 2);
  }

  const inputPath = path.resolve(process.argv[2]);
  if (!fs.existsSync(inputPath)) {
    console.error(`[ERROR] File not found: ${inputPath}`);
    process.exit(3);
  }

  const format = getArg("format");
  if (!format || !SCAFFOLDERS[format]) {
    console.error("[ERROR] --format required: yaml|markdown|json|xml");
    process.exit(2);
  }

  const agentCount = parseInt(getArg("agents") || "1", 10);
  if (agentCount < 1) {
    console.error("[ERROR] --agents must be >= 1");
    process.exit(2);
  }

  let data;
  try {
    data = JSON.parse(fs.readFileSync(inputPath, "utf-8"));
  } catch (e) {
    console.error(`[ERROR] Invalid JSON: ${e.message}`);
    process.exit(1);
  }

  const scaffold = SCAFFOLDERS[format](data, agentCount);
  const outputPath = getArg("output");

  if (outputPath) {
    const resolved = path.resolve(outputPath);
    fs.writeFileSync(resolved, scaffold, "utf-8");
    console.log(`[OK] 7層骨格を出力: ${resolved}`);
    console.log(`[INFO] {{LLM_FILL}} マーカー箇所をLLMが埋めてください`);
  } else {
    process.stdout.write(scaffold);
  }

  // LLM_FILL統計
  const fillCount = (scaffold.match(/\{\{LLM_FILL[^}]*\}\}/g) || []).length;
  const filledCount = Object.keys(LAYER_MAPPING)
    .filter(k => data[k] && data[k] !== "")
    .length;
  console.error(`\n[STATS] 自動充填: ${filledCount}項目, LLM必要: ${fillCount}箇所`);

  process.exit(0);
}

main();
