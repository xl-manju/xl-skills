---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに起動する。
user-invocable: false
context: fork
agent: general-purpose
allowed-tools: [Read, Write, Edit]
pair: {{evaluator}}
kind: {{kind}}
role_suffix: generator
owner: {{owner}}
since: {{date}}
---

# {{name}}

## Purpose & Output Contract
{{output_contract}}

## Boundary
{{boundary}}

## Key Rules
{{key_constraints}}

## Steps
### Step 1
TODO

## Gotchas
- TODO

## Additional Resources
- `templates/`
{{additional_resources}}
