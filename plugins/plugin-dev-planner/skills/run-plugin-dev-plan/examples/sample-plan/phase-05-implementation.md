---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装)

## 目的
全 buildable component を後段 builder へ委譲して実体化し、P04 で設計した criteria を満たす (Green) 状態にする。build routing は `component-inventory.json` の依存 top-sort 順に実行する (phase 順 ≠ build 順)。

## 実行タスク
build は component 単位で `handoff-run-plugin-dev-plan.json` の routes に従い、以下の runnable checklist を inventory の top-sort 順で実行する:
1. C09 validate-sync-payload.py — parent-skill-build (script)。
2. C10 notion-idempotency-key.py — parent-skill-build (script)。
3. C11 guard-destructive-sync — run-build-skill (hook)。
4. C01 run-notion-task-sync — run-skill-create (skill・C09/C10 に依存)。
5. C03 run-notion-task-backfill — run-skill-create (skill・C09/C10 に依存)。
6. C02 run-notion-task-reconcile — run-skill-create (skill・C09/C01 に依存)。
7. C04/C05/C06 各 auditor sub-agent — run-build-skill (agent)。
8. C07 sync-tasks / C08 reconcile-tasks — run-build-skill (command)。

## 成果物
- 全 11 component の実体 (skills/agents/commands/hooks/scripts) が build_target に生成された状態。
- `envelope-draft/plugin.json` を基にした plugin manifest (後段 scaffold owner)。

## 完了条件
- 依存順に全 component が build され、skill loop の criteria が Green (受入テスト PASS) になる。
- build 実体パスが inventory の build_target と一致する。
