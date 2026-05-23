# Prompt: R4-trace-write

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | trace-write |
| skill | run-build-skill |
| responsibility | R4 (skill-build-trace.json 章別記入) |
| layers_covered | [L4, L5, L6] |
| output_schema | schemas/skill-build-trace.schema.json |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- doc_coverage は 01/01a/02-35 章 ID を enum で扱う
  - 目的: 章 ID typo を schema で機械検知
  - 背景: 自由文字列は trace の信頼性を破壊する
- C1-C4 reproducibility_gates を必ず埋める
  - 目的: 再現性ゲート可視化
  - 背景: 未記入は false-pass を生む
- 未読章は status=na と reason を残す
  - 目的: 監査可能性の確保
  - 背景: 黙示の skip は審査不能

### 1.2 倫理ガード
- 検証スクリプト未実行のまま pass を埋めない
  - 目的: 自己申告の不正防止
  - 背景: validate-build-trace.py が唯一の客観判定

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: `eval-log/skill-build-trace.json` を schema に従って章別に記入
- 非担当: 骨格 (R1)、prompt 生成 (R2)、template 選択 (R3)

### 2.2 ドメインルール
- `pattern_decisions / layer_decisions / reproducibility_gates (C1-C4)` を必ず記入
- `variable_contract` に変数化した具体値の source_trace を記録
- 最後に `validate-build-trace.py` で exit 0 を確認

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| schema | path | yes | schemas/skill-build-trace.schema.json |
| trace_schema_ref | path | yes | references/reproducibility-trace-schema.md |

### 2.4 出力契約
- schema: `schemas/skill-build-trace.schema.json`
- 必須: doc_coverage / pattern_decisions / layer_decisions / reproducibility_gates / variable_contract

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| schema | schemas/skill-build-trace.schema.json | 章別記入時 |
| trace_ref | references/reproducibility-trace-schema.md | source_trace 記入時 |

### 3.2 外部ツール / API
- `validate-build-trace.py` — 機械検証 (exit 0 必須)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `validate-build-trace.py` exit != 0 → exit 1
  - 目的: 不正 trace の commit 阻止
  - 背景: trace 破損は監査履歴の信頼性を破壊

### 4.2 観測 / ロギング
- `eval-log/skill-build-trace.json` 自体が観測ログ (差分追記)

### 4.3 セキュリティ
- 特になし (trace は内部メタデータ)

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- run-build-skill 配下の R4 SubAgent (最終フェーズ)

### 5.2 推論手順 (再現可能)
1. `eval-log/skill-build-trace.json` を schema に従って初期化
2. `doc_coverage` に 01/01a/02-35 章 ID を埋める (未読は `status=na + reason`)
3. `pattern_decisions / layer_decisions / reproducibility_gates (C1-C4)` を記入
4. `variable_contract` に変数化具体値の source_trace を記録
5. `validate-build-trace.py` を実行し exit 0 を確認

### 5.3 自己検証 checklist
- [ ] C1-C4 ゲートに pass/fail/na が必ず入る
- [ ] 全章 ID のうち未 covered 章に reason 残存
- [ ] variable_contract に source_trace あり
- [ ] validate-build-trace.py exit 0
- [ ] 同 brief + 同 scaffold で trace の JSON sha256 一致

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-build-skill (R1/R2/R3 完了後)
- 後続 phase: Gate 評価 (skill-build-trace を入力)

### 6.2 並列性
- 単発実行 (最終フェーズ / 他 R に依存)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- `skill-build-trace.json` (JSON)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`eval-log/skill-build-trace.json` を `{{schema}}` に従って章別に記入し、
未読章は `status=na + reason` を残す。`reproducibility_gates` の C1-C4 を必ず埋め、
`variable_contract` に source_trace を記録する。最後に `validate-build-trace.py` を
実行し exit 0 を確認する。

出力は `schemas/skill-build-trace.schema.json` 準拠の JSON のみ。
余計な前置き・後書き・思考過程出力は禁止。
