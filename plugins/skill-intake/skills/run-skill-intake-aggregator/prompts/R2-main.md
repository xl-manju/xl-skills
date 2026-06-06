# Prompt: R0-orchestrate-11-aggregate-phases

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | main |
| skill | run-skill-intake-aggregator |
| responsibility | R0-orchestrate-11-aggregate-phases (top-level entry / R1 詳細は prompts/R1.md) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
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

#### 動的入力 (Runtime Inputs) — ホストから実行時注入

| variable | type | required | 説明 |
|---|---|---|---|
| `initial_utterance` | string (user utterance) | yes | ユーザーの初期発話 (slash command 引数または対話入力)。R1 phase の起点となる。`--page-url` / `--page-id` / `--database-id` が含まれる場合は Notion publish の明示指定として Phase 11 まで保持する。 |

#### 静的参照リソース

| field | type | required | 説明 |
|---|---|---|---|
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

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- `@intake-aggregator-orchestrator` (非対話、context-fork して各 R-phase を分離 context で起動)

### 5.2 ゴール定義
- 目的: 非エンジニアの skill 要望を、再現可能な workflow (R1-R11) を通して intake.md / intake.json / Notion ページに結実させること。
- 背景: phase ごとに責務を分割し下位 skill に委譲することで、各 phase の品質を独立検証でき、改修コストと回帰リスクを下げる。
- 達成ゴール: workflow-manifest.json の全 R-phase が PASS で完了し、intake-final.schema.json 準拠の成果物が生成され、rubric 閾値以上の `quality_score` が validation に記録されている状態。

### 5.3 完了チェックリスト (停止条件)
- [ ] 全 R-phase が PASS で完了し intake.md / intake.json / Notion URL が揃っている
- [ ] intake-final.schema.json に適合している (additionalProperties:false)
- [ ] `quality_score` が quality-rubric.md 閾値以上で `validation` に書き戻されている
- [ ] 固有名詞 (社名 / 個人名 / 固定 page_id) が成果物に直書きされていない (variable_abstraction)
- [ ] orchestrator-trace.json が再実行で phase 順 + 入出力パスとも一致する (determinism)

### 5.4 実行方式
- 固定手順を持たない。完了チェックリストを唯一の停止条件とし、未充足項目→次に起動すべき R-phase をその都度選択→実行→trace 更新→自己評価を反復する (上限: Layer 4 最大反復回数)。
- 各 R-phase は分離 context (SubAgent) で起動し、親へは最終差分と exit code のみ返却 (中間ログは親 context に流さない)。
- 逸脱時: 上限到達または fatal_exit_codes 連続発生時は Layer 4.1 規約で中断し、orchestrator-trace.json に error を残す。

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: `/intake` slash command / `run-skill-create` Step 1
- 後続 phase: `run-notion-intake-publish` を完了した後、必要な場合のみ skill-creator (`run-build-skill`)

### 6.2 ハンドオフ / 並列性
- 直列: 各 R-phase の出力 (受領先 = 次 phase) を後続 phase の入力 (提供元 = 前 phase) に workflow-manifest.json 経由で接続。
- 並列: 既定は R1→…→R11 の直列。dependsOn が独立な phase に限り並列起動を検討 (atomic write 競合がない場合のみ)。
- 後続接続: intake.json 生成後は必ず `run-notion-intake-publish` にハンドオフし、Notion publish 成功 (`notion-log.json.status=="published"`) を確認してから `run-build-skill` など skill-creator 側へ渡す。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- intake.md (人間可読) + intake.json (機械可読) + Notion URL

### 7.2 言語
- 本文: 日本語 (R-id / schema key は英語のまま)

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

動的入力 `initial_utterance` の値 (ユーザー初期発話) を起点に `workflow-manifest.json` の R1-R11 を順序通り起動せよ。R1 は `prompts/R1.md` に従い brief.json を出力し、R2-R11 は対応 references をロードして各責務を実行する。任意 phase が fatal_exit_codes を返したら直ちに中断し orchestrator-trace.json に error を残すこと。全 phase PASS の場合のみ intake.md / intake.json / Notion URL を schemas/intake-final.schema.json 準拠で出力し、quality-rubric に基づく自己採点を validation に書き戻すこと。前置き禁止。
