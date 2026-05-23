---
# Command Skeleton (kind: command)
#
# CapabilityManifest schema: definitions/kindCommand
# 用途: SlashCommand (commands/*.md) frontmatter。
# 規約: command は薄いラッパ。実体ロジックは entrypoint で指す Skill に置く。
# 書式は install-bundle.md 等の既存 command に準拠。
#
# TODO: build-skill が以下プレースホルダを置換する
#   {{CAPABILITY_NAME}}    command 名 (kebab-case, slash 後の identifier)
#   {{OWNER}}              governance 担当
#   {{ARGUMENT_HINT}}      /{{name}} <hint> の <hint>
#   {{ALLOWED_TOOLS_JSON}} ["Read", "Bash(git *)", ...]
#   {{ENTRYPOINT_SKILL}}   実体ロジックを持つ Skill name
---
name: {{CAPABILITY_NAME}}
description: {{TRIGGERS}}
kind: command
version: 0.1.0
owner: {{OWNER}}
since: {{DATE}}
argument-hint: {{ARGUMENT_HINT}}
allowed-tools: {{ALLOWED_TOOLS_JSON}}
entrypoint: {{ENTRYPOINT_SKILL}}
contract:
  intent: {{COMMAND_INTENT}}
  interface:
    args: {{ARGS_SCHEMA}}
    delegates_to: {{ENTRYPOINT_SKILL}}
  invariant:
    - command 自体にビジネスロジックを書かない (entrypoint へ委譲)
    - allowed-tools を最小集合に保つ
---

# /{{CAPABILITY_NAME}}

## 振る舞い
本コマンドは `{{ENTRYPOINT_SKILL}}` を起動する薄いラッパである。
{{BEHAVIOR_SUMMARY}}

## 引数
- `{{ARGUMENT_HINT}}`: {{ARG_DESCRIPTION}}
- 省略時: {{ARG_DEFAULT_BEHAVIOR}}

## 実行フロー
1. 引数 `{{ARGUMENT_HINT}}` を parse する
2. `{{ENTRYPOINT_SKILL}}` に payload を渡して起動する
3. 結果を user に提示する

## 失敗時
- 引数 parse error: usage を表示し exit
- entrypoint skill が存在しない: 設定ミスを通知
- {{ADDITIONAL_FAILURE_CASE}}

## 注意
- 本 command は副作用を伴う可能性がある。`permissions.deny` で破壊的操作を静的に禁止すること
- allowed-tools に列挙していないツールは entrypoint からも呼べない
- {{ADDITIONAL_NOTE}}
