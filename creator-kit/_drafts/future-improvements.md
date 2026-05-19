# 将来課題

elegant-review (2026-05-19) で抽出された、今回スコープ外の将来改善候補。

| ID | 内容 | 起源 | 優先度 |
|---|---|---|---|
| FI-001 | `run-skill-elicit` の Onboarding/Expert 切替を機械判定化（現状 LLM 任意）。`elicit-wizard.py` 案 (Phase 2-B) | フェーズ2-B O8 | 低 |
| FI-002 | `aggregate-violation-rate.py` を実装し、`eval-log/skill-build-trace.jsonl` から rubric 項目別の違反率時系列を CSV 出力 | フェーズ2-C O4/O6 + 23章 | 中 |
| FI-003 | `lint-path-canonical.py` の正式運用（変数化ポリシー違反のCI検出） | F6 CONVENTIONS §9.2 | 中 |
| FI-004 | atomic combinator の自動適用エンジン（`apply-combinators.py`）。現状は patch ファイルを手動 / scripts 経由で適用 | F3 | 中 |
| FI-005 | `run-skill-rename` の改名自動化（現状は手動 runbook + CHANGELOG） | 23章 第6条 | 低 |
