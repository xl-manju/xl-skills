# Prompt: R3-governance-decide

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | governance-decide |
| skill | run-skill-create |
| responsibility | R3 (Step 6 governance 承認判定) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/handoff.schema.json |
| reproducible | true (4 条件機械評価) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール

- **CONST_001 (機械評価)**: 4 条件を機械的に評価する (LLM 判断で甘くしない)
  - **目的**: 承認基準の再現性を担保するため
  - **背景**: LLM 判断は同一入力に対しブレが出るため、論理式に固定
- **CONST_002 (手動 fallback)**: solo_operator_mode=false なら必ず手動承認フロー
  - **目的**: チーム運用での proposer ≠ approver 原則を守るため
  - **背景**: 単独運用前提の自動承認は組織運用で逸脱を招く
- **CONST_003 (handoff 保存固定)**: 判定結果は `handoff-after_governance.json` に書き出す

### 1.2 倫理ガード

- 自動承認条件を恣意的に緩めない
- governance_params を改変しない (read-only)

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)

- 担当: Step 6 governance 承認判定 (自動 or 手動振り分け)
- 非担当: ヒアリング (R1)、Gate 確認 (R2)、改善実行

### 2.2 ドメインルール

自動承認条件 (全て満たす場合のみ `solo_auto_approved`):

| no | 条件 |
|---|---|
| 1 | solo_operator_mode == true |
| 2 | stable_frozen == true (安定版凍結済み) |
| 3 | newly_failing == 0 |
| 4 | LLM-reviewer pass (findings の verdicts 全て PASS or N/A) |

いずれか欠ければ `Skill(run-skill-rubric-governance)` を起動し通常 governance フローへ遷移する。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| phase | string | yes | governance |
| manifest | path | yes | workflow-manifest.json |
| governance_params | path | yes | references/governance-params.json |
| findings | path | yes | eval-log/findings.json |
| evaluator_result | path | yes | eval-log/docs/<NN>-<timestamp>.json |

### 2.4 出力契約

- schema: `schemas/handoff.schema.json` (approver=solo_operator_auto または user)
- 出力先: `handoff-after_governance.json`
- next_phase=report に繋がること

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| params | references/governance-params.json | solo_operator_mode 確認時 |
| findings | eval-log/findings.json | verdicts 確認時 |
| evaluator | eval-log/docs/<NN>-<timestamp>.json | newly_failing 確認時 |

### 3.2 外部ツール / API

- `Skill(run-skill-rubric-governance)` — 通常 governance フォールバック

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動

- 条件評価が判定不能 → 手動承認に回す (safe-fail)
- governance_params 不在 → exit 3 (structural error)

### 4.2 観測 / ロギング

- `handoff-after_governance.json` を保存
- stderr に 4 条件の評価結果を記録

### 4.3 セキュリティ

- governance_params を改変しない
- approver=solo_operator_auto を任意に付与しない (条件成立時のみ)

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent

- run-skill-create 配下の R3 SubAgent
- context-fork: 不要 (純粋判定ロジック)

### 5.2 推論手順 (再現可能)

1. `references/governance-params.json` を Read し solo_operator_mode を取得
2. `eval-log/findings.json` と evaluator_result を Read し 4 条件を機械評価
3. 4 条件全充足 → approver=solo_operator_auto で handoff 出力
4. いずれか不充足 → `Skill(run-skill-rubric-governance)` を起動し approver=user で handoff 出力
5. `handoff-after_governance.json` に書き出す

### 5.3 自己検証 checklist

- [ ] 4 条件を機械的に評価したか (LLM 判断で甘くしていないか)
- [ ] solo_operator_mode=false なら必ず手動承認フローに回したか
- [ ] 否認時の required_fixes[] が後続 Step に再投入可能な形か
- [ ] approver フィールドが正しく solo_operator_auto / user のどちらか
- [ ] handoff 出力が next_phase=report に繋がるか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続

- 呼び出し元: `run-skill-create` (Step 6)
- 後続 phase: report (Gate 4)

### 6.2 並列性

- 単発実行 (同一 phase に複数判定を許さない)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式

- handoff JSON (Markdown サマリは Gate 4 で表示)

### 7.2 言語

- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM は `{{governance_params}}` + `{{findings}}` + `{{evaluator_result}}` から 4 条件を機械評価し、approver=solo_operator_auto / user を確定して `handoff-after_governance.json` を出力する。Layer 5.2 の手順を逐次実行する。出力は `schemas/handoff.schema.json` 準拠の JSON のみ。前置き・後書き・思考過程出力は禁止。
