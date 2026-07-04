---
description: Capability (Skill/Agent/Hook/Command/Plugin-Composition/Prompt/Workflow) を新規作成または更新する統一入口。run-build-skill Skill を起動し、kind に応じた scaffold とリソースを生成する。
argument-hint: "<kind> <name> [options]  例: skill run-foo / agent reviewer-bar / hook on-save / command deploy"
allowed-tools: Read, Write, Edit, Bash
name: capability-build
kind: command
version: 0.1.0
owner: team-platform
since: 2026-05-24
entrypoint: run-build-skill
---

# /capability-build

`$ARGUMENTS` を `<kind> <name> [options]` としてパースし、`run-build-skill` Skill に委譲する薄いラッパ。Capability 種別の正規化と前提チェックのみを担当し、実体ロジックは Skill 側で実行する。

## 振る舞い

1. `$ARGUMENTS` を空白区切りでパース。`kind` が `skill|agent|hook|command|plugin-composition|prompt|workflow` の 7 capability kind (この 7 種が正本) のいずれでなければ利用可能 kind を表示して停止。参照する `capability-manifest.schema.json#/definitions/commonCore.kind` はこの 7 種に加え skill sub-role prefix (`run/ref/assign/wrap/delegate`) も含む**上位集合**なので kind 受理判定にはそのまま使わず、本文の 7 種を厳密列挙として突合する (例: `run` は sub-role prefix であって capability kind ではない)。
   - `kind=skill` は scaffold 止まり。単体スキルを評価・統治まで端から端で作るなら `/run-skill-create` を使う (標準フローの Step2 も skill component は run-skill-create へ回す)。本 command は主に非 skill kind (agent/hook/command/prompt/workflow/plugin-composition) の入口。
2. `name` の命名規約を `ref-skill-naming-convention` 準拠で軽く検証 (run-/ref-/assign- prefix など)。
3. `run-build-skill` Skill を起動し、引数として `kind / name / options` を渡す。
4. 生成後に `validate-build-trace.py` を実行し、PASS/FAIL を報告。

## 引数

| 引数 | 説明 |
|---|---|
| `kind` | capability 種別 (必須) |
| `name` | capability 名 (必須、命名規約準拠) |
| `options` | `--update` で既存更新、`--plugin=<name>` で配置先指定 |

## 失敗時

- kind 不正: 受理 kind 一覧を表示
- name 規約違反: `ref-skill-naming-convention` の該当節を案内
- 既存と衝突: `--update` 未指定時は停止し、現状パスを表示

## 注意

- 本 command は scaffold のみ。設計品質は `/capability-review` で別途評価する。
