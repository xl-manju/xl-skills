---
name: run-build-skill
description: Capability 7 kind を新規作成・更新するとき、CapabilityManifest と plugin-composition.yaml を整備するときに使う。
triggers:
  [
    'skill作成',
    'skill更新',
    'agent作成',
    'hook配線',
    'slashcommand作成',
    'plugin-composition編集',
    'prompt生成',
    'workflow定義',
  ]
disable-model-invocation: false
user-invocable: true
argument-hint: '[skill-name] [kind?] [--mode create|update] [--with-subagent] [--with-prompts] [--with-evaluator] [--with-hooks] [--with-knowledge index-search|router-registry] [--model opus|sonnet]'
arguments:
  [
    skill_name,
    kind,
    mode,
    with_subagent,
    with_prompts,
    with_evaluator,
    with_hooks,
    with_knowledge,
    model,
  ]
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
prefix: run
effect: local-artifact
owner: team-platform
since: 2026-05-17
version: 0.2.0 # Capability 7 kind 対応 (skill/agent/hook/command/plugin-composition/prompt/workflow)
manifest: workflow-manifest.json
responsibility_refs:
  - prompts/R1-scaffold.md
  - prompts/R2-responsibility-emit.md
  - prompts/R3-template-select.md
  - prompts/R4-trace-write.md
template_refs:
  - templates/agent-skeleton.md
  - templates/hook-skeleton.md
  - templates/command-skeleton.md
  - templates/plugin-composition-skeleton.yaml
  - templates/prompt-skeleton.md
  - templates/workflow-skeleton.md
schema_refs:
  - references/capability-manifest.schema.json
prompt_format: markdown # 既定: Markdown (.md)。YAML (.yaml) は legacy 許容、新規禁止
script_refs:
  - scripts/render-combinators.py
  - scripts/render-frontmatter.py
  - scripts/validate-naming.py
  - scripts/build-subagent.py
  - scripts/validate-build-trace.py
  - scripts/lint-goal-seek.py
  - scripts/lint-ssot-duplication.py
reference_refs:
  - ref-skill-glossary
  - ref-task-context-map
  - ref-output-routing
  - ref-knowledge-loop
  - references/reproducibility-trace-schema.md
  - references/goal-seek-paradigm.md
# context-budget (CD-005): 章一括ロード禁止 / max-reference-chapters: 3
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-22
audit-trigger: quarterly
---

# run-build-skill

> Phase 2 移行後は `plugins/skill-creator/skills/` が正本、`.claude/skills/` は symlink/deploy target。ただし Step 4 等の lint コマンドは **repo-root cwd 前提**で実行する (bundles.json full bundle 同梱の `plugins/skill-governance-lint/` への repo-root 相対パスに依存)。skill 自身の資産は `$SKILL_DIR` 経由の self-relative 参照。

## Purpose & Output Contract

ユーザー要求から Claude Code Skill を 1 本構築するワークフロー。

- **入力**: `skill_name` (kebab-case), `kind` (run|ref|assign|wrap|delegate), `mode` (create|update), 各種 `--with-*` フラグ, `model` (opus|sonnet)。フラグ仕様は `schemas/build-flags.schema.json`。
- **出力**: `$OUT_BASE/<name>/SKILL.md` (170 行以下を目標、frontmatter 完備、本文は日本語) / `templates/` / `references/` / `scripts/` / `prompts/` / `eval-log/skill-build-trace.json` / `assign-skill-design-evaluator` の評価レポート。
- **完了条件**: rubric score >= 80 かつ high severity 0 件、C1-C4 ゲート pass、`validate-build-trace.py` exit 0。

## Key Rules

### 契約系 (contract)

1. 本文 300 行以下 (07章)。`description` は発動条件のみ、trigger 2-3 個 (08章)。
2. ディレクトリ名 == `frontmatter.name`、`name` に plugin 名を含めない (06/34章)。
3. Python 標準ライブラリ正本。`.sh` / `.js` 新規禁止、scripts 内 yaml import 禁止 (22/28章)。
4. `--mode update` は Edit 差分のみ。全書き換え禁止 (CD-002)。
5. 具体値直書き禁止。`{{PROJECT_ROOT}}` 等の変数で表現し source_trace に残す。

### 責務系 (responsibility)

6. R-id 単位の責務分離。生成 SubAgent は `references/agent-template.md` 9 セクション固定構造。
7. 評価分離: 生成本体は採点せず `assign-skill-design-evaluator` を fork 呼び (09章 Goodhart)。
8. 実行レイヤー (Skill/Subagent/Hook/MCP/CLI/script) の配置理由を trace に記録 (01a/05章)。
9. 横展開候補 (Skill Creator 基盤/hook/lint/adapter/rubric/reference) は plugin 登録判定へ戻す。
10. 量産情報 (`pattern_refs` / `variant_axes` / `reuse_targets` / `deterministic_checks` / `placement_candidates` / `hook_events`) を trace と本文へ反映 (29-35章)。

### lint 系 (lint)

11. P0 lint 4 種 + script-frontmatter + goal-seek + **ssot-duplication** + validate-build-trace を **manual-preflight** として実行 (28章: A/B 強制 gate と呼称分離)。`lint-ssot-duplication.py` は編集前に対象プラグイン全体を重複解析する事前ゲート (両方残し禁止・上書き一本化の判断材料)。検出は **DUP-SCHEMA-ID** (同一 `$id`=正本曖昧, **exit1 で fail**) / **REDIRECT-FAT-BODY** / **DUP-REQUIRED-SET** / **DUP-PASSAGE** (後 3 者は smell、build 時は warn・CI の `--strict` で fail 化) の 4 種。build Step4 は早期警告、強制は `governance-check.yml` の `--strict` 実行が担う。
12. `validate-build-trace.py` が `source_docs` / `build_flow_coverage` / `doc_coverage` / `layer_decisions` / `reproducibility_gates` の空欄・未読・N/A 理由なしを拒否。
13. context 予算 (CD-005): 同時 Read は 3 章まで。`references/resource-map.yaml` で task category → 章選択。
14. ch15/ch16 公式参照確認は必須 (Step 1 冒頭)。
15. 26/27/28 章 / 29-35 章ゲートは N/A 理由つきで省略可、未記入は不可。
16. **prompt 形式**: 新規 prompt は **Markdown (`.md`) を既定**とし、`prompts/<R-id>-<slug>.md` で生成する。骨格は `plugins/prompt-creator/skills/run-prompt-creator-7layer/references/seven-layer-markdown-template.md` を写経。YAML (`.yaml`) は既存資産のみ許容し、新規作成は禁止 (warn を発する)。
17. **Capability 7 kind 統一**: skill / agent / hook / command / plugin-composition / prompt / workflow の全 kind で `CapabilityManifest commonCore` を必須とする。**必須項目集合の正本は `references/capability-manifest.schema.json#/definitions/commonCore.required` 唯一**（本文に再掲しない＝SSOT。現行は `name` / `description` / `kind` / `version` / `owner` の5項目。`since` / `source-tier` 等は任意）。kind 別追加フィールドは同 schema の `definitions/<kind>` を参照。`commonCore` 欠落は `validate-frontmatter.py` が exit 1（同 lint は必須集合を schema から動的ロードし、`--self-test` で正本との drift を検出）。

18. **ゴールシーク必須 (固定手順禁止)**: 実行系 kind (run / assign / wrap / delegate / orchestrator / agent / agent-team / hook-integrated) は達成手順を固定列挙せず、`## ゴールシーク実行` (**Goal + 目的/背景 + 完了チェックリスト + ゴールシークループ**) で構成する。手順は実行時に AI がチェックリストの未達項目から都度生成する。`ref-*` (read-only) は対象外で `## 手順` は「参照用。手順なし。」のまま。正本定義は `references/goal-seek-paradigm.md`。lint は `lint-goal-seek.py` (固定 `### Step N:` の連番羅列を実行系本文で検出したら violation)。
    - **実行可能機構の配線 (with-goal-seek combinator)**: loop 実行系 (run / wrap / delegate) は `render-combinators.py` が `with-goal-seek.patch` を**default-ON で自動適用**し (`--no-goal-seek` で opt-out)、frontmatter `goal_seek:` と `### ゴールシーク配線` を注入する。周回状態は `schemas/goal-seek-loop.schema.json` 準拠の `eval-log/<skill>-progress.json` に記録し、重い周回は `Skill(run-goal-seek)` に fork 委譲する。`assign-*` は checklist のみ (ループ非配線)。`lint-goal-seek.py` は loop 実行系に対し二値チェックリスト項目の存在・曖昧語不在を violation、`### ゴールシーク配線` 不在を warning で検査する。フラグ仕様は `schemas/build-flags.schema.json#/properties/with_goal_seek`。

`kind → templates/_base + combinator` 対応表は **`schemas/template-selection.schema.json#/selection_rules`** を正本とする (本文に再掲しない)。

## ゴールシーク実行

> 本 Skill は固定手順ではなく、下記ゴールへ向けて完了チェックリストの未達項目を埋める手順を都度生成して反復する。下記「局面カタログ」は順序固定の手順ではなく、未達項目に応じてループが選ぶ局面メニュー。正本: `references/goal-seek-paradigm.md`。

### ゴール (Goal)

対象 Capability (7 kind) が、全ゲート (命名/構造 lint・frontmatter・goal-seek/completeness lint・trace exit0・score>=80 かつ high=0) を満たす再利用可能な成果物として `$OUT_BASE/<name>/` に生成・更新され、`eval-log/skill-build-trace.json` が同一 brief→同一判断順序の再現性を証跡化している状態。

### 目的・背景 (Why)

量産対象は kind・ドメイン・出力先が多様で、固定手順は前提が崩れると破綻する。ゴール (= 全ゲート PASS) とチェックリストを到達点に固定し、手順は未達項目から都度導出することで、多様な Capability を同一基盤で再現性高く構築できる。

### 完了チェックリスト (Checklist)

- [ ] kind を 7 種から確定し、commonCore frontmatter (必須集合の正本 = `references/capability-manifest.schema.json#/definitions/commonCore.required`: `name`/`description`/`kind`/`version`/`owner`) を生成した
- [ ] 本文 300 行以下・description は発動条件のみ・trigger 2-3 個 (08章)
- [ ] kind 別必須サポート資産 (prompts/references/schemas/scripts) を実在・共有正本参照・`completeness_exempt` 理由付き宣言のいずれかで満たした (`lint-skill-completeness.py` exit0)
- [ ] P0 lint 群 + `lint-goal-seek.py` + `lint-skill-completeness.py` + `lint-ssot-duplication.py` + `validate-build-trace.py` が exit 0
- [ ] fork した `assign-skill-design-evaluator` の score>=80 かつ high=0
- [ ] `eval-log/skill-build-trace.json` に `source_docs`/`doc_coverage`/`layer_decisions`/`reproducibility_gates` を空欄なく記録 (未使用は N/A 理由付き)
- [ ] (`--with-*` 指定時のみ) subagent/prompt/evaluator/hook 生成と整合 lint を完了
- [ ] (`--with-knowledge` or `brief.knowledge_loop` 指定時のみ) knowledge/ 雛形展開 + 4スクリプト同梱 + `## ナレッジループ`節注入 + `knowledge_loop`記述子(`consult_at: ["runtime"]`) + `lint-knowledge-loop.py` exit0 (KL-001..007)

### ゴールシークループ

正本 `references/goal-seek-paradigm.md` の 6 ステップ (現状評価→手順生成→実行→検証→Anchor Step→反復/差し戻し) に従う。本 Skill 固有の差分:

- 現状評価は上記チェックリストの未達項目を対象にし、それを埋める局面を下記「局面カタログ」から選ぶ (順序固定なし)。
- 検証は決定論検査 (lint/trace/score) を優先し、`### 局面: 命名・構造 Lint` / `### 局面: フォーク評価` のコマンド群で機械判定する。
- ゲート未達は最大 3 周で findings を反映し再実行、超過時は `open_issues` に残し差し戻す。

## 局面カタログ (順序は都度判断)

詳細フローは `workflow-manifest.json` の phases、各責務プロンプトは `prompts/<R-id>.md` (Markdown 既定。legacy `.yaml` も読み取り可) に委譲する。下記は固定順序ではなく、ゴールシークループが未達チェックリスト項目に応じて選ぶ局面群。

### Step 0: kind 分岐ナビゲーション (phase: init-pre)

本 Skill は **Capability 7 kind** (skill / agent / hook / command / plugin-composition / prompt / workflow) を統一抽象として扱う。以下 4 段で分岐する。

1. **kind 確認**: 引数 `kind` または `brief.kind` を確定。既定は `skill`。未指定なら Step 1 のヒアリングで決める。7 kind 以外は exit 1。
2. **対応 skeleton 選択**: kind → skeleton/出力先の対応は `schemas/template-selection.schema.json#/selection_rules` の `capability_kind_map` を正本とする (本文に再掲しない=SSOT)。人間可読の対応表+検証コマンドは `references/build-steps.md` §I.1。
3. **Manifest 検証**: 全 kind で `CapabilityManifest commonCore` を `references/capability-manifest.schema.json` で検証。kind 別追加フィールド (`definitions/kindSkill`, `definitions/kindAgent` …) も同 schema で検証する。
4. **lint hook 連動**: kind に応じた lint を Step 4 で起動 (skill→既存 4 種、agent→`lint-agent-prompt-section.py`、hook→`lint-script-frontmatter.py`、command→`lint-command-md.py`、plugin-composition→`lint-plugin-composition.py`、prompt→`lint-prompt-md.py`、workflow→`lint-workflow-md.py`)。未整備 lint は warn 出力に留め、Hook/CI で再実行する。

> 既存「Skill のみ作る」呼び出し (`kind=run|ref|assign|wrap|delegate`) は **kind=skill 配下のサブ種別** として後方互換維持。引数なしまたは `kind` が 5 択のいずれかなら従来通り Step 1 以降の skill 専用フローへ直行する。

### Step 1: 要求ヒアリング (phase: init)

> **[MANDATORY]** 冒頭で `Skill(ref-yaml-spec-fetcher)` を呼び `yaml-spec-cache.md` を Read。`validate-build-trace.py` が 15/16 章未実施を exit 1 で拒否する。

`resolve-skill-dirs.py` で `$SKILL_DIR` / `$OUT_BASE` 確定 → `references/resource-map.yaml` で task category 選択 → 01章 5 要素 + 01a Step2 実行レイヤー判断表を埋める。詳細は `references/build-steps.md`。

### Step 2: テンプレ展開 / 既存読込 (phase: scaffold)

kind → template 選択は `prompts/R3-template-select.md` (R3) と `schemas/template-selection.schema.json` に従う。骨格生成は `prompts/R1-scaffold.md` (R1)。`COMPOSER_MODE=atomic` の場合は combinator を kind → flag 順で適用。

### Step 3: 補助 references / 生成 (phase: references)

run 系は `templates/` / `scripts/` / `examples/`、ref 系は `references/articles-full.md`、assign 系は `references/rubric.json` / `scripts/render-findings-score.py`。本文 100 行超は `references/` へ追い出す。

### Step 3.5: 再現性トレース生成 (phase: trace-write)

`eval-log/skill-build-trace.json` を `schemas/skill-build-trace.schema.json` と `prompts/R4-trace-write.md` (R4) に従って章別記入。

### Step 4: 命名・構造 Lint (phase: scripts)

> `workflow-manifest.json` は**宣言的リソース** (schema/prompt/reference) の正本。**命令的 lint コマンド**は SKILL.md Step4 + CI が正本管理する (責務分離)。lint を manifest に resource 登録はしない。

```bash
python3 plugins/skill-governance-lint/scripts/lint-skill-name.py "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 plugins/skill-governance-lint/scripts/lint-skill-description.py "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 plugins/skill-governance-lint/scripts/lint-skill-tree.py "$OUT_BASE/$SKILL_NAME"
python3 plugins/skill-governance-lint/scripts/validate-frontmatter.py "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 plugins/skill-governance-lint/scripts/lint-script-frontmatter.py "$OUT_BASE/$SKILL_NAME"
python3 plugins/skill-governance-lint/scripts/lint-skill-completeness.py "$OUT_BASE/$SKILL_NAME"  # kind別必須サポート資産(prompts/references/schemas/scripts)を実在/共有正本参照/completeness_exempt理由付きのいずれかで充足。空欄(無宣言の欠落)は exit 1
python3 "$SKILL_DIR/scripts/lint-goal-seek.py" "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 "$SKILL_DIR/scripts/lint-ssot-duplication.py" --plugin-dir "$(dirname "$OUT_BASE")"  # SSOT 重複(正本曖昧/redirect 太り/required 二重定義/本文再掲)を検出。DUP-SCHEMA-ID は exit 1
python3 "$SKILL_DIR/scripts/lint-knowledge-loop.py" "$OUT_BASE/$SKILL_NAME"  # knowledge/ がある場合のみ KL-001..007 を検査(無ければ exit0 skip)。既定 warn、CI の --strict で fail 化
python3 "$SKILL_DIR/scripts/validate-build-trace.py" eval-log/skill-build-trace.json
```

全て exit 0 でなければ Step 2 / 3.5 へ戻る。

### Step 5: フォーク評価 (phase: trace-write)

`Skill(assign-skill-design-evaluator) target=$OUT_BASE/$SKILL_NAME` を fork 呼び、`{"score":N,"findings":[...]}` を受領。`skill-build-trace.json` も評価対象に含め、01/01a / 26-28 章漏れを C2、rubric 自己編集を C1/C4 失敗として扱う。

### Step 6: ゲート判定

score >= 80 かつ high=0 で完了。それ以外は findings を本文に反映し Step 4 へ戻る (最大 3 周)。

### Step 7: subagent 派生 (phase: prompts-emit, `--with-subagent`)

`build-subagent.py` で `.claude/agents/<skill-name>-subagent.md` を派生 → `lint-skill-description.py` で検証。9 セクション固定構造に準拠。

### Step 7.5: prompt-creator ループ (phase: prompts-emit, `--with-prompts` or `brief.use_prompt_creator`)

`brief.responsibilities[]` の **R-id 単位** でループ。詳細は `prompts/R2-responsibility-emit.md` (R2) と `references/prompt-placement-convention.md`。

### Step 8: evaluator ペア生成 (phase: evaluator-emit, `--with-evaluator` or `brief.generate_pair_evaluator`)

公式 CLI は `render-frontmatter.py --out --pair --rubric-refs`。詳細は `references/build-steps.md#h5-evaluator-ペア生成`。

### Step 9: Hook 配線生成 (phase: scripts, `--with-hooks` or `brief.hook_events` 非空)

`scripts/hook-<name>-<event>.py` スケルトンと `settings.json` マージ案を生成。自動 merge 禁止、人間承認後の手動 merge とする。

### Step 10: ナレッジループ注入 (phase: references, `--with-knowledge` or `brief.knowledge_loop`)

生成スキルに「知識を更新・蓄積し、検索して活用し、使うほど良くなる」ループを組み込む横断 combinator。正本仕様は `Skill(ref-knowledge-loop)`(構築編+運用編)。手順:

1. `ref-knowledge-loop` を Read し、`brief.knowledge_loop.pattern`(`index-search` | `router-registry`)を確定(未指定なら §パターン選択フローで決定)。
2. `templates/knowledge-skeleton/<pattern>/` を `$OUT_BASE/$SKILL_NAME/knowledge/` へ展開し、`scripts/{search_knowledge,build_index,record_usage,add_entry}.py` を `scripts/` へコピー(注入される `## ナレッジループ` 節が参照する4スクリプトと一致させる)。
3. `render-combinators.py --with-knowledge` で SKILL.md に `## ナレッジループ` 節と frontmatter `knowledge_loop` ブロックを決定論注入(検索・追加・§12活用ログ・分割閾値・`consult_at` を記載)。注入本文は同梱 `scripts/` のみ参照し skill-creator 内部へ依存しない(配布スキル自己完結)。
4. frontmatter `knowledge_loop` 記述子に `consult_at: ["runtime"]` が入る(`references/capability-manifest.schema.json#/definitions/commonCore.properties.knowledge_loop`)。Loop A は必ず runtime。
5. Step 4 の `lint-knowledge-loop.py` で KL-001..007 を検査(KL-006=add_entry.py存在/warn、KL-007=ストア位置↔consult_at一致/error)。`assign-skill-design-evaluator` も KL-\* を採点。

> **Loop B (skill-creator 自己適用)**: skill-creator 自身も `plugins/skill-creator/knowledge/` を持ち、`consult_at: [build-time]` で過去ビルド知見を作成時に検索する。生成物側(Loop A)と同一機構を dogfooding する(SSOT)。

### Step 11: Notion スキル一覧 DB へ upsert (phase: notion-register, `--notion-register`)

build 完了後、量産プラグインを Notion の SSOT (スキル一覧 DB) に冪等登録する。**プラグイン単位 1 行**で、配下の個別 Skill はページ本文に列挙される(`scripts/notion-upsert-plugin.py` が `plugins/<plugin>/skills/` を走査)。手順:

1. `--notion-register` または `brief.notion_register=true` 未指定なら phase skip。
2. `python3 scripts/notion-upsert-plugin.py --plugin <plugin>` 実行 (TITLE 検索→PATCH/POST 冪等)。ヒアリングシート由来なら `--hearing-sheet-id <notion-page-id>` で 1:1 relation を埋める。
3. token は `.notion-config.json` の `keychain_service` / `keychain_account` (既定: `notion-api-key.xl-skills` / `xl-skills`) から Keychain 経由で取得する。CI では `INTAKE_ALLOW_ENV_TOKEN=1` を明示した場合のみ `$NOTION_TOKEN` を許可する。不在なら警告のみで skip。
4. 整合性は `scripts/lint-notion-relations.py` が 1:1 / N:1 不変条件 (プラグイン名重複・ヒアリング多重紐付け・改善要望の対象未設定) を CI で検証。

正本スクリプト: `scripts/notion-upsert-plugin.py` / スキーマ SSOT: `doc/notion-schema/skill-list.schema.json` (含む `feedback_protocol` SSOT)。

### Step 11.5: feedback-loop 同梱と配備 (default-ON / 再現性の核)

量産プラグインに改善要望ループを **default-ON で機械的に保証** する。詳細は `references/feedback-loop-deployment.md`。要点:

- **配備**: phase `feedback-deploy` (workflow-manifest, `default_on: true`) が `plugins/<plugin>/skills/run-skill-feedback` を skill-creator 正本への相対 symlink で冪等配備。物理コピー禁止 (drift 防止)。
- **SSOT**: 発火条件 / 対話項目は `doc/notion-schema/skill-list.schema.json#feedback_protocol`。プラグイン側で再定義しない。
- **周知**: 量産先の plugin.json / README / commands / agents いずれかに `run-skill-feedback` への発火経路を必ず記載。
- **lint**: `scripts/lint-feedback-protocol.py --strict` が R1-R7 (schema/SKILL.md/upsert 三者整合 + R6 周知 + R7 配備存在) を CI で検査。違反時 merge ブロック。
- **opt-out**: `brief.no_feedback_loop: true` または CLI `--no-feedback-loop` のみ。trace.layer_decisions に理由必須。skill-creator 自身は自動除外。

### Step 12: 内容 adequacy LLM 評価 (content-review, default-ON / ハーネスの核)

機械 lint は「ひな形通り」しか見ない。**内容がユーザー要望を最適反映しているか** は LLM 評価で担保する。詳細: `references/content-review-protocol.md`。要点: ローカル build 完了時に `run-elegant-review` + `assign-skill-design-evaluator` を必須起動し verdict json を `eval-log/<plugin>/<skill>/content-review/` に保存。CI/pre-push は `scripts/lint-content-review.py --changed-only` で成果物存在 + verdict=PASS のみ機械検査 (LLM はリモートで実行しない)。`--skip-content-review` 明示時のみ skip / trace 必須。verdict=FAIL は SKILL.md 改善→再評価を max_iter=3 まで反復。

## 配置先

| 用途               | 出力先                                          | 正本                            |
| ------------------ | ----------------------------------------------- | ------------------------------- |
| Skill Creator 基盤 | `plugins/skill-creator/skills/<skill>/SKILL.md` | `plugins/skill-creator/skills/` |
| 他 plugin 所属     | `plugins/<plugin>/skills/<skill>/SKILL.md`      | `plugins/<plugin>/`             |

`.claude/{skills,agents,commands}/<name>` は symlink 派生 (直接書き込まない)。**build/更新後は build 完了契約として `bash scripts/sync-skills-to-claude.sh --apply` (唯一の生成器 `scripts/build-claude-symlinks.py` を冪等呼び出し。`make sync` も可) を必ず実行**し、新規 skill/agent/command を `.claude/` へ展開する (未実行だと Claude Code が認識しない)。最終ゲートは CI `build-claude-symlinks.py --check` (orphan/broken/欠落 を fail-closed 検出)。生成器が SSOT であり、build 工程内に別途 symlink 生成を再実装しない。詳細: 34章 § plugin 物理レイアウトと symlink 戦略。

## Gotchas

- frontmatter 順序事故 / description 長文化 / ref-\* body 肥大 / scripts 内 yaml import / fork 評価の自己採点 / update 全書き換え / 全章一括ロード / `.js` `.sh` 新規生成、いずれも禁止。詳細は `references/build-steps.md`。

## Additional Resources

- 資産索引の正本は frontmatter (`manifest` / `responsibility_refs` / `template_refs` / `schema_refs` / `script_refs` / `reference_refs`) と `references/resource-map.yaml` (task category → 設計書章選択)。`examples/` = 完成例 (minimal-ref / workflow-with-evaluator)。
- references/ 主要補助: `design-docs-index.md` (設計書索引) / `build-steps.md` (詳細手順) / `capability-manifest.schema.json` (Capability 7 kind 統一 Manifest 正本)。他の references/ は本文各 Step から個別参照。
