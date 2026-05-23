# Prompt: phase1-reset

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | phase1-reset |
| skill | run-elegant-review |
| responsibility | Phase1 (バイアスリセット + 素観察) |
| layers_covered | [L0, L1, L2] |
| output_schema | ./schemas/phase-output.schema.json#/definitions/phase1_output |
| reproducible | true (read-only) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- read-only ツール (Read/Glob/Grep) のみ使用
  - 目的: 観察フェーズの中立性確保
  - 背景: 編集が混在すると採点バイアスを生む
- rubric / findings 構造に触れない
  - 目的: Phase2 の独立採点を保護
  - 背景: 先行構造化は思考法多様性を潰す
- 採点や C1-C4 verdict は Phase2 に委ねる
  - 目的: 責務単一性の維持
  - 背景: 観察と評価の混在は再現性を破壊

### 1.2 倫理ガード
- 既存 rubric の言葉を観察に持ち込まない
  - 目的: フレーム効果の排除
  - 背景: 既存語彙は新規発見を抑制する

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 対象 (`{{target_type}}` @ `{{target_path}}`) を素のまま観察し、事実/仮定/変数化候補を抽出
- 非担当: 採点 (Phase2)、改善パッチ (Phase3)

### 2.2 ドメインルール
- 第一印象の懸念を「事実」と「仮定」に分けて記録
- 固有名詞・固定パス・固定 URL・固定 owner を kind 付きで variable_candidates にマーク
- in_scope / out_of_scope を明示区別

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| target_type | string | yes | 対象種別 (skill/agent/script) |
| target_path | string | yes | 対象パス |
| review_workspace | path | yes | 観察ログ保存先 |
| variable_contract | path | yes | ./references/variable-template-contract.md |

### 2.4 出力契約
- schema: `./schemas/phase-output.schema.json#/definitions/phase1_output`
- 必須: facts / assumptions / variable_candidates / scope (in/out)

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| contract | ./references/variable-template-contract.md | 変数化候補マーク時 |

### 3.2 外部ツール / API
- Read / Glob / Grep のみ (編集系禁止)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 編集系ツール呼び出し検出 → 即 exit 1
  - 目的: read-only 保証の強制
  - 背景: 観察フェーズでの編集は採点を汚染する

### 4.2 観測 / ロギング
- 出力先: `review_workspace/raw_observations.json`

### 4.3 セキュリティ
- 対象ファイルを編集しない (read-only)
  - 目的: 元状態の保存
  - 背景: Phase3 で diff を取るための基準

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- `../../agents/elegant-reset-observer.md` (context-fork 推奨)

### 5.2 推論手順 (再現可能)
1. `target_path` を Read/Glob し、目的・スコープ・関係者・既知制約を列挙 (L0)
2. 第一印象の懸念を「事実」と「仮定」に分けて記録 (L1)
3. 固有名詞・固定パス・固定 URL・固定 owner を kind 付きで variable_candidates にマーク (L2)
4. in_scope / out_of_scope を区別して記録
5. `./schemas/phase-output.schema.json#/definitions/phase1_output` に従い出力

### 5.3 自己検証 checklist
- [ ] bias_reset: 既存 rubric の言葉を観察に持ち込まなかった
- [ ] read_only: 対象ファイルを編集しなかった
- [ ] fact_assumption_split: 事実と仮定を明示分離
- [ ] variable_candidates: 変数化候補を kind 付きで列挙
- [ ] scope_explicit: in_scope / out_of_scope を区別
- [ ] determinism: 同 target_path で facts が並び順含め一致 (sort 安定化)

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-elegant-review (Phase1)
- 後続 phase: phase2-parallel

### 6.2 並列性
- 単発実行 (Phase2 の前段として直列)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- `raw_observations.json` (構造データ + 自然文)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

read-only で `{{target_path}}` を観察し、`facts / assumptions / variable_candidates / scope`
を抽出する。編集系ツールは使用禁止 (検出時 exit 1)。採点・改善提案はしない。

出力は `./schemas/phase-output.schema.json#/definitions/phase1_output` 準拠の JSON のみ。
余計な前置き・後書き・思考過程出力は禁止。
