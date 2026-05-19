---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに起動する。
disable-model-invocation: false
user-invocable: true
context: fork
agent: {{subagent}}
delegate_agent: {{delegate_agent}}
allowed-tools: [Read, Write]
kind: delegate
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
1. 入出力契約のみ定義、ロジックは subagent 側。
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
本Skillは subagent へ委譲するが、委譲先の権限も親の `permissions` で制御される。設計書04章の二段防御原則に従い、(1) `settings.json` の `permissions.deny` に禁止コマンド・パスを静的に列挙し、(2) `PreToolUse` hook で文脈依存の危険検査を動的に行うこと。委譲先が信頼境界外なら deny を厳しく、hook で入出力を検証する。例設定は `creator-kit/config/claude-settings-hooks.json.example` を参照。
