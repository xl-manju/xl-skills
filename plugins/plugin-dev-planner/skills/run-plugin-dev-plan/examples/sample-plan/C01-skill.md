---
id: C01
component_kind: skill
skill_name: run-notion-task-sync
prefix: run
kind: run
hierarchy_level: L1
trigger_conditions: [Notionにタスク同期, タスク同期計画, sync-tasks]
goal: タスク台帳が Notion DB へ冪等同期され差分0で完了した状態
purpose_background: 手動転記の漏れ/重複を排除し台帳を単一正本にするため
checklist: [差分抽出, 冪等upsert, 同期検証]
output_contract: 同期レポート(追加/更新/skip 件数 + 失敗一覧)
boundary: 入力=タスク台帳/出力=Notion upsert。物理削除はしない
output_language: ja
placement_candidates: [Skill]
mass_production_profile: strict
responsibilities: [R1-elicit, R2-plan, R3-sync]
cli_tools: []
mcp_tools: [notion]
external_systems: [Notion API]
deterministic_checks: [validate-sync-payload.py]
needs_independent_context: true
needs_lifecycle_enforcement: true
feedback_contract:
  criteria:
    - id: IN1
      loop_scope: inner
      text: validate-sync-payload で同期ペイロードを送信前検証し差分抽出の必須キー欠落が 0 件
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 同一台帳を二回同期し 2 回目の追加/更新が 0 件=冪等同期で差分0 になることを検証テストが確認する
      verify_by: test
goal_seek:
  engine: inline
  fork: subagent
  max_loops: 5
prompt_layer: 7layer
combinators: [with-goal-seek, with-feedback-contract]
depends_on: [C05]
quality_gates:
  p0_lint: [lint-skill-name, lint-skill-description, lint-skill-tree, validate-frontmatter, lint-dependency-direction, lint-skill-dep-step7, lint-forbidden-deps, lint-manifest-contents]
  build_trace: required
  elegant_review:
    conditions: [C1, C2, C3, C4]
    all_pass: true
  content_review:
    verdict: PASS
    sha_match: true
  evaluator:
    threshold: 80
    high_max: 0
harness_coverage:
  min: 80
  kind_pass: loop=criteria-test+content-review-verdict
---

# C01: run-notion-task-sync (skill / kind=run)

## 目的
タスク台帳の差分を抽出し Notion DB へ冪等 upsert する端から端までの orchestrator。検証用ペイロードは C05 スクリプトで送信前検証する。

## 成果物
- `skills/run-notion-task-sync/` 一式 (SKILL.md + prompts/R1-R3 + references/ + scripts/)
- `feedback_contract` criteria を frontmatter と build-trace の両方に固定
- 後段 `run-skill-create` へ無加工で投入できる skill-brief 主要 14 フィールド相当を携帯

## 完了条件
- **purpose-acceptance**: feedback_contract criteria (goal「冪等同期で差分0」由来) が build 後の harness criteria-test で検証され、二回同期の冪等性 (2 回目 0 件) が PASS する
- P0 lint 8 本 exit0・build-trace 章 coverage 全 PASS・content-review verdict=PASS(sha 一致)
- harness-coverage ≥80% (criteria 検証テスト inner/outer + content-review verdict + scripts 機能テスト)
- 新規/30 行超のため elegant-review C1-C4 全 PASS
