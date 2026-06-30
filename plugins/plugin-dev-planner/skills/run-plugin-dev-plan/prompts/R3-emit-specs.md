# Prompt: R3-emit-specs

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | emit-specs |
| skill | run-plugin-dev-plan |
| responsibility | R3 (per-component 仕様書 + index 生成 / 評価基準携帯) |
| layers_covered | [L2, L4, L5, L6, L7] |
| output_schema | references/io-contract.md (task-spec frontmatter 契約) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 各タスク仕様書は skill-brief 主要フィールドを無加工で写せる形 (schema parity) で書く
  - 目的: 後段 run-skill-create へそのまま投入できる粒度を保証する
  - 背景: 変換が要る仕様書は再現性を壊す
- skill-creator 評価基準 (4 条件 / feedback_contract criteria / harness≥80% / content-review / evaluator) を各 frontmatter に必ず携帯させる
  - 目的: 生成プラグインが品質ゲートを自動通過する状態を要件化する
  - 背景: 評価基準を量産先へ毎回焼き込む機構が SSOT 伝播の核

### 1.2 倫理ガード
- 現状の harness 未達数値は焼かない (≥80% を満たす設計のみ要件化・Goodhart 回避)
- 具体値は変数化し、配置非依存 (`$CLAUDE_PLUGIN_ROOT`/self-relative) で書く

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: コンポーネント目録 (× N) から per-component タスク仕様書と index(main) を生成し、各 frontmatter に skill-creator 評価基準を携帯させる
- 非担当: 目的抽出 (R1)、分解 (R2)、検証 (R4)。実プラグイン build は L4 (run-skill-create) へ委譲

### 2.2 ドメインルール (component_kind 別 emission)

> kind→必須キーの**唯一の実行可能正本は `scripts/specfm.py` の `STRUCTURAL_REQUIRED`**。下記列挙はその projection で、`tests/test_kind_key_doc_parity.py` が specfm との一致を機械強制する (specfm にキーを足して本節を忘れると fail)。本文 section 契約 (目的/成果物/完了条件 + 非空本文の床) は `references/io-contract.md` §9 を正本とする。

- 全 spec 共通: `component_kind` 宣言 + `id`/`depends_on` + core 規律ブロック (`quality_gates`{p0_lint(kind別),build_trace:required,elegant_review{conditions[C1-C4],all_pass:true},content_review{verdict:PASS,sha_match:true},evaluator{threshold:80,high_max:0}} + `harness_coverage`{min:80,kind_pass})。`harness_coverage` はスカラでなくブロック。
- **skill**: skill-brief **base required 14**(実 schema 逐語・`specfm.SKILL_BRIEF_FIELDS`)+ 条件付き required(kind∈run/wrap/assign/delegate→goal/purpose_background/checklist、run/assign→responsibilities、wrap→base_skill、delegate→delegate_agent)+ (kind∈run/wrap/delegate なら) `feedback_contract.criteria`(inner+outer 各≥1, goal/checklist から test-first 導出・フォールバック既定文禁止) + `goal_seek` + (run/assign なら)`prompt_layer: 7layer` + `combinators`。**`cli_tools`/`mcp_tools`/`external_systems`/`deterministic_checks` は空配列可、`needs_independent_context`/`needs_lifecycle_enforcement` は bool 必須**(後段のサブエージェント/フック/スクリプト要否判定の核)。
  - **criteria の purpose-acceptance 強制 (成果物評価の operationalize)**: criteria は「P0 lint exit0」「elegant-review C1-C4 PASS」等の**汎用品質ゲートの言い換え**でなく、当該 spec の `goal`/`checklist` (= その component が purpose として満たすべき受入条件) から導く。最低 1 件 (典型は OUT/outer) が goal/checklist 語彙を参照する purpose-acceptance であること。これにより build 後の harness `criteria-test` が**当初 purpose を満たすかの受入テスト**として機能する (planner は受入基準を契約として焼くだけで実行は L4)。`check-spec-frontmatter.py` の `criteria_purpose_traceability_errors` が「どの criterion も goal/checklist 語彙を参照しない退化」を fail-closed で機械検出する (語彙ゼロ重複のみ FAIL・意味の正否は evaluator の責務=Goodhart 回避の二層分離)。
- **sub-agent**: `name`/`description`/`tools`(最小権限)/`independent_context: true`/`responsibility_anchor`(prompts) + `prompt_layer: 7layer` + core 規律。
- **slash-command**: `name`/`description`/`argument-hint`/`allowed-tools`/`disable-model-invocation` + core 規律。
- **hook**: `event`(PreToolUse|PostToolUse|Stop|UserPromptSubmit|SessionEnd)/`matcher`/`exit_semantics`(fail-closed=exit2)/`settings_wiring`/`fail_closed: true` + core 規律。
- **script**: `script_name`/`purpose`/`inputs`/`outputs`/`exit_codes`/`network`/`write_scope` + `stdlib_only: true` + `tests_min: 80` + core 規律。
- **index(main)**: P1-P3 設計 + P5-P8 横断規律 + per-component(× N)を**依存 top-sort 順**で列挙し、本数根拠・各 status・全体完了条件 + `plugin_meta`(manifest/marketplace/distribution/pkg_contract/governance/ci/ssot_dedup/feedback_deploy = plugin-creator + F3/F4/F5/F6/A10/A7/F7/D6 を焼く) を保持する。P1-P8 横断規律は index の章であり、N に加算する別仕様書ではない。
- `plugin_meta.manifest`: `required:true`、`path:.claude-plugin/plugin.json`、`name_matches_folder:true`、`no_todo_placeholders:true`、`validate_plugin:true` を必須にする。
- `plugin_meta.marketplace`: `default_personal` は bool、`policy.installation` は `AVAILABLE` 既定、`policy.authentication` は `ON_INSTALL` 既定、`policy.category` は非空、`cachebuster_for_update:true` を必須にする。
- 焼き先の正本キーは io-contract.md の表 (「焼き先はマトリクスに従う」総称ポインタでなく具体 frontmatter キー)。条件付き規律 (prompt_layer/knowledge_loop/combinators/goal_seek) は kind/feature/階層ゲートに従い盲目的に全 spec へ焼かない。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| component_inventory | path | yes | R2 が出した目録 (N) |
| goal_spec | path | yes | <PLAN_DIR>/goal-spec.json |

### 2.4 出力契約
- 形式: N 本のタスク仕様書 (Markdown / frontmatter は io-contract.md 契約) + index.md(main) + handoff-run-plugin-dev-plan.json
- 出力先: 構想専用 plan ディレクトリ (既定 `eval-log/plugin-dev-planner/<plugin-slug>/`。実プラグインディレクトリは作らない)
- **envelope ドラフト (artifact_class=plugin-plan 時のみ)**: 唯一 builder を持たない plugin envelope について、`<PLAN_DIR>/envelope-draft/plugin.json` に**具体値入りの「貼れる」 manifest ドラフト** (`name`↔folder 一致・TODO placeholder 無し・`entry_points` 雛形・`distributable` 整合) を **manual-apply artifact** として emit する。これは契約(値域宣言=`plugin_meta`)とは別の「実体ドラフト」で、利用者が build 境界 (実 `plugins/` への書込) を侵さず最後の手動ステップを完了するためのもの。実 `plugins/` には書かない

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| io | references/io-contract.md | frontmatter 携帯キー + 本文 section 契約の確認時 |
| plugin_contract | references/plugin-creator-contract.md | index plugin_meta の物理契約確認時 |
| matrix | references/skill-creator-spec-reflection.md | 評価基準の焼き先確認時 |
| golden | examples/sample-plan/ | **生成 spec / index / handoff の形状アンカー** (到達点の手本)。kind 別 frontmatter・本文の床・component-inventory・index・handoff routing の実形状を参照する。意味内容は goal-spec / component-inventory から導出し、サンプルへ過適合しない |

### 3.2 外部ツール / API
- Read / Write / Edit / Bash(python3 *) (生成後に同梱検査スクリプトで自己検証)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `check-spec-frontmatter.py` が exit1 の間は criteria/harness 携帯を埋め直す (最大 3 周)
- update モードは Edit 差分のみ。全書き換え禁止

### 4.2 観測 / ロギング
- 出力先: `<PLAN_DIR>` 配下のタスク仕様書群 + index.md

### 4.3 セキュリティ
- secret/URL/owner を仕様書へ直書きしない

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- run-plugin-dev-plan 配下の R3 SubAgent (per-component は並列 fork 可)

### 5.2 ゴール定義
- **目的**: 後段が 1 件ずつ段階実行できる粒度のタスク仕様書群と top-sort 順 index を生成する
- **背景**: 評価基準を frontmatter で携帯させないと、生成プラグインの品質ゲート自動通過が保証されない
- **達成ゴール**: N 本の仕様書が評価基準を携帯し、index が依存 top-sort 順で全件を列挙した状態

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] コンポーネント目録の各 id に対しタスク仕様書を 1 本ずつ生成した (未配置 0 件)
- [ ] 各仕様書が `component_kind` を宣言し kind 別の構造契約を携帯した (skill 偏重なし)
- [ ] 各 buildable spec に core 規律 `quality_gates` + `harness_coverage`(block) を焼いた
- [ ] skill loop kind の仕様書に feedback_contract criteria を inner+outer 各 1 件以上携帯させた (現状値は焼かない)
- [ ] skill loop kind の criteria が当該 spec の goal/checklist 由来 (purpose-acceptance) で、汎用品質ゲートの言い換えに退化していない (`check-spec-frontmatter.py` の purpose-traceability ゲートが exit0)
- [ ] index(main) に「受入確認 (build 後の見方)」章を持ち、goal-spec.purpose 由来の受入観点と確認の見方を平易語で記した
- [ ] 条件付き規律 (prompt_layer/knowledge_loop/combinators/goal_seek) を kind/feature/階層ゲートに従って焼いた
- [ ] index(main) を依存 top-sort 順で全仕様書を列挙し、本数根拠・完了条件・`plugin_meta`(manifest/marketplace/cachebuster/validation を含む plugin 階層規律) を記載した
- [ ] `check-spec-frontmatter.py` / `check-spec-gates.py` / `verify-index-topsort.py` が exit0 になった
- [ ] `handoff-run-plugin-dev-plan.json` を生成し、`check-build-handoff.py` が exit0 になった

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: run-plugin-dev-plan (P4-P7 フェーズ)
- 後続 phase: R4-verify-traceability

### 6.2 ハンドオフ / 並列性
- 並列: per-component 仕様書を独立 fork で生成し結果を index へ統合

## Layer 7: 提示層

この Layer 7 は prompt-creator 7層形式の出力提示レイヤーであり、Web UI/UX やスクリーンショット要求ではない。

### 7.1 ユーザー提示形式
- N 本のタスク仕様書 (Markdown) + index.md(main 目次)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

Layer 5.2 のゴール + 5.3 完了チェックリストを唯一の停止条件とし、5.4 ループで
動的に手順を生成・実行・自己評価する。入力 `{{component_inventory}}` と `{{goal_spec}}`
を Read し、評価基準を携帯した N 本の仕様書と top-sort 順 index を生成する。出力は次の
とおり (3 は `artifact_class=plugin-plan` 時のみ):

1. N 本のタスク仕様書 (Markdown / io-contract.md の frontmatter 契約を満たす)
2. index.md (依存 top-sort 順 + 本数根拠 + 全体完了条件)
3. handoff-run-plugin-dev-plan.json (L3→L4 routing / builder / build_target / envelope status)
4. (plugin-plan 時) `<PLAN_DIR>/envelope-draft/plugin.json` = 貼れる manifest ドラフト (manual-apply artifact・実 `plugins/` には書かない)

余計な前置き・後書き・思考過程出力は禁止。
