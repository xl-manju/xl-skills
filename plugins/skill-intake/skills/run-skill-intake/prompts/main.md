# Prompt: R1-orchestrate-11-phases

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | main |
| skill | run-skill-intake |
| responsibility | R1-orchestrate-11-phases (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L2, L4, L5, L6] |
| output_schema | schemas/output.schema.json |
| reproducible | true (workflow-manifest.json の phases を順序通り起動) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 業務ロジックは orchestrator 内に書かない (各 phase の delegateSkill に委譲)。
- 任意 phase の FAIL でパイプライン全体を中断する (silent-fail 禁止)。

### 1.2 倫理ガード
- ユーザー入力は phase 1 でのみ取得。orchestrator が後付けで意図推測しない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: intake 11 phase を子 Skill / SubAgent に順次委譲する薄い orchestrator。
- 非担当: 5 軸ヒアリング、可視化、Notion 公開などの個別 phase ロジック。

### 2.2 ドメインルール
- 各 phase 出力は次 phase の入力 schema に適合すること (handoff-contract.md 準拠)。
- artifacts は 11 phase 全 PASS のときのみ書き出す (部分成果物の混乱回避)。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| initial-utterance | resource://user | yes | ユーザー初期発話 |
| handoff-contract | resource://run-skill-intake/references/handoff-contract.md | yes | phase 間 schema |
| workflow-sequence | resource://run-skill-intake/references/workflow-sequence.md | yes | 順序仕様 |

### 2.4 出力契約
- schema: `schemas/output.schema.json`
- 必須フィールド: `orchestrator_trace`, `artifacts.intake_md`, `artifacts.intake_json`, `artifacts.notion_url`

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| handoff-contract | references/handoff-contract.md | phase 間 handoff 直前 |
| workflow-sequence | references/workflow-sequence.md | phase 起動順を決めるとき |
| manifest | workflow-manifest.json | phase 定義の SoT |

### 3.2 外部ツール / API
- SubAgent / delegateSkill 起動 (workflow-manifest.json 駆動)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 任意 phase が FAIL → orchestrator-trace.json に error を記録し中断、exit 非 0。
- 中断後の再開は手動 (orchestrator は冪等な resume 機構を持たない)。

### 4.2 観測 / ロギング
- orchestrator-trace.json に各 phase の入出力パス、exit code、所要時間を残す。

### 4.3 セキュリティ
- Notion トークン等の secret は orchestrator のログに残さない (delegateSkill 内で扱う)。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- `@intake-orchestrator` (非対話、phase 起動のみ)

### 5.2 推論手順 (再現可能)
1. workflow-manifest.json の phases を順次起動する。
2. 各 phase の delegateSkill を起動し、出力 artifact のパスを受け取る。
3. handoff-contract.md に従い、次 phase に必要な入力のみを引き渡す。
4. 任意 phase が FAIL した場合は orchestrator-trace.json に error を記録し中断する。
5. 11 phase 完了後、intake.md / intake.json / Notion URL を `orchestrator-trace.artifacts` に書き出す。

### 5.3 自己検証 checklist
- [ ] 業務ロジックを orchestrator 内に書いていないか (薄さ維持)
- [ ] 各 phase の出力が次 phase の input schema に適合しているか
- [ ] FAIL 時に中断し、戻り先 phase を error に記録しているか
- [ ] 11 phase 全てが PASS した場合のみ artifacts.intake_md/intake_json を埋めているか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: `/intake` slash command または `run-skill-create` Step 1
- 後続 phase: `run-notion-intake-publish` (公開) または skill-creator 引き渡し

### 6.2 並列性
- 既定は直列。並列実行可能 phase (例: P6 visualize と P7 quality) は dependsOn 整理後に検討。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- orchestrator-trace.json + artifacts (intake.md / intake.json / notion-url)

### 7.2 言語
- 本文: 日本語 (phase id / schema key は英語)

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`{{initial_utterance}}` を起点に `workflow-manifest.json` の phases を順次起動し、各 phase の出力パスを次 phase の入力に handoff せよ。FAIL を観測したら直ちに中断し、`orchestrator-trace.json` に error を記録すること。全 phase PASS の場合のみ artifacts を埋めて schemas/output.schema.json 準拠の JSON を出力せよ。前置き・後書き禁止。
