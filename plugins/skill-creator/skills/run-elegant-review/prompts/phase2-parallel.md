# Prompt: phase2-parallel

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | phase2-parallel |
| skill | run-elegant-review |
| responsibility | Phase2 (3 エージェント並列 30 paradigm findings 生成) |
| layers_covered | [L0, L1, L2] |
| output_schema | ./schemas/phase-output.schema.json#/definitions/phase2_output |
| reproducible | true (read-only) |
| parallel | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 3 エージェントは互いの中間結果を参照しない
  - 目的: 思考法の独立性を担保
  - 背景: 相互参照は paradigm 多様性を均質化する
- 編集禁止、Read/Glob/Grep のみ
  - 目的: 観察フェーズの read-only 保証継続
  - 背景: 編集混在は採点バイアスを生む
- 問題なしの条件は `issues: []` で明示
  - 目的: 省略と未評価の区別
  - 背景: 黙示の skip は false-pass を生む

### 1.2 倫理ガード
- 他エージェントの出力を覗かない
  - 目的: 独立評価の確保
  - 背景: のぞき見は多様性の損失

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: Phase1 raw_observations を入力に、3 エージェント並列で 30 件 paradigm_findings を生成
- 非担当: バイアスリセット (Phase1)、改善パッチ (Phase3)

### 2.2 ドメインルール
- 3 エージェント構成 (正本: `./references/thought-methods.yaml`、配分 A2=10 / A3=9 / A4=11):
  - `elegant-logical-structural-analyst`: 10 paradigm (critical / deduction / induction / abduction / vertical / decomposition / mece / two-axis / process / why)
  - `elegant-meta-divergent-analyst`: 9 paradigm (meta / abstraction / double-loop / brainstorming / lateral / paradox / analogy / if / naive)
  - `elegant-system-strategic-analyst`: 11 paradigm (systems / causal / causal-loop / trade-on / plus-sum / value-proposition / strategic / kaizen / hypothesis / issue / kj)
- 各 finding に `observations(>=1) / issues / score` を含む
- 具体値は `variable_abstraction[]` に分離し `{{VAR}}` 形式で抽象化

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| phase1_output | path | yes | raw_observations.json |
| paradigms_ref | path | yes | ./references/30-paradigms-full.md |
| conditions_ref | path | yes | ./references/4-conditions.json |
| variable_contract | path | yes | ./references/variable-template-contract.md |
| findings_schema | path | yes | ./schemas/findings.schema.json |

### 2.4 出力契約
- schema: `./schemas/phase-output.schema.json#/definitions/phase2_output`
- 各 paradigm_finding: `./schemas/findings.schema.json#/definitions/paradigm_finding` 準拠
- 必須: paradigm_findings (合計 30) / variable_abstraction[]

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| paradigms | ./references/30-paradigms-full.md | 思考法レンズ適用時 |
| conditions | ./references/4-conditions.json | C1-C4 verdict 付与時 |
| contract | ./references/variable-template-contract.md | 変数化時 |

### 3.2 外部ツール / API
- `scripts/validate-paradigm-coverage.py` — count==30 確認
- `scripts/build-paradigm-scorecard.py` — matrix 生成

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- paradigm count != 30 → 該当エージェント再実行
  - 目的: 30 思考法の網羅性確保
  - 背景: 欠落は採点 bias を生む
- 他エージェント参照検出 → exit 1
  - 目的: 独立性の強制
  - 背景: 参照は paradigm 多様性を均質化

### 4.2 観測 / ロギング
- 出力先: `findings.json`

### 4.3 セキュリティ
- 対象ファイルを編集しない (read-only)

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- `elegant-logical-structural-analyst` / `elegant-meta-divergent-analyst` / `elegant-system-strategic-analyst` (3 並列起動)

### 5.2 推論手順 (再現可能)
1. 担当思考法のレンズで対象を読み、観察を列挙 (L0)
2. C1-C4 ごとに verdict を付け、issues を `severity / bucket / recommended_intervention` 付きで記録 (L1)
3. 具体値を `variable_abstraction` に登録し source_trace を残す (L2)
4. (orchestrator 責務) 集約後 `validate-paradigm-coverage.py` を実行し count==30 を確認 — **これは並列 agent ローカルではなく `workflow-manifest.json` の `phase2-exit` hook の責務**。各 agent は自分の findings 出力のみを担当する
5. (orchestrator 責務) `build-paradigm-scorecard.py` で matrix を生成 — **同じく `phase2-exit` hook 側で実行**。並列 agent 内で実行すると 3 重実行と中間結果共有を誘発するため禁止

> **責務直交**: workflow-manifest.json `exit[phase2-exit].command` と論理同一。step4/5 を agent 内で実行する古い記述は廃止 (G5)。

### 5.3 自己検証 checklist
- [ ] paradigm_coverage: 担当思考法をすべて埋めた (9 or 12)
- [ ] condition_matrix: 各 finding で C1-C4 全てに言及
- [ ] issue_structure: severity / bucket / recommended_intervention が揃う
- [ ] variable_extracted: 具体値が `{{VAR}}` で variable_abstraction に登録
- [ ] independence: 他エージェント出力を参照していない
- [ ] determinism: 同 phase1_output 再実行で findings の (paradigm, observations) が並び順含め一致

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-elegant-review (Phase2, Phase1 完了後)
- 後続 phase: phase3-execute

### 6.2 並列性
- 3 エージェント完全独立並列 (context-fork 必須)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- `findings.json` + paradigm-scorecard matrix

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

各エージェントは独立に担当 paradigm のレンズで `{{phase1_output}}` を観察し、
C1-C4 verdict を付与し、具体値を `variable_abstraction` に登録する。
集約後 30 件で `validate-paradigm-coverage.py` / `build-paradigm-scorecard.py` を実行する。
他エージェントの中間結果を覗かない (検出時 exit 1)。

出力は `./schemas/phase-output.schema.json#/definitions/phase2_output` 準拠の JSON のみ。
余計な前置き・後書き・思考過程出力は禁止。
