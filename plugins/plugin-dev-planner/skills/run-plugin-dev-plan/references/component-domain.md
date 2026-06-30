---
name: component-domain
description: 「プラグイン」を 5 構成要素へ写像する対象ドメイン定義と用語集。R2 分解と本数 N 導出の正本として読む。
kind: reference
owner: team-platform
since: 2026-06-29
source-tier: internal
---

# 対象ドメイン定義: プラグイン = 5 buildable 構成要素 + plugin-level surfaces (§4 / §12)

> パス表記: 本書の絶対パスはすべて xl-skills repo root 相対。

## 5 buildable 構成要素 (component spec の物理アーティファクト種別)

plugin が生成し得る**buildable な capability 種別**。`skill-brief.schema.json#placement_candidates` enum (`Skill`/`Subagent`/`Agent Team`/`Hook`/`MCP`/`CLI`/`API`/`script`) とは**対応するが別軸**: placement_candidates は「能力をどこに置く候補か」(brief の判断材料・casing も大文字)、本 5 種は「実際に生成する capability ファイルの種別」。両者を同一視しない。R2 は 5 種すべてを `considered_component_kinds` で検討済みにし、実際に必要なものだけを `components[]` へ写像する。`components[]` の数が **N (component spec 本数)** の導出根拠になる。

| 構成要素 | 定義 | 実体例 |
|---|---|---|
| **skill** | `SKILL.md` 入口の能力単位 (kind ∈ run/ref/wrap/assign/delegate) | `run-skill-create` |
| **sub-agent** | `agents/*.md`、独立 context | `assign-skill-design-evaluator` |
| **slash-command** | `commands/*.md` | `/install-bundle` |
| **hook** | `plugin.json`/`settings.json` 配線スクリプト | `preflight-git-commit.py` |
| **script** | `scripts/*.py`、決定論処理 | `validate-build-trace.py` |

→ §8 P3 (phase-lifecycle.md) で構想に対してこの 5 種を検討し、必要なものだけを component として kind/prefix/hierarchy/pattern 確定する。構成要素数が本数 N の導出根拠であり、本数は固定 (13 等) でも 5 種強制生成でもなく構想に依存して変動する。

## plugin-level surfaces (個別 component_kind に押し込まないが必須確認する面)

| surface | 実体例 | 記録先 |
|---|---|---|
| **plugin manifest** | `.claude-plugin/plugin.json` | `index.md` の `plugin_meta.manifest` |
| **plugin composition** | `plugin-composition.yaml` | `index.md` の `plugin_meta.pkg_contract` / `component-inventory.json` |
| **harness/eval** | `EVALS.json`, `eval-log/coverage/**` | `index.md` の `plugin_meta.ci` / `harness_coverage` |
| **references/config/assets** | `references/**`, `config/**`, `assets/**` | component spec の references または `plugin_meta.ssot_dedup` |
| **MCP/app connector** | `.mcp.json`, `.app.json` | `plugin_meta.manifest` と `component-inventory.json` |

これらは component spec の `component_kind` ではない。欠落すると plugin として不完全になるため、R2/R3 で要否を判定し、不要なら `plugin_level_surfaces.<surface>.omitted_reason` に理由を残す。省略理由のキーは `omitted_reason` 一本のみ (評価器が読むのもこのキーのみ)。

## 用語集 (§12)

| 用語 | 定義 |
|---|---|
| plugin | skill/sub-agent/slash-command/hook/script と plugin-level surfaces の集合・配布単位 |
| plugin manifest | `.claude-plugin/plugin.json`。plugin root の物理契約であり、folder name と `name` が一致する |
| marketplace | `.claude-plugin/marketplace.json` (repo/team marketplace)。plugin の表示順・install/auth policy・category を定義する |
| skill | `SKILL.md` 入口の能力単位。kind ∈ {run,ref,wrap,assign,delegate} |
| sub-agent | `agents/*.md`・独立 context |
| slash-command | `commands/*.md` |
| hook | `plugin.json`/`settings.json` 配線スクリプト |
| script | `scripts/*.py`・決定論処理 |
| タスク仕様書 | 本スキル(L2)が出力する Markdown 1 単位(L3)・`run-skill-create` 投入可能粒度 |
| フェーズ | プラグイン開発ライフサイクルの 1 段階 (§8 P1-P8)。機能開発 Phase 1-13 とは別物 |
| name(slug) | 機械識別子 (例 `run-plugin-dev-plan`)・lint で形式検証 |
| displayName | 人間向け表示名・slug と区別 |
| 依頼書 | `run-skill-create` への入力 (skill-brief 相当) |
| TDD (本文脈) | Red=未達 criteria/チェックリスト項目、Green=goal-seek ループで充足し lint/test/verdict exit0/PASS (vitest でなく pytest harness-coverage) |
| N | 構成要素数 = per-component タスク仕様書本数 |

## 4 層分離 (root cause「作成する」混線の解消)

| 層 | 内容 |
|---|---|
| L0 | プラグイン構想 (本スキルへの入力) |
| L1 | 道具 `run-skill-create` (既存) |
| L2 | 本スキル `run-plugin-dev-plan` (タスク仕様書を生成する) |
| L3 | N 本のタスク仕様書 + index (L2 を実行して作る)。index は manifest/marketplace/cachebuster/validation 契約を `plugin_meta` に持つ |
| L4 | 実プラグイン (L3 を L1 に投入して作る) |

本スキルは L3 までを担い、L4 (実 build) は各仕様書を `run-skill-create` へ委譲する。実コードは生成しない。
