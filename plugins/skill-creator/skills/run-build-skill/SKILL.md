---
name: run-build-skill
description: 新規Skillを作成するとき、既存Skillを更新するときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[skill-name] [kind?] [--mode create|update] [--with-subagent] [--with-prompts] [--with-evaluator] [--with-hooks] [--model opus|sonnet]"
arguments: [skill_name, kind, mode, with_subagent, with_prompts, with_evaluator, with_hooks, model]
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash(python3 *)
  - Skill(assign-skill-design-evaluator *)
pair: assign-skill-design-evaluator
kind: run
effect: local-artifact
owner: team-platform
since: 2026-05-17
script_refs:
  - scripts/render-combinators.py
  - scripts/render-frontmatter.py
  - scripts/validate-naming.py
  - scripts/build-subagent.py
  - scripts/validate-build-trace.py
reference_refs:
  - ref-skill-glossary
  - ref-task-context-map
  - ref-output-routing
  - references/reproducibility-trace-schema.md
# context-budget (CD-005): 章一括ロード禁止 / max-reference-chapters: 3
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
---

# run-build-skill

> ※ Phase 2 移行後は `plugins/skill-creator/skills/` が正本、`.claude/skills/` は symlink/deploy target。本SKILL.mdは両配置で動作するよう self-relative パスを使用。

## Purpose & Output Contract

ユーザー要求からClaude Code Skillを1本構築するワークフロー。

**入力**: skill_name (kebab-case), kind (run|ref|assign|wrap|delegate),
         mode (create|update, デフォルト: create),
         with_subagent (フラグ、指定時のみStep7実行),
         model (opus|sonnet, デフォルト: opus)
**出力**:
- `$OUT_BASE/<name>/SKILL.md`（既定は `plugins/skill-creator/skills/`、`.claude/skills/` は派生/symlink/deploy target。300行以下、frontmatter完備。本文はパラメーター名を除き日本語）
- 必要に応じ `templates/`, `references/`, `scripts/`, `examples/`
- `eval-log/skill-build-trace.json`（task→refs map、01aフロー、02/03/04/05/06/07/08/09/10/11/13/14/15/16/26/27/28/29/30/31/32/33/34/35 concern への対応証跡）
- assign-skill-design-evaluator による評価レポート (`eval-log/docs/<NN>-<timestamp>.json`) と `eval-log/<plugin>/<date>-score.jsonl` 追記

**完了条件**: rubric score >= 80 かつ high severity 0件。

## Key Rules

1. **300行制約**: SKILL.md本文は300行以下。超過分は `references/` へ分割（07章）。
2. **descriptionは発動条件のみ**: 動作詳細は本文化（08章）。
3. **triggerは2〜3個**: description内のUse when句は2〜3個の動詞ベース条件（08章 hard rule）。
4. **ディレクトリ名 == frontmatter.name**: 第8条。
5. **Python実行基盤**: Mac/Linux/Windows すべてで Python 標準ライブラリを正本にする。Bash/PowerShell 断片や Node 系 runtime を生成物の必須依存にしない（設計書22章）。
6. **評価分離**: 生成本体は評価しない。`assign-skill-design-evaluator` をforkで呼ぶ（09章 Goodhart対策）。
7. **kindに応じたテンプレ選択**: 11章テンプレを `templates/` から展開。
8. **context予算制約 (CD-005)**: 全章一括ロード禁止。各Stepで必要な章のみ参照。
9. **--mode update**: 既存Skillへの増分改修。既存SKILL.mdを読んでdiffを適用する。
10. **モデル既定値**: build-subagent.py は --model opus で実行（PF-F3-001）。
11. **横展開候補は登録案を作る**: 生成物が Skill Creator 基盤、hook、lint、adapter、rubric、reference に該当する場合は `run-skill-create` の plugin/marketplace 登録判定へ戻し、`.claude-plugin/plugin.json` / marketplace 更新をユーザー確認に委ねる。
12. **正本トレース必須**: 生成・更新ごとに `skill-build-trace.json` に doc_coverage (01〜16 / 26〜28) と `pattern_decisions` を残す。詳細項目は `references/build-steps.md` 参照。
13. **実行レイヤー判断を固定化**: Skill / Subagent / Hook / MCP / CLI / script の配置理由を trace に記録し、決定論で落とせる検査は script/hook へ分離する。
14. **再現性ゲートは機械検証**: `scripts/validate-build-trace.py` で source_docs / build_flow_coverage / doc_coverage / layer_decisions / gates を検証し、空欄・未読・N/A理由なしを通さない。
15. **量産情報を消費する**: `pattern_refs` / `variant_axes` / `reuse_targets` / `deterministic_checks` / `placement_candidates` / `hook_events` を trace と生成本文へ反映し、未消費のまま捨てない。
16. **日本語成果物**: SKILL.md、SubAgent、review、完了レポートの説明文は日本語で作成する。frontmatterキー、JSONキー、CLI引数、テンプレート変数などのパラメーター名は英語のままでよい。
17. **26/27/28章ゲートを省略しない**: メタSkill/rubric/script/hook/subagent 生成時は 26/27/28 章を読み対応 model を trace に記録。対象外でも N/A と理由を残す。
18. **29〜35章を量産判断へ接続する**: 該当時は `references/skill-factory-reproducibility.md` を読み、量産関連 model 群を trace に記録。対象外でも N/A と理由を残す。詳細項目は `references/build-steps.md` 参照。

20. **SubAgent / Skill 本文も 300 行制約**: agent-template.md の 9 セクション準拠で SubAgent ファイルも 300 行以下に保ち、超過分は references/ へ分割。プロンプトの責務分離と Progressive Disclosure を生成プロンプトにも徹底する。
19. **具体値は変数化する**: 再利用される本文・テンプレ・config に固定値を直書きしない。`{{PROJECT_ROOT}}` 等の変数で表現し、具体値は `source_trace` に残す。

## Steps

### Step 1: 要求ヒアリング

> **[MANDATORY - ch15/ch16 公式参照確認]** このステップの最初に `ref-yaml-spec-fetcher` を呼び出して
> `yaml-spec-cache.md` を Read すること。スキップは禁止。
> `validate-build-trace.py` が `15-official-source-notes` / `16-official-skills-reference` を検証し、
> 未実施の場合 exit 1 となる。
>
> ```
> Skill(ref-yaml-spec-fetcher)
> ```

- skill_name の kebab-case とprefix妥当性を確認 → `scripts/validate-naming.py`
- kind を確定（run/ref/assign/wrap/delegate）
- mode を確定（create / update、デフォルト: create）
- `references/resource-map.yaml` を最初に読み、task category と読む設計書を決める
- 01章の5要素（Intent / Contract / Boundary / Execution / Feedback）を1文ずつ埋める
- 01a Step 2 の実行レイヤー判断表で、Skill / Subagent / Hook / MCP / CLI / script の分担を決める
- 02章で配置スコープ / reference-task 境界 / Additional Resources を決める
- 03章で frontmatter の trigger 2〜3個、独自メタデータ、依存注入フィールドを決める
- 04章で `allowed-tools` と `permissions.deny` / hook の責務分離を決める
- 詳細仕様が不足する場合は `references/build-steps.md` を参照
- **context予算**: 設計書は `references/resource-map.yaml` が選んだものだけ読む。同時に読む設計書は原則3章以下。
- **章番号の事前特定**: task category から読むべき章番号を特定してから Read する (CD-005)。
- **メタSkill量産系の追加選定**: 要求に skill creator / rubric / governance / script / hook / subagent / dogfooding / 再現性 が含まれる場合、26/27/28章を優先候補に加える。3章上限を超える場合は、基礎章を `references/build-steps.md` の既読要約で代替し、26/27/28章を正本として読む。
- **L1 ドメイン rubric の解決**: `brief.domain` が指定されている場合、`plugins/skill-governance-config/config/rubric-registry.json` から該当 domain の L1 rubric パスを引き、`DOMAIN_RUBRIC_REFS` 環境変数に空白区切りで詰める。これが Step 5 の assign-evaluator 呼出時に `--rubric-refs` へ append される（設計書29、append-only）。未指定なら L0+L2 のみで採点（L1 スキップ）。
- **量産基盤の文脈選択**: 要求に skill creator / 量産 / 再現性 / rubric合成 / output routing / adapter / 類推理解 / テンプレート変数が含まれる場合は、task category を `skill-factory-reproducibility` にし、設計書29/30/31章と `references/skill-factory-reproducibility.md` を読む。3章上限を超える基礎章は `references/build-steps.md` の既読要約で代替する。

```bash
python3 plugins/skill-creator/skills/run-build-skill/scripts/resolve-skill-dirs.py \
  --skill-dir-name run-build-skill
```

### Step 2: テンプレ展開（create）/ 既存読込（update）

**kind → template 選択表**（COMPOSER_MODE=template の場合）:

| kind / role_suffix | 既存テンプレ | atomic combinator |
|---|---|---|
| `run` (workflow) | `templates/run.md` | `_base.md` + `with-run.patch` |
| `run` (agent-team 複合) | `templates/agent-team.md` | `with-run.patch` + `with-subagent.patch` |
| `run` (orchestrator 複合) | `templates/orchestrator.md` | `with-run.patch` + `with-subagent.patch`×N |
| `run` (hook-integrated 複合) | `templates/hook-integrated.md` | `with-run.patch` + `with-hooks.patch` |
| `ref` | `templates/ref.md` | `_base.md` + `with-ref.patch` |
| `assign` + `role_suffix=generator` | `templates/assign-generator.md` | `with-assign-generator.patch` (+ `with-evaluator.patch`) |
| `assign` + `role_suffix=evaluator` | `templates/assign-evaluator.md` | `with-assign-evaluator.patch` |
| `wrap` | `templates/wrap.md` | `_base.md` + `with-wrap.patch` |
| `delegate` | `templates/delegate.md` | `_base.md` + `with-delegate.patch` |

`COMPOSER_MODE="atomic"` を選択した場合は `scripts/render-combinators.py` で kind-specific combinator を必ず 1 つ適用し、flag combinator を 0〜N 個重ねる（順序固定: kind → flag）。詳細は `templates/combinators/README.md`。

**create モード**:

```bash
python3 plugins/skill-creator/skills/run-build-skill/scripts/resolve-skill-dirs.py \
  --skill-name "$SKILL_NAME" \
  --skill-dir-name run-build-skill \
  > eval-log/skill-dirs.json
python3 plugins/skill-creator/skills/run-build-skill/scripts/render-frontmatter.py \
  --name "$SKILL_NAME" --kind "$KIND" \
  --brief eval-log/skill-brief.json \
  --template plugins/skill-creator/skills/run-build-skill/templates/"$KIND".md \
  --out plugins/skill-creator/skills/"$SKILL_NAME"/SKILL.md
```

**update モード (CD-002)**:
既存 `SKILL.md` を読み込み、Edit で差分のみ適用する。バックアップや path 解決が必要な場合も Python stdlib script で行い、shell script には委譲しない。

### Step 3: 補助ファイル生成

- run系: `templates/`, `scripts/`, `examples/`
- ref系: `references/articles-full.md` 等の長文置き場
- assign系: `references/rubric.json`, `scripts/render-findings-score.py`
- いずれも本文100行超なら `references/` に追い出す
- `references/` は `skill-build-trace.json` の `source_docs` / `doc_coverage` に対応付ける
- **context予算**: このステップで読む設計書は11章のみ。

### Step 3.5: 再現性トレース生成

`eval-log/skill-build-trace.json` を schema に従って生成する。schema 全項目（design_model / context_map_decision / build_flow_coverage / doc_coverage / layer_decisions / variant_support / pattern_decisions / script_execution_model / governance_model / dogfooding_model / reproducibility_gates / rubric_composition_model / paradigm_analogy_model / output_routing_model / implementation_ledger_model / change_governance_model / plugin_boundary_model / meta_harness_model / variable_contract）は `references/reproducibility-trace-schema.md` を参照。`scripts/validate-build-trace.py` で N/A 理由を含めて検証する。

### Step 4: 命名・構造Lint

```bash
python3 plugins/skill-governance-lint/scripts/lint-skill-name.py "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 plugins/skill-governance-lint/scripts/lint-skill-description.py "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 plugins/skill-governance-lint/scripts/lint-skill-tree.py "$OUT_BASE/$SKILL_NAME"
python3 plugins/skill-governance-lint/scripts/validate-frontmatter.py "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 plugins/skill-governance-lint/scripts/lint-script-frontmatter.py "$OUT_BASE/$SKILL_NAME"
python3 "$SKILL_DIR/scripts/validate-build-trace.py" eval-log/skill-build-trace.json
```

ここでの lint は `manual-preflight` とし、28章の A/B 実行禁止に該当する強制 gate とは呼ばない。最終強制は Hook/CI の `enforced-hook-ci` で同じ検査を再実行する。

6つすべて exit 0 でなければ Step 2 または Step 3.5 へ戻る。

### Step 5: フォーク評価

`assign-skill-design-evaluator` をforkで呼び出し、rubric採点:

```
Skill(assign-skill-design-evaluator) target=$OUT_BASE/$SKILL_NAME
```

出力JSON:
```json
{"rubric_id":"skill-design","rubric_version":"1.0.0","score":N,"findings":[...]}
```

評価時は `skill-build-trace.json` も対象に含め、01/01a の正本フローに未対応の Step があれば C2 漏れとして扱う。メタSkill・rubric・script・hook を含む場合は、26/27/28章の trace 欠落を C2 漏れ、rubric自己編集や実行経路矛盾を C1/C4 失敗として扱う。

### Step 6: ゲート判定

- score >= 80 かつ high=0 → 完了
- それ以外 → findings を本文に反映 → Step 4 へ戻る（最大3周）

### Step 7: subagent自動生成と検証（`--with-subagent` 指定時のみ）

`--with-subagent` フラグが指定された場合に実行する (PF-G3-001: 条件明確化):

```bash
# Step 2 で確定した $SKILL_DIR / $OUT_BASE を再利用 (self-relative + fallback)。
python3 "$SKILL_DIR/scripts/build-subagent.py" \
  --skill-name "$SKILL_NAME" \
  --skill-md "$OUT_BASE/$SKILL_NAME/SKILL.md" \
  --output-dir .claude/agents/ \
  --model "${MODEL:-opus}"
python3 plugins/skill-governance-lint/scripts/lint-skill-description.py ".claude/agents/$SKILL_NAME-subagent.md"
```

SKILL.md frontmatter と本文の目的・手順から `.claude/agents/<skill-name>-subagent.md` を派生し、派生物も lint 対象にする。生成される SubAgent は **`references/agent-template.md` の 9 セクション固定構造**（Frontmatter / Purpose / Inputs / Outputs / Steps / Constraints / **Prompt Templates** / **Self-Evaluation** / Handoff）に準拠すること。詳細は `references/build-steps.md#h2-subagent-生成の詳細実装`。

### Step 7.5: prompt-creator ループ（`--with-prompts` 指定時 または brief.use_prompt_creator=true）

`brief.responsibilities[]` の **R-id 単位** でループする（SubAgent 単位ではない）。各 R-id ごとに `run-prompt-creator-7layer` を呼び、7 層 YAML を `plugins/<plugin>/skills/<skill>/prompts/<R-id>.yaml` へ出力 → 該当 SubAgent の Prompt Templates / Self-Evaluation へ Edit 注入 → `lint-agent-prompt-section.py --strict-coverage --brief <brief>` で検証 → FAIL なら再起動 (max 3 回)。同 brief で再実行時の sha256 一致を `validate-build-trace.py` が `prompt_generation_model.per_responsibility[].layer_yaml_path` で機械検証する。詳細・配置規約は `references/prompt-placement-convention.md` と `references/build-steps.md#h25-prompt-creator-ループ詳細`。

### Step 8: evaluator ペア自動生成（`--with-evaluator` 指定時 または brief.generate_pair_evaluator=true）

generator として作った skill に対し、対称な evaluator を同時生成して **孤児 evaluator** / 孤児 generator を防ぐ。公式CLIは `render-frontmatter.py --out --pair --rubric-refs` とする。詳細手順は `references/build-steps.md#h5-evaluator-ペア生成`。

### Step 9: Hook 配線自動生成（`--with-hooks` 指定時 または brief.hook_events 非空）

Hook 統合スキルの場合、scripts/hook-<name>-<event>.py スケルトンと settings.json マージ案を生成する。settings.json への自動 merge は行わず、人間承認後の手動 merge とする。詳細手順は `references/build-steps.md#h6-hook-配線生成`。

## 配置先（plugin 移行後の正本）

| 用途 | 出力先 | 正本 |
|---|---|---|
| Skill Creator 基盤 | `plugins/skill-creator/skills/<skill>/SKILL.md` | `plugins/skill-creator/skills/` |
| 他 plugin 所属 | `plugins/<plugin-name>/skills/<skill>/SKILL.md` | `plugins/<plugin-name>/` |

- **正本/派生**: `.claude/skills/<skill>/` は `plugins/*/skills/` への symlink 経由派生（直接書き込まない）。`name:` には plugin 名を含めない。詳細: 34章 § plugin 物理レイアウトと symlink 戦略

## Gotchas

- **frontmatter 順序事故**: `disable-model-invocation: true` と `user-invocable: true` の共存は手動呼び出し専用。意図を本文に明記。
- **description 長文化 / ref-* body 肥大**: 動作詳細は本文化、原文は `references/`（08章）。300行制約は SKILL.md 本文のみ。
- **scripts 内 yaml import 禁止 / fork 評価の自己採点禁止**: stdlib のみ（28章）、同context採点は Goodhart 罠（09章）。
- **update 時の全書き換え禁止 (CD-002)** / **全章一括ロード禁止 (CD-005)**: Edit で差分のみ。必要な章だけ Read。
- **Node/Bash 実体禁止**: `.js` / `.sh` を新規生成しない。必要な決定論処理は `scripts/*.py` に置く。

## Additional Resources

- `references/{design-docs-index.md, resource-map.yaml, build-steps.md}` — 設計書索引 / task→設計書map / 詳細手順 (02/03/04 coverage と trace schema 含む)
- `templates/`, `examples/{minimal-ref,workflow-with-evaluator}.md` — kind別雛形と完成例
- `scripts/`: render-frontmatter / validate-naming / validate-build-trace / lint-skill-name / build-manifest-registration-plan
