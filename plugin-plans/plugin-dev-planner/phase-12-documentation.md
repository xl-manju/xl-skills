---
id: P12
phase_number: 12
phase_name: documentation
category: 文書
prev_phase: 11
next_phase: 13
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P12 — documentation (ドキュメント)

## 目的
task-graph 機構の利用者向けドキュメント (中学生説明 Part1 概念 + Part2 技術) を確定し、反映先 (feedback_contract_ssot/lessons-learned/bundles.json 相当) と install 手順への影響有無を明示する。

## 背景
本サイクルは既存プラグインの内部拡張であり、entry_points (skills/agents/commands) の追加・削除を伴わないため、install 手順自体への変更はない。ドキュメントは task-graph という新概念の説明に限定される。

## 前提条件
- P11 の evidence 設計が完了している。

## ドメイン知識
- Part1 (概念): 「plan は 13 個の作業手順書 (phase ファイル) と 1 個の部品台帳 (component-inventory.json) を持っていたが、今回、作業手順書の中の細かい作業同士がどの順番で・どのファイルを待って進めるべきかを表す『地図 (task-graph)』が新しく増えた」という説明。
- Part2 (技術): task-graph.json の node/edge 型・ready-set 計算・discovered-task 二段受理・canonical serialization の技術詳細。
- 反映先: 新規スクリプト群の変更点は `references/task-graph-contract.md` (新規) へ集約し、既存 `references/phase-lifecycle.md`/`references/component-domain.md` への言及追記は最小限 (task-graph が第 3 の射影であることの 1 文相当) に留める。
- install 手順: entry_points 変更なしのため既存 README/setup 手順は不変。

## 成果物
- `references/task-graph-contract.md` の設計方針 (node/edge 型・ready-set アルゴリズム・discovered-task 受理フロー・canonical 規約・handoff-notes 契約を集約する新規 reference)。

## スコープ外
- README/setup 手順の実編集 (entry_points 変更を伴わないため本 plan では不要)。

## 完了チェックリスト
- [ ] Part1/Part2 の 2 タスク雛形が task-graph という新概念に即して具体化されている。
- [ ] 反映先 (新規 reference ファイルの位置と役割) が明示されている。
- [ ] install 手順への影響有無 (無し) が明示されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: Part1 の説明文が「地図」という具体的比喩で task-graph の役割を説明し、Part2 が node/edge 型・ready-set・discovered-task・canonical・handoff-notes の 5 点を具体的に列挙する。
- 満たさない例: 「ドキュメントを更新する」とだけ記され、対象ファイルや説明内容が未確定である。

### 事前解決済み判断
- 分岐点: task-graph の説明を既存 `phase-lifecycle.md` 内に統合するか、新規 reference ファイルへ分離するか → 判断: 新規ファイル (`references/task-graph-contract.md`) へ分離 (task-graph は独立した検証可能な契約群 (schema 3 件・script 5 件) を持ち、既存ファイルへの追記のみでは規模に見合わないため)。

## 参照情報
- P11 (evidence)。
- 後続 P13 (release)。
