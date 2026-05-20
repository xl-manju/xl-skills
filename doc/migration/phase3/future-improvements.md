# 将来改善 backlog

Phase 2 carry-over から移管。削除対象ではなく、Phase 3 以降の改善候補として保持する。

| ID | 内容 | 起源 | 優先度 | 取扱い |
|---|---|---|---|---|
| FI-001 | `run-skill-elicit` の Onboarding/Expert 切替を機械判定化。`elicit-wizard.py` 案 | フェーズ2-B O8 | 低 | backlog |
| FI-002 | `aggregate-violation-rate.py` を実装し、`eval-log/skill-build-trace.jsonl` から rubric 項目別の違反率時系列を CSV 出力 | フェーズ2-C O4/O6 + 23章 | 中 | backlog |
| FI-003 | `lint-path-canonical.py` の正式運用。変数化ポリシー違反のCI検出 | F6 CONVENTIONS §9.2 | 中 | backlog |
| FI-004 | atomic combinator の自動適用エンジン (`plugins/skill-creator/skills/run-build-skill/scripts/apply-combinators.py`) を実装済み。kind-specific → optional flag の順で自動合成 | F3 | 中 | done |
| FI-005 | `run-skill-rename` の改名自動化。現状は手動 runbook + CHANGELOG | 23章 第6条 | 低 | backlog |
