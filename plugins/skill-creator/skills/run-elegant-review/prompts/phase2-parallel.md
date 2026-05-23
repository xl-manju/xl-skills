# Prompt: phase2-parallel

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | phase2-parallel |
| skill | run-elegant-review |
| responsibility | Phase2 (3エージェント並列 30 paradigm findings 生成) |
| layers_covered | [L0, L1, L2] |
| output_schema | ./schemas/phase-output.schema.json#/definitions/phase2_output |
| reproducible | true (read-only) |
| parallel | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 3 エージェントは互いの中間結果を参照しない (独立性確保)
- 編集禁止、Read/Glob/Grep のみ
- 問題なしの条件は issues: [] で明示 (省略禁止)

### 1.2 倫理ガード
- 他エージェントの出力を覗かない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: Phase1 raw_observations を入力に、3 エージェント並列で 30 件の paradigm_findings を生成
- 非担当: バイアスリセット (Phase1)、改善パッチ (Phase3)

### 2.2 ドメインルール
- 3 エージェント構成:
  - elegant-logical-structural-analyst: 9 paradigm (critical / deductive / inductive / abductive / vertical / decomposition / mece / two-axis / process)
  - elegant-meta-divergent-analyst: 9 paradigm (meta / abstraction / double-loop / brainstorming / lateral / paradox / analogy / what-if / beginners-mind)
  - elegant-system-strategic-analyst: 12 paradigm (system / causal-analysis / causal-loop / trade-on / positive-sum / value-proposition / strategic / why / improvement / hypothesis / issue / kj-method)
- 各 finding に observations(>=1), issues, score を含む
- 具体値は variable_abstraction[] に分離し `{{VAR}}` 形式で抽象化

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| phase1_output | path | yes | raw_observations |
| paradigms_ref | path | yes | ./references/30-paradigms-full.md |
| conditions_ref | path | yes | ./references/4-conditions.json |
| variable_contract | path | yes | ./references/variable-template-contract.md |
| findings_schema | path | yes | ./schemas/findings.schema.json |

### 2.4 出力契約
- schema: `./schemas/phase-output.schema.json#/definitions/phase2_output`
- 各 paradigm_finding: `./schemas/findings.schema.json#/definitions/paradigm_finding` 準拠
- 必須: paradigm_findings (合計 30)、variable_abstraction[]

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
- 他エージェント参照検出 → exit 1

### 4.2 観測 / ロギング
- findings.json として保存

### 4.3 セキュリティ
- 対象ファイルを編集しない (read-only)

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- elegant-logical-structural-analyst / elegant-meta-divergent-analyst / elegant-system-strategic-analyst (並列起動)

### 5.2 推論手順 (再現可能)
1. 担当思考法のレンズで対象を読み、観察を列挙 (L0)
2. C1-C4 ごとに verdict を付け、issues を severity/bucket/recommended_intervention 付きで記録 (L1)
3. 具体値を variable_abstraction に登録し source_trace を残す (L2)
4. 集約後 validate-paradigm-coverage.py を実行し count==30 を確認
5. build-paradigm-scorecard.py で matrix を生成

### 5.3 自己検証 checklist
- [ ] paradigm_coverage: 担当思考法をすべて埋めた (9 or 12)
- [ ] condition_matrix: 各 finding で C1-C4 全てに言及した
- [ ] issue_structure: severity / bucket / recommended_intervention が揃った
- [ ] variable_extracted: 具体値が `{{VAR}}` で variable_abstraction に登録された
- [ ] independence: 他エージェントの出力を参照していない
- [ ] determinism: 同 phase1_output 再実行で findings の (paradigm, observations) が並び順含め一致 (sort 安定化)

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-elegant-review (Phase2, Phase1 完了後)
- 後続 phase: phase3-execute

### 6.2 並列性
- 3 エージェント完全独立並列

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- findings.json + paradigm-scorecard matrix

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

各エージェントは独立に担当 paradigm のレンズで観察 → C1-C4 verdict → variable_abstraction
を実行し findings を出力する。集約後 30 件で validate / scorecard を生成。
出力は ./schemas/phase-output.schema.json#/definitions/phase2_output 準拠の JSON のみ。
余計な前置き・思考過程出力は禁止。
