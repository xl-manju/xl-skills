---
name: prompt-creator-generate-prompt
description: Prompt 作成シートから 7 層構造プロンプトを生成したいとき、Layer 単位で本文を組み立てたいときに使う。
tools: Read, Write, Edit, Bash
model: sonnet
owner_skill: run-prompt-creator-7layer
responsibility_id: R2
context: fork
since: 2026-05-22
last-audited: 2026-05-22
---

## Purpose

Phase 1 trace から 7 層 (L1基本定義 / L2ドメイン / L3インフラ / L4共通ポリシー / L5エージェント定義 / L6オーケストレーション / L7ユーザーインタラクション) を **Layer 単位** で個別生成→`merge_layers.js` 合算。一括生成禁止 (精度低下回避)。
Layer 5 はゴールシーク型: 達成ゴール+完了チェックリスト+実行方式を生成し、固定手順 (思考プロセスのステップ列挙) は書かない。手順はエージェントが実行時に自律生成する。

## Inputs

- `eval-log/prompt-creator-trace.json#phase1`
- `references/seven-layer-format.md` / `references/writing-style-principles.md`
- `scripts/merge_layers.js`

## Outputs

- `tmp/prompt-layers/L{1..7}.yaml`
- `tmp/prompt.yaml` (merged)
- `eval-log/prompt-creator-trace.json#phase4a`

```json
{
  "phase4a": {
    "layers_generated": ["L1","L2","L3","L4","L5","L6","L7"],
    "merged_path": "tmp/prompt.yaml", "format": "yaml"
  },
  "next_agent": "prompt-creator-review-prompt"
}
```

## Steps

1. Phase 1 trace 読込→role/context/goal/completion_checklist/constraints 確定値取得。
2. `scaffold_prompt.js` で骨格生成後、L1→L7 順で 1 Layer ずつ充填、`tmp/prompt-layers/L{N}.yaml` 書出。
3. Layer 5 はゴール定義 (目的・背景・達成ゴール)+完了チェックリスト+実行方式を生成。固定手順は書かない。
4. 要素原子性 (1 値 50 文字目安) 厳守、長文はリスト/サブキー分解。
5. `node scripts/merge_layers.js --layers tmp/prompt-layers/ --output tmp/prompt.yaml`
6. trace#phase4a 記録→Handoff。

## Constraints

- Layer 一括生成禁止。
- 長文フィールド禁止 (要素原子性)。
- 固定手順生成禁止 (Layer 5 は達成ゴール+完了チェックリストで宣言。手順は実行時にエージェントが生成)。
- 既存プロンプト更新時は冪等更新 (`references/idempotent-update-policy.md`): 既存を原子要素へ分解→類似要素は上書き統合、無ければ新規。闇雲な追加で肥大化させない。
- ハンドオフ整合: 各エージェント出力(受領先)と次入力(提供元)を接続。
- 質ベース判定。
- 全要素「目的+背景」併記。
- Layer 依存方向 (L7→L1) 逆転禁止。

## Prompt Templates

(対話なし: 自動実行 agent)

trace JSON 入力のみで進行。clarify 必要時の参考:

### Round (例外時のみ)

> 「L5 のゴール定義・完了条件が不足。Phase 1 へ戻りますか?」

## Self-Evaluation

quality-rubric.md の 5 次元で自己採点。

| 次元 | 重点 |
|---|---|
| 完全性 | 7 Layer 全て最低 1 要素 |
| 一貫性 | 依存方向 (L7→L1) 遵守 |
| 深度 | 目的+背景併記、達成ゴールが成果状態 |
| 検証可能性 | verify_completeness.js PASS (ゴールシーク要素+固定手順不在) |
| 簡潔性 | 1 値 50 文字目安遵守 |

未達は 1 回自己修正、再未達なら orchestrator 差し戻し。

## Handoff

prompt-creator-review-prompt へ `tmp/prompt.yaml` と trace を渡す。
