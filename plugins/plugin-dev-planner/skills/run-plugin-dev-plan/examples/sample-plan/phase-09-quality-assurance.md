---
id: P09
phase_number: 9
phase_name: quality-assurance
category: 品質
prev_phase: 8
next_phase: 10
status: 未実施
gate_type: qa
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P09 — quality-assurance (品質保証)

## 目的
全 component に対し P0 lint + build-trace + schema parity + content-review を実行する qa gate。各 component の quality_gates ブロックが機械的に強制され、content-review verdict が現 SHA で genuine に PASS していることを保証する。

## 実行タスク
- 各 component の quality_gates.p0_lint を component_kind 別に実行し exit0 を確認する。
- build-trace 章の coverage が全 component で PASS することを確認する。
- schema parity (frontmatter ↔ schema required) を検査する。
- content-review を独立 SubAgent で実行し verdict=PASS・sha_match=true を得る。

## 成果物
- 全 component の P0 lint / build-trace / schema parity / content-review verdict の結果一式。

## 完了条件
- 全 component で P0 lint exit0・build-trace coverage PASS・content-review verdict=PASS(sha 一致) を満たす。
