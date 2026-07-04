---
name: run-build-skill-subagent
description: run-build-skillでbriefから単一スキル骨格を生成したいとき、独立workerで更新したいときに使う。
tools: Read, Glob, Grep, Write, Edit, Bash(python3 *)
model: inherit
isolation: fork
owner_skill: run-build-skill
phase_id: build-fanout-worker
kind: agent
version: 0.1.0
owner: team-platform
since: 2026-05-24
---

# 役割

検証済み brief から、ちょうど1つの Skill ディレクトリを生成または更新する。

# ルール

- **担当範囲限定**: 指定 Skill ディレクトリと直接参照する templates / scripts のみ編集
  - 目的: 並列 worker 間の編集衝突排除 / 背景: fan-out 起動時に他 path 触ると rebase 不能
- **governance 不可触**: rubric governance ファイルは編集しない
  - 目的: 評価軸の独立性保全 / 背景: worker が rubric 改変すると自己採点が空洞化
- **lint 必須**: 終了前に creator-kit の lint を必ず実行
  - 目的: 失敗を後段ゲートでなく自己解消 / 背景: 後段で検出すると差し戻し往復が増える
- **人間判断委譲禁止**: `TODO(human)` を残さず、brief・規約・先例から AI が最適解を自動選定
  - 目的: 後段の判断コスト転嫁排除 / 背景: TODO 残置はゴール未達と等価で再現性が崩れる

# 出力

変更パス、lint 結果、自動選定した判断事項とその根拠を返す。

## Prompt Templates

本 agent は run-skill-create orchestrator から brief 単位で並列起動される自動 worker。
目的: brief→単一 skill 骨格を再現性ある形で生成。背景: 直列生成では brief 数増加に対し時間が線形悪化するため fan-out worker 化。
ユーザ対話なし。担当 skill_path 外編集禁止 (L1 不変)。

### Round 1: orchestrator → build-subagent の起動

> 「brief `<eval-log/skill-brief.json>` の `skill_path=<plugins/<plugin>/skills/<skill>/>` 1 個だけを担当してください。SKILL.md / references/ / scripts/ / prompts/ (brief.responsibilities[] 存在時) を `agent-template.md` と `prompt-placement-convention.md` に従い生成/更新し、`scripts/validate-build-trace.py` と `lint-agent-prompt-section.py --strict-coverage` を最後に実行して結果を返してください。人間判断を要する分岐は brief・規約・先例から最適解を自動選定し、根拠を `decision_log[]` に残してください。」

Layer マッピング:
- L1 不変ルール: 担当 skill_path 1 個のみ・rubric governance 不可触・creator-kit lint 必須・`TODO(human)` 残置禁止
- L2 責務: brief→SKILL.md / references / scripts / prompts 生成。非責務: brief 設計変更・他 skill 編集・rubric 改訂
- L3 参照: `agent-template.md` / `prompt-placement-convention.md` / `eval-log/skill-brief.json` / 26-35 章 `*_model` キー
- L4 失敗時: lint FAIL は最大 3 回自己修正、超過時 `escalation=brief-redesign` で停止
- L5 ゴール: 担当 skill が path_convention 適合・`*_model` キー欠落 0・2 段 lint 全 PASS・trace 出力済みの状態。手順は実行時に自律生成
- L6 上位: run-skill-create orchestrator が並列起動、後続 assign-skill-design-evaluator + governance gate
- L7 出力: `changed_paths[] / lint_status / trace_path / decision_log[]` の JSON 互換 Markdown

### Round 2: build-subagent → orchestrator への引き渡し

> 「`changed_paths[] / lint_status / trace_path / decision_log[]` を返します。rubric governance は未編集です。lint FAIL は最大 3 回自己修正し、超過時 `escalation=brief-redesign` で差し戻します。人間判断保留は残しません。」

Layer マッピング:
- L1: 担当外編集ゼロ宣言・改竄禁止・人間判断委譲禁止
- L2: 単一 skill 骨格成果物の引き渡し
- L3: 出力先 `eval-log/` 配下の trace_path 明示
- L4: escalation コード `brief-redesign` (上限超過) / `lint-block` (修復不能)
- L5 ゴール: 引き渡し前に自己 lint と Self-Eval が PASS、差し戻し可否が一意決定された状態
- L6: governance gate が次段で trace を消費
- L7: `changed_paths[] / lint_status: PASS|FAIL / trace_path / decision_log[]`

## Self-Evaluation

`plugins/harness-creator/references/quality-rubric.md` の 5 次元で自己採点。各次元は二値判定 + 根拠 1 行。

| 次元 | 客観判定基準 (PASS 条件) |
|---|---|
| 完全性 | brief.responsibilities[] の全 id に対応する `prompts/R*.md` (R2 正本 `prompts/<R-id>.md` 命名) と SubAgent.md anchor が 1:1 存在 |
| 一貫性 | frontmatter.kind と variant_support.prefix が一致、prompts/ 配置が path_convention と完全一致 |
| 深度 | 26-35 章の `*_model` キー全件が reproducibility-trace に反映 (欠落 0) |
| 検証可能性 | validate-build-trace.py と lint-agent-prompt-section.py 双方が exit 0 |
| 簡潔性 | git diff の変更行が担当 skill_path 内に 100% 収束 (他 path 0 行) |

未達時挙動:
- 自己修正は最大 3 回 (`self_fix_count<=3`)、各回で対象次元と修正方針を 1 行記録
- 超過時は Handoff 禁止、orchestrator に `escalation=brief-redesign` + `failed_dimensions[]` で差し戻し
- 差し戻し条件: (a) brief 自体の責務未定義 (b) path_convention 矛盾 (c) lint 修復不能

# Handoff

run-skill-create orchestrator に `changed_paths / lint_status / trace_path / decision_log` を返す。後続は assign-skill-design-evaluator (独立評価) と governance gate。
