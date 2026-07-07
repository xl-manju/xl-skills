---
id: P06
phase_number: 6
phase_name: test-run
category: テスト
prev_phase: 5
next_phase: 7
status: 未実施
gate_type: none
entities_covered: [C01, C02]
applicability:
  applicable: true
  reason: ""
---

# P06 — test-run (テスト実行)

## 目的
C01/C02 の `harness_coverage` (min≥80・kind_pass) を設計として確定し、build 後に実測される達成率の数値は本 phase では焼き込まず「≥80% を満たす設計」の要件化に留める (Goodhart 回避)。

## 背景
harness-coverage は 6 種別 (mechanical/llm_eval の対) × 2 軸で測定される。C01 は `loop=criteria-test+content-review-verdict` (feedback_contract.criteria IN1-IN13/OUT1-OUT3 のテスト網羅 + content-review verdict)、C02 は `assign=evaluator-verdict` (fork evaluator の verdict 網羅) を kind_pass の型として持つ。

## 前提条件
- P05 の実装設計が確定している。

## ドメイン知識
- 新規 pytest ファイル (P05 の設計に対応): `test_derive_task_graph.py` (C2/C11 canonicalize 再現性)・`test_validate_task_graph.py` (C2/C3/C11 の 6 検査項目)・`test_compute_ready_set.py` (C4 の 4 ケース、P04 の受入例テーブルをフィクスチャとして使用)・`test_accept_discovered_task.py` (C5 の additive/structural 二段受理)・`test_apply_handoff_notes.py` (C12 の件数/文字数上限・有界伝播)・`test_task_graph_backward_compat.py` (C7: task-graph.json 不在時に既存ゲート全 exit0)・`test_check_plan_ledger.py` (C13: active 重複 fail-closed 検出・status enum 値域・cycle_id 形式 (`CYCLE_ID_RE`) 検証)・`test_migrate_plan_layout.py` (C13: 既存 flat 配置 → cycle-id 配置への移行・`plugin-plans/finish/` 配下は台帳への `status: finished` 登録のみで物理移動しないことの確認)・`test_check_shape_non_regression.py` (C14: (a) 二値受入基準携帯率が旧shape基準線を下回らないことの計測・(c) task-graph byte 一致 + 仕様書構成一致の再現性検証。P04 の A/B fixture (旧shape/新shape) をそのままフィクスチャとして使用)・`test_render_task_graph_mermaid.py` (C15: 同一graphからの2回連続renderがbyte一致すること・出力mermaidのnode id集合が入力graphのnode id集合とset一致すること (graph外要素非描画) をP04のT1-T4フィクスチャで検証)・`test_check_task_state_schema.py` (C16: task-state.schema.json整合 (running状態のlease必須) + graph_hash pin不一致のfail-closed検出をP04のfixtureで検証)。
- 既存 pytest への追加: `check-build-handoff.py`/`verify-index-topsort.py` の既存テストファイルへ `_check_task_graph_ref`/`_shape_marker` のデフォルト引数ケース (未設定時に検査スキップ・既定値フォールバック) を追加する。
- 現状の plugin-dev-planner 全体テスト件数 (既存 388+ 件、`test_gate_parity.py` の 9 parity アサーション) からの退行が 0 であることを OUT1 として設計する。

## 成果物
- C01/C02 の `harness_coverage` ブロック (component-inventory.json に反映済み・min:80)。

## スコープ外
- 実測カバレッジ数値の記録 (build 後の実測作業・本 plan の対象外)。

## 完了チェックリスト
- [ ] C01/C02 双方の harness_coverage.min が 80 以上に設計されている。
- [ ] kind_pass が component の kind (run/assign) に整合する型で記述されている。
- [ ] 新規 pytest ファイル 11 本の対象 (C2/C3/C4/C5/C7/C11/C12/C13/C14/C15/C16) が具体的に特定されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: `test_compute_ready_set.py` が P04 の 4 ケーステーブルをそのままフィクスチャとして使用する設計になっている。
- 満たさない例: 「テストを追加する」とだけ記され、対象ファイル名・検証観点が未確定である。

### 事前解決済み判断
- 分岐点: harness_coverage.min に現状の実測値 (未計測) を仮に記載するか → 判断: 記載しない (constraints: harness 現状未達数値は component へ焼かない。「≥80% を満たす設計」の要件化に留める)。

## 参照情報
- P05 (implementation)。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/tests/test_gate_parity.py`。
- 後続 P07 (acceptance-criteria)。
