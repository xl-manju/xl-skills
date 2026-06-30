---
id: C04
component_kind: hook
event: PreToolUse
matcher: Bash
exit_semantics: fail-closed-exit2
settings_wiring: settings.json
fail_closed: true
depends_on: []
quality_gates:
  p0_lint: [validate-frontmatter, lint-script-frontmatter]
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
  kind_pass: content-review-verdict+test
---

# C04: guard-destructive-sync (hook)

## 目的
破壊的同期 (Notion ページ一括削除/上書き) を実行する Bash 呼出を PreToolUse で検知し、ユーザー明示承認が無い限り exit2 で遮断する (保証要件は機械層=hook で担保)。

## 成果物
- `hooks/guard-destructive-sync.py` (PreToolUse・matcher=Bash・fail-closed exit2)
- `settings.json` への hook 配線差分

## 完了条件
- `validate-frontmatter` / `lint-script-frontmatter` exit0
- 破壊的コマンド検知で exit2・通常コマンドで exit0 を機能テストで固定 (fail-open 穴が無い)
