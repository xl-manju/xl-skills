---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C03]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
skill loop 系 component (C01/C02/C03) の受入基準を test-first に導出し、`feedback_contract` の inner/outer criteria として固定する。実装前は criteria が未達 (Red) であることを確認する tdd-red gate。

## 実行タスク
- C01 (run-notion-task-sync): 「二回同期で差分0=冪等」の outer criterion と送信前検証の inner criterion を goal 由来で設計する。
- C02 (run-notion-task-reconcile): 「既知の発行漏れを全件検出」の outer criterion と照合ペイロード検証の inner criterion を設計する。
- C03 (run-notion-task-backfill): 「全件が Notion に存在し取りこぼし0」の outer criterion と一括投入検証の inner criterion を設計する。
- 各 criteria が対応 skill の goal/checklist 語彙を参照する (汎用ゲートの言い換えに退化させない) ことを確認する。

## 成果物
- C01/C02/C03 の `feedback_contract.criteria` (inner+outer 各 1 件以上) が inventory に確定した状態。

## 完了条件
- 3 skill の criteria が purpose 由来で inner/outer を各 1 件以上持つ。
- 実装前は criteria が未達 (Red) であることが確認できる。
