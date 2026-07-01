---
name: quality-rubric
description: 全 SubAgent 共通の 5 次元品質ルブリック
type: reference
---

# 共通 5 次元ルブリック

> **正本注記**: 本ファイルが skill-creator 系 (生成 agent 含む) の正本。判定基準のうち `intake.json` 等 skill-intake ドメイン固有の例は対象ドメインの成果物に読み替え可。

各 SubAgent は出力前に必ずこのルブリックで自己採点する。`scripts/quality_gate.py` も同基準で機械検証する。

## 5 次元

| 次元 | 一言 | 重み |
|------|------|------|
| 完全性 | 必要な情報が揃っているか | 0.25 |
| 一貫性 | 矛盾がないか | 0.20 |
| 深度 | 表層に止まっていないか | 0.25 |
| 検証可能性 | 数値・具体例で確認できるか | 0.15 |
| 簡潔性 | 冗長を排しているか | 0.15 |

各次元 0〜3 点。合計 15 点満点。

## 派生 plugin の rubric 継承ルール

派生 plugin が独自 rubric（例: skill-intake の `rubric.json` の SE-* 構造 lint 体系）を持つ場合、本 5 次元 rubric との関係は以下で定める。

- **原則: 直交（orthogonal）**: 派生 plugin 独自 rubric は本 5 次元 rubric と直交させる。本 5 次元は**成果物採点層**（生成物の完全性/一貫性/深度/検証可能性/簡潔性を採点）、独自 SE-* は**構造 / frontmatter lint 層**（章・section 構造や frontmatter の binary 充足を lint）で責務が異なる。責務が異なる限り deep-merge せず、両方を独立に適用する。構造 fidelity 検証は Gate A（機械契約）に属し（`orchestrate-gate-pattern.md` 参照）、5 次元採点とは検出粒度が異なるため直交で共存する。
- **例外: 同一次元の再定義時のみ deep-merge**: 派生 rubric が本 5 次元と**同じ次元**を再定義する場合に限り deep-merge し、派生側が upstream（本ファイル）を上書きする。上書きした箇所は派生 rubric 側に `overrides: <upstream-dimension>` を明記する。これは `ref-skill-design-rubric` KeyRule 1（downstream `rubric.json` は upstream を deep-merge）と整合する。同 KeyRule が指す deep-merge は「同一 rubric 家系（設計 rubric 層）内の継承」を対象とし、責務層が異なる SE-* lint はそもそも deep-merge 対象外（直交）である点で矛盾しない。
- **governance 宣言義務**: 派生 rubric は冒頭に、本ファイル（skill-creator quality-rubric.md, 5 次元）との関係が**直交か deep-merge か**を governance 宣言する。deep-merge の場合は上書き次元を、直交の場合は責務層の違いを明記する。

## 1. 完全性（Completeness）

| 点 | 基準 |
|----|------|
| 0 | 必須項目の 50% 未満 |
| 1 | 必須項目の 50〜79% |
| 2 | 必須項目の 80〜99% |
| 3 | 必須項目 100% |

**判定基準**

- intake.json の必須キーが揃っているか
- 5 軸が全 verified か（knowledge_assets 含む）
- 図解 1〜3 図が各セクションに配置されているか

**閾値**: 2 以上で PASS。1 以下は再ヒアリング。

## 2. 一貫性（Consistency）

| 点 | 基準 |
|----|------|
| 0 | 重大な矛盾あり（例: 出力先が 2 箇所で違う） |
| 1 | 軽微な矛盾あり |
| 2 | 矛盾なし、ただし用語ゆれあり |
| 3 | 完全に一貫 |

**判定基準**

- フィールド間の整合（jtbd と purpose.excavated）
- 用語統一（例: 「フォーム」と「申込書」の混在）
- 図解と本文の一致

**閾値**: 2 以上 PASS。`scripts/cross_check.py` が SubAgent 間整合を検証。

## 3. 深度（Depth）

| 点 | 基準 |
|----|------|
| 0 | 表層要望のまま |
| 1 | 1 段下まで掘った |
| 2 | 5 Whys 3 段以上 |
| 3 | 5 Whys 完走 + Magic Wand + Pain Story |

**判定基準**

- purpose.excavated が stated と十分異なる
- five_axes.true_problem.depth = "deep"
- pain_stories が 1 件以上で時刻・感情含む

**閾値**: 2 以上 PASS。

## 4. 検証可能性（Verifiability）

| 点 | 基準 |
|----|------|
| 0 | 数値・例ゼロ |
| 1 | 数値 1 個以下 |
| 2 | 数値 2〜3 個、例 1 個 |
| 3 | 数値 3 個以上、例 2 個以上 |

**判定基準**

- 価値 KPI に数値が含まれる（時間／件数／率）
- pain_stories に具体時刻・場所
- jtbd.when が具体的契機

**閾値**: 2 以上 PASS。

## 5. 簡潔性（Conciseness）

| 点 | 基準 |
|----|------|
| 0 | 冗長度高（同じ説明 3 回以上） |
| 1 | やや冗長 |
| 2 | 適切 |
| 3 | 必要十分 |

**判定基準**

- 同義語反復が 3 回以下
- セクション当たりの説明文が 200 字以内
- 図解のラベルが 10 字以内

**閾値**: 2 以上 PASS。

## 自己採点フロー

```
[SubAgent 出力]
  ↓
1. 5 次元各々で自己採点
2. 合計点 / 15 を計算
3. 閾値:
   - 全次元 >= 2 → PASS
   - 1 次元でも < 2 → 自己修正（最大 3 回）
   - 3 回後も未達 → エスカレーション
```

## サンプル: interviewer の自己採点（google-forms-generator 中盤）

| 次元 | 点 | 根拠 |
|------|----|------|
| 完全性 | 2 | 5 軸 3/5 充足、share_target 未確定 |
| 一貫性 | 3 | 矛盾なし |
| 深度 | 2 | 5 Whys 3 段達成 |
| 検証可能性 | 3 | 90 分／月 4 回の数値あり |
| 簡潔性 | 2 | 適切 |

合計 12/15 → 完全性のみ閾値ギリギリ → share_target を 1 問だけ追加質問。

## 自己修正手順

| 不足次元 | 修正手順 |
|----------|----------|
| 完全性 | 不足キーを特定 → question-bank から 1 問抽出 |
| 一貫性 | 矛盾箇所を特定 → Reverse Brief で確認 |
| 深度 | 5 Whys 1 サイクル追加 |
| 検証可能性 | Pain Story / Current Workaround で数値要求 |
| 簡潔性 | 重複文を統合・削除 |

## エスカレーション

3 回の自己修正後も閾値未達の場合:

1. ユーザーに「ここが詰まっています」と提示
2. 部分完了で `run-skill-create` に渡す
3. open_questions に未解決項目を明記
