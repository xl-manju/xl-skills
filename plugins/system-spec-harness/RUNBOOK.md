# system-spec-harness Runbook

## Purpose
システム構築 (Web/モバイル/タブレット/デスクトップ横断) の仕様情報を往復ヒアリングで漏れなく収集し、章立て複数 Markdown + index の仕様書ドキュメントセットへまとめるハーネスの運用手順。

## Entry Points
- `/spec-hearing-start [--resume] [--status]` — 往復ヒアリングを起動 (C09→C01)。`--status` は収集マトリクス充足状況のみ表示。
- `/spec-compile [--out-dir DIR]` — 収集済み仕様を章立て仕様書へコンパイルし (C10→C03)、完了後に完成度評価 (C05) を自動連鎖。
- Skill: `run-system-spec-elicit` / `run-system-spec-doc-fetch` / `run-system-spec-compile` / `ref-system-design-knowledge` / `assign-system-spec-completeness-evaluator`。

## Environment
- Python 標準ライブラリのみ (.sh/.js 新規禁止・scripts 内 yaml import 禁止)。
- スクリプト起動は repo-root cwd 前提、skill 資産は self-relative 参照。
- 中間成果物: `spec-state.json` (収集マトリクス+質疑ログ) / `fetched-references.json` (出典記録) / `system-spec/*.md` + `index.md` (仕様書ドキュメントセット)。
- 最新公式ドキュメント取得は WebSearch/WebFetch のみ (MCP 連携は将来拡張・GAP-MCP-DOCFETCH)。

## Write Protection
- `spec-state.json` の確定状態は C01/C03 所有の単一 transition writer のみが変更する。
- 確定済み章 (`system-spec/` 章 frontmatter `status: confirmed`) への Write/Edit/Bash は `hooks/guard-confirmed-chapter-overwrite.py` (PreToolUse・fail-closed exit2) が補助防御で遮断する。
- 確定セルの再オープンは C01 R4-reopen 経由のみ。再オープン状態のセル対応章は hook が通す。

## Verification
- 収集マトリクス網羅性 (C7): `python3 scripts/validate-coverage-matrix.py --matrix spec-state.json [--require-complete]`。
- 出典記録 (C5): `python3 scripts/validate-source-citation.py --targets <targets.json> --references fetched-references.json`。
- 独立監査: `system-spec-hearing-auditor` (聞き漏れ/誘導/早期停止) / `system-spec-matrix-auditor` (マトリクス状態) / `system-spec-doc-freshness-auditor` (公式サイト再照合)。
- 完成度評価: `assign-system-spec-completeness-evaluator` が3観点 (網羅性/設計知識反映/出典) で PASS/FAIL 判定。
- テスト: `python3 -m pytest plugins/system-spec-harness/tests -q`。

## Acceptance Evidence
- 受入観点 (C1-C12) の正本は `plugin-plans/system-spec-harness/phase-07-acceptance-criteria.md` と `EVALS.json`。
- 6周超サンプル対話で5周目に状態保存+resume が働くこと (C3)。
- 生成仕様書がカテゴリ別収集状態 (未着手/収集中/確定/対象外+理由) を各章に明示すること (C1)。

## Recovery
- ヒアリング中断: `/spec-hearing-start --resume` で `hearing_progress` から再開。
- マトリクス不整合: validate-coverage-matrix.py の VIOLATION を解消してから再コンパイル。
- 誤った確定: C01 R4-reopen で根拠付き再オープンしてから修正 (直接編集は hook が拒否)。
- 改善要望: `/run-skill-feedback system-spec-harness` で投入。
