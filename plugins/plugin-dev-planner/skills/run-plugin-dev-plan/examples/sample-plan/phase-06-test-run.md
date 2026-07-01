---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P06 — test-run (テスト実行)

## 目的
全 component の harness coverage を ≥80% (kind 別・6 種別 × 二軸) まで拡充し、テストを実行して緑にする。計画段階では現状カバレッジ数値を焼かず、min=80 の閾値と kind_pass の見方のみを契約する。

## 実行タスク
- script (C09/C10): pytest 行カバレッジ ≥80% を確認する。
- skill loop (C01/C02/C03): criteria 検証テスト (inner/outer) + content-review verdict を実行する。
- sub-agent (C04/C05/C06): 機能テスト + content-review verdict を実行する。
- slash-command (C07/C08) / hook (C11): 起動分岐・遮断の機能テスト + content-review verdict を実行する。

## 成果物
- 全 component の harness テスト実行ログ (kind 別 ≥80%)。

## 完了条件
- 全 component の harness_coverage.min≥80 が実測で満たされ、kind_pass の観点が緑になる。
- 現状値を計画に焼かず、閾値と観点のみを契約として保持している。
