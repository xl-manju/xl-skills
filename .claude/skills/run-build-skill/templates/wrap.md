---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Bash({{tool}} *)]
kind: wrap
base: {{base_skill}}
owner: {{owner}}
since: {{date}}
# permissions: 副作用ありスキルは settings.json の permissions.deny に明示禁止を書くこと（設計書04章）
# PreToolUse hook: 文脈次第の危険検査を hook で追加（二段防御）。例: creator-kit/config/claude-settings-hooks.json.example 参照
---

# {{name}}

## Purpose & Output Contract
{{output_contract}}

## Boundary
{{boundary}}

## Key Rules
1. allowed-tools は glob 制限。
{{key_constraints}}

## Steps
### Step 1
TODO

## Gotchas
- TODO

## Additional Resources
- TODO
{{additional_resources}}

## Security & Permissions
本Skillは外部ツールをラップし副作用を伴う。設計書04章の二段防御原則に従い、(1) `settings.json` の `permissions.deny` に禁止コマンド・パスを静的に列挙し、(2) `PreToolUse` hook で文脈依存の危険検査（破壊的引数・対象パス・分岐条件）を動的に行うこと。`allowed-tools` の glob 制限だけでは不十分である。例設定は `creator-kit/config/claude-settings-hooks.json.example` を参照。
