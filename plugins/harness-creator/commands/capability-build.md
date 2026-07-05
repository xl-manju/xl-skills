---
description: Capability (Skill/Agent/Hook/Command/Plugin-Composition/Prompt/Workflow) を新規作成または更新する統一入口。通常 kind は run-build-skill Skill、script route は build-script-route.py に委譲する。
argument-hint: "<kind> <name> [options] | --handoff <path> --route-id <Cxx>  例: skill run-foo / agent reviewer-bar / --handoff plugin-plans/x/handoff-run-plugin-dev-plan.json --route-id C09"
allowed-tools: Read, Skill, Bash(python3 *)
name: capability-build
kind: command
version: 0.1.0
owner: team-platform
since: 2026-05-24
entrypoint: run-build-skill
---

# /capability-build

`$ARGUMENTS` を `<kind> <name> [options]` または E2 の `--handoff <path> --route-id <Cxx>` としてパースする薄いラッパ。Capability 種別の正規化・route 解析・前提チェックのみを担当し、7 capability kind は `run-build-skill` Skill、`build_kind=script` route は `build-script-route.py` に委譲する (run-build-skill 本体は無改修)。

## 振る舞い

1. **入力形態の判別**: `--handoff` / `--route-id` があれば **route モード** (E2・下記 1r)、無ければ従来の **明示モード** (`<kind> <name>`・下記 1e)。
   - **1e (明示モード)**: `$ARGUMENTS` を空白区切りでパース。`kind` が `skill|agent|hook|command|plugin-composition|prompt|workflow` の 7 capability kind (この 7 種が正本) のいずれでなければ利用可能 kind を表示して停止。参照する `capability-manifest.schema.json#/definitions/commonCore.kind` はこの 7 種に加え skill sub-role prefix (`run/ref/assign/wrap/delegate`) も含む**上位集合**なので kind 受理判定にはそのまま使わず、本文の 7 種を厳密列挙として突合する (例: `run` は sub-role prefix であって capability kind ではない)。
     - `kind=skill` は scaffold 止まり。単体スキルを評価・統治まで端から端で作るなら `/run-skill-create` を使う (標準フローの Step2 も skill component は run-skill-create へ回す)。本 command は主に非 skill kind (agent/hook/command/prompt/workflow/plugin-composition) の入口。
   - **1r (route モード / E2)**: `--handoff` の JSON を Read し `routes[]` から `--route-id` に一致する route を取り出す。まず `Bash(python3 $CLAUDE_PLUGIN_ROOT/scripts/check-route-component-parity.py <handoff>)` で routes↔inventory 一致を preflight し (exit0 でなければ停止)、次に route の `build_kind` を `kind`、`build_args`(`name`/`script_path`)・`build_target` を明示引数として抽出する。`build_kind=script` の route は run-build-skill の 7 capability kind 外なので、専用 executor `Bash(python3 $CLAUDE_PLUGIN_ROOT/scripts/build-script-route.py --handoff <handoff> --route-id <Cxx>)` に委譲する。
     - **skill route (`build_kind=skill`) の brief preflight (brief 実体化の owner)**: skill route は `run-skill-create` が `build_args.brief_path` (PLAN_DIR 相対) の skill-brief を「射影済み」前提で Read する。dispatch 前にこの brief 実体の存在を assert し、未 materialize なら planner 同梱の射影器で inventory から決定論射影してから渡す (壊れた「再ヒアリングなし build」を防ぐ)。PLAN_DIR は handoff の `plan_dir`:
       `Bash(python3 plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/render-skill-brief.py --inventory <PLAN_DIR>/component-inventory.json --component <route-id> --out <PLAN_DIR>/<build_args.brief_path>)`
       brief 実在を確認してから skill route を `/run-skill-create` へ dispatch する (skill route の消費者は run-build-skill でなく run-skill-create=E2 契約)。射影器の孤児化を防ぐフロー上の発火点はこの route preflight。
2. `name` の命名規約を `ref-skill-naming-convention` 準拠で軽く検証 (run-/ref-/assign- prefix など)。route モードでは route.name を用いる。
3. `build_kind=script` は `build-script-route.py` が実行し、既存ファイルは非破壊で確認、新規ファイルは標準 Python scaffold を作成するが route status は `skipped` として後続依存を進めない。どちらの場合も `eval-log/<slug>/build/route-<id>.json` を書いて `validate-route-build-reports.py --route <id>` を通す。7 capability kind の route は `run-build-skill` Skill を起動し、引数として `kind / name / options`(route モードでは加えて `build_target`) を渡し、同じ route-build-report 契約に従って route 結果を記録する。
4. 7 capability kind の生成後は `validate-build-trace.py` を実行し、PASS/FAIL を報告する。script route は route-build-report を書き、`validate-route-build-reports.py --route <id>` の exit0 を確認する。route モードでは `check-route-component-parity.py` の exit0 を実行証跡に含める。

## 引数

| 引数 | 説明 |
|---|---|
| `kind` | capability 種別 (明示モードで必須) |
| `name` | capability 名 (明示モードで必須、命名規約準拠) |
| `options` | `--update` で既存更新、`--plugin=<name>` で配置先指定 |
| `--handoff <path>` | route モード: `handoff-run-plugin-dev-plan.json` のパス (E2) |
| `--route-id <Cxx>` | route モード: 消費する route の component id (例 C09) |

## 失敗時

- kind 不正: 受理 kind 一覧を表示
- name 規約違反: `ref-skill-naming-convention` の該当節を案内
- 既存と衝突: `--update` 未指定時は停止し、現状パスを表示
- script route の依存未完了: `build-script-route.py` が依存 route report 欠落 / failure を検出して停止

## 注意

- 本 command は scaffold / route 消費のみ。設計品質は `/capability-review` で別途評価する。
