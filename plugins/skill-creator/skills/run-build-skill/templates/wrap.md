---
name: {{name}}
description: {{trigger1}}とき、{{trigger2}}ときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Bash(python3 *), Agent]
kind: wrap
base: {{base_skill}}
owner: {{owner}}
since: {{date}}
# doc/21 source-traceability
source: {{source_url_or_path}}
source-tier: {{source_tier | default("internal") }}
last-audited: {{last_audited_date}}
audit-trigger: {{audit_trigger | default("quarterly") }}
hierarchy_level: {{hierarchy_level | default("L1") }}   # wrap は通常 L1（外部 CLI 連携）
rubric_refs: {{rubric_refs | default([]) }}            # ref-pr-conventions 等のラップ対象規約
# permissions: 副作用ありスキルは settings.json の permissions.deny に明示禁止を書くこと（設計書04章）
# PreToolUse hook: 文脈次第の危険検査を hook で追加（二段防御）。例: plugins/skill-governance-config/config/claude-settings-hooks.json.example 参照
---

# {{name}}

## 目的と出力契約
{{output_contract}}

## 境界
{{boundary}}

## 主要ルール
1. 外部CLIを直接許可せず、Python stdlib adapter (`scripts/*.py`) 経由で入力検証・dry-run・ログ記録を行う。
{{key_constraints}}

## ゴールシーク実行
> 固定手順は書かない。毎周「ゴール・目的/背景・チェックリスト」を読み、その時点で最適な手順を AI が生成・実行する。詳細は run-build-skill `references/goal-seek-paradigm.md`。

### ゴール (Goal)
{{goal}}

### 目的・背景 (Why)
{{purpose_background}}

### 完了チェックリスト (Checklist)
{{generated_checklist}}

### ゴールシークループ
1. 未達 `[ ]` を特定 → 2. 手順を都度生成（固定化禁止）→ 3. 実行 → 4. チェックリスト再評価し `[x]` 更新 → 全 `[x]` まで反復。規定周回で未達なら open_issues に差し戻す。

## 検証
{{generated_checks}}

## 注意点
{{generated_gotchas}}

## 変数化契約
{{variable_contract}}

## 追加リソース
- TODO
{{additional_resources}}

## セキュリティと権限
本Skillは外部ツールをラップし副作用を伴う。外部CLIを直接 `allowed-tools` に広げず、Python stdlib の薄い adapter (`scripts/*.py`) で入力検証・dry-run・ログ記録を行ってから必要最小の実行へ進む。設計書04章の二段防御原則に従い、(1) `settings.json` の `permissions.deny` に禁止コマンド・パスを静的に列挙し、(2) `PreToolUse` hook で文脈依存の危険検査（破壊的引数・対象パス・分岐条件）を動的に行うこと。
