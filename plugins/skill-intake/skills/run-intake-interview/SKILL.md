---
name: run-intake-interview
description: ヒアリングシートの 5 軸空欄を順次埋めたいとき、run-skill-intake から phase 4 として呼ばれて sheet.md と interview.json を生成したいときに使う。
allowed-tools:
  - Read
  - Write
  - Edit
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

# run-intake-interview

## Purpose & Output Contract

Phase 4 担当。ヒアリングシート `sheet.md` の空欄および `[?]` を **5 軸 (出力先 / 情報源 / 共有相手 / 真の課題 / ナレッジ資産) 優先順位**で AskUserQuestion により順次充足する。語彙は `profile.json` の `vocabulary_tier` に固定し、抽象的回答は `needs_excavation` フラグを立てるのみで深掘りはしない (Phase 5 の責務)。

**入力**: `profile.json`, `sheet.md` (空欄を含む), `references/question-bank-pointer.md` 経由の質問雛形
**出力**:
- `output/<hint>/sheet.md` (更新済)
- `output/<hint>/interview.json` (filled_ratio / five_axes_complete / unresolved / needs_excavation / abstract_answers)

**完了条件**: 5 軸すべて非空 (`five_axes_complete=true`) + `scripts/check-five-axes-coverage.py` PASS。

## Key Rules

1. **5 軸シート充足のみ**: 深掘り (excavation) / 仮説検証 / 要約 は行わない。それぞれ Phase 5 / 2 / 8 の責務。
2. **AskUserQuestion 1 問ずつ**: 並列質問禁止。最大 3 択推奨、自由入力許可。
3. **vocabulary_tier 固定**: profile.json の tier をセッション中変更しない。
4. **抽象回答検出時はフラグのみ**: `references/abstract-answer-patterns.md` のパターンに合致したら needs_excavation=true にして次へ進む。
5. **5 軸優先順位固定**: 出力先 → 情報源 → 共有相手 → 真の課題 → ナレッジ資産。

## Steps

### Step 1: profile.json 読込と vocabulary_tier 固定

```
profile = read("output/<hint>/profile.json")
tier = profile["vocabulary_tier"]   # beginner|intermediate|expert
```

### Step 2: sheet.md ロードと未回答抽出

`sheet.md` を読み、空欄および `[?]` マーカーを 5 軸別に走査し未回答リストを作成する。

### Step 3: 5 軸優先順位で質問ループ

各軸につき:
1. `references/question-bank-pointer.md` 経由で旧 aggregator references の質問雛形を引く
2. tier に合わせ言い換える (beginner なら平易語)
3. AskUserQuestion で 1 問実行
4. 回答を sheet.md に反映 (Edit)
5. 抽象回答パターン検出 → `abstract_answers` に追記 + `needs_excavation=true`

### Step 4: interview.json 書き出し

```json
{
  "filled_ratio": 0.85,
  "five_axes_complete": true,
  "unresolved": [],
  "needs_excavation": true,
  "abstract_answers": ["真の課題が抽象的"]
}
```

### Step 5: 検証

```bash
python3 plugins/skill-intake/skills/run-intake-interview/scripts/validate-interview-json.py output/<hint>/interview.json
python3 plugins/skill-intake/skills/run-intake-interview/scripts/check-five-axes-coverage.py output/<hint>/sheet.md
```
両者 PASS で完了。

## Gotchas

1. **深掘りに踏み込まない**: 「なぜ?」を 3 回以上重ねたら excavator の領域。本 phase は 1 問で次軸へ進む。
2. **抽象語の最終確定禁止**: 「効率化」「最適化」をそのまま記録しない。needs_excavation=true で Phase 5 に委ねる。
3. **vocabulary_tier 変更禁止**: セッション中の tier 変更は混乱の原因。Phase 3 で固定した値を尊重する。

## Additional Resources

- `references/five-axes-priority.md` — 5 軸の処理順序とスキップ条件
- `references/abstract-answer-patterns.md` — needs_excavation を立てる基準
- `references/question-bank-pointer.md` — 旧 aggregator references/question-bank.md への参照ガイド
- `scripts/validate-interview-json.py`, `scripts/check-five-axes-coverage.py` — 出力検証
