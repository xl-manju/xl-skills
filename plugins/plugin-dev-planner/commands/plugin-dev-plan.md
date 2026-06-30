---
description: プラグイン構想からタスク仕様書 plan を生成したいとき、skill/sub-agent/command/hook/script/harness/manifest を漏れなく分解したいときに使う。
argument-hint: "<plugin-concept> [--mode create|update] [--force-13] [--out-dir <path>]"
allowed-tools: Read, Write, Edit, Bash(python3 *), Skill, Agent
entrypoint: run-plugin-dev-plan
name: plugin-dev-plan
kind: command
version: 0.1.0
owner: team-platform
since: 2026-06-30
---

# /plugin-dev-plan

`$ARGUMENTS` を `run-plugin-dev-plan` に渡す薄い入口。単一 skill の作成ではなく、plugin 全体 (skill / sub-agent / slash-command / hook / script / harness-eval / manifest) の **計画 (タスク仕様書群 + index)** を作る。実プラグイン/実コードは作らない (build は `run-skill-create` へ委譲)。

## 前提条件 (再現性のための実行環境)

| 条件 | 要件 | 確認方法 |
|---|---|---|
| cwd | repo ルート (`xl-skills/`) で起動する | lint・同梱スクリプトは repo-root 相対で動く |
| python | `python3 >= 3.10` (標準ライブラリのみ。`yaml`/`.sh`/`.js` 不使用) | `python3 --version` |
| 依存 plugin | `plugins/skill-creator/` が同梱されている (repo-bundled) | `run-skill-create` / `run-build-skill` / `run-elegant-review` / `run-goal-elicit` / `goal-seek-paradigm.md` を参照するため |
| symlink | 更新後は `make sync` で `.claude/` へ展開済み | `.claude/skills/run-plugin-dev-plan` は symlink 派生 (未同期だと旧版が動く) |
| 配布 | `distributable:false` (marketplace/bundles 非登録) | 計画専用・本 plugin は配布対象でない |

## 引数

| 引数 | 必須 | 既定 | 説明 |
|---|---|---|---|
| `plugin-concept` | yes | — | プラグイン構想 1 件 (自然文 + 任意でコンポーネント希望)。曖昧な場合も停止せず仮 slug + `open_questions` で進める |
| `--mode create\|update` | no | `create` | `update` は既存 plan への Edit 差分のみ (全書き換え禁止) |
| `--force-13` | no | off | component spec 13 本固定が必要な明示要件があるときだけ指定。理由を `index.md` の本数根拠に記録する。Phase1-13 文書ビューそのものではない。既定は構成要素数 N から本数を導出 |
| `--out-dir <path>` | no | `eval-log/plugin-dev-planner/<plugin-slug>/` | 計画成果物の出力先を明示上書きする。相対パスは repo root 基準。指定値も `goal-spec.plan_dir` に固定する |

## 入力契約

- 入力 = プラグイン構想 1 件のみ。外部システム連携・secret は入力にしない。
- 分析材料 (例: UBM-Hyogo 配下) は read-only 抽出のみ。fork/複製しない。

## 実行手順 (決定論的・再現可能)

ゴールシークループ本体は `Agent` ツールで SubAgent に fork し、R 責務を 3 agent へ 1:1 dispatch する (prompt-creator 仕様準拠の薄いアダプタ)。

1. **R1 (elicitor / `isolation:inherit`)**: 構想文 + 会話履歴から目的ドリブンに `eval-log/plugin-dev-planner/<plugin-slug>/goal-spec.json` (purpose/background/goal/二値 checklist + target_plugin_slug + plan_dir) を確定する。追加質問しない。goal-spec 生成本体は `run-goal-elicit` へ委譲。
2. **R2/R3 (architect / `isolation:fork`)**: capability を 5 構成要素へ単一責務分解 → 本数 N と依存 DAG を `component-inventory.json` に記録 → per-component 仕様書 (× N) を component_kind 別契約で生成し、core 規律 (`quality_gates` + `harness_coverage`) を frontmatter へ焼く → `index.md` に top-sort 目次 + `plugin_meta` (manifest/marketplace/cachebuster/validate_plugin) を焼く。
3. **R4 (evaluator / `isolation:fork` / read-only)**: assign evaluator が core 5 scripts / 6 invocations + surface inventory gate + build handoff gate を実行し 4 条件へ写像。NG は R3 へ差し戻す (最大 3 周)。
4. 各周回末に `<PLAN_DIR>/run-plugin-dev-plan-intermediate.jsonl` へ不変アンカー (`original_goal` ほか 5 要素) を append し、次周回の必須入力にする (ドリフト圧縮)。

## 出力成果物

構想専用 plan ディレクトリ (既定 `eval-log/plugin-dev-planner/<plugin-slug>/`、`$CLAUDE_PROJECT_DIR`/cwd 基準で解決) へ:

- `component-inventory.json` — 本数 N + 導出根拠 + 依存 DAG + `plugin_level_surfaces.<surface>.omitted_reason` (不要サーフェスの根拠)
- `<NN>-<kind>.md` × N — component_kind 別タスク仕様書 (frontmatter は `references/io-contract.md` 契約)
- `index.md` (main) — 依存 top-sort 順目次 + 本数根拠 + `plugin_meta` + 完了条件
- `goal-spec.json` / `run-plugin-dev-plan-progress.json` / `run-plugin-dev-plan-intermediate.jsonl` — plugin 別 goal-seek 作業ログ
- `handoff-run-plugin-dev-plan.json` / `plan-findings.json` — plan パス + component_kind 別 builder/build_target ルーティング + envelope gap/approval reason + 達成チェックリスト + 4条件評価

## 検証 (PASS 条件 = 全 exit0)

```bash
PLAN_DIR=<plan ディレクトリ>
SKILL_DIR=plugins/plugin-dev-planner/skills/run-plugin-dev-plan
python3 "$SKILL_DIR/scripts/verify-index-topsort.py" "$PLAN_DIR"                                   # top-sort 全列挙
python3 "$SKILL_DIR/scripts/check-plugin-goal-spec.py" "$PLAN_DIR/goal-spec.json"                  # R1 goal-spec + plugin anchors
python3 "$SKILL_DIR/scripts/detect-unassigned.py" --inventory "$PLAN_DIR/component-inventory.json" --specs-dir "$PLAN_DIR"  # unassigned 0
python3 "$SKILL_DIR/scripts/check-spec-frontmatter.py" --specs-dir "$PLAN_DIR"                     # kind 別構造 + core 規律
python3 "$SKILL_DIR/scripts/check-spec-gates.py" --specs-dir "$PLAN_DIR"                           # quality_gates + harness
python3 "$SKILL_DIR/scripts/check-spec-matrix-coverage.py" --self-test                             # 43 行 table drift
python3 "$SKILL_DIR/scripts/check-spec-matrix-coverage.py" "$PLAN_DIR"                             # 焼き先反映
python3 "$SKILL_DIR/scripts/check-surface-inventory.py" "$PLAN_DIR/component-inventory.json"       # 5種検討証跡 + surface 採否
python3 "$SKILL_DIR/scripts/check-build-handoff.py" "$PLAN_DIR/handoff-run-plugin-dev-plan.json"   # L3→L4 routing
```

成功条件: 上記 9 コマンド全 exit0 + elegant-review C1-C4 全 PASS の設計が記述されている。形状と handoff の生きた手本は `skills/run-plugin-dev-plan/examples/sample-plan/`。

## 失敗時

- **plugin 名が曖昧**: `constraints.open_questions` に残し、仮 slug で進める (停止しない)。
- **単一 skill だけになる**: agent/command/hook/harness を不要と判断した根拠を `plugin_level_surfaces.<surface>.omitted_reason` に明記するまで PASS にしない (単一 skill plan を既定にしない)。
- **検証スクリプト未実行 / NG**: `plugin-dev-plan-evaluator` に差し戻す。3 周超過は `open_issues` に残す。
- **goal-spec schema NG**: 最大 3 周で再生成、超過時 `open_issues` へ。

## 注意

- 実プラグイン/実コードを生成しない (成果物は計画のみ)。
- 具体値を直書きせず `{{PROJECT_ROOT}}` / `$CLAUDE_PLUGIN_ROOT` / self-relative で表現する。
- `--mode update` は Edit 差分のみ。capability の実 build は `/skill-creator:capability-build` 系へ委譲する。
