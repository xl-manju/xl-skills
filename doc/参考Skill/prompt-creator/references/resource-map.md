# リソースマップ

prompt-creatorスキルの全リソース一覧。

## agents/

| ファイル | 用途 | 読み込みタイミング |
|---------|------|-------------------|
| interview-user.md | ヒアリング・要件収集 | Phase 1 |
| generate-prompt.md | 7層プロンプト生成 | Phase 4-A |
| review-prompt.md | 品質レビュー（4パス） | Phase 4-B |

## references/

| ファイル | 用途 | 読み込みタイミング |
|---------|------|-------------------|
| prompt-sheet-template.md | Prompt作成シートテンプレート | Phase 2 |
| seven-layer-format.md | 7層構造YAMLテンプレート | Phase 4-A |
| quality-criteria.md | 品質チェック基準 | Phase 4-B |
| workflow-guide.md | Phase詳細ワークフロー | 必要時 |
| writing-style-principles.md | 生成プロンプトの記述スタイル原則（目的+背景併記/簡潔/大まかな流れ） | Phase 4-A, 4-B（必読） |
| resource-map.md | 本ファイル（リソース一覧） | 必要時 |

## scripts/

| ファイル | 用途 | 入力 | 出力 |
|---------|------|------|------|
| generate_sheet.js | シートテンプレート展開 | hearing.json | prompt-sheet.md |
| validate_sheet.js | シート充足度検証 | hearing.json | 検証結果 |
| scaffold_prompt.js | 7層骨格生成 | hearing.json | scaffold.yaml |
| merge_layers.js | 7Layerファイル合算 | layer1-7.yaml | merged.yaml |
| validate_prompt.js | 7層構造検証 | *.yaml | 検証結果 |
| verify_completeness.js | 網羅性検証 | *.yaml + hearing.json | 検証結果 |
| convert_format.js | フォーマット変換 | *.yaml | *.md/json/xml |
| log_usage.js | 使用ログ記録 | --result --phase | LOGS.md |

## schemas/

| ファイル | 用途 |
|---------|------|
| hearing-result.schema.json | ヒアリング結果JSONスキーマ |

## 依存関係

```
Phase 1: interview-user.md → hearing-result.json
    ↓
Phase 2: generate_sheet.js + validate_sheet.js → prompt-sheet.md
    ↓
Phase 3: AskUserQuestion（フォーマット・出力先選択）
    ↓
Phase 4-A: scaffold_prompt.js → generate-prompt.md(×7) → merge_layers.js
    ↓
Phase 4-B: validate_prompt.js + verify_completeness.js + review-prompt.md
    ↓
Phase 4-C: convert_format.js → 最終出力
```
