---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
「タスク台帳を Notion DB へ冪等同期する」という構想を目的ドリブンに要件化し、後続フェーズが参照する `goal-spec.json` を確定させる。target_plugin_slug=`notion-task-sync` を固定し、Notion を中核とする外部依存 (MCP/API・冪等性・破壊防止) の制約を開示する。

## 実行タスク
- run-goal-elicit で purpose / background / goal / 受入観点を引き出し `goal-spec.json` へ焼く。
- target_plugin_slug を kebab (`notion-task-sync`) で確定し `plan_dir=plugin-plans/notion-task-sync` を決める。
- 中核が Notion API/MCP であることから、冪等同期・発行漏れ検出・破壊操作防止という受入観点を purpose 由来で明文化する (このフェーズは特定 component へは紐づかない)。

## 成果物
- `goal-spec.json` (purpose/background/goal/checklist/constraints/handoff_targets)。
- target_plugin_slug と plan_dir の確定値。

## 完了条件
- `goal-spec.json` が purpose を非空で保持し、受入観点が purpose 語彙から導出されている。
- target_plugin_slug が ASCII kebab で確定し以降のフェーズがそれを参照できる。
