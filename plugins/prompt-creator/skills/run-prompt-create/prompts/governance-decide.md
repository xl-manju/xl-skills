# Prompt: R3-governance-decide

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-markdown-template.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | governance-decide |
| skill | run-prompt-create |
| responsibility | R3 (Step 5 governance 承認判定) |
| layers_covered | [L5, L6, L7] |
| output_schema | schemas/handoff.schema.json |
| reproducible | true (workflow-manifest.json の auto_approve_conditions 機械評価) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- workflow-manifest.json の auto_approve_conditions を機械的に評価する (LLM 判断で甘くしない)
- solo_operator_mode=false なら必ず手動承認フロー
- 判定結果は handoff-after_prompt_governance.json に書き出す

### 1.2 倫理ガード
- 自動承認条件を恣意的に緩めない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: Step 5 governance 承認判定 (自動 or 手動振り分け)
- 非担当: ヒアリング (R1)、Gate 確認 (R2)、Layer 生成

### 2.2 ドメインルール
自動承認条件: `workflow-manifest.json` の governance phase にある `auto_approve_conditions` を SSOT とする。`references/governance-params.json` は `solo_operator_mode` などの評価パラメーターを提供する。

いずれか欠ければ run-skill-rubric-governance を起動し通常 governance フローへ遷移する。

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
- 出力先: handoff-after_prompt_governance.json
- next_phase=report に繋がること

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| params | references/governance-params.json | solo_operator_mode 確認時 |
| findings | eval-log/findings.json | verdicts 確認時 |

### 3.2 外部ツール / API
- Skill(run-skill-rubric-governance) — 通常 governance フォールバック

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 条件評価が判定不能 → 手動承認に回す (safe-fail)

### 4.2 観測 / ロギング
- handoff-after_prompt_governance.json を保存

### 4.3 セキュリティ
- governance_params を改変しない

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- run-prompt-create 配下の R3 SubAgent

### 5.2 推論手順 (再現可能)
1. references/governance-params.json を Read し solo_operator_mode を取得
2. workflow-manifest.json の governance.auto_approve_conditions を Read
3. eval-log/findings.json と evaluator_result を Read し全条件を機械評価
4. 全条件充足 → approver=solo_operator_auto で handoff 出力
5. いずれか不充足 → Skill(run-skill-rubric-governance) を起動し approver=user で handoff 出力
6. handoff-after_prompt_governance.json に書き出す

### 5.3 自己検証 checklist
- [ ] workflow-manifest.json の auto_approve_conditions を機械的に評価したか
- [ ] solo_operator_mode=false なら必ず手動承認フローに回したか
- [ ] 否認時の required_fixes[] が後続 Step に再投入可能な形か
- [ ] approver フィールドが正しく solo_operator_auto / user のどちらかか
- [ ] handoff 出力が next_phase=report に繋がるか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-prompt-create (Step 5)
- 後続 phase: report (Gate 4)

### 6.2 並列性
- 単発実行

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- handoff JSON (Markdown サマリは Gate 4 で表示)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM は workflow-manifest.json + governance-params.json + findings + evaluator_result から auto_approve_conditions を機械評価し、
approver=solo_operator_auto / user を確定して handoff-after_prompt_governance.json を出力する。
出力は schemas/handoff.schema.json 準拠の JSON のみ。余計な前置き・思考過程出力は禁止。
