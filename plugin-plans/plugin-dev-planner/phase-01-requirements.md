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
plugin-dev-planner が生成する plan 成果物へ、13 phase 仕様書の直列消化に律速されない第 3 の射影 (型付き task-graph) を追加するという改善要求から、`goal-spec.json` (purpose/background/goal/checklist C1-C16/constraints/handoff_targets) を確定する。`target_plugin_slug: plugin-dev-planner` を固定し、既存 2 軸 (13 phase ファイル / component-inventory.json) の意味論を task-graph が置換しないことを要件レベルで明文化する。

## 背景
現行 plan は 13 phase ファイル (ライフサイクル軸) と component-inventory.json (実体軸 depends_on DAG) の 2 軸を持つが、phase 仕様書 §5 のタスク項目が粗粒度のまま直列読み物に留まり、(1) タスク単位の依存エッジ不在による並列可能作業の直列待ち、(2) タスク完了成果物 (build_target / eval-log route-build-report) が次タスク入力として機械参照されない spec/output 間の断絶、(3) 実行中に発見された新タスクの構造化還流経路の不在、の 3 問題を抱える。ユーザーは親子関係・depends/blocks・成果物エッジを厳密に型付けした依存グラフと、discovered-task 形式での計画進化 (作りながら改善) を要求している。

## 前提条件
- 対象プラグイン `plugins/plugin-dev-planner/` は既に 2 skill (run-plugin-dev-plan, assign-plugin-plan-evaluator) を持つ既存プラグインであり、本 plan は `artifact_class: existing-plugin-update` として自己拡張を行う。
- 直前の plan サイクル (`plugin-plans/finish/plugin-dev-planner/`) は generative-fidelity/downstream-harness 層 (旧 C1-C12) を対象にしており、build 済みで既存スクリプト群 (check-generative-fidelity.py 等) として現存する。本 plan の checklist C1-C16 は task-graph という別テーマであり、旧サイクルの checklist と番号が重複するが対象は異なる。

## ドメイン知識
- goal-spec の checklist は 16 件 (C1-C16)。verify_by の内訳は script=9件 (C1/C2/C3/C5/C6/C9/C12/C13/C16)・test=5件 (C4/C7/C10/C11/C15)・human=2件 (C8/C14)。C14 (新旧shape非劣化ゲート) は (a)精度/(c)再現性は script 計測、(b)品質は fork evaluator の genuine 判定 (human) のため checklist 全体としては verify_by=human に分類する。C15 (graph 可視化 renderer) は byte一致 render テストで verify_by=test、C16 (実行時契約 schema SSOT) は schema 検査で verify_by=script。
- constraints の中核は「task-graph は第 3 の射影であり既存 2 軸の意味論を置換しない」「メタ循環の分離: 本 plan 自体は現行 shape (13 phase ファイル) で記述する」「canonicalizer が唯一の serializer」「blocks は depends_on の逆向き導出ビューで独立宣言禁止」「L4 実 build 実行は本 plan の責務外」の 5 点。
- handoff_targets: run-skill-create / run-build-skill / capability-build。max_loops: 5。

## 成果物
- `goal-spec.json` (確定済み・本 phase 時点で再読込による内容確認のみ行い、書き換えは行わない)。

## スコープ外
- component-inventory.json の分解 (P02 の責務)。
- task-graph の schema/導出/検証ロジックの詳細設計 (P04/P05 の責務)。

## 完了チェックリスト
- [ ] purpose/background/goal が task-graph 追加という改善要求の文脈で一貫している。
- [ ] checklist C1-C16 それぞれに verify_by (script/test/human) が付与されている。
- [ ] target_plugin_slug が `plugin-dev-planner` に固定され、plan_dir が `plugin-plans/plugin-dev-planner` に固定されている。
- [ ] constraints の 5 点 (2軸非置換/メタ循環分離/単一writer/blocks派生専用/L4責務外) が本 plan 全体の設計判断へ反映される前提が明示されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: goal-spec の goal 文が「task-graph を第 3 の射影として追加し、既存 2 軸を置換しない」ことを明示し、checklist 16 件それぞれが独立した verify_by を持つ。
- 満たさない例: task-graph の目的が「グラフ機能を追加する」とだけ記され、既存 2 軸との関係 (置換か包含参照か) が未確定のまま P02 へ進む。

### 事前解決済み判断
- 分岐点: 本 plan 自体の出力形式を 13 phase ファイル固定にするか、C10 が要求する可変 shape で書くか → 判断: 13 phase ファイル固定 (constraints のメタ循環分離規約により、本 plan は現行 skill・現行ゲートで生成/検証されるため現行 shape を採る。C10 は将来の plan が可変 shape を使える機能要件であり、本 plan 自身の記述形式ではない)。

## 参照情報
- `plugin-plans/plugin-dev-planner/goal-spec.json`。
- `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/references/phase-lifecycle.md` §7/§8。
- 後続 P02 (design)。
