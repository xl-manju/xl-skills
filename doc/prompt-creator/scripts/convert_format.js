#!/usr/bin/env node
// convert_format.js - YAML正規形を他フォーマット（Markdown/JSON/XML）に決定論的変換
// Usage: node scripts/convert_format.js <input-file> --to markdown|json|xml [--output <path>]
// Exit: 0=成功, 1=エラー, 2=引数エラー, 3=ファイル不在
//
// 注記: このスクリプトはYAMLパーサーを使わず、行ベースの構造変換を行う。
// 7層構造プロンプトの正規形（YAML）を他形式に変換する。

const fs = require("fs");
const path = require("path");

function getArg(name) {
  const idx = process.argv.indexOf(`--${name}`);
  return idx !== -1 && process.argv[idx + 1] ? process.argv[idx + 1] : null;
}

// === YAML → Markdown 変換 ===
function yamlToMarkdown(content) {
  const lines = content.split("\n");
  const output = [];
  let inBlock = false; // YAML block scalar (|)

  for (const line of lines) {
    const trimmed = line.trim();

    // コメント行（# で始まる行 → Markdown見出しまたはコメント）
    if (/^# -+$/.test(trimmed)) {
      // セパレータ行 → Markdown水平線
      output.push("---");
      continue;
    }
    if (/^# =+$/.test(trimmed)) {
      continue; // 装飾用セパレータはスキップ
    }
    if (/^# Layer \d+:/.test(trimmed) || /^# (.+層)/.test(trimmed)) {
      // Layer見出し → ## 見出し
      output.push(`## ${trimmed.replace(/^# /, "")}`);
      continue;
    }
    if (/^#\s/.test(trimmed) && !trimmed.startsWith("# {")) {
      // その他のコメント → HTMLコメントまたはMarkdownコメント
      output.push(`<!-- ${trimmed.replace(/^# /, "")} -->`);
      continue;
    }

    // トップレベルYAMLキー（インデントなし、: で終わる） → ### 見出し
    if (/^[^\s#].*:$/.test(line) && !line.includes('"')) {
      output.push(`\n### ${line.replace(/:$/, "")}`);
      continue;
    }

    // 2スペースインデントのキー → #### 見出し
    if (/^  [^\s].*:$/.test(line) && !line.includes('"')) {
      output.push(`\n#### ${line.trim().replace(/:$/, "")}`);
      continue;
    }

    // 4スペースインデントのキー → **太字**ラベル
    if (/^    [^\s-].*:\s*$/.test(line) && !line.includes('"')) {
      output.push(`\n**${line.trim().replace(/:$/, "")}**`);
      continue;
    }

    // キー: 値 のペア
    if (/:\s+[^|]/.test(line) && !trimmed.startsWith("-")) {
      const [key, ...vals] = line.split(/:\s+/);
      const value = vals.join(": ");
      const indent = line.match(/^\s*/)[0].length;
      if (indent <= 4) {
        output.push(`- **${key.trim()}**: ${value.trim()}`);
      } else {
        output.push(`  - ${key.trim()}: ${value.trim()}`);
      }
      continue;
    }

    // ブロックスカラー (|)
    if (/:\s+\|$/.test(line)) {
      const key = line.split(":")[0].trim();
      output.push(`\n**${key}**:`);
      inBlock = true;
      continue;
    }

    // リスト項目
    if (trimmed.startsWith("- ")) {
      output.push(`- ${trimmed.substring(2)}`);
      continue;
    }

    // ブロックスカラーの継続行
    if (inBlock && trimmed === "") {
      inBlock = false;
      output.push("");
      continue;
    }

    // その他
    output.push(line);
  }

  return output.join("\n");
}

// === YAML → JSON 変換（簡易パーサー） ===
function yamlToJSON(content) {
  // コメントと空行を除去したクリーンな構造を作成
  const lines = content.split("\n").filter(l => !l.trim().startsWith("#") && l.trim() !== "");

  // 簡易的なYAML→JSON変換: キー: 値のペアを再帰的にオブジェクトに変換
  const result = {};
  const stack = [{ obj: result, indent: -1 }];
  let currentKey = null;
  let blockValue = null;
  let blockIndent = 0;
  let currentArray = null;

  for (const line of lines) {
    const indent = line.match(/^\s*/)[0].length;
    const trimmed = line.trim();

    // ブロックスカラー収集中
    if (blockValue !== null) {
      if (indent > blockIndent) {
        blockValue += trimmed + "\n";
        continue;
      } else {
        // ブロック終了
        const top = stack[stack.length - 1];
        if (currentKey && top.obj) {
          top.obj[currentKey] = blockValue.trim();
        }
        blockValue = null;
      }
    }

    // リスト項目
    if (trimmed.startsWith("- ")) {
      const listContent = trimmed.substring(2).trim();
      // キー: 値を持つリスト項目
      if (listContent.includes(": ") && !listContent.startsWith('"')) {
        const [k, ...v] = listContent.split(": ");
        const top = stack[stack.length - 1];
        if (currentArray && top.obj[currentArray]) {
          const arr = top.obj[currentArray];
          if (arr.length === 0 || typeof arr[arr.length - 1] !== "object") {
            arr.push({});
          }
          const lastItem = arr[arr.length - 1];
          const val = v.join(": ").replace(/^"(.+)"$/, "$1");
          if (lastItem[k.trim()] !== undefined) {
            arr.push({ [k.trim()]: val });
          } else {
            lastItem[k.trim()] = val;
          }
        }
        continue;
      }
      // 単純なリスト項目
      const top = stack[stack.length - 1];
      if (currentArray && top.obj[currentArray]) {
        const val = listContent.replace(/^"(.+)"$/, "$1");
        top.obj[currentArray].push(val);
      }
      continue;
    }

    // キー: 値
    if (trimmed.includes(":")) {
      const colonIdx = trimmed.indexOf(":");
      const key = trimmed.substring(0, colonIdx).trim().replace(/^"(.+)"$/, "$1");
      const value = trimmed.substring(colonIdx + 1).trim();

      // スタック調整
      while (stack.length > 1 && stack[stack.length - 1].indent >= indent) {
        stack.pop();
      }
      const top = stack[stack.length - 1];

      if (value === "" || value === "|") {
        // ネストされたオブジェクトまたはブロックスカラー
        if (value === "|") {
          blockValue = "";
          blockIndent = indent;
          currentKey = key;
        } else {
          top.obj[key] = {};
          stack.push({ obj: top.obj[key], indent });
          currentArray = null;
        }
      } else if (value.startsWith("[")) {
        // インライン配列
        try {
          top.obj[key] = JSON.parse(value.replace(/'/g, '"'));
        } catch {
          top.obj[key] = [value];
        }
        currentArray = key;
      } else {
        // 単純な値
        const cleanValue = value.replace(/^"(.+)"$/, "$1");
        top.obj[key] = cleanValue;
      }
      currentKey = key;

      // 配列の場合の準備
      if (value === "") {
        // 次の行がリストかもしれない
        currentArray = key;
        if (!Array.isArray(top.obj[key])) {
          // オブジェクトとして初期化済み、リストかどうかは次の行で判定
        }
      }
    }
  }

  return JSON.stringify(result, null, 2);
}

// === YAML → XML 変換 ===
function yamlToXML(content) {
  const lines = content.split("\n");
  const output = ['<?xml version="1.0" encoding="UTF-8"?>'];
  output.push("<prompt>");

  let currentLayer = null;
  let depth = 1;

  for (const line of lines) {
    const trimmed = line.trim();

    // Layer見出しコメント
    const layerMatch = trimmed.match(/^# Layer (\d+): (.+)$/);
    if (layerMatch) {
      if (currentLayer) {
        output.push(`${"  ".repeat(1)}</layer${currentLayer}>`);
      }
      currentLayer = layerMatch[1];
      output.push(`${"  ".repeat(1)}<layer${currentLayer} name="${layerMatch[2]}">`);
      depth = 2;
      continue;
    }

    // コメント行
    if (trimmed.startsWith("#")) {
      if (!trimmed.startsWith("# -") && !trimmed.startsWith("# =")) {
        output.push(`${"  ".repeat(depth)}<!-- ${trimmed.replace(/^# /, "")} -->`);
      }
      continue;
    }

    // 空行
    if (trimmed === "") continue;

    // トップレベルキー
    if (/^[^\s-].*:/.test(line)) {
      const [key, ...vals] = line.split(/:\s*/);
      const value = vals.join(": ").trim();
      const tag = key.trim().replace(/\s+/g, "-");
      if (value === "" || value === "|") {
        output.push(`${"  ".repeat(depth)}<${tag}>`);
        depth++;
      } else {
        const cleanVal = value.replace(/^"(.+)"$/, "$1");
        output.push(`${"  ".repeat(depth)}<${tag}>${escapeXml(cleanVal)}</${tag}>`);
      }
      continue;
    }

    // インデントされたキー
    const indent = line.match(/^\s*/)[0].length;
    if (/[^\s-].*:/.test(trimmed) && !trimmed.startsWith("-")) {
      const [key, ...vals] = trimmed.split(/:\s*/);
      const value = vals.join(": ").trim();
      const tag = key.trim().replace(/\s+/g, "-").replace(/"/g, "");
      if (value === "" || value === "|") {
        output.push(`${"  ".repeat(depth)}<${tag}>`);
      } else {
        const cleanVal = value.replace(/^"(.+)"$/, "$1");
        if (cleanVal.length > 80) {
          output.push(`${"  ".repeat(depth)}<${tag}><![CDATA[${cleanVal}]]></${tag}>`);
        } else {
          output.push(`${"  ".repeat(depth)}<${tag}>${escapeXml(cleanVal)}</${tag}>`);
        }
      }
      continue;
    }

    // リスト項目
    if (trimmed.startsWith("- ")) {
      const val = trimmed.substring(2).replace(/^"(.+)"$/, "$1");
      output.push(`${"  ".repeat(depth)}<item>${escapeXml(val)}</item>`);
      continue;
    }
  }

  if (currentLayer) {
    output.push(`  </layer${currentLayer}>`);
  }
  output.push("</prompt>");

  return output.join("\n");
}

function escapeXml(s) {
  return (s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const CONVERTERS = {
  markdown: yamlToMarkdown,
  json: yamlToJSON,
  xml: yamlToXML,
};

function main() {
  if (process.argv.length < 3 || process.argv[2] === "-h" || process.argv[2] === "--help") {
    console.log("Usage: node convert_format.js <input-yaml> --to markdown|json|xml [--output path]");
    console.log("  Converts 7-layer YAML prompt to other formats deterministically.");
    console.log("  Exit codes: 0=OK, 1=error, 2=args error, 3=file not found");
    process.exit(process.argv[2] === "-h" || process.argv[2] === "--help" ? 0 : 2);
  }

  const inputPath = path.resolve(process.argv[2]);
  if (!fs.existsSync(inputPath)) {
    console.error(`[ERROR] File not found: ${inputPath}`);
    process.exit(3);
  }

  const targetFormat = getArg("to");
  if (!targetFormat || !CONVERTERS[targetFormat]) {
    console.error("[ERROR] --to required: markdown|json|xml");
    process.exit(2);
  }

  const content = fs.readFileSync(inputPath, "utf-8");
  const result = CONVERTERS[targetFormat](content);
  const outputPath = getArg("output");

  if (outputPath) {
    const resolved = path.resolve(outputPath);
    fs.writeFileSync(resolved, result, "utf-8");
    console.log(`[OK] ${targetFormat}形式で出力: ${resolved}`);
  } else {
    process.stdout.write(result);
  }

  process.exit(0);
}

main();
