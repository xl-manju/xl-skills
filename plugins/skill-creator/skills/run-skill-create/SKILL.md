---
name: run-skill-create
description: 実行して新規Skillを端から端まで作りたいとき、複数Gateを通した品質保証付きフローを起動したいときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[topic?] [--mode create|update] [--fast]"
arguments: [topic, mode, fast]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(python3 *)
  - Bash(git diff *)
  - Bash(git status *)
  - Skill
model: opus
kind: run
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-05-18
pair: assign-skill-design-evaluator
manifest: workflow-manifest.json
responsibility_refs:
  - prompts/elicit.md
  - prompts/gate-review.md
  - prompts/governance-decide.md
rubric_refs:
  - ref-skill-design-rubric
reference_refs:
  - ref-task-context-map
  - ref-skill-glossary
  - ref-domain-task-spec-rubric
# context-budget: orchestrationのみ。各子スキルがそれぞれの設計書を参照する。本スキルは05/06/07/13/23/25章のみ参照。
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
---

# run-skill-create

> Phase 2 移行後は `plugins/skill-creator/skills/` が正本、`.claude/skills/` は symlink/deploy target。本SKILL.md は両配置で動作するよう self-relative パスを使用。

## Purpose & Output Contract

ユーザー要望 → `skill-brief.json` → Skill生成 → plugin/marketplace 登録判定 → P0 lint → 設計評価 → パラダイム評価 → governance 承認 を**ゲートあり自動連鎖**で実行する端から端まで orchestrator。各 Step/Gate の機械可読定義は `workflow-manifest.json`、責務別プロンプトは `prompts/*.md`、データ契約は `schemas/*.schema.json` を参照。

**入力**: topic (任意), mode ∈ {create, update}
**出力**:
- `plugins/skill-creator/skills/<skill_name>/` 一式 (SKILL.md + references/ + scripts/)
- `eval-log/skill-build-trace.json` (`schemas/build-trace.schema.json` 準拠)
- 共通基盤の場合は `plugins/skill-creator/.claude-plugin/plugin.json` 登録差分
- `eval-log/docs/<NN>-<timestamp>.json` (評価結果、`schemas/findings.schema.json` 準拠)
- `eval-log/handoff-<step>.json` (`schemas/handoff.schema.json` 準拠)
- 完了レポート (日本語本文、パラメーター名のみ英語)

**完了条件**: P0 lint pass + evaluator JSON pass (`--fast` 低リスク ref/wrap は `evaluator: N/A` 理由必須) + (solo_operator_mode 下) LLM-reviewer pass。

### 起動モード

- **引数なし**: Step 1 (run-skill-elicit) が起動、対話で topic を確定。フィールド意味は `schemas/skill-brief.schema.json` (詳細は `references/skill-brief-schema.json`)。
- **`--fast`**: 1ファイル変更/<=30行/kind ∈ {ref,wrap}/evaluator pair 不要を全て満たす場合のみ軽量フロー (Step 4b/5 skip)。判定は機械決定:
  ```bash
  python3 plugins/skill-creator/skills/run-skill-create/scripts/evaluate-create-gates.py \
    --skill-name "$SKILL_NAME" --kind "$KIND" --brief eval-log/skill-brief.json --fast
  ```
  条件不一致時は黙って通常フローに戻す。

## Key Rules

1. **ゲート前で必ず止まる**: ユーザー承認なしに次フェーズへ進まない。全ゲートは AskUserQuestion 経由 (`prompts/gate-review.md`)。
2. **子スキルへの委譲**: 各フェーズは独立 Skill を Skill tool で起動 (`workflow-manifest.json` の `delegateSkill`)。本スキルは制御のみ。
3. **失敗時の停止**: P0 lint fail または evaluator FAIL なら停止し findings 提示。
4. **context:fork**: evaluator/governance reviewer は必ず context:fork で起動 (Sycophancy 防止)。
5. **handoff 保存**: 各ゲート通過時に `eval-log/handoff-<step>.json` を `schemas/handoff.schema.json` 準拠で残す。PostCompact hook で復元。
6. **plugin/marketplace 登録は確認後**: 自動更新禁止。`build-manifest-registration-plan.py` の提案 → Gate 2.5 承認 → `--apply` の順。
7. **resource-map 先読み**: `references/resource-map.yaml` を最初に読み、必要ファイルのみ open。
8. **日本語成果物ゲート**: brief の `output_language=ja` と `parameter_language_exception=true` を既定とし、本文・レビュー・完了レポートを日本語に保つ (パラメーター名・JSON キー・CLI 引数は英語)。
9. **prompt 形式**: 新規 prompt は **Markdown (`.md`) 既定**。`prompts/<R-id>-<slug>.md` で `plugins/prompt-creator/skills/run-prompt-creator-7layer/references/seven-layer-markdown-template.md` を写経して生成。YAML は legacy のみ許容 (新規禁止、P0 lint で warn)。

## End-to-End Flow

```
[Step 1 elicit] run-skill-elicit ─→ skill-brief.json ─[Gate 1]─▶
[Step 2 build]  run-build-skill  ─→ skill-build-trace.json
[Step 3 manifest-register] [Gate 2.5] [Step 3.5 bundle-register]
[Step 4a p0-lint] (fail→Step 2、最大3周) ─[Gate 2 diff]─▶
[Step 4b design-evaluate] (context:fork) ─→ findings
[Step 5 elegant-review] (条件: new or >30 行, context:fork) ─[Gate 3]─▶
[Step 6 governance] (solo_operator_mode 自動承認) ─[Gate 4]─▶
[Step 7 report]
```

依存・entryHook/exitHook・resourceIds・fatal_exit_codes は `workflow-manifest.json` 参照。

## Steps (圧縮形)

各 Step の詳細は `workflow-manifest.json phases[].id` と対応する `prompts/*.md` に委譲。

### Step 1: 要求ヒアリング (phase=elicit)
`Skill(run-skill-elicit, args=topic)` → `eval-log/skill-brief.json`。プロンプトは `prompts/elicit.md` (R1)。スキーマは `schemas/skill-brief.schema.json`。

### Gate 1: brief 確認
`prompts/gate-review.md` テンプレで承認取得。否認時は Step 1 へ戻る (最大 3 回)。

### Step 2: スキル生成 (phase=build)
`Skill(run-build-skill, args=[skill_name, kind, --mode={mode}])`。`eval-log/skill-build-trace.json` が `schemas/build-trace.schema.json` 準拠で章 coverage 全 PASS/N/A/skip 理由付きであることを Gate 2 前提とする。

### Step 3: plugin/marketplace 登録判定 (phase=manifest-register) + Gate 2.5
横展開対象 (run-/assign-/ref- 系、hook/lint/adapter、共通 rubric/template) なら `python3 plugins/skill-governance-automation/scripts/build-manifest-registration-plan.py` で提案生成 → 承認後 `--apply`。プロジェクト固有は未登録理由を完了レポートに残す。

### Step 3.5: bundle 登録判定 (phase=bundle-register)
他 plugin の skill/agent/command/hook を呼ぶ場合は `.claude-plugin/bundles.json` に登録。対象 bundle は `xl-skills-full` (基本) / `xl-skills-minimal` / `xl-skills-intake`。登録不要時は理由を完了レポートに残す。**理由なき未登録は rubric 違反**。

### Step 4a: P0 lint (自動) (phase=p0-lint)
cwd はプロジェクトルート。`SKILLS_DIR="${CLAUDE_SKILLS_DIR:-plugins/skill-creator/skills}"`。コマンド列は `workflow-manifest.json phases[id=p0-lint].commands` に集約 (8 本 lint + manifest-contents)。**全 exit 0 必須**、失敗時は findings → Step 2 (最大 3 周)。`TODO` / 未展開 `{{...}}` / 英語仮文残存も Step 2 へ戻す (パラメーター名除く)。

### Gate 2: diff 確認
`git diff plugins/skill-creator/skills/<name>/` と `eval-log/skill-build-trace.json` を提示して承認取得。前提: Step 4a 全 pass。

### Step 4b: 設計評価 (phase=design-evaluate)
`Skill(assign-skill-design-evaluator, args=<skill_path>, context=fork)` → `eval-log/docs/<NN>-<timestamp>.json` (`schemas/findings.schema.json` 準拠)。FAIL 項目は findings 提示 → Step 2 / TODO(human) 判断。

### Step 5: パラダイム評価 (phase=elegant-review, 条件付き)
新規または >30 行変更時のみ。判定は機械化:
```bash
python3 plugins/skill-creator/skills/run-skill-create/scripts/evaluate-create-gates.py \
  --skill-name "$SKILL_NAME" --kind "$KIND" --brief eval-log/skill-brief.json
```
`Skill(run-elegant-review, args=[skill, <skill_path>], context=fork)` で C1-C4 全 PASS 必須。PASS 時、`findings.pattern_ref_candidates / new_patterns / mass_production_risk` を `eval-log/pattern-feedback.json` に提案として残す (template/rubric/lint/hook 反映は Step 6 経由)。

### Gate 3: 評価結果確認
findings 提示。FAIL 残存時は修正方針確認。

### Step 6: governance 承認 (phase=governance) + Gate 4
プロンプト `prompts/governance-decide.md` (R3) の判定ロジックに従う。プロジェクトルート `references/governance-params.json` の `solo_operator_mode` を読み、4 条件 (solo=true / 安定版凍結 / newly_failing=0 / LLM-reviewer pass) 全充足で自動承認、それ以外は `run-skill-rubric-governance` 起動。Gate 4 で完了レポート提示。

### Step 7: 完了レポート (phase=report)
```markdown
# Skill Creation Report: <skill_name>
- mode: create|update
- gates_passed: [1,2,3,4]
- creator_kit_registration: applied|skipped|not_applicable
- evaluator_result: PASS
- elegant_review: PASS (or N/A)
- governance: solo_auto_approved (or manual)
- TODO(human): [...]
```

## Gotchas

1. **Gate skip 禁止**: 「次へ」を自動推測しない。明示確認必須。
2. **同一 context 評価禁止**: evaluator/governance reviewer は必ず context:fork (Sycophancy 防止)。
3. **lint 失敗時の自動修正禁止**: 根本原因をユーザー提示。LLM 判断で勝手に直さない。
4. **mode=update 時の改名**: `run-skill-rename` に委譲。本スキル対象外。
5. **context 予算**: 31 章全部を読まない。本スキルは 05/06/07/13/23/25 章のみ参照。
6. **handoff 保存**: 各ゲート通過時に `schemas/handoff.schema.json` 準拠で必ず保存。
7. **manifest 二重管理禁止**: 手書き追加後も `lint-manifest-contents.py` を必ず通す。

## 品質ゲート: Elegant Review Protocol

新規/更新/プロンプト改善時は `plugins/skill-intake/skills/run-skill-intake-aggregator/references/elegant-review-protocol.md` を適用 (3 フェーズで C1-C4 全 PASS を確認、大規模設計は必須、軽微修正は `--fast` と整合可)。結果は Step 5 findings に紐付け `eval-log/` に残す。

## Additional Resources

`references/resource-map.yaml` を最初に読む (machine-readable と人間向け資料を一覧化)。主要参照:

- `workflow-manifest.json` — Step/Gate/Phase の機械可読定義 (entryHook/exitHook/dependsOn/delegateSkill)
- `schemas/skill-brief.schema.json` — Step 1→2 渡し正本スキーマ
- `schemas/handoff.schema.json` — Gate 通過時 handoff 共通形式
- `schemas/findings.schema.json` — evaluator/elegant-review 出力形式 (C1-C4)
- `schemas/build-trace.schema.json` — Step 2 emit する章別 coverage 形式
- `schemas/rubric-merge.schema.json` — L0/L1/L2 rubric deep-merge 物質化形式
- `prompts/elicit.md` / `prompts/gate-review.md` / `prompts/governance-decide.md` — R1/R2/R3 責務別プロンプト
- `references/gate-templates.md` — Gate 確認質問テンプレ (人間向け詳細手順)
- 子スキル: `run-skill-elicit`, `run-build-skill`, `assign-skill-design-evaluator`, `run-elegant-review`, `run-skill-rubric-governance`, `run-skill-rename`
- 設計書: 05/06/07/11/13/23/25 章
