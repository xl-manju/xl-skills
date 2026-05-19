---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに起動する。
user-invocable: false
context: fork
agent: general-purpose
allowed-tools: [Read, Grep, Bash(python3 *)]
pair: {{generator}}
kind: {{kind}}
role_suffix: evaluator
owner: {{owner}}
since: {{date}}
rubric_refs:
  - {{upstream-rubric}}
  - references/rubric.json
merge_strategy: deep-merge
conflict_policy: most-specific-wins
---

# {{name}}

## Purpose & Output Contract
{{output_contract}}

## Boundary
{{boundary}}

## Key Rules
1. Goodhart対策: 被採点物を改変しない。
{{key_constraints}}

## Steps
### Step 1
rubric.json ロード → findings 収集 → score算出 → JSON出力。

## Gotchas
- TODO

## Additional Resources
- `references/rubric.json`
- `scripts/render-findings-score.py`
{{additional_resources}}
