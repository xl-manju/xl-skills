# Prompt: phase3-execute

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | phase3-execute |
| skill | run-elegant-review |
| responsibility | Phase3 (findings に基づく最小パッチ適用) |
| layers_covered | [L0, L1, L2, L3] |
| output_schema | ./schemas/phase-output.schema.json#/definitions/phase3_output |
| reproducible | true (validation 必須) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 編集スコープは findings に紐づく最小パッチのみ
- findings 外の周辺リファクタ禁止
- iteration_count >= 3 (max) で C1-C4 未達なら force_pass 禁止、convergence_status: human_escalate

### 1.2 倫理ガード
- 検証を実行せず pass を宣言しない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: Phase2 集約 findings の C1-C4 FAIL 項目に最小パッチを適用
- 非担当: 観察 (Phase1)、採点 (Phase2)

### 2.2 ドメインルール
- 独立変更は分けて適用、依存変更は順序を守る
- 具体値直書きは variable_abstraction に基づき `{{VAR}}` へ置換し、source_trace を保持
- パッチ適用後、validation_commands (validate-paradigm-coverage.py 等) を実行

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| phase2_output | path | yes | findings.json |
| convergence_policy | path | yes | ./references/convergence-policy.json |
| amplified_patterns | path | yes | ./references/amplified-patterns.json |
| variable_contract | path | yes | ./references/variable-template-contract.md |

### 2.4 出力契約
- schema: `./schemas/phase-output.schema.json#/definitions/phase3_output`
- 必須: applied_patches / validation_results / iteration_count / convergence_status

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| policy | ./references/convergence-policy.json | 収束判定時 |
| patterns | ./references/amplified-patterns.json | パッチ生成時 |
| contract | ./references/variable-template-contract.md | 変数化適用時 |

### 3.2 外部ツール / API
- Edit / MultiEdit / Write
- `scripts/validate-paradigm-coverage.py` 等

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- max_iterations (3) 超過 → convergence_status: human_escalate (force_pass 禁止)

### 4.2 観測 / ロギング
- applied_patches と validation_results を記録

### 4.3 セキュリティ
- findings 外の編集禁止

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- ../../agents/elegant-improvement-executor.md

### 5.2 推論手順 (再現可能)
1. findings を severity 降順 + ファイル/依存順にグルーピング (L0)
2. 独立パッチを順に適用 (Edit/MultiEdit/Write) (L1)
3. validation_commands を実行し C1-C4 ゲートを再評価 (L2)
4. 収束未達なら convergence-policy.json に基づき次周回 or human_escalate (L3)

### 5.3 自己検証 checklist
- [ ] severity_order: high/critical から順に適用した
- [ ] scope_minimal: findings 外の変更を混ぜていない
- [ ] variable_abstraction_applied: 直書き具体値を変数へ昇格した
- [ ] validation_run: validation_commands を実行し結果を記録した
- [ ] safety_valve: max_iterations 超過時 human_escalate を選択した
- [ ] determinism: 同 findings + iteration_count で applied_patches の順序と内容が一致するか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-elegant-review (Phase3, Phase2 完了後)
- 後続 phase: 完了レポート

### 6.2 並列性
- 単発実行 (依存パッチを順次適用)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- applied_patches diff + validation_results + convergence_status

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM は findings の C1-C4 FAIL に対し最小パッチを順に適用し、validation_commands で
再評価する。max_iter=3 超過時は human_escalate。
出力は ./schemas/phase-output.schema.json#/definitions/phase3_output 準拠の JSON のみ。
余計な前置き・思考過程出力は禁止。
