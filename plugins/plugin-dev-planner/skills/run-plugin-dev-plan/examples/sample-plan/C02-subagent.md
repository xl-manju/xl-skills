---
id: C02
component_kind: sub-agent
name: notion-sync-verifier
description: 同期計画を独立 context で再検査し冪等性違反/重複 upsert を検出したいときに使う
tools: [Read, Bash]
independent_context: true
responsibility_anchor: prompts/R-verify.md
prompt_layer: 7layer
depends_on: [C01]
quality_gates:
  p0_lint: [validate-frontmatter, lint-skill-description, lint-agent-prompt-section]
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
  kind_pass: content-review-verdict+verdict
---

# C02: notion-sync-verifier (sub-agent)

## 目的
C01 の同期計画 (upsert plan) を proposer≠approver の原則で独立 context 再検査し、冪等性違反・重複 upsert・必須キー欠落を承認前に検出する。

## 成果物
- `agents/notion-sync-verifier.md` (最小権限 tools・independent_context・responsibility anchor=prompts/R-verify.md)
- 親 skill build 内 `run-build-skill --with-subagent` で生成される

## 完了条件
- `validate-frontmatter` / `lint-skill-description` / `lint-agent-prompt-section` exit0
- 検証結果が verdict 形式で返り、誤検出/見逃しを機能テストで抑止
