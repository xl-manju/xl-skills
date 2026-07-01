---
id: P11
phase_number: 11
phase_name: evidence
category: 検証
prev_phase: 10
next_phase: 12
status: 未実施
gate_type: evidence
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P11 — evidence (手動テスト検証)

## 目的
UBM のスクショ検証を DROP し、Markdown による evidence 5 要素へ写像する evidence gate。プラグインが受入を満たしたことを再現可能な形で記録する。

## 実行タスク
Markdown evidence として以下 5 要素を残す:
1. P0 lint が exit0 になったログ。
2. schema parity テストの結果。
3. build-trace coverage の結果。
4. content-review verdict (PASS・sha 一致)。
5. harness coverage の JSON (kind 別 ≥80%)。

## 成果物
- evidence 5 要素を集約した Markdown 検証記録。

## 完了条件
- evidence 5 要素が全て Markdown に記録され、第三者が再現・確認できる状態になっている。
