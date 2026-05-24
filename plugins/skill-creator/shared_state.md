# shared_state (Phase1 観察 / read-only)

## 構成俯瞰
skill-creator は SKILL 25本。主要グループ = goal-seek系(run-goal-elicit/run-goal-seek + goal-seek-paradigm.md)、skill生成系(run-skill-elicit/run-skill-create/run-build-skill)、ref-*辞書群(13本)、評価系(assign-*-evaluator/run-elegant-review)。

## 重複/冗長/曖昧が疑われる位置 (結論なし・位置のみ)
- A. ゴール抽出の二重化: run-goal-elicit vs run-skill-elicit Step4.4 / brief.goal,checklist
- B. ゴールシーク実行ループ本文の重複: goal-seek-paradigm.md / run-goal-seek SKILL / run-goal-elicit SKILL / templates/run.md (4箇所)
- C. brief schema 二重: run-skill-elicit/schemas/output.schema.json vs run-skill-create/schemas/skill-brief.schema.json(+references/skill-brief-schema.json redirect)
- D. brief雛形二重: run-skill-elicit/references/brief-template.md(旧.md形式) vs skill-brief.schema.json
- E. 生成フロー二重: run-skill-create vs run-build-skill(elicit/lint/評価/ゲート重複)
- F. goal-spec.json と skill-brief.json の goal/checklist 概念重複
- G. elicit プロンプト形式の二重: run-skill-elicit/prompts/main.yaml(YAML) vs run-skill-create/prompts/elicit.md(MD7層)
