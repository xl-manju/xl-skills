---
id: C03
component_kind: slash-command
name: sync-tasks
description: タスク台帳の Notion 同期を手動起動する
argument-hint: "[--dry-run]"
allowed-tools: [Read, Bash, Skill]
disable-model-invocation: false
depends_on: [C01]
quality_gates:
  p0_lint: [validate-frontmatter]
  build_trace: required
  elegant_review:
    conditions: [C1, C2, C3, C4]
    all_pass: true
  content_review:
    verdict: PASS
    sha_match: true
  evaluator:
    threshold: 80
    high_max: 0
harness_coverage:
  min: 80
  kind_pass: content-review-verdict+test
---

# C03: /sync-tasks (slash-command)

## 目的
`run-notion-task-sync` (C01) を手動起動するための薄い slash-command。`--dry-run` で差分プレビューのみを行う。

## 成果物
- `commands/sync-tasks.md` (argument-hint / allowed-tools 最小 / disable-model-invocation 明示)
- 親 skill build 内 run-build-skill kind=command dispatch で生成される

## 完了条件
- `validate-frontmatter` exit0 (command 専用 lint は未提供のため frontmatter 検証で担保)
- `--dry-run` 有無で起動経路が分岐することを機能テストで確認
