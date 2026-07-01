---
id: P08
phase_number: 8
phase_name: refactoring
category: 改善
prev_phase: 7
next_phase: 9
status: 未実施
gate_type: tdd-refactor
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P08 — refactoring (リファクタリング)

## 目的
テストが緑の状態を保ったまま、SSOT 重複を排除する (lint-ssot-duplication・上書き一本化)。本プラグインでは C09/C10 の共有 script が sync/reconcile/backfill から二重定義されない単一実体であることを保証する改善フェーズ。

## 実行タスク
- lint-ssot-duplication を実行し、共有 script (C09/C10) やペイロード規約が複製されていないか検査する。
- 重複が見つかれば両方残さず上書きで一本化し、第二消費者は import/参照で共有する。
- リファクタ後に P06 のテストが引き続き緑であることを再確認する (tdd-refactor)。

## 成果物
- SSOT 重複が 0 件になった状態 (共有 script が単一実体)。

## 完了条件
- lint-ssot-duplication が exit0 で、共有ロジックが一本化されている。
- リファクタリングによってテストが赤に戻っていない。
