---
name: io-contract
description: 生成スキルの入出力契約と、生成プラグインが満たすべき検証接続/Markdown evidence 定義を読む。R3 出力形式と R4 検証の正本。
kind: reference
owner: team-platform
since: 2026-06-29
source-tier: internal
---

# 入出力契約と検証 (§9 入出力契約 / §10 検証・evidence)

> パスはすべて repo root 相対。

## §9 生成スキルの入出力契約

- **入力**: プラグイン構想 1 件 (自然文 + 任意でコンポーネント希望)。`--mode create|update`。
- **処理**: R1(要件定義)→R2(分解)→R3(生成)→R4(検証) の責務 (= §8 P1-P8 ライフサイクル) を goal-seek ループで実行する。各責務の詳細プロンプトは `prompts/R1-R4`。
- **出力**:
  1. **N 本のタスク仕様書 (Markdown)** — 各々が skill-brief 主要フィールド + §14 (skill-creator-spec-reflection.md) の評価基準を frontmatter で携帯。
  2. **index.md(main)** = top-sort 順目次 + 本数根拠 (`requested_count`/`derived_count` 並記) + 完了条件 + plugin-creator 物理契約。
  3. **component-inventory.json** = 5種を検討した証跡 (`considered_component_kinds`) と、実際に生成する buildable components、plugin-level surfaces の採否、不要理由、依存 DAG、本数透明化フィールド (`requested_count`/`derived_count`)。省略理由の正本キーは `plugin_level_surfaces.<surface>.omitted_reason` 一本のみ (評価器が読むのもこのキーのみ)。

### 本数透明化フィールド (13 問題の可視化)

ユーザーの具体的本数要求を黙殺しないため、`component-inventory.json` と `index.md` 本数根拠に次を必ず併記する (「13 の扱い」節と対応):

| フィールド | 意味 | 既定 |
|---|---|---|
| `requested_count` | ユーザーが要求した本数 (例 13)。R1 が会話履歴から検出 | 要求が無ければ `null` |
| `derived_count` | 構成要素数 N (= buildable component spec 本数) と依存 DAG から導出した既定本数 | = 実生成 spec 本数 (`--force-13` 時は 13) |
| `derivation` | `derived_count` の導出根拠 (自然文) + `requested_count` との差の理由 | 必須 |

`requested_count != null` かつ `requested_count != derived_count` の場合、`derivation` に差の理由を明示する (一方で他方を上書きしない)。`--force-13` 指定時のみ `derived_count == 13` に上書きし理由を記録する。

### 出力先 (決定論的に解決・再現性の SSOT)

タスク仕様書の出力先は曖昧にせず**決定論的に解決する** (同一構想 → 常に同一ディレクトリ)。

| 項目 | 規約 |
|---|---|
| **既定パス** | repo-root (`$CLAUDE_PROJECT_DIR`/cwd) 相対の **`eval-log/plugin-dev-planner/<plugin-slug>/`** |
| **`<plugin-slug>`** | 対象プラグインの **ASCII kebab フォルダ名** (例 `notion-task-sync`)。**R1 が `goal-spec.json` の `target_plugin_slug` に固定し全 goal-seek 周回で不変** (中間成果物アンカーと同じ不変アンカー原則=ループが何周しても出力先がブレない)。R1 は構想自由文でなく確定済みの target plugin kebab 名を渡す (日本語主体の自由文は ASCII 以外が脱落し別構想と slug 衝突しうるため) |
| **slug 導出** | 決定論: 小文字化 → 英数とハイフン以外を `-` → 連続ハイフン圧縮 → 前後 `-` 除去 (`specfm.plan_slug` が正本実装) |
| **上書き** | `--out-dir <path>` 明示指定で既定を上書き (相対は repo-root 基準)。指定値も `goal-spec` に固定 |
| **内容** | `goal-spec.json` + `run-plugin-dev-plan-progress.json` + `run-plugin-dev-plan-intermediate.jsonl` + `index.md`(main) + `component-inventory.json` + `C01-<kind>.md` … `CNN-<kind>.md` (N 本) + `handoff-run-plugin-dev-plan.json` + `plan-findings.json`。`examples/sample-plan/` と同形の plan 成果物を plugin 別ディレクトリに同居 |
| **PLAN_DIR** | 検証 core 5 scripts / 6 invocations、build handoff gate、R4 evaluator はこの出力先を `PLAN_DIR` 引数に取る。plugin-dev-planner 自身の dogfood は別途 `check-plugin-surface-audit.py --plugins-dir plugins --strict-manifest --expect-plan-ready plugin-dev-planner` で現物 surface を横断棚卸しする。`specfm.plan_output_dir(name, out_dir)` が解決の正本 (第 1 引数は生 plugin 名でも `plan_slug` 済 slug でも可=冪等。戻り値は repo-root 相対で、絶対化は呼び出し側が repo-root 基準で行う) |
| **component kind 検討証跡** | `considered_component_kinds` は 5 種 (`skill`/`sub-agent`/`slash-command`/`hook`/`script`) を全列挙する。これは「全種を検討した」証跡であり、「全種を必ず生成する」要求ではない。生成対象は `components[]` に必要最小で列挙する。`check-surface-inventory.py` がこの分離を機械検査する |
| **L3→L4 追跡 (`build_target`)** | 各コンポーネント (inventory / index) は run-skill-create が実体を置く L4 パスを `build_target` に記録する (例 skill→`plugins/<plugin-slug>/skills/<skill>/`、sub-agent→`plugins/<plugin-slug>/agents/<name>.md`、hook→`plugins/<plugin-slug>/hooks/<name>.py`、slash-command→`plugins/<plugin-slug>/commands/<name>.md`、script→親 skill の `scripts/<name>.py`)。計画(L3)は専用 dir に分離しつつ「どの仕様書がどこで実体化するか」を追跡可能にする (co-location せずトレーサビリティ確保)。**`detect-unassigned.py` が object 形式 `component-inventory.json` の各 component に `build_target` 非空を機械検査**し、doc-only に留まらせない (欠落で exit1) |
| **非生成** | 実プラグインディレクトリ (`plugins/<plugin-slug>/`) は本スキルでは作らない (計画のみ・L4 は run-skill-create が生成)。`eval-log/plugin-dev-planner/<plugin-slug>/` は gitignore 対象の plugin 別計画作業領域 |

- **後段接続**: 各仕様書 → `run-skill-create`(L1) → L4 build。本スキルは投入も build もしない。

### component_kind 別 frontmatter 契約 (skill 偏重を解消)

**plugin = 5 buildable 構成要素 + plugin-level surfaces** (`component-domain.md`)。生成 spec は単一形状でなく `component_kind` を宣言し、kind 別に異なる frontmatter を携帯する。`component_kind` ∈ {skill, sub-agent, slash-command, hook, script} を必須宣言し、`id` / `depends_on` (index top-sort + unassigned 検出に使う) は全 kind 共通。manifest / harness / eval / composition / MCP / app connector は `component_kind` ではなく `plugin_meta` と inventory に記録する。

> **kind→必須キーの正本は1つ (SSOT=`scripts/specfm.py` の `STRUCTURAL_REQUIRED`)**。下表と `prompts/R3-emit-specs.md` §2.2 の kind 別キー列挙は、その実行可能正本の**人間可読 projection** であって第二の正本ではない。両者の一致は `tests/test_kind_key_doc_parity.py` が機械強制する (specfm にキーを足して散文を忘れると fail)。「ひな形が無い」のでなく「frontmatter のひな形を実行可能 schema (specfm) + lint + 生成 skeleton + ゴールデン例として持つ」のが本スキルの方式。手書きの穴埋め skeleton ファイルは持たず、必要時は `scripts/render-spec-skeleton.py` が specfm 正本から生成する。

| component_kind | 構造的必須キー (kind 固有) | 後段ルーティング |
|---|---|---|
| **skill** | skill-brief **base required 14**(実 schema 逐語): `skill_name`/`prefix`/`kind`(=run/ref/wrap/assign/delegate)/`hierarchy_level`/`trigger_conditions`/`output_contract`/`boundary`/`placement_candidates`/`cli_tools`/`deterministic_checks`/`external_systems`/`mcp_tools`/`needs_independent_context`/`needs_lifecycle_enforcement`。**条件付き**(allOf): kind∈{run,wrap,assign,delegate}→`goal`/`purpose_background`/`checklist`、kind∈{run,assign}→`responsibilities`、wrap→`base_skill`、delegate→`delegate_agent`。`output_language`/`mass_production_profile` は任意 property | `run-skill-create`(L1) へ 1 本ずつ投入 |
| **sub-agent** | `name`/`description`/`tools`(最小権限)/`independent_context: true`/`responsibility_anchor`(prompts 参照)/(任意)`evaluator_pair` | 親 skill build 内 `run-build-skill --with-subagent` |
| **slash-command** | `name`/`description`/`argument-hint`/`allowed-tools`/`disable-model-invocation` | 親 skill build 内 run-build-skill kind=command dispatch |
| **hook** | `event`(PreToolUse\|PostToolUse\|Stop\|UserPromptSubmit\|SessionEnd)/`matcher`/`exit_semantics`(fail-closed は exit2)/`settings_wiring`/`fail_closed: true` | 親 skill build 内 `run-build-skill --with-hooks` |
| **script** | `/// script` 相当 (`script_name`/`purpose`/`inputs`/`outputs`/`exit_codes`/`network`/`write_scope`) + `stdlib_only: true` + `tests_min: 80` | 親 skill build の scripts/ + tests/ |

`run-skill-create` は **skill 専用**。非 skill 4 種は単独投入せず、親 skill の build フロー (run-build-skill の kind dispatch / `--with-*`) で生成される。

### タスク仕様書 本文 section 契約 (frontmatter と別軸・`detect-unassigned.py` の正本)

frontmatter は specfm が厳格に operationalize する一方、本文 (prose) は LLM の判断を要するため形状を凍結しない。ただし**空セクションを許すと品質精度の床が抜ける**ため、本文にも最小の機械的な床を敷く。これが `scripts/detect-unassigned.py` の `REQUIRED_SECTIONS` / `empty_body_sections` の正本 (旧 `phase-templates.md` 参照は実体不在だったため本節へ置換):

| section | 必須 | 中身の床 (機械強制) | 中身の指針 (非強制・ゴールデン例が手本) |
|---|---|---|---|
| `## 目的` | yes | 見出し存在 + 直後に非空本文 | このコンポーネントが端から端で何を達成するか 1-3 文 |
| `## 成果物` | yes | 見出し存在 + 直後に非空本文 | 生成される実体 (`build_target` 配下) と携帯する評価基準を箇条書き |
| `## 完了条件` | yes | 見出し存在 + 直後に非空本文 | quality_gates / harness の充足条件を観測可能な形で列挙 |

機械の床は「見出し存在 + 非空本文」までに留める (`## 成果物` に `build_target` リテラルを必記する等の意味検査はしない=ゴールデン例も満たさず Goodhart 化するため)。床を超える本文の精度は**下流トラスト** (後述 §10) と evaluator の意味判定に委ねる。skeleton 穴埋めファイルは置かない (形状の正本は frontmatter=specfm、本文は床付きの自由記述)。

### build handoff 契約 (L3 計画 → L4 実 build の橋)

`handoff-run-plugin-dev-plan.json` は、plan が「後段で build できる粒度か」を機械検証するための routing artifact。run-plugin-dev-plan 自身は L4 実 build を実行しないが、後段 `run-skill-create` / `run-build-skill` / 将来の scaffold executor が消費できるよう次を必須にする。

| field | 要件 |
|---|---|
| `plan_dir` | 解決済み PLAN_DIR。repo-root 相対または絶対パス |
| `target_plugin_slug` | ASCII kebab plugin slug |
| `mode` | `create` / `update` |
| `requested_count` | `null` または正の int |
| `derived_count` | routes 件数と一致する正の int |
| `force_13` | bool。`true` なら `derived_count == routes.length == 13` を検査する |
| `routes[]` | top-sort 順。各 route は `id` / `component_kind` / `name` / `spec` / `depends_on` / `builder` / `build_kind` / `build_args` / `build_target` を持つ |
| `routes[].builder` | skill→`run-skill-create`、sub-agent/slash-command/hook→`run-build-skill`、script→`parent-skill-build` |
| `routes[].build_kind` | skill→`skill`、sub-agent→`agent`、slash-command→`command`、hook→`hook`、script→`script`。`run-build-skill` の Capability 7 kind へ渡す実行 kind を明示する |
| `routes[].build_args` | 後段 builder へ渡す最小引数。`run-build-skill` route では `kind == build_kind` を必須にする |
| `envelope` | manifest/marketplace 等 plugin-level surface の owner/status/build_target。`external_gap` / `manual-user-gated` は gap/approval reason 必須 |
| `envelope.manifest.draft_path` | `<PLAN_DIR>` 相対の manifest draft。存在・JSON parse・`name == target_plugin_slug`・TODO placeholder 不在を検査する |

`scripts/check-build-handoff.py` が spec 実在、top-sort、builder/build_kind/build_args 整合、`force_13` と `derived_count` と routes 件数一致、manifest draft、envelope gap reason を検査する。これにより「仕様書をもとにプラグインを構築できるか」の最低条件を、実 build 実行前に fail-closed で確認する。

### core 規律 (全 buildable spec が必ず携帯。check-spec-gates.py が機械検証)

skill-creator ネイティブ規律を参照でなく **frontmatter キーへ焼いて検証**する (operationalize)。

```yaml
quality_gates:
  p0_lint: [<component_kind 別の必須 lint 名を網羅>]   # skill は P0 lint 8 本
  build_trace: required                                # F2
  elegant_review: {conditions: [C1, C2, C3, C4], all_pass: true}  # A1
  content_review: {verdict: PASS, sha_match: true}     # A8
  evaluator: {threshold: 80, high_max: 0}              # A5
harness_coverage:
  min: 80                                              # C1/C2 (スカラでなくブロック)
  kind_pass: <ref→source-traceability+ref-review / assign→evaluator verdict / loop→criteria検証test+content-review verdict>
```

`quality_gates.p0_lint` が網羅すべき必須 lint 集合は component_kind 別 (`specfm.P0_LINT_BY_KIND`): skill=8 本 / sub-agent=[validate-frontmatter,lint-skill-description,lint-agent-prompt-section] / slash-command=[validate-frontmatter] (command 専用 lint は未提供) / hook=[validate-frontmatter,lint-script-frontmatter] / script=[lint-script-frontmatter]。

### 条件付き規律 (kind/feature/階層でゲート。盲目的に全 spec へ焼かない=bloat/Goodhart 回避)

| 規律 (キー) | 適用条件 | 焼き先 |
|---|---|---|
| `feedback_contract.criteria` (B1) | skill かつ kind∈{run,wrap,delegate} (ref/assign は `skip_reason` 可)。criteria は当該 spec の goal/checklist 由来 (**purpose-acceptance**)・汎用ゲート言い換え禁止 (`check-spec-frontmatter.py` が機械検証) | component spec |
| `goal_seek` (D1/D2/D5) | skill かつ kind∈{run,wrap,delegate} | component spec |
| `prompt_layer: 7layer` (A11/E5/E6) | prompts を持つ component (skill run/assign, sub-agent) のみ | component spec |
| `knowledge_loop` (G1) | opt-in (`features: [knowledge_loop]`) 時のみ | component spec |
| `combinators` (D5/G2) | 全 skill (build flag 非該当時は空配列 `combinators: []` で no-flag を明示)。`check-spec-matrix-coverage.py` の述語 `_is_skill` が全 skill spec に焼き先キー存在を要求する | component spec |
| manifest/marketplace/cachebuster/配布判定/bundles/PKG/governance/CI/SSOT重複 (plugin-creator + F3/F4/F5/F6/A10/A7/F7/D6) | **plugin 階層** (per-component でなく) | index(main) の `plugin_meta` |

`skill-brief.schema.json` 主要フィールドへ無加工で写せること (schema parity) は skill-kind spec で要件化する。

### index(main) の plugin_meta (plugin 階層の規律を焼く)

index frontmatter に `plugin_meta` を持たせ、plugin 階層の規律を集約する:

```yaml
plugin_meta:
  manifest:
    required: true
    path: .claude-plugin/plugin.json
    name_matches_folder: true
    no_todo_placeholders: true
    validate_plugin: true
  marketplace:
    default_personal: true
    policy:
      installation: AVAILABLE
      authentication: ON_INSTALL
      category: Productivity
    cachebuster_for_update: true
  distribution: {distributable: <bool>, bundles: [...], marketplace: <bool>}  # F3/F4
  pkg_contract: {...}        # A7/F5 (plugin-package-evaluator / PKG 契約)・条件付き(下記)
  governance: {...}          # A10 (rubric governance runbook)・条件付き(下記)
  ci: {...}                  # F6 (governance-check.yml 配線)・コア(常に必須)
  ssot_dedup: {...}          # F7 (lint-ssot-duplication)・条件付き(下記)
  feedback_deploy: {...}     # D6 (量産先への run-skill-feedback 配備)・条件付き(下記)
  # 条件付き 4 キー (pkg_contract/governance/ssot_dedup/feedback_deploy) は該当しない構想では
  #   <key>: {applicable: false, reason: "<N/A の根拠>"}
  # と明示宣言できる (例 skill のみ・非配布構想で PKG packaging が不要 → A7「skill-only は PKG 一部 N/A」と整合)。
  # 空 dict / 欠落は不可 (省略は必ず根拠付き明示=plugin_level_surfaces.<surface>.omitted_reason 原則と同型)。
```

`check-spec-gates.py` が plugin_meta を**値域検証**する (存在チェックでない): `manifest.path` は `.claude-plugin/plugin.json`、`manifest.validate_plugin` は true。`marketplace.policy.installation` は `NOT_AVAILABLE` / `AVAILABLE` / `INSTALLED_BY_DEFAULT`、`marketplace.policy.authentication` は `ON_INSTALL` / `ON_USE`、`category` は非空。`distributable` は bool 必須。`distributable:false` なら `bundles` は空 (=非登録を明示) かつ `marketplace` は false/不在 (非配布整合)。`distributable:true` なら `bundles` に最低 1 件。**コア** `manifest`/`marketplace`/`ci` は常に非空 dict。**条件付き** `pkg_contract`/`governance`/`ssot_dedup`/`feedback_deploy` は非空 dict だが、該当しない構想では `{applicable: false, reason: <非空>}` で明示 N/A 可 (reason 空はエラー)。matrix-coverage は焼き先スロットの addressed (空コンテナ・`{applicable:false}` 含む)、gates は値域、と責務分離する。

## §10 検証・完了条件 (xl-skills 接続 / Markdown evidence)

対象スキル(L2)が `run-skill-create` 完了時に満たす条件 (詳細強制内容は skill-creator-spec-reflection.md):

| 接続先 | 検証 |
|---|---|
| **P0 lint 8 本** | `plugins/skill-governance-lint/scripts/` の 8 本 全 exit0 |
| **build-trace** | `validate-build-trace.py` exit0・章 coverage 全 PASS/N-A/skip |
| **content-review** | `scripts/lint-content-review.py` verdict=PASS (独立 SubAgent で genuine 生成・sha 一致) |
| **harness-coverage** | `validate-harness-coverage.py` / `make coverage-gate`。run=loop パス: criteria 検証テスト(inner/outer) + content-review verdict + 同梱 scripts 機能テスト ≥80% |
| **schema parity** | 出力仕様書が `skill-brief.schema.json` 主要フィールドへ無加工で写せる |
| **evaluator** | `assign-skill-design-evaluator`(fork) score≥80 / high=0 |
| **elegant-review** | 新規/30 行超で C1-C4 全 PASS (`phase-output.schema.json` convergence_status enum 準拠) |
| **feedback_contract** | criteria を `feedback_contract_ssot.py`(SSOT) 制約に適合・content-review の criteria_evaluated と突合 |

**Markdown 主体プラグインの evidence 定義 (スクショ代替)**: lint exit0 ログ + schema parity + build-trace coverage 全 PASS + content-review verdict(PASS) + `eval-log/coverage/skills/<plugin>__<skill>.json`(mechanical/llm_eval)。**ランタイムスクショは取得しない** (取得不要を確定明記。対象=Claude Code の skill/plugin/hook/script=GUI ランタイム非保有の Markdown/CLI 主体ゆえ、視覚受入証跡でなく lint/test/coverage 等のテキスト受入証跡で完了を証明する)。

**本文トラスト境界 (L3 が保証する範囲・skeleton 不要の根拠)**: 本スキル(L3 計画)が各タスク仕様書で**機械的に保証するのは (i) frontmatter 形状=shape (specfm/lint) と (ii) 評価基準=criteria の携帯**であり、**本文 prose の最終的な内容品質は下流 L1 `run-skill-create` の再ヒアリング (`run-skill-elicit`) と build 時 evaluator の意味判定で確定する**。L3 本文の責務は「shape + criteria を運べる粒度 + §9 本文の床 (空セクションを弾く)」までで、完成された本文ではない。ゆえに本スキルが渡す価値 (criteria を携帯した spec) は frontmatter に宿り、本文穴埋め skeleton を新設しても搬送価値は増えない (skeleton 不要の構造的根拠)。中心問い「ひな形を持つべきか」は、この境界の明示により「frontmatter=specfm/lint/例で既にひな形相当・本文=床付き自由記述で下流が仕上げる」へ解消される。

**成果物評価の境界 (purpose-acceptance は委譲しない)**: 本スキルが下流へ委譲するのは**本文 prose の仕上げ**であって、**成果物が当初 purpose を満たすかの受入基準 (purpose-acceptance) の定義ではない**。「build しない」を「評価基準も焼かない」と過剰一般化しない。purpose-acceptance は (i) 各 skill loop spec の `feedback_contract.criteria` を当該 spec の goal/checklist から導いて焼く (汎用品質ゲートの言い換えに退化させない・`check-spec-frontmatter.py` が purpose-traceability を機械検証)、(ii) index(main) に「受入確認 (build 後の見方)」章を持たせ goal-spec.purpose 由来の受入観点と平易語の確認の見方を記す、(iii) `EVALS.json` の `llm_eval` で受入が評価系に配線されていることを宣言する、の 3 点で **plan が契約として焼く**。実行 (criteria-test の実走) は build フェーズ (L4 `run-skill-create` の harness) が担い、planner は build しない原則と両立する (契約として焼く ≠ 実行する)。これにより「各 spec が品質ゲートを携帯する」だけでなく「組み上がった実プラグインが purpose を満たしたか」を build 後に確認できる trace が通る。意味の正否 (criterion が purpose を正しく受入検証するか) は evaluator の意味判定に残す (機械層は語彙ゼロ参照の退化のみ検出=二層分離)。

**PR / feature→main は本スキルの焼き先対象外 (soft note)**: `phase-lifecycle.md` §7 P13 のとおり PR 作成・`make validate`・`pytest` 緑化は **build 完了後の repo git 操作**で、本スキル(L3 計画)/`run-skill-create`(L1 build)いずれの責務でもない。`quality_gates`/§10 検証表/検査スクリプトに PR キーは設けない (operationalize しない=ユーザー意図「PR/Cloudflare/IPC は今回スコープ外」と整合)。最終仕様書が言及する場合も「下流で人手が feature→main する」旨の note に留め、評価ゲート化しない。

## 本スキル同梱の決定論検査スクリプト (R1 入力ゲート + R4 検証を自然言語突合から機械化)

| スクリプト | 役割 (検査する完了チェックリスト項目) |
|---|---|
| `scripts/check-plugin-goal-spec.py` | R1 入力ゲート: `goal-spec.json` が汎用 goal-spec + plugin 固有アンカー (`target_plugin_slug`/`plan_dir`/`requested_count`/`force_13`) を満たすか検証 (schema 契約は `schemas/plugin-goal-spec.schema.json`、両者の parity は `tests/test_check_plugin_goal_spec.py`) |
| `scripts/verify-index-topsort.py` | index が依存 top-sort 順で全タスク仕様書を列挙 (C1) |
| `scripts/detect-unassigned.py` | コンポーネント目録に対し未配置タスク 0 件 + 必須セクション + 各 buildable component の `build_target` 存在 (L3→L4 追跡。object 形式目録のみ検査) (C5) |
| `scripts/check-spec-frontmatter.py` | 各仕様書が `component_kind` を宣言し kind 別構造契約 + core 規律ブロック存在を携帯 (C2/C3)。**skill loop kind は criteria の purpose-traceability** (criteria が当該 spec の goal/checklist 語彙を最低 1 件参照する purpose-acceptance か) も検査=汎用ゲート言い換えへの退化を弾く |
| `scripts/check-spec-gates.py` | 各 buildable spec の `quality_gates` (p0_lint 網羅/build_trace/elegant_review C1-C4/content_review verdict/evaluator≥80,high0) と `harness_coverage` (min≥80/kind_pass) を機械検証 (A1/A5/A8/C1-C2/F1/F2) |
| `scripts/check-spec-matrix-coverage.py` | `skill-creator-spec-reflection.md` の43行を component_kind/階層別適用述語で評価し、適用行の焼き先 (component frontmatter / index plugin_meta) の存在を検査。OP/conditional/N-A 内訳を出力。`--self-test` で43行 table drift 検出 |
| `scripts/check-surface-inventory.py` | `component-inventory.json` が 5 component_kind の検討証跡 (`considered_component_kinds`) と plugin-level surfaces (`manifest`/`composition`/`harness_eval`/`references_config_assets`/`mcp_app_connector`) の required/omitted_reason を漏れなく持つことを検査 |
| `scripts/check-build-handoff.py` | `handoff-run-plugin-dev-plan.json` の L3→L4 routing を検証。builder 種別 / build_kind / build_args / build_target / spec 実在 / top-sort / force_13 / manifest draft / envelope gap reason |
| `scripts/check-plugin-surface-audit.py` | `plugins/` 配下の現物 plugin surface を横断棚卸し。skill/agent/command/hook/script/test/reference/config/assets/schemas/vendor/MCP-app/harness/composition/manifest と owned/symlink 内訳を数え、`--expect-plan-ready` 指定 plugin が必須 surface を dogfood していることを検査 |
| `scripts/render-spec-skeleton.py` | `specfm.py` から component_kind 別の最小 skeleton を生成。手書き skeleton ファイルを増やさず、ひな形の正本を実行可能契約へ一本化 |
| `scripts/specfm.py` | (import 専用) frontmatter 最小 YAML パーサ + criteria/component_kind 契約の SSOT |

`check-spec-matrix-coverage.py` の分類: OP=10 (全 buildable へ機械強制) / conditional=16 (kind/feature/階層でゲート) / N-A=17 (process・reference で per-spec 焼き先キーを持たない=計数のみ)。計 43。
