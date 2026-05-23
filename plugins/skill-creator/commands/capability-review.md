---
description: 既存 Capability に対し run-elegant-review を起動する。多視点 agent 並列レビュー → 集約 → ゲート判定までを一括実行する薄いラッパ。
argument-hint: "<target-path> [scope]  例: plugins/skill-creator/skills/run-build-skill / agents/elegant-reset-observer.md full"
allowed-tools: Read, Bash
kind: command
---

# /skill-creator:capability-review

`$ARGUMENTS` の `<target-path>` を `run-elegant-review` Skill に渡し、Phase 1 (発散) → Phase 2 (集約) → Phase 3 (収束判定) を起動する薄いラッパ。

## 振る舞い

1. `$ARGUMENTS` を `<target-path> [scope]` にパース。target が存在しなければ停止。
2. target_type を自動判定 (skill/agent/hook/command/composition)。
3. `run-elegant-review` Skill を起動。`scope` 省略時は `default` (severity high のみ)、`full` で全 severity 評価。
4. 集約後の C1〜C4 ゲート結果と residual_risks を報告。FAIL 時は `/skill-creator:skill-improve <target-path>` を案内。

## 引数

| 引数 | 説明 |
|---|---|
| `target-path` | レビュー対象の絶対 or リポジトリ相対パス (必須) |
| `scope` | `default` / `full` / `quick` (省略時 default) |

## 失敗時

- target 不在: パス候補を表示
- target_type 判定不能: 明示指定 (`--type=skill` 等) を案内
- 収束未達 (max 3 iteration 超過): human_review に escalate

## 注意

- 改善実行は行わない (analyse only)。実行は `/skill-creator:skill-improve` を使う。
