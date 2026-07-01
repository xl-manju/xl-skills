---
id: P10
phase_number: 10
phase_name: final-review
category: レビュー
prev_phase: 9
next_phase: 11
status: 未実施
gate_type: final-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P10 — final-review (最終レビューゲート)

## 目的
完成したプラグイン全体を final-gate として elegant-review C1-C4 (final) + governance で審査し、unassigned component が 0 件であることを確認する。proposer≠approver で最終承認を下すゲート。

## 実行タスク
- elegant-review C1-C4 を final スコープ (プラグイン全域) で実行する。
- governance-check (runbook / CI 配線) を確認する。
- detect-unassigned で orphan component 0 件・13 フェーズ完全性を再確認する。
- 独立 approver がプラグイン全体を承認する。

## 成果物
- final-gate の判定記録 (C1-C4 全 PASS / governance PASS / unassigned 0)。

## 完了条件
- elegant-review C1-C4 全 PASS・governance PASS・unassigned 0 件で、独立 approver が承認している。
