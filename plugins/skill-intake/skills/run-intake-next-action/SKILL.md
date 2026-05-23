---
name: run-intake-next-action
description: skill-creator への引き渡しモードを判定したいとき、summary.json から A/B/C/D/E のいずれかを決定論的に確定したいときに使う。
allowed-tools:
  - Read
  - Write
  - Bash
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

# run-intake-next-action

## Purpose & Output Contract

Phase 9 担当。summary.json / purpose.json / options.json / kickoff.json を基に、`run-skill-create` への引き渡しモード (A/B/C/D/E) を **決定論的に**判定する。Phase 1 の暫定 pattern と異なる場合のみユーザー確認を取る。

**入力**: summary.json, purpose.json, options.json, kickoff.json
**出力**: `output/<hint>/next-action.json`

```json
{
  "mode": "A|B|C|D|E",
  "reason": "...",
  "multi_skill_suspicion": false,
  "split_candidates": [{"name": "...", "responsibility": "..."}],
  "skill_creator_handoff_phase": "Phase 1 (kickoff)"
}
```

**完了条件**: mode が確定 + reason に判定根拠 + (Phase 1 と異なる場合) ユーザー追認。

## Key Rules

1. **決定論判定優先**: ルールは `references/pattern-recognition-rules-pointer.md` (旧 aggregator) に従い、`scripts/decide-mode.py` で機械判定する。
2. **LLM 判断は補助のみ**: 同点時のタイブレークでのみ LLM が選ぶ。
3. **Phase 1 との不一致は要追認**: kickoff.json.pattern と異なる場合は AskUserQuestion で確認。

## Steps

### Step 1: 入力読込

4 つの JSON を Read。

### Step 2: 機械判定

```bash
python3 plugins/skill-intake/skills/run-intake-next-action/scripts/decide-mode.py \
  --kickoff output/<hint>/kickoff.json \
  --purpose output/<hint>/purpose.json \
  --options output/<hint>/options.json \
  --summary output/<hint>/summary.json \
  --out output/<hint>/next-action.json
```

### Step 3: Phase 1 との突合

decide-mode.py の出力 mode と kickoff.json.pattern を比較。一致なら自動承認、不一致なら AskUserQuestion で追認。

### Step 4: multi_skill_suspicion 処理

mode=D の場合、split_candidates を提示し分割合意を取る。

## Gotchas

1. **D (マルチスキル分離疑い) の取り扱い**: split_candidates が空のままなら mode=E に格下げする。
2. **E (判定不能) は次工程で再判定**: skill_creator_handoff_phase に Phase 1 を指定し再ヒアリング扱い。

## Additional Resources

- `references/pattern-recognition-rules-pointer.md` — 判定ルールの旧 aggregator 参照ガイド
- `references/mode-catalog.md` — A/B/C/D/E の意味と判定基準サマリ
- `scripts/decide-mode.py` — 決定論判定ロジック
