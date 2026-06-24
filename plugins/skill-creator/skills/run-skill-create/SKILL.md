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
version: 0.1.0
pair: assign-skill-design-evaluator
manifest: workflow-manifest.json
responsibility_refs:
  - prompts/R1-elicit.md
  - prompts/R2-gate-review.md
  - prompts/R3-governance-decide.md
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

> Phase 2 移行後は `plugins/skill-creator/skills/` が正本、`.claude/skills/` は symlink/deploy target。schema/prompt 参照は self-relative パスだが、本SKILL.md 内の lint / スクリプト起動コマンド (`python3 plugins/...`) は repo-root cwd 前提。

## Purpose & Output Contract

ユーザー要望 → `skill-brief.json` → Skill生成 → plugin/marketplace 登録判定 → P0 lint → 設計評価 → パラダイム評価 → governance 承認 を**ゲートあり自動連鎖**で実行する端から端まで orchestrator。各 Step/Gate の機械可読定義は `workflow-manifest.json`、責務別プロンプトは `prompts/*.md`、データ契約は `schemas/*.schema.json` を参照。

**入力**: topic (任意), mode ∈ {create, update}
**出力**:
- `plugins/skill-creator/skills/<skill_name>/` 一式 (SKILL.md + references/ + scripts/)
- `eval-log/skill-build-trace.json` (`schemas/build-trace.schema.json` 準拠)
- 共通基盤の場合は `plugins/skill-creator/.claude-plugin/plugin.json` 登録差分
- `eval-log/docs/<NN>-<timestamp>.json` (評価結果、`schemas/findings.schema.json` 準拠)。deprecated: 27章 §3.1 の `eval-log/<plugin>/<skill>/<gate>/<run-id>/` (repo root 基準) へ移行
- `eval-log/handoff-<step>.json` (`schemas/handoff.schema.json` 準拠)
- 完了レポート (日本語本文、パラメーター名のみ英語)

**完了条件**: P0 lint pass + evaluator JSON pass (`--fast` 低リスク ref/wrap は `evaluator: N/A` 理由必須) + (solo_operator_mode 下) LLM-reviewer pass。

### 起動モード

- **引数なし**: Step 1 (run-skill-elicit) が起動、対話で topic を確定。フィールド意味は `schemas/skill-brief.schema.json` (詳細は `references/skill-brief-schema.json`)。
- **Notion 指定あり**: topic / 引数に `--page-url` または `--page-id` が含まれる場合、Step 1 は `skill-intake` の publish 完了証跡を必須入力とする。`output/<hint>/notion-log.json.status=="published"`、`notion-publish-result.json.page_id`、`notion-url.txt` が揃い、指定 page と一致するまで Step 2 build へ進まない。
- **`--fast`**: 1ファイル変更/<=30行/kind ∈ {ref,wrap}/evaluator pair 不要を全て満たす場合のみ軽量フロー (Step 4b/5 skip)。判定は機械決定:
  ```bash
  python3 plugins/skill-creator/skills/run-skill-create/scripts/evaluate-create-gates.py \
    --skill-name "$SKILL_NAME" --kind "$KIND" --brief eval-log/skill-brief.json --fast
  ```
  条件不一致時は黙って通常フローに戻す。

## Key Rules

1. **ゲート前で必ず止まる**: ユーザー承認なしに次フェーズへ進まない。全ゲートは AskUserQuestion 経由 (`prompts/R2-gate-review.md`)。
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
[Step 4a.5 pkg-check] run-plugin-package-check (条件: kind==plugin-composition or 新規 plugin 横展開)
[Step 4b design-evaluate] (context:fork) ─→ findings
[Step 5 elegant-review] (条件: new or >30 行, context:fork) ─[Gate 3]─▶
[Step 6 governance] (solo_operator_mode 自動承認) ─[Gate 4]─▶
[Step 7 report]
```

依存・entryHook/exitHook・resourceIds・fatal_exit_codes は `workflow-manifest.json` 参照。

## ゴールシーク実行

### ゴール (Goal)

ユーザー要望から生成された `<skill_name>/` 一式が、全 P0 lint pass・evaluator JSON pass・(solo_operator_mode 下) LLM-reviewer pass を満たし、4 ゲート全承認済みで、登録判定・handoff・完了レポートまで完結した状態になっている。

### 目的・背景 (Why)

新規/更新 Skill を「端から端まで」品質保証付きで送り出すための制御層。各フェーズは独立 Skill へ委譲し、本スキルはゲート制御とハンドオフ整合のみを担う。固定手順では入力 (topic/mode/--fast)・lint 失敗・FAIL 差し戻しなど実行時文脈に脆いため、未達ゲートを都度埋める。

### 完了チェックリスト (Checklist)

- [ ] `eval-log/skill-brief.json` が `schemas/skill-brief.schema.json` 準拠で生成され、Gate 1 承認済み
- [ ] Notion 指定ありの場合、`python3 plugins/skill-creator/skills/run-skill-create/scripts/validate-intake-publish-ready.py --dir output/<hint> --page-url <url>` が exit 0。未公開・page_id 不一致・URL 欠落なら Gate 1 で停止し、skill 本体生成へ進んでいない
- [ ] `<skill_name>/` 一式 (SKILL.md + references/ + scripts/) が `Skill(run-build-skill, args=[skill_name, kind, --mode={mode}])` で生成され、`eval-log/skill-build-trace.json` が `schemas/build-trace.schema.json` 準拠・章 coverage 全 PASS/N/A/skip 理由付き
- [ ] 横展開対象なら plugin/marketplace 登録が Gate 2.5 承認後 `--apply` 済み (`build-manifest-registration-plan.py`)。プロジェクト固有は未登録理由がレポートに記録されている
- [ ] 他 plugin リソースを呼ぶ場合 `.claude-plugin/bundles.json` (`xl-skills-full`/`-minimal`/`-intake`) 登録済み。不要なら理由がレポートにある (理由なき未登録は rubric 違反)
- [ ] P0 lint 8 本 + manifest-contents が全 exit 0 (`workflow-manifest.json phases[id=p0-lint].commands`)。`TODO`/未展開 `{{...}}`/英語仮文の残存なし (パラメーター名除く)
- [ ] Gate 2 で `git diff <skill_path>` + build-trace を提示し承認済み
- [ ] `assign-skill-design-evaluator` (context:fork) の `eval-log/docs/<NN>-<timestamp>.json` (`schemas/findings.schema.json` 準拠) が FAIL 残存なし
- [ ] 新規 or >30 行変更時、`run-elegant-review` (context:fork) で C1-C4 全 PASS。PASS 時 `eval-log/pattern-feedback.json` に pattern_ref_candidates/new_patterns/mass_production_risk を提案保存
- [ ] governance 承認済み: `references/governance-params.json` の 4 条件 (solo=true/安定版凍結/newly_failing=0/LLM-reviewer pass) 全充足で自動、不充足なら `run-skill-rubric-governance` 経由 (`prompts/R3-governance-decide.md` R3)。Gate 4 承認済み
- [ ] 各ゲート通過時に `eval-log/handoff-<step>.json` が `schemas/handoff.schema.json` 準拠で保存されている
- [ ] 完了レポート (下記項目: mode/gates_passed/creator_kit_registration/evaluator_result/elegant_review/governance/open_questions) が日本語本文で提示されている (パラメーター名のみ英語)

### ゴールシークループ

正本 `../run-build-skill/references/goal-seek-paradigm.md` の 6 ステップ (現状評価/手順生成/実行/検証/Anchor Step/反復) に従う。本スキル固有の差分:

- **未達評価の単位はゲート**: Gate 1→2→2.5→3→4 を順に「未承認」とみなして都度埋める。ゲート前で必ず止まりユーザー承認を取る (自動推測禁止、AskUserQuestion 経由 `prompts/R2-gate-review.md`)。
- **委譲先 (子 Skill)**: `run-skill-elicit` / `run-build-skill` / `assign-skill-design-evaluator` / `run-elegant-review` / `run-skill-rubric-governance`。Notion 指定ありの非技術者 intake は `skill-intake` 完了証跡を先に検証する。本スキルは制御のみ、各子が自設計書を参照。
- **context:fork 必須**: evaluator / elegant-review / governance reviewer は必ず fork で起動 (Sycophancy 防止)。
- **差し戻し**: P0 lint fail または evaluator/elegant FAIL なら `run-build-skill` 再実行へ戻す (最大 3 周)。`--fast` 判定・elegant 起動判定は `scripts/evaluate-create-gates.py` で機械決定 (条件不一致は黙って通常フロー)。
- **lint 自動修正禁止**: 根本原因をユーザー提示し LLM 判断で勝手に直さない。
- 各フェーズ phase=id・entryHook/exitHook・dependsOn・fatal_exit_codes は `workflow-manifest.json` 参照。プロンプト R1/R2/R3 は `prompts/*.md`。

## Gotchas

1. **Gate skip 禁止**: 「次へ」を自動推測しない。明示確認必須。
2. **同一 context 評価禁止**: evaluator/governance reviewer は必ず context:fork (Sycophancy 防止)。
3. **lint 失敗時の自動修正禁止**: 根本原因をユーザー提示。LLM 判断で勝手に直さない。
4. **mode=update 時の改名**: `run-skill-rename` に委譲。本スキル対象外。
5. **context 予算**: 31 章全部を読まない。本スキルは 05/06/07/13/23/25 章のみ参照。
6. **handoff 保存**: 各ゲート通過時に `schemas/handoff.schema.json` 準拠で必ず保存。
7. **manifest 二重管理禁止**: 手書き追加後も `lint-manifest-contents.py` を必ず通す。

## 品質ゲート: Elegant Review Protocol

新規/更新/プロンプト改善時は Elegant Review Protocol を適用する。本プロトコルの正本は `plugins/skill-creator/skills/run-elegant-review/SKILL.md` (Phase 1→2→3 で C1-C4 全 PASS を確認、大規模設計は必須、軽微修正は `--fast` と整合可)。結果は Step 5 findings に紐付け `eval-log/` に残す。

## Additional Resources

`references/resource-map.yaml` を最初に読む (machine-readable と人間向け資料を一覧化)。主要参照:

- `workflow-manifest.json` — Step/Gate/Phase の機械可読定義 (entryHook/exitHook/dependsOn/delegateSkill)
- `schemas/skill-brief.schema.json` — Step 1→2 渡し正本スキーマ
- `schemas/handoff.schema.json` — Gate 通過時 handoff 共通形式
- `schemas/findings.schema.json` — orchestrator handoff envelope (evaluator 集約結果の封筒)。Step 5 producer 出力の正本は `../run-elegant-review/schemas/findings.schema.json`
- `schemas/build-trace.schema.json` — Step 2 emit する章別 coverage 形式
- `schemas/rubric-merge.schema.json` — L0/L1/L2 rubric deep-merge 物質化形式
- `prompts/R1-elicit.md` / `prompts/R2-gate-review.md` / `prompts/R3-governance-decide.md` — R1/R2/R3 責務別プロンプト
- `references/gate-templates.md` — Gate 確認質問テンプレ (人間向け詳細手順)
- 子スキル: `run-skill-elicit`, `run-build-skill`, `run-plugin-package-check`, `assign-skill-design-evaluator`, `run-elegant-review`, `run-skill-rubric-governance`, `run-skill-rename`
- 設計書: 05/06/07/11/13/23/25 章
