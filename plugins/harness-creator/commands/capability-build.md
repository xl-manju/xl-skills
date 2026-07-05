---
description: Capability (Skill/Agent/Hook/Command/Plugin-Composition/Prompt/Workflow) を新規作成または更新する統一入口。run-build-skill Skill を起動し、kind に応じた scaffold とリソースを生成する。
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

`$ARGUMENTS` を `<kind> <name> [options]` または E2 の `--handoff <path> --route-id <Cxx>` としてパースし、`run-build-skill` Skill に委譲する薄いラッパ。Capability 種別の正規化・route 解析・前提チェックのみを担当し、実体ロジックは Skill 側で実行する (run-build-skill 本体は無改修)。

## 振る舞い

1. **入力形態の判別**: `--handoff` / `--route-id` があれば **route モード** (E2・下記 1r)、無ければ従来の **明示モード** (`<kind> <name>`・下記 1e)。
   - **1e (明示モード)**: `$ARGUMENTS` を空白区切りでパース。`kind` が `skill|agent|hook|command|plugin-composition|prompt|workflow` の 7 capability kind (この 7 種が正本) のいずれでなければ利用可能 kind を表示して停止。参照する `capability-manifest.schema.json#/definitions/commonCore.kind` はこの 7 種に加え skill sub-role prefix (`run/ref/assign/wrap/delegate`) も含む**上位集合**なので kind 受理判定にはそのまま使わず、本文の 7 種を厳密列挙として突合する (例: `run` は sub-role prefix であって capability kind ではない)。
     - `kind=skill` は scaffold 止まり。単体スキルを評価・統治まで端から端で作るなら `/run-skill-create` を使う (標準フローの Step2 も skill component は run-skill-create へ回す)。本 command は主に非 skill kind (agent/hook/command/prompt/workflow/plugin-composition) の入口。
   - **1r (route モード / E2)**: `--handoff` の JSON を Read し `routes[]` から `--route-id` に一致する route を取り出す。まず `Bash(python3 $CLAUDE_PLUGIN_ROOT/scripts/check-route-component-parity.py <handoff>)` で routes↔inventory 一致を preflight し (exit0 でなければ停止)、次に route の `build_kind` を `kind`、`build_args`(`name`/`script_path`)・`build_target` を明示引数として抽出する。`build_kind=script` の route は GAP-SCRIPT-BUILDER の代替生成手順に従い `script_path`/`build_target` を run-build-skill へ渡して直接生成する (parent-skill-build/plugin-scaffold は contract-only ゆえ run-build-skill 内代替)。
2. `name` の命名規約を `ref-skill-naming-convention` 準拠で軽く検証 (run-/ref-/assign- prefix など)。route モードでは route.name を用いる。
3. `run-build-skill` Skill を起動し、引数として `kind / name / options`(route モードでは加えて `script_path` / `build_target`) を渡す。
4. 生成後に `validate-build-trace.py` を実行し、PASS/FAIL を報告。route モードでは併せて `check-route-component-parity.py` の exit0 を build_trace evidence に記録する。

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

## 注意

- 本 command は scaffold のみ。設計品質は `/capability-review` で別途評価する。
