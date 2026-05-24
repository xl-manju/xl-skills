#!/usr/bin/env node
// verify_completeness.js — 正規形プロンプト（merge_layers.js 出力 YAML）の網羅性検証
//   1. 7 Layer 全てに最低 1 要素があるか（構造網羅）
//   2. ゴールシーク要素が Layer 5 に在るか（ゴール定義 / 完了チェックリスト / 達成ゴール）
//   3. 固定手順（思考プロセスのステップ列挙）が不在か（ゴールシーク禁止構造の検出）
// マーカーは scaffold_prompt.js / merge_layers.js が出力する「# Layer N:」に一致させる。
// Exit: 0=OK, 1=不備あり, 2=引数エラー
"use strict";
const fs = require("fs");

function parseArgs(argv) {
  const args = { input: null };
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "--input") args.input = argv[++i];
  }
  return args;
}

// 「# Layer N:」マーカーで本文を 7 層に分割する。
// 半角/全角コロン・# の個数（# / ##）の揺れを許容する。
function splitLayers(text) {
  const sections = {};
  for (let n = 1; n <= 7; n++) {
    const re = new RegExp(
      `#+\\s*Layer\\s*${n}\\s*[:：][^\\n]*\\n([\\s\\S]*?)(?=#+\\s*Layer\\s*${n + 1}\\s*[:：]|$)`
    );
    const m = text.match(re);
    sections[n] = m ? m[1] : null;
  }
  return sections;
}

function nonCommentBody(body) {
  return body
    .split("\n")
    .filter((l) => {
      const s = l.trim();
      return s.length > 0 && !s.startsWith("#");
    });
}

function main() {
  const { input } = parseArgs(process.argv);
  if (!input) {
    console.error("usage: verify_completeness.js --input <prompt.yaml>");
    process.exit(2);
  }
  const text = fs.readFileSync(input, "utf8");
  const sections = splitLayers(text);
  const problems = [];

  // 1. 構造網羅: 各 Layer が存在し本文が空でない
  for (let n = 1; n <= 7; n++) {
    const body = sections[n];
    if (body === null) {
      problems.push(`Layer ${n}: section missing`);
      continue;
    }
    if (nonCommentBody(body).length === 0) {
      problems.push(`Layer ${n}: empty body`);
    }
  }

  // 2. ゴールシーク要素: Layer 5 にゴール定義・完了チェックリスト・達成ゴールが在る
  const layer5 = sections[5] || "";
  const goalSeekRequired = [
    { key: "ゴール定義", label: "ゴール定義（目的・背景・達成ゴール）" },
    { key: "完了チェックリスト", label: "完了チェックリスト（停止条件）" },
    { key: "達成ゴール", label: "達成ゴール（成果状態）" },
  ];
  for (const r of goalSeekRequired) {
    if (sections[5] !== null && !layer5.includes(r.key)) {
      problems.push(`Layer 5: ${r.label} がない（ゴールシーク必須要素）`);
    }
  }

  // 3. 固定手順の不在: 「思考プロセス」+「ステップN」列挙はゴールシーク違反
  //    実行方式.ループ の箇条書きは許容（「思考プロセス」キーを伴わない）。
  if (/思考プロセス/.test(layer5) && /ステップ\s*[0-9０-９]/.test(layer5)) {
    problems.push(
      "Layer 5: 固定手順（思考プロセスのステップ列挙）が検出された — ゴール定義+完了チェックリストに置換すること"
    );
  }

  if (problems.length > 0) {
    console.error("FAIL incomplete:");
    for (const p of problems) console.error(`  - ${p}`);
    process.exit(1);
  }
  console.log("OK 7 layers verified (goal-seek 要素確認済み)");
}

main();
