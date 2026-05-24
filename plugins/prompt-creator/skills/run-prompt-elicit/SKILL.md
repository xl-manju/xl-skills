---
name: run-prompt-elicit
description: プロンプト要望を対話でヒアリングして prompt-brief.json を生成するとき、target_skill と responsibility_id を確定するときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[--topic <text>] [--target-skill <skill_name>] [--responsibility-id <R-id>] [--batch]"
arguments: [topic, target_skill, responsibility_id, batch]
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - AskUserQuestion
  - Task
kind: run
version: 2.1.0
effect: local-artifact
owner: team-platform
contract:
  intent: プロンプト要望を対話で構造化し、後続 build/evaluate が依拠できる prompt-brief.json を確定するため、Step 1 ヒアリング責務を提供する。
  interface:
    inputs: [topic, target_skill, responsibility_id, batch]
    outputs: [prompt-brief.json, hearing-result.json]
  invariant:
    - 質問は 1 セッション 3-5 問 + 評価優先度に絞ること
    - AI の推定・解釈は導出確認 (ユーザー承認) を経るまで confirm 扱いしないこと
    - responsibility_id は target_skill の responsibilities[].id と 1:1 で対応すること
    - batch モードでは AskUserQuestion を使用しないこと
since: 2026-05-22
script_refs: []
reference_refs:
  - references/resource-map.yaml
  - references/elicit-question-bank.md
source: doc/prompt-creator/agents/interview-user.md
source-tier: internal
last-audited: 2026-05-22
audit-trigger: quarterly
responsibility_refs:
  - prompts/interview.md
schema_refs:
  - ../run-prompt-create/schemas/prompt-brief.schema.json
  - schemas/hearing-result.schema.json
responsibilities:
  - id: R1
    name: interview
    prompt_required: true
---

# run-prompt-elicit

> ユーザー要望から `prompt-brief.json` を構築する Step 1 skill。`prompt-creator-interview-user` agent を context:fork で起動し、対話で必要項目を埋める。

## Purpose & Output Contract

**入力**: topic (任意) / target_skill (任意) / responsibility_id (任意) / batch flag
**出力**:
- `eval-log/prompt-brief.json` (`../run-prompt-create/schemas/prompt-brief.schema.json` 準拠)
- `eval-log/hearing-result.json` (`schemas/hearing-result.schema.json` 準拠、中間生データ)

**完了条件**: brief schema validation PASS + responsibility_id が target_skill の SKILL.md responsibilities[] と整合。

## Key Rules

1. **AskUserQuestion 集約**: 質問は 1 セッション 3-5 問 + 評価優先度に絞る (doc/prompt-creator/ 由来の核心原則)。
2. **導出確認**: AI の推定・解釈は必ずユーザーに透明化して承認を得る。推測を事実として埋めない。
3. **質ベース判定**: 「この回答で次に何をすべきか迷わないか?」で十分性を判断。数量カウント禁止。
4. **R-id 1:1**: responsibility_id は target_skill の responsibilities[].id と必ず一致。不在なら open_questions に記録。
5. **batch モード**: `--batch` 指定時は AskUserQuestion 不使用。topic / target_skill / responsibility_id 全指定必須。
6. **言語**: 出力本文は日本語、パラメーター名と JSON キーは英語のまま。

## Steps

### Step 1: 既存 brief 確認
`eval-log/prompt-brief.json` が存在すれば差分のみヒアリング。新規なら全項目。

### Step 2: target_skill 突合
`target_skill` の `plugins/*/skills/<target_skill>/SKILL.md` を Read し、`responsibilities[]` を抽出。
`responsibility_id` 指定なら該当エントリを基に boundary/layers_required を推定 (導出確認必須)。

### Step 3: 対話ヒアリング
prompt-creator-interview-user agent を `Task(subagent_type=prompt-creator-interview-user)` で起動。
質問項目: prompt_name / responsibility_id / target_skill / owner_agent_or_skill / layers_required / trigger_conditions / output_contract / boundary / self_evaluation_checklist / open_questions。

### Step 4: brief 構築
`schemas/hearing-result.schema.json` 準拠の hearing-result を `eval-log/hearing-result.json` に保存後、
`schemas/prompt-brief.schema.json` 準拠の brief を `eval-log/prompt-brief.json` に保存。

### Step 5: 自己検証
- prompt_name が `[a-z][a-z0-9-]*` パターン
- responsibility_id が target_skill responsibilities[].id に実在
- layers_required が L1-L7 のサブセットで非空
- trigger_conditions が 2-3 件、各 80 文字以内
- boundary が 200 文字以内

## Gotchas

1. 既存 brief がある場合は差分のみ。既知項目を再質問しない。
2. responsibility_id 不在で target_skill 側の更新が必要なら open_questions に保持。
3. AI 推定値は導出確認 (ユーザー承認) を経ずに confirm 扱いしない。
4. doc/prompt-creator/ の writing-style-principles に従い「目的+背景」併記。

## Additional Resources

- `references/elicit-question-bank.md` — 質問テンプレ集
- `schemas/hearing-result.schema.json` — Step 3 中間スキーマ
- `../run-prompt-create/schemas/prompt-brief.schema.json` — Step 4 出力スキーマ
- caller: `run-prompt-create` (Step 1)
- delegate agent: `prompt-creator-interview-user`
