# skill-creator / agents 責務境界

本ディレクトリには 2 系統 6 個の SubAgent が並存する。各 agent は **生成系 (build)** と **レビュー系 (elegant-review)** のいずれかに属し、責務は重複しない。本書はそのマトリクスと呼び出し関係を明文化する。

## 系統の分離

- **生成系**: `run-build-skill-subagent`
  - 呼び出し元 Skill: `run-build-skill`
  - 役割: brief から 1 個の Skill ディレクトリを生成・更新する worker (fan-out)。
- **レビュー系**: `elegant-reset-observer` / `elegant-logical-structural-analyst` / `elegant-meta-divergent-analyst` / `elegant-system-strategic-analyst` / `elegant-improvement-executor`
  - 呼び出し元 Skill: `run-elegant-review`
  - 役割: 既存成果物のレビュー 4 phase (reset → 並列分析 → 統合改善) を分担する。

両系統は入力 (brief vs 既存成果物パス)・出力 (Skill 骨格 vs findings + patch) ともに異なるため、機能的に重複しない。

## 責務マトリクス

| Agent | 系統 | 呼び出し元 Skill | Phase / タイミング | 入力 | 出力 | 重複しない責務 |
|---|---|---|---|---|---|---|
| `run-build-skill-subagent` | 生成 | `run-build-skill` | brief 検証後の fan-out worker | `skill-brief.json` (skill_path 1 個) | `changed_paths[] / lint_status / trace_path / todo_human[]` | 単一 Skill ディレクトリの SKILL.md / references/ / scripts/ / prompts/ 生成。rubric governance は触らない。 |
| `elegant-reset-observer` | レビュー | `run-elegant-review` | Phase 1 (reset, read-only) | `target_type / target_path` | `purpose / scope / assumptions / stakeholders / raw_observations / concrete_values_to_abstract` | 初見観察のみ。採点・改善提案は禁止。 |
| `elegant-logical-structural-analyst` | レビュー | `run-elegant-review` | Phase 2 並列 (論理・構造) | Phase 1 JSON メモ | 論理・構造観点の findings | 4 条件 (C1-C4) のうち論理整合・構造分解の観点。 |
| `elegant-meta-divergent-analyst` | レビュー | `run-elegant-review` | Phase 2 並列 (メタ・発想) | Phase 1 JSON メモ | メタ・代替案 findings | 抽象階層の引き上げと代替案の発散。 |
| `elegant-system-strategic-analyst` | レビュー | `run-elegant-review` | Phase 2 並列 (システム・戦略) | Phase 1 JSON メモ | 戦略・根本原因 findings + severity | 優先順位付け・価値判定・根本原因分析。 |
| `elegant-improvement-executor` | レビュー | `run-elegant-review` | Phase 3 (統合改善) | Phase 2 集約 findings | `changed_paths[] / validation_commands[] / residual_risks[] / convergence_status` | findings に基づく最小パッチ適用と検証実行。新規分析はしない。 |

## 呼び出し関係図

- `run-build-skill` (orchestrator skill)
  - → `run-build-skill-subagent` (brief ごとに並列 fan-out)
  - → (独立評価) `assign-skill-design-evaluator` ※agents 配下ではなく別 skill
- `run-elegant-review` (orchestrator skill)
  - Phase 1 → `elegant-reset-observer`
  - Phase 2 → 並列 3 agent:
    - `elegant-logical-structural-analyst`
    - `elegant-meta-divergent-analyst`
    - `elegant-system-strategic-analyst`
  - Phase 3 → `elegant-improvement-executor`
  - (収束未達なら Phase 2 を再起動。max 3 回で human_review に escalate)

## 重複が無いことの根拠

- 生成系 worker は brief を入力にファイルを **生成** する。レビュー系は既存ファイルを入力に findings を **生成** または patch を **適用** する。入力種別と出力種別が直交している。
- レビュー系 5 個は同一 Skill (`run-elegant-review`) の Phase 1/2/3 に 1 対 1 で割り当てられており、phase_id が frontmatter で識別されるため互いに代替不可。
- `elegant-improvement-executor` のみ Edit/Write/Bash を持ち、他 4 個は read-only で観察・分析に専念する。執行権限の所在も重複していない。

## 関連規約

- 各 agent の自己評価ルーブリック: `plugins/skill-intake/skills/run-skill-intake-aggregator/references/quality-rubric.md`
- 収束判定: `plugins/skill-creator/skills/run-elegant-review/references/convergence-policy.json`
- prompt 配置規約: `plugins/skill-creator/skills/run-build-skill/references/prompt-placement-convention.md`
