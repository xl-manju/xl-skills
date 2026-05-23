---
name: run-intake-finalize
description: intake 全 JSON を統合したいとき、intake.md と intake.json を Jinja2 で render して quality_gate と cross_check を通したいときに使う。
allowed-tools:
  - Read
  - Write
  - Bash
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

# run-intake-finalize

## Purpose & Output Contract

Phase 10 担当。Phase 1-9 で生成された全 JSON / sheet.md / visuals.json を統合し、最終成果物 `intake.md` (人間向け) と `intake.json` (skill-creator 入力) を **決定論的に**生成する。`render-intake-final.py` (Jinja2) と `quality_gate.py` / `cross_check.py` を順に exec する。

**入力**: Phase 1-9 の全成果物 + `intake-final-template.md.tmpl` + `intake-final-schema.json`
**出力**:
- `output/<hint>/intake.md`
- `output/<hint>/intake.json` (validation field を含む)

**完了条件**: render PASS + quality_gate PASS + cross_check PASS。

## Key Rules

1. **LLM は呼ばない**: render は Jinja2、検証は決定論 script のみ。
2. **schema/template の正本**: 旧 aggregator references を参照。Phase C で物理移管予定。
3. **失敗時の戻り先明示**: render fail → 該当 Phase へ、quality_gate fail → 該当軸の Phase へ。

## Steps

### Step 1: context 集約

```bash
python3 plugins/skill-intake/scripts/build-intake-final-context.py \
  --out-dir output/<hint>/ \
  --context-out output/<hint>/intake-final-context.json
```

### Step 2: render

```bash
python3 plugins/skill-intake/scripts/render-intake-final.py \
  --context output/<hint>/intake-final-context.json \
  --template plugins/skill-intake/skills/run-skill-intake-aggregator/references/intake-final-template.md.tmpl \
  --schema   plugins/skill-intake/skills/run-skill-intake-aggregator/references/intake-final-schema.json \
  --md-out   output/<hint>/intake.md \
  --json-out output/<hint>/intake.json
```

### Step 3: quality_gate + cross_check

```bash
python3 plugins/skill-intake/scripts/quality_gate.py output/<hint>/intake.json
python3 plugins/skill-intake/scripts/cross_check.py output/<hint>/intake.json output/<hint>/intake.md
```

両者 PASS で完了。fail 時は `intake.json.validation` に詳細を記録し orchestrator に戻す。

## Gotchas

1. **template / schema は移管前**: 旧 aggregator references パスを直書きしている。Phase C で本 references 配下へ移管後にパス書き換える。
2. **render と quality_gate は単一発火点**: 重複呼び出し禁止。orchestrator は本 Skill を 1 回だけ呼ぶ。

## Additional Resources

- `references/template-pointer.md` — Jinja2 テンプレ / schema の正本パス案内
- `references/validation-flow.md` — render → quality_gate → cross_check の順序と失敗戻り先表
