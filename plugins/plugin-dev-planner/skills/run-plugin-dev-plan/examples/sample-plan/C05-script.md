---
id: C05
component_kind: script
script_name: validate-sync-payload.py
purpose: Notion へ送る同期ペイロードの schema/必須キーを送信前に検証する決定論ゲート
inputs: argv(--payload FILE)
outputs: stdout(OK)/stderr(violation)
exit_codes: 0/1/2
network: false
write_scope: none
stdlib_only: true
tests_min: 80
depends_on: []
quality_gates:
  p0_lint: [lint-script-frontmatter]
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
  kind_pass: content-review-verdict+coverage
---

# C05: validate-sync-payload.py (script)

## 目的
Notion 同期ペイロードが schema と必須キー (task_id/title/status) を満たすことを送信前に検証し、不正ペイロードの送信を fail-closed で防ぐ。

## 成果物
- `scripts/validate-sync-payload.py` (Python 標準ライブラリのみ・`/// script` メタ携帯)
- `tests/test_validate_sync_payload.py` (行カバレッジ ≥80%)

## 完了条件
- `lint-script-frontmatter` exit0、`python3 -m pytest tests/` 全 PASS かつカバレッジ ≥80%
- 正例ペイロードで exit0 / 必須キー欠落で exit1 / usage error で exit2 を機能テストで固定
