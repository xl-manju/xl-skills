# orchestrate-gate-pattern

> skill-creator 横断パターン。Step 5 / 5.5 / 6 の三段ゲート設計を抽象化 (ABS-001)。
>
> **read_when** (G9, plugin-level resource-map):
> - Step 5 / 5.5 / 6 の三段ゲート設計を新規 plugin に展開する時
> - Gate 間で同一 finding が重複検出された時 (優先順位 A>B>C を適用)
> - 1 ゲートで複数次元採点する設計提案を検出した時 (アンチパターン)
>
> 正本: `plugins/skill-creator/references/resource-map.yaml#orchestrate-gate-pattern`

## パターン概要

複数の品質ゲートを直列に配置し、各ゲートが独立した検証次元 (契約 / elegance / 規範) を担うことで、Goodhart 罠と単一ゲート過負荷を回避する。

## 抽象モデル

```
input ──▶ [Gate A: 機械契約] ──▶ [Gate B: elegance lint] ──▶ [Gate C: 規範採点] ──▶ output
              │                       │                          │
              ▼                       ▼                          ▼
         PKG-* fail              C1-C4 fail                rubric score < threshold
         (eval-log)              (verdict.json)            (assignment report)
```

## 責務直交ルール

| 次元 | 担当ゲート | 一次判定 |
|---|---|---|
| 契約適合 (binary, 機械検査) | Gate A | exit code |
| 設計 elegance (30 思考法) | Gate B | findings + verdict |
| rubric 適合度 (採点) | Gate C | score 集計 |

衝突時の優先順位: A > B > C (契約 > elegance > 規範)。

## 適用先

- `run-plugin-package-check` (Gate A)
- `run-elegant-review` (Gate B)
- `assign-skill-design-evaluator` (Gate C)

## アンチパターン

- 1 ゲートで複数次元を採点する (検出粒度と修正粒度が一致しない)
- ゲート間で findings を握りつぶす (proposer ≠ approver 違反)
- Gate B / C で write を許す (read-only 強制で Sycophancy 予防)。write は別 step に分離

## 関連

- 25 章 §runbook Step 5 / 5.5 / 6
- 35 章 § 3 層メタモデル (Layer 2 = Review-level)
- ANAL-001 di-quartet (ref / lookup / assign / run の役割四重奏)
