---
name: run-prompt-create
description: 新規プロンプト作成・既存プロンプト更新を端から端まで実行するとき、Gate/eval-log 連鎖で再現性高くプロンプトを生成するときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[--topic <text>] [--mode create|update] [--fast]"
arguments: [topic, mode, fast]
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(python3 *)
  - Bash(git *)
  - AskUserQuestion
  - Skill
kind: run
version: 2.1.0
effect: local-artifact
owner: team-platform
contract:
  intent: 7 層プロンプトを要望から成果物まで品質保証付きで送り出すため、elicit→build→evaluate→governance をゲート制御で連鎖させる orchestrator を提供する。
  interface:
    inputs: [topic, mode, fast]
    outputs: [seven-layer-prompt.md, prompt-build-trace.json, findings.json, "handoff-*.json", completion-report]
  invariant:
    - Gate 1 (brief 確認) のみユーザー対話を行い、Gate 2-4 は workflow-manifest.json の auto_approve_conditions を機械評価すること
    - 各フェーズは独立 Skill へ委譲し、本スキルは制御のみを担うこと
    - evaluator / governance reviewer は必ず context:fork で起動すること (Sycophancy 防止)
    - 各ゲート通過時に handoff-<step>.json を schemas/handoff.schema.json 準拠で永続化すること
    - Layer 依存方向 L7→L1 を逸脱した生成物は Gate で差し戻すこと
since: 2026-05-22
script_refs:
  - scripts/evaluate-create-gates.py
  - ../run-prompt-creator-7layer/scripts/verify-completeness.py
  - ../run-prompt-creator-7layer/scripts/validate-prompt.py
reference_refs:
  - references/resource-map.yaml
  - references/governance-params.json
source: plugins/prompt-creator/skills/run-prompt-create/
source-tier: internal
last-audited: 2026-05-22
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-gate-review.md
  - prompts/R3-governance-decide.md
schema_refs:
  - schemas/prompt-brief.schema.json
  - schemas/build-trace.schema.json
  - schemas/findings.schema.json
  - schemas/handoff.schema.json
manifest: workflow-manifest.json
responsibilities:
  - id: R1
    name: elicit
    prompt_required: true
  - id: R2
    name: gate-review
    prompt_required: true
  - id: R3
    name: governance-decide
    prompt_required: true
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: workflow-manifest.json phases[id=p0-lint] の 8 本 lint が全て exit 0 で通り、未解決 TODO や未展開プレースホルダ {{...}} や英語仮文の残存(パラメーター名を除く)を検出した場合は Step 2 へ自律差し戻すことを lint で機械検証できる。
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: 各ゲート通過時に eval-log/handoff-<step>.json が schemas/handoff.schema.json 準拠で永続化され、Gate 2-4 が workflow-manifest.json の auto_approve_conditions を機械評価した証跡を伴うことを script で機械検証できる。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: orchestrator が制御のみを担い各フェーズを独立 Skill へ委譲する責務分割と、evaluator や governance reviewer を必ず fork コンテキスト(context=fork)で起動する Sycophancy 防止と、Layer 依存方向 L7→L1 不変の差し戻しが、ユーザ目的(再現性高い 7 層プロンプト生成)に対し過不足ないこと。
      verify_by: elegant-review
---

# run-prompt-create

> 端から端まで 7 層プロンプトを構築する **orchestrator skill**。Gate 1 のみユーザー確認を行い、以降は manifest 条件に基づく自動ゲートと eval-log 永続化で再現性を担保する。

## Purpose & Output Contract

ユーザー要望 → `prompt-brief.json` → 7 層プロンプト生成 → P0 lint → 設計評価 → パラダイム評価 → governance 承認 を**ゲートあり自動連鎖**で実行する orchestrator。各 Step/Gate の機械可読定義は `workflow-manifest.json`、責務別プロンプトは `prompts/*.md`、データ契約は `schemas/*.schema.json`。

**入力**: `topic` (任意), `mode` ∈ {create, update}, `--fast` (任意)
**出力**:
- `plugins/<plugin>/skills/<skill>/prompts/<R-id>-<slug>.md` (skill-local-v1)
- `eval-log/prompt-build-trace.json` (`schemas/build-trace.schema.json` 準拠)
- `eval-log/docs/<NN>-<timestamp>.json` (`schemas/findings.schema.json` 準拠)
- `eval-log/handoff-<step>.json` (`schemas/handoff.schema.json` 準拠) ×7
- 完了レポート (日本語、パラメーター名のみ英語)

**完了条件**: P0 lint pass + (`--fast` でない場合は evaluator JSON pass と elegant-review pass) + `workflow-manifest.json` の `auto_approve_conditions` 全充足または governance handoff 確定。

### 起動モード

- **引数なし**: Step 1 (run-prompt-elicit) が起動、対話で topic を確定。
- **`--fast`**: new_prompt でなく、diff_lines <= 30 のときのみ design-evaluate / elegant-review を skip。判定:
  ```bash
  python3 plugins/prompt-creator/skills/run-prompt-create/scripts/evaluate-create-gates.py \
    --prompt-name "$PROMPT_NAME" --brief eval-log/prompt-brief.json --fast
  ```

## Key Rules

1. **自動承認既定**: 初回 brief 確定 (Gate 1) のみユーザーに AskUserQuestion を発行。Gate 2-4 は `workflow-manifest.json` の `auto_approve_conditions` を機械評価し、全充足時は `solo_operator_auto` で自動承認。
2. **条件不充足時のみ停止**: P0 lint fail / evaluator FAIL / Layer 依存違反 / 充足率 95% 未満などのいずれかで停止し findings 提示。
3. **子スキルへの委譲**: 各フェーズは独立 Skill を Skill tool で起動 (`workflow-manifest.json` の `delegateSkill`)。本スキルは制御のみ。
4. **context:fork**: evaluator/governance reviewer は必ず context:fork で起動 (Sycophancy 防止)。
5. **handoff 保存**: 各ゲート通過時に `eval-log/handoff-<step>.json` を `schemas/handoff.schema.json` 準拠で残す。
6. **resource-map 先読み**: `references/resource-map.yaml` を最初に読み、必要ファイルのみ open。
7. **日本語成果物**: 本文・レビュー・完了レポートを日本語に保つ (パラメーター名・JSON キー・CLI 引数は英語)。
8. **Markdown 既定**: 新規 prompt は `prompts/<R-id>-<slug>.md` で `references/seven-layer-markdown-template.md` 写経 (YAML は legacy のみ許容、新規禁止)。
9. **Layer 依存方向不変**: L7 → L6 → ... → L1。逆方向参照は C2 FAIL。
10. **質ベース判定**: 数量カウント (3 つ以上等) を排し「実行可能か」「検証可能か」で判定。doc/prompt-creator/ 由来の核心原則。
11. **要素原子性**: 1 フィールド=1 概念、1 値=1 短文 (50 字目安)。長文は分解。
12. **目的+背景併記**: 全ルール/制約に「目的」と「背景」を必ず併記する記述スタイル。

## End-to-End Flow

```
[Step 1 elicit] run-prompt-elicit ─→ prompt-brief.json ─[Gate 1 ★唯一の対話]─▶
[Step 2 build]  run-prompt-creator-7layer ─→ prompt-build-trace.json
[Step 3a p0-lint] (fail→Step 2、最大 3 周) ─[Gate 2 自動]─▶
[Step 3b design-evaluate] assign-prompt-design-evaluator (context:fork) ─→ findings
[Step 4 elegant-review] (条件: new or >30 行, context:fork) ─[Gate 3 自動]─▶
[Step 5 governance] (manifest 条件充足で solo_operator_auto) ─[Gate 4 自動]─▶
[Step 6 report]
```

★ ユーザー対話は Gate 1 のみ。Gate 2-4 は `workflow-manifest.json` の `auto_approve_conditions` を機械評価し、全充足で自動承認。1 条件でも不充足なら findings 提示 + 修正ループ。

依存・entryHook/exitHook・resourceIds・fatal_exit_codes は `workflow-manifest.json` 参照。

## Steps (圧縮形)

### Step 1: 要求ヒアリング (phase=elicit)
`Skill(run-prompt-elicit, args=topic)` → `eval-log/prompt-brief.json`。プロンプトは `prompts/elicit.md` (R1)。スキーマは `schemas/prompt-brief.schema.json`。

### Gate 1: brief 確認
`prompts/gate-review.md` テンプレで承認取得。否認時は Step 1 へ戻る (最大 3 回)。

### Step 2: プロンプト生成 (phase=build)
`Skill(run-prompt-creator-7layer, args=[responsibility_id, output, target_agent, prompt_brief, format])`。`eval-log/prompt-build-trace.json` が `schemas/build-trace.schema.json` 準拠で Layer coverage 全 PASS/N/A/skip 理由付きであることを Gate 2 前提とする。

### Step 3a: P0 lint (自動) (phase=p0-lint)
`workflow-manifest.json phases[id=p0-lint].commands` に集約 (8 本)。**全 exit 0 必須**、失敗時は findings → Step 2 (最大 3 周)。`TODO` / 未展開 `{{...}}` / 英語仮文残存も Step 2 へ戻す (パラメーター名除く)。

### Gate 2: lint/diff 自動判定
`git diff` と `eval-log/prompt-build-trace.json` をもとに manifest 条件を機械評価し、全充足なら handoff を `solo_operator_auto` で保存。条件不充足時のみ findings を提示して停止する。

### Step 3b: 設計評価 (phase=design-evaluate)
`Skill(assign-prompt-design-evaluator, args=<prompt_path>, context=fork)` → `eval-log/docs/<NN>-<timestamp>.json` (`schemas/findings.schema.json` 準拠)。FAIL 項目は findings を Step 2 へ自律差し戻し (最大 3 周回)。3 周未収束は Step 5 governance-decide へ昇格して solo_operator_auto 失効を判定する。

### Step 4: パラダイム評価 (phase=elegant-review, 条件付き)
新規または >30 行変更時のみ。判定は `scripts/evaluate-create-gates.py`。`Skill(run-elegant-review, args=[prompt, <prompt_path>], context=fork)` で C1-C4 全 PASS 必須。

### Gate 3: 評価結果自動判定
findings と C1-C4 を機械評価し、全充足なら handoff を `solo_operator_auto` で保存。FAIL 残存時のみ findings を提示して修正ループへ戻す。

### Step 5: governance 承認 (phase=governance) + Gate 4
`prompts/governance-decide.md` (R3) は `workflow-manifest.json` の `auto_approve_conditions` と `references/governance-params.json` を読み、全充足で自動承認。それ以外は `run-skill-rubric-governance` 起動。

### Step 6: 完了レポート (phase=report)
```markdown
# Prompt Creation Report: <prompt_name>
- mode: create|update
- responsibility_id: R<n>
- target_skill: <skill_name>
- gates_passed: [1,2,3,4]
- p0_lint: PASS
- evaluator_result: PASS
- elegant_review: PASS (or N/A)
- governance: solo_auto_approved (or manual)
- output_path: <path>
- residual_findings: [<未収束 finding 一覧 / 空配列なら全解消>]
- follow_up_actions: [<AI が自動選定した次アクション>]
```

## Gotchas

1. **Gate 条件 skip 禁止**: Gate 1 は明示確認必須。Gate 2-4 は manifest 条件の評価証跡なしに進めない。
2. **同一 context 評価禁止**: evaluator/governance reviewer は必ず context:fork。
3. **lint 失敗時の自動修正禁止**: 根本原因をユーザー提示。
4. **mode=update 時の改名**: prompt 名変更は `run-skill-rename` 相当を経由 (本スキル対象外)。
5. **context 予算**: SKILL.md / 各 prompt 300 行以下、`references/` は Phase 直前で必要分のみ読込。
6. **manifest 二重管理禁止**: 手書き追加後も `lint-manifest-contents.py` を必ず通す。

## Additional Resources

`references/resource-map.yaml` を最初に読む。主要参照:

- `workflow-manifest.json` — Step/Gate/Phase の機械可読定義
- `schemas/prompt-brief.schema.json` — Step 1→2 渡し正本スキーマ
- `schemas/handoff.schema.json` — Gate 通過時 handoff 共通形式
- `schemas/findings.schema.json` — evaluator/elegant-review 出力形式 (C1-C4)
- `schemas/build-trace.schema.json` — Step 2 emit する Layer 別 coverage 形式
- `prompts/elicit.md` / `prompts/gate-review.md` / `prompts/governance-decide.md` — R1/R2/R3 責務別プロンプト
- 子スキル: `run-prompt-elicit`, `run-prompt-creator-7layer`, `assign-prompt-design-evaluator`, `run-elegant-review` (skill-creator), `run-skill-rubric-governance` (skill-creator)
