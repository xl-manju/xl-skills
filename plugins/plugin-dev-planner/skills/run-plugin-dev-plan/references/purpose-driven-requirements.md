---
name: purpose-driven-requirements
description: 固定手順でなく目的ドリブンで動かすための要件定義(goal-spec/ゴールシーク/中間成果物アンカー/収束閾値/feedbackループ/TDD対応)を読む。R1 と横断パラダイムの正本。
kind: reference
owner: team-platform
since: 2026-06-29
source-tier: internal
---

# 目的ドリブン駆動開発の要件定義 (§13)

> 本スキルは固定手順でなく**目的ドリブン**で動く。以下を P1 + 横断パラダイムとして要件化する。正本の数値/形式は skill-creator-spec-reflection.md の D1-D6 を参照。

1. **要件定義 = goal-spec 固定**: `run-goal-elicit` が曖昧構想から `purpose/background/goal/checklist` を `<PLAN_DIR>/goal-spec.json` に固める。`PLAN_DIR` は既定 `eval-log/plugin-dev-planner/<plugin-slug>/` で、`target_plugin_slug` とともに goal-spec へ固定する。checklist 各項目は `{id:^C[0-9]+$, criterion, done, verify_by ∈ {reasoning,script,lint,test,human}}`。追加質問せず仮定は constraints/open_questions に明示。

2. **固定手順禁止**: 「## ゴールシーク実行」4 ブロック (ゴール=観測可能完了形 1 文 / 目的背景 Why / 完了チェックリスト=二値 / ループ) + 6 ステップ (現状評価→手順生成→実行→検証→Anchor Step→反復・既定 5 周)。AI 最尤ゴール推定。

3. **中間成果物アンカー**: 各周回末に `<PLAN_DIR>/run-plugin-dev-plan-intermediate.jsonl` へ 5 要素 (`original_goal`=不変・SHA256 照合 / `current_goal_snapshot` / `delta_from_original` / `merged_directive_for_next` / `drift_signal` ∈ {initial,aligned,compressing,stagnant,widening,oscillating}) を追記。次周回 Step2 は前 merged_directive + original_goal を必須入力。改竄検知で停止。

4. **収束閾値**: `convergence-policy.json` (all_conditions_score_min=0.85 / delta_max_ratio=0.20 / 収束 Δ<0.10 / max_iterations=3 / loop_bounds: goal_seek_inner=5・content_review_inner=3・outer=3)。

5. **feedback ループ**: Stop hook `decision:block` で評価差し戻し起動・proposer≠approver・量産先に run-skill-feedback 実体配備。

6. **TDD 対応づけ**: Red→Green = 「未達チェックリスト項目 → goal-seek ループで埋める → 検証 exit0/PASS」。

## 本スキルへの適用

- R1 (R1-elicit-goal.md) が構想から goal-spec を確定する (目的ドリブン要件定義)。
- 本スキル自身の `## ゴールシーク実行` も上記 4 ブロック + 6 ステップで構成し、`### ゴールシーク配線` に中間成果物アンカー (`intermediate.jsonl`/`original_goal`/`merged_directive_for_next`) を配線する。
- 量産する各タスク仕様書にも、上記 1-6 を「生成プラグインが満たすべき設計」として焼き込む (D1-D6 の焼き先)。
