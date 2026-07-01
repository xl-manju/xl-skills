---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
capability を 5 種の component_kind (skill/sub-agent/slash-command/hook/script) へ写像し、N=11 実体を `component-inventory.json` へ分解する。各 component の build_target・依存 DAG・品質機構を確定し、plugin envelope (`.claude-plugin/plugin.json`) の draft を設計する owner フェーズ。

## 実行タスク
- 同期/照合/初期投入の 3 skill (C01/C02/C03)、独立検証 sub-agent 3 (C04/C05/C06)、手動起動 command 2 (C07/C08)、破壊防止 hook 1 (C11)、共有 script 2 (C09/C10) を `component-inventory.json` に確定する。
- 各 component の depends_on を張り循環の無い DAG にする (C09/C10 が skill から共有される第二消費者関係を含む)。
- `envelope-draft/plugin.json` に manifest draft (entry_points / hooks 配線 / distribution) を設計する。
- 5 種の component_kind を全て検討した証跡 (considered_component_kinds) と plugin-level surface の採否を inventory に記録する。

## 成果物
- `component-inventory.json` (build 軸の唯一 SSOT・全 11 component)。
- `envelope-draft/plugin.json` (manifest draft)。

## 完了条件
- 全 11 component が build_target 非空・builder/build_kind 整合・depends_on 非循環で inventory に載っている。
- considered_component_kinds が 5 種全列挙され、plugin_level_surfaces の採否が明示されている。
