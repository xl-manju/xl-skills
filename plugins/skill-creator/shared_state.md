# shared_state (Phase1 観察 / read-only / scope=評価フィードバックループ機構)

## 先行context要約 (200字以内)
利用者の訴え: skill-creator がスキルを生成する際「そのスキル固有の評価基準」が漏れ、評価→改善ループが回らない。フックで評価が確実に起動せず毎回スキップされる。内ループ(小機能ごとのゴールシーク)と外ループ(ハーネス全体)を正負フィードバックで設計し、有界反復(トークン節約)で回したい。既存改善・矛盾/重複なしが要件。

## 評価フィードバック機構の構成俯瞰 (事実のみ)
### フック (plugin.json, 8配線)
- Stop → `run-elegant-review/scripts/check-review-trigger.py`
- SessionEnd → `run-skill-rubric-governance/scripts/aggregate-evals.py`
- PostToolUse(Skill) → `run-skill-update-notifier/hook-notify-skill-end.py` + `run-build-skill/auto-record-lesson.py`
- PostToolUse(Edit|Write) → `run-build-skill/lint-capability-manifest.py`
- PostToolUse(Edit) → `run-skill-rubric-governance/diff-rubric-impact.py`
- PreToolUse(Bash) → `wrap-git-commit-safe/preflight-git-commit.py`
- UserPromptSubmit → `ref-task-context-map/preload-context-map.py`
- UserPromptExpansion → `run-skill-update-notifier/hook-cache-refresh.py`

### 内ループ (per-skill goal-seek)
- `run-build-skill/references/goal-seek-paradigm.md`(正本): Goal/Why/Checklist/Loop 6ステップ + Anchor Step/drift_signal, max_loops=5
- `run-goal-seek` / `run-goal-elicit`(ゴール抽出・実行)
- combinator `with-goal-seek.patch` + `lint-goal-seek.py` + `schemas/goal-seek-loop.schema.json`

### 外ループ (whole-harness elegant-review)
- `run-elegant-review` + `references/convergence-policy.json`: 解像度3層(L1/L2/L3) + 正負フィードバック両輪 + halt(converged/diverged/max_iterations=3)
- `references/amplified-patterns.json`(正フィードバック蓄積先)

### 評価基準
- `assign-skill-design-evaluator` + `ref-skill-design-rubric/references/rubric.json`(汎用 rubric)
- `run-skill-rubric-governance`(rubric改訂提案) + `proposals/`
- `EVALS.json`(集計対象・現状ほぼ空baseline)
- `ref-domain-rubric-template` / `ref-domain-task-spec-rubric`(ドメイン別 rubric 雛形)

### 知識ループ
- `knowledge/` / `lessons-learned/` / `auto-record-lesson.py`(PostToolUse(Skill)で記録)

## 第一印象として気になる点 (結論なし・位置のみ)
- P1: `check-review-trigger.py` が「stdout に推奨 JSON を書くだけ」で評価を**起動していない**位置(Stop hook)
- P2: 起動閾値が `git status 変更20件固定`。スキル単位/小変更での起動条件が無い位置
- P3: `EVALS.json` に**実評価を書き込む経路**が見当たらない位置(`aggregate-evals.py` は読むだけ)
- P4: スキル生成(`run-build-skill`)時に「そのスキル固有の評価基準」を**生成・保存する記述の所在**
- P5: 内ループ(goal-seek)と外ループ(convergence-policy)の**正負フィードバック概念が別ファイルに分散**。接続点/SSOTの所在
- P6: `convergence-policy.json` が `run-elegant-review` 配下に閉じ、内ループ goal-seek 側から参照されているかの所在
- P7: 「評価基準=各スキルの目的に紐づく」を保持する**成果物(per-skill criteria file)の所在**
- P8: `goal-seek-paradigm.md` の「評価系(assign-*)はループしない read-only 工程」と、利用者要望「評価→改善ループ」の整合の所在
