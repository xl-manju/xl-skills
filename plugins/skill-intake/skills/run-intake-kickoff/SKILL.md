---
name: run-intake-kickoff
description: intake セッション起動直後にパターン・深度・痛点 3 軸を確定したいとき、run-skill-intake から phase 1 として呼ばれて kickoff.json を生成したいときに使う。
allowed-tools:
  - Read
  - Write
  - AskUserQuestion
kind: run
user-invocable: true
effect: local-artifact
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-22
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
role_suffix: null
owner: team-platform
since: 2026-05-22
responsibility_refs:
  - prompts/main.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
---

# run-intake-kickoff

## Purpose & Output Contract

intake セッションの最初の phase。ユーザー初期発話から **3 軸 (pattern A-E / depth / pain ranking)** を AskUserQuestion で 1 問ずつ確定し、後続 phase の共通基盤となる `kickoff.json` を生成する。

**入力**: 初期発話 (自由記述、orchestrator から渡される)
**出力**: `output/<hint>/kickoff.json`
**完了条件**: pattern / depth / skill_name_hint / pain_ranking 4 項目が揃い、`scripts/validate-kickoff-json.py` PASS。

### 出力 JSON

```json
{
  "pattern": "A|B|C|D|E",
  "depth": "quick|standard|detailed",
  "skill_name_hint": "...",
  "pain_ranking": [{"task": "...", "frequency_per_week": 3, "minutes_per_run": 30}],
  "initial_utterance": "...",
  "timestamp": "ISO8601"
}
```

## Key Rules

1. **3 軸のみ**: pattern / depth / pain。仮説検証 (assumption-challenger) や 6 軸プロファイル (user-profiler) や 5 軸シート (interview) には踏み込まない。
2. **AskUserQuestion は 1 問ずつ**: 3 軸を一括質問しない。順次確定する。
3. **語彙は beginner 既定**: 初対面のため平易語を使う。
4. **口語→技術用語整形**: 初期発話の「定型作業」→「ルーチンタスク」のような整形は許可するが、ユーザー本旨は保持する。

## Steps

### Step 1: 初期発話の受領と整形

orchestrator から渡される初期発話を受け取り、口語表現を整形する。本旨は変えない。

### Step 2: pattern 確定 (Q1)

`references/pattern-catalog.md` の 5 パターン (A: 完全新規 / B: 既存類似 / C: プロンプト改善 / D: マルチスキル分離 / E: 不明) を提示し AskUserQuestion で 1 つ選んでもらう。

### Step 3: depth 確定 (Q2)

`references/depth-criteria.md` の 3 段階 (quick / standard / detailed) を提示し選択を取る。

### Step 4: pain ranking 取得 (Q3)

最も時間を奪っている作業を 1〜3 件、frequency_per_week と minutes_per_run と共に確認する。`references/pain-ranking-template.md` の構造に揃える。

### Step 5: skill_name_hint 仮決定

pain の動詞 + 目的語から kebab-case の仮 hint を生成 (ユーザー確認は次 phase 以降に委ねる)。

### Step 6: kickoff.json 書き出しと検証

```bash
python3 plugins/skill-intake/skills/run-intake-kickoff/scripts/validate-kickoff-json.py output/<hint>/kickoff.json
```
exit 0 で完了。

## Gotchas

1. **3 軸以外を質問しない**: 「真の課題は?」などの深掘りは Phase 5 の責務。本 phase で踏み込むと同意ループを誘発する。
2. **AskUserQuestion 3 連発禁止**: 1 問ずつ。並列質問は認知負荷が高い。
3. **pattern E (不明) 許容**: 確定できない場合は E で進め、Phase 8 の Gate A 時点で再判定する。

## Additional Resources

- `references/pattern-catalog.md` — pattern A-E の選択肢と判定基準
- `references/depth-criteria.md` — quick / standard / detailed の判断基準
- `references/pain-ranking-template.md` — 痛点構造化フォーマット
- `scripts/validate-kickoff-json.py` — 出力 JSON の schema validate
