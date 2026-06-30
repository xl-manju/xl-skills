---
name: four-condition-criteria
description: 4条件 (矛盾なし/漏れなし/整合性あり/依存関係整合) の詳細基準を確認したいとき、plan-findings の verdict を確定したいときに読む。
kind: reference
version: 0.1.0
owner: team-platform
since: 2026-06-30
source: plugins/plugin-dev-planner/skills/run-plugin-dev-plan/prompts/R4-verify-traceability.md
source-tier: internal
---

# 4条件 詳細基準 (plan 評価)

`plan-rubric.json` の機械判定を補う人間向け基準。決定論ゲート (core 5 scripts / 6 invocations + surface inventory gate + build handoff gate の exit code) を一次根拠とし、意味判定は最小限に留める。

## C1 矛盾なし (no_contradiction)

plan 内の契約が相互に衝突しないこと。`check-build-handoff.py` exit0 (handoff routing の builder↔component_kind 整合) を決定論の一次根拠とし、残りは意味判定 (script では捕捉しにくい)。

- `component_kind` と handoff 先が整合するか (例: script kind を run-skill-create へ投入していないか — script は親 skill 付随物)。
- index の `plugin_meta` (manifest/marketplace/cachebuster) と各 spec frontmatter の値が相反しないか。
- harness の `surfaces` と実体 capability が矛盾しないか。
- `distributable` フラグと bundles/marketplace 登録意図が整合するか。

**FAIL 例**: spec が `kind: script` なのに index が独立 Capability として run-skill-create 投入を指示している。

## C2 漏れなし (no_missing)

必要な surface が必要性ベースで全評価され、不要なものは根拠付きで除外されていること。

- `detect-unassigned.py` exit0: inventory に列挙された全 component に spec が存在 (未配置 0)。
- `check-spec-frontmatter.py` exit0: 各 spec が kind 別構造 + core 規律 frontmatter を携帯。
- `check-spec-gates.py` exit0: quality_gates + harness_coverage を値域まで携帯。
- **単一 skill 退化の検出**: `check-surface-inventory.py` が 5 component_kind の検討証跡と plugin-level surface (harness/manifest/composition/MCP 等) の required/omitted_reason を機械検査する。LLM は omitted_reason の意味妥当性のみ補助判定する。

**FAIL 例**: hook/agent/command を一切評価せず単一 skill plan を出し、`plugin_level_surfaces.<surface>.omitted_reason` が空。

## C3 整合性あり (consistent)

用語・フォーマット・データ構造が統一されていること。

- `check-spec-matrix-coverage.py --self-test` exit0: 43 行マトリクスの行 ID 集合に drift がない。
- `check-spec-matrix-coverage.py PLAN` exit0: 適用行の焼き先が反映され OP/conditional/N-A 内訳が整合。
- 用語 (component_kind / plugin_meta / quality_gates) が spec 間・index 間で同一語彙。

**FAIL 例**: ある spec が `quality_gates`、別 spec が `quality-gates` (表記揺れ) を使う。

## C4 依存関係整合 (dependency_integrity)

タスク間・モジュール間の依存が正しく定義されていること。

- `verify-index-topsort.py` exit0: index が依存 top-sort 順で全タスク仕様書を列挙し、DAG に循環がない。
- `detect-unassigned.py` exit0: inventory の全 component に spec が存在 (未配置 0)。
- `check-build-handoff.py` exit0: handoff routes が top-sort 成立・builder 整合・envelope gap reason を満たす。
- 依存 DAG (`dependency_edges`) が inventory と index で一致。

**FAIL 例**: C02 が C03 に依存するのに index で C03 より先に C02 が並ぶ (top-sort 違反)。

## verdict 確定

| 条件 | PASS 条件 (gate は `plan-rubric.json` deterministic_gates が正本) |
|---|---|
| C1 | `check-build-handoff` exit0 かつ契約衝突 0 |
| C2 | `detect-unassigned` / `check-spec-frontmatter` / `check-spec-gates` / `check-surface-inventory` 全 exit0 かつ単一 skill 退化なし |
| C3 | `check-spec-frontmatter` / `check-spec-gates` / `check-spec-matrix-coverage --self-test` / `check-spec-matrix-coverage PLAN` 全 exit0 かつ語彙統一 |
| C4 | `verify-index-topsort` / `detect-unassigned` / `check-build-handoff` 全 exit0 |

`global_thresholds`: high == 0 かつ medium <= 2 かつ all_gates_exit0 == true で全体 PASS。1 つでも high があれば全体 FAIL。
