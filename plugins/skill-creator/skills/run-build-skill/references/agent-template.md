---
name: agent-template
description: run-build-skill が SubAgent ファイルを量産するための正本テンプレート。9 セクション固定で Prompt Templates と Self-Evaluation を必須化する。
type: reference
version: 1.0.0
---

# SubAgent 9 セクション正本テンプレート

`plugins/<plugin>/agents/<role>.md` を量産する際の骨格。

## なぜこの 9 セクションか

| # | セクション | 役割 | lint 必須 |
|---|---|---|---|
| 1 | Frontmatter | name / description / tools / model / context-fork | ✅ |
| 2 | Purpose | 役割定義 (Layer 1 相当: 不変定義) | ✅ |
| 3 | Inputs | 前提・参照 reference (Layer 2 相当: ドメイン定義) | ✅ |
| 4 | Outputs | 成果物パス + JSON 雛形 (Layer 6 相当: 出力契約) | ✅ |
| 5 | Steps | 思考プロセス (Layer 5/6 相当: 実行仕様) | ✅ |
| 6 | Constraints | 制約・禁止事項 (Layer 4 相当: ガードレール) | ✅ |
| 7 | **Prompt Templates** | ユーザーに投げる実発話例 (Layer 7 相当) | ✅ **NEW** |
| 8 | **Self-Evaluation** | quality-rubric.md の 5 次元採点 | ✅ **NEW** |
| 9 | Handoff | 次 agent と引き継ぎデータ | ✅ |

7 と 8 が legacy `doc/skill-intake-interviewer/agents/` には有り、現状 `plugins/skill-intake/agents/` には欠落していた領域。本テンプレで再導入する。

## 完全な骨格テンプレ

```markdown
---
name: <plugin-prefix>-<role>
description: <一行で何をする agent か。"~ するエージェント。" で終わる。>
tools: <最小権限。例: Read, Write, AskUserQuestion>
model: <sonnet|haiku>  # 対話系=sonnet / 決定論系=haiku
---

## Purpose

<役割 2-3 文。Layer 1 相当の不変定義。>

## Inputs

- <参照する output/<hint>/*.json>
- <参照する references/*.md (Progressive Disclosure)>

## Outputs

- `output/<hint>/<name>.json` (構造化結果)
- `output/<hint>/<name>.md` (人間向けサマリ, 任意)

出力 JSON 雛形:

```json
{
  "<field>": "<value>",
  "next_agent": "<successor-agent-name>"
}
```

## Steps

1. <思考プロセス番号付きステップ>
2. <次のステップ>

## Constraints

- <禁止事項。"~ しない" 形式>
- <ガードレール>

## Prompt Templates

各ラウンドでユーザーに投げる実発話例。`vocabulary_tier` (beginner/intermediate/expert) に応じて差し替える。

### Round 1: <局面名>

> 「<実発話例。語彙 tier=beginner 想定>」

選択肢 (任意):
1. <option 1>
2. <option 2>
3. <option 3>

### Round N: <局面名>

> 「<実発話例>」

## Self-Evaluation

`plugins/skill-intake/skills/run-skill-intake-aggregator/references/quality-rubric.md` の 5 次元で自己採点する。

| 次元 | 本 agent での重点 |
|---|---|
| 完全性 | <この agent で重点的に見る合格条件> |
| 一貫性 | <矛盾を排除する観点> |
| 深度 | <深掘り十分性> |
| 検証可能性 | <スクリプト/客観条件で判定可能か> |
| 簡潔性 | <冗長排除> |

未達なら自己修正を 1 回試行し、それでも未達なら Handoff せず orchestrator に差し戻す。

## Handoff

<次 agent 名> へ <引き渡しデータ> を渡す。
```

## prompt-creator 連携 (任意)

`brief.use_prompt_creator: true` 指定時、run-build-skill は `Skill(run-prompt-creator-7layer)` を起動して 7 層 YAML を `agents/prompts/<role>.yaml` に生成し、本テンプレの Prompt Templates / Self-Evaluation セクションを自動充填する。

詳細は `plugins/prompt-creator/skills/run-prompt-creator-7layer/SKILL.md` を参照。

## lint 規則

`plugins/skill-governance-lint/scripts/lint-agent-prompt-section.py` で以下を必須化:

1. `## Prompt Templates` 見出しが存在する
2. `## Self-Evaluation` 見出しが存在する
3. Prompt Templates 配下に少なくとも 1 つの `>` 引用 (実発話) または `### Round` 見出しがある (純自動 agent でユーザー対話が無い場合は本文に `(対話なし: 自動実行 agent)` を明記すれば skip 許可)
4. Self-Evaluation 配下に 5 次元 (完全性/一貫性/深度/検証可能性/簡潔性) のいずれか 1 つ以上が言及されている

## 命名規則 (再掲)

- agent 名: `<plugin-prefix>-<role>` (例: `skill-intake-interviewer`)
- description は `~ する <名詞>。` で終わる
- nested directory 禁止 (lint-skill-tree 第 13 条準拠)
