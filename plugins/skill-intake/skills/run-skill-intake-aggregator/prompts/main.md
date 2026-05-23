# Prompt: R0-orchestrate-11-aggregate-phases

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | main |
| skill | run-skill-intake-aggregator |
| responsibility | R0-orchestrate-11-aggregate-phases (top-level entry / R1 詳細は prompts/R1.md) |
| layers_covered | [L2, L4, L5, L6] |
| output_schema | schemas/intake-final.schema.json |
| reproducible | true (workflow-manifest.json の R1-R11 を順序通り起動) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 各 R-phase の詳細責務は `prompts/R<n>.md` に分割する (本ファイルは entry のみ)。
- R10 で render、R11 で Notion 公開 (fidelity-guard 経由) を行う順序を変えない。

### 1.2 倫理ガード
- 固有名詞 (社名 / 個人名 / 固定 page_id) を成果物に直書きしない (variable_abstraction)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 非エンジニアの skill 要望対話を入力に R1-R11 を順次実行し、intake.md / intake.json / Notion ページを生成する top-level entry。
- 非担当: 各 phase の業務ロジック (それぞれ `prompts/R<n>.md` または下位 intake skill に委譲)。

### 2.2 ドメインルール
- quality-rubric.md に基づき自己採点し、`quality_score` を validation に書き出す。
- workflow-manifest.json の `fatal_exit_codes` (2, 3) を受け取ったら即中断。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| initial-utterance | resource://user | yes | ユーザー初期発話 |
| handoff-contract | resource://run-skill-intake-aggregator/references/handoff-contract.md | yes | phase 間 schema |
| execution-contract | resource://run-skill-intake-aggregator/references/execution-contract.md | yes | 実行規約 |
| quality-rubric | resource://run-skill-intake-aggregator/references/quality-rubric.md | yes | 5 次元採点 |

### 2.4 出力契約
- schema: `schemas/intake-final.schema.json`
- 必須フィールド: `intake_md`, `intake_json`, `notion_url`, `validation.quality_score`

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| manifest | workflow-manifest.json | phase 順序の SoT |
| handoff-contract | references/handoff-contract.md | phase handoff 前 |
| quality-rubric | references/quality-rubric.md | 自己採点時 |
| R1 詳細 | prompts/R1.md | brief-aggregation 詳細責務 |

### 3.2 外部ツール / API
- 下位 intake skill 群 (kickoff / interview / visualize / finalize / next-action / option-catalog)
- Notion API (Keychain 経由、R11 phase で publisher が扱う)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 任意 R-phase が `fatal_exit_codes` を返した → orchestrator-trace.json に error を残し中断。
- quality_score が rubric 閾値未満 → exit 1 (warn)、validation に詳細を残す。

### 4.2 観測 / ロギング
- 全 R-phase の入出力パス・exit code・所要時間を `orchestrator-trace.json` に残す。

### 4.3 セキュリティ
- Notion API トークンは Keychain 経由のみ取得。orchestrator のログ・成果物に絶対に書かない。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- `@intake-aggregator-orchestrator` (非対話、各 R-phase を起動)

### 5.2 推論手順 (再現可能)
1. workflow-manifest.json の R1-R11 phases を順次起動する。
2. R1 は `prompts/R1.md` の詳細責務に従って構造化 brief を生成する。
3. R2-R11 は対応 references をロードし、各 phase の責務を遂行する。
4. R10 で render、R11 で Notion 公開 (fidelity-guard 経由) を行う。
5. quality-rubric.md に基づき自己採点し、`quality_score` を `validation` に書き出す。

### 5.3 自己検証 checklist
- [ ] 全 R-phase が PASS で完了し intake.md / intake.json を生成したか
- [ ] intake-final.schema.json に適合しているか
- [ ] quality_score が rubric 閾値以上か
- [ ] 固有名詞 (社名 / 個人名 / 固定 page_id) を直書きしていないか (variable_abstraction)
- [ ] determinism: workflow-manifest.json の phases を順序通り起動した orchestrator-trace.json が再実行で一致するか (phase 順 + 入出力パス)

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: `/intake` slash command / `run-skill-create` Step 1
- 後続 phase: skill-creator (`run-build-skill`) または `run-notion-intake-publish`

### 6.2 並列性
- 既定は R1→…→R11 の直列。並列実行可能 phase は dependsOn 見直し後に検討。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- intake.md (人間可読) + intake.json (機械可読) + Notion URL

### 7.2 言語
- 本文: 日本語 (R-id / schema key は英語のまま)

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`{{initial_utterance}}` を起点に `workflow-manifest.json` の R1-R11 を順序通り起動せよ。R1 は `prompts/R1.md` に従い brief.json を出力し、R2-R11 は対応 references をロードして各責務を実行する。任意 phase が fatal_exit_codes を返したら直ちに中断し orchestrator-trace.json に error を残すこと。全 phase PASS の場合のみ intake.md / intake.json / Notion URL を schemas/intake-final.schema.json 準拠で出力し、quality-rubric に基づく自己採点を validation に書き戻すこと。前置き禁止。
