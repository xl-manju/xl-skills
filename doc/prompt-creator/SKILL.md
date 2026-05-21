---
name: prompt-creator
description: |
  ユーザーへのヒアリングからPrompt作成シートを生成し、
  7層構造プロンプト（YAML/Markdown/JSON/XML）を自動生成するスキル。
  クライアント向け・自社向け両対応。

  Anchors:
  - Prompt作成シート / 適用: 要件整理 / 目的: 漏れのない情報収集
  - 7層アーキテクチャ / 適用: プロンプト構造 / 目的: 再現性と拡張性
  - Design Thinking / 適用: ヒアリング / 目的: ユーザー課題の深掘り
  - Clean Architecture (Robert C. Martin) / 適用: 依存性の方向制御 / 目的: 層間の疎結合
  - Domain-Driven Design (Eric Evans) / 適用: ユビキタス言語・境界づけられたコンテキスト / 目的: ドメイン精度向上

  Trigger:
  プロンプト作成, プロンプト生成, Prompt作成シート, prompt-creator,
  新しいプロンプト, プロンプト設計

allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
  - Task
  - AskUserQuestion
---

# Prompt Creator

ユーザーへのヒアリングでPrompt作成シートを埋め、構造化プロンプトを生成するスキル。

## 設計原則

| 原則 | 説明 |
|------|------|
| **質ベース判定** | 数量ではなく「実行可能か」「検証可能か」で判定 |
| **1パス=1観点** | レビューは網羅性→整合性→深度→実用性の順次実行 |
| **動的評価基準** | ユーザーのevaluation_prioritiesに基づきPass別チェックを強化 |
| **導出確認** | AIの解釈・推定は必ずユーザーに透明化して承認を得る |
| Script First | 決定論的処理はスクリプトで実行（100%精度） |
| Progressive Disclosure | 必要な時に必要なリソースのみ読み込み |
| **記述スタイル** | 全ルール/制約に「目的+背景」併記。細部手順を冗長列挙せず、概念・大まかな流れで記述。Markdown既定。詳細: [references/writing-style-principles.md](references/writing-style-principles.md) |

## ワークフロー概要

```
Phase 1: ヒアリング（3-5問 + 評価優先度収集）     [LLM]
    ↓
Phase 2: Prompt作成シート生成 + 導出確認 → 承認   [Script→LLM]
    ↓
Phase 3: フォーマット・出力先選択                 [LLM]
    ↓
Phase 4-A: Layer単位生成（1Layer=1出力）          [Script→LLM]
    ↓
Phase 4-B: 動的評価基準生成 + 4パス検証           [Script→LLM]
    ↓
Phase 4-C: AI自律評価・改善（最大3回反復）        [LLM]
    ↓
Phase 4-D: フォーマット変換・ファイル出力         [Script + Write]
```

📖 [references/workflow-guide.md](references/workflow-guide.md)

---

## リソース一覧

| カテゴリ | 詳細参照 |
|---------|---------|
| agents/ | [resource-map.md#agents](references/resource-map.md) |
| references/ | [resource-map.md#references](references/resource-map.md) |
| scripts/ | [resource-map.md#scripts](references/resource-map.md) |
| schemas/ | [resource-map.md#schemas](references/resource-map.md) |

📖 [references/resource-map.md](references/resource-map.md)

---

## 主要エントリポイント

| Phase | 種別 | 参照 |
|-------|------|------|
| ヒアリング | LLM (agent) | agents/interview-user.md |
| プロンプト生成 | LLM (agent) | agents/generate-prompt.md |
| 品質レビュー | LLM (agent) | agents/review-prompt.md |
| 7層フォーマット | reference | references/seven-layer-format.md |
| 品質基準 | reference | references/quality-criteria.md |

---

## ベストプラクティス

| すべきこと | 避けるべきこと |
|-----------|---------------|
| Script優先（決定論的処理は100%精度） | 全てをLLMに任せる |
| 1Layer=1出力で個別生成→merge_layers.jsで合算 | 7層を一括生成する |
| 質ベース判定（「次に何をすべきか迷わないか？」） | 数量カウント（3つ以上、4つ以上） |
| レビューは1パス=1観点で順番に実行 | 全観点を1回でチェックする |
| references/を遅延読み込み | 全リソースを一度に読み込む |

---

## フィードバック

実行後は必ず記録：

```bash
node scripts/log_usage.js --result success --phase "Phase 5"
node scripts/log_usage.js --result failure --phase "Phase 3" --error "ValidationError"
```

---

## 変更履歴

| Version | Date | Changes |
|---------|------|---------|
| **2.2.0** | 2026-05-20 | 記述スタイル原則を追加: 全ルール/制約に「目的+背景」併記、細部手順を冗長列挙せず大まかな流れに留める、Markdown既定。`references/writing-style-principles.md` 新設、generate-prompt.md（核心原則5）/ review-prompt.md（Pass 5）/ resource-map.md / SKILL.md に反映 |
| **2.1.0** | 2026-02-06 | 生成プロンプト評価機能: Layer 4に出力評価基準、Layer 6に自己評価・改善ループを追加。Phase 4-CをAI自律評価に変更（ユーザー介入不要）。generate-prompt.mdにPass 0・評価基準生成ルール追加 |
| 2.0.0 | 2026-02-06 | 評価機能強化: Round 2.5（評価優先度収集）、導出確認（Phase 2統合）、動的評価基準（Pass 0）、Phase 4-C（クイック評価）→4-D（出力）の順序修正、データフロー整合性修正 |
| 1.9.0 | 2026-01-30 | 深層品質改善: スキーマminItems修正、Phase 4-Bを4パス構造に整合、残り数量表現を質ベース化、ファイル間整合性強化 |
| 1.8.1 | 2026-01-30 | 残留した数量ベース表現を質ベースに修正（interview-user.md:94）、全ファイル整合性検証完了 |
| 1.8.0 | 2026-01-30 | skill-creator基準でリファクタリング: SKILL.md 299→122行、resource-map.md・workflow-guide.md作成、Phase詳細を分離 |
| 1.7.0 | 2026-01-30 | 質ベース判定原則を全面導入。数量カウント→質的判定質問に変更。核心原則3を質ベースに刷新、核心原則4（1パス=1観点）追加 |
| 1.6.0 | 2026-01-30 | 意味的深度（Semantic Depth）原則を追加 |
| 1.5.0 | 2026-01-29 | 要素原子性原則を全体に適用 |
| 1.4.0 | 2026-01-29 | Layer単位生成 + merge_layers.js合算アーキテクチャ導入 |
| 1.3.0 | 2026-01-29 | DDD/CA原則統合、Script追加 |
| 1.2.0 | 2026-01-29 | Script/LLM責務分離 |
| 1.1.0 | 2026-01-29 | skill-creator仕様準拠 |
| 1.0.0 | 2026-01-29 | 初版作成 |
