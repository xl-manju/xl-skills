---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
各 component の二値の受入基準 (AC) を build 後の受け入れとして判定する。purpose「タスク台帳を Notion DB へ冪等同期する」が組み上がったプラグインで実際に満たされているかを確認する見方を固定する。

## 実行タスク
- C01/C03: 同期・初期投入後に台帳差分/全件が Notion に反映され、二回目実行の追加/更新が 0 件 (冪等) であることを判定する。
- C02: 既知の発行漏れを注入して reconcile が全件検出することを判定する。
- C11: 破壊的操作が hook で fail-closed に阻まれることを判定する。
- C04/C05/C06/C07/C08/C09/C10: 各 component の output_contract が満たされ受入テストが二値で PASS することを判定する。

## 成果物
- 全 component の AC 判定結果 (PASS/FAIL の二値)。

## 完了条件
- 各 component の受入基準が二値で判定され、purpose 由来の受入観点が全て PASS している。
