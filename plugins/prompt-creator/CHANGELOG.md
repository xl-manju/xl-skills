# CHANGELOG

本ファイルは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に準拠し、`prompt-creator` plugin の変更履歴を記録する。設計書 33 章 `change-governance` に紐付き、SemVer に従う。

## [Unreleased] - 2026-05-24

### Added
- `plugin-composition.yaml` を新設し、capabilities / dependencies DAG / governance / eval_sinks / observability を skill-creator 仕様 (kindPluginComposition) で宣言。
- 4 SKILL.md (`run-prompt-create` / `run-prompt-elicit` / `run-prompt-creator-7layer` / `assign-prompt-design-evaluator`) に commonCore (`version: 2.1.0`) と `contract { intent, interface, invariant }` を付与。
- `assign-prompt-design-evaluator` に `rubric_refs` (L0 共通 `ref-skill-design-rubric` + L2 固有 `prompt-rubric.json`) を追加し `lint-skill-completeness` の rubric カテゴリを充足。
- `.github/workflows/governance-check.yml` に prompt-creator スコープの lint 5 ステップ (frontmatter / skill-name / skill-description / skill-completeness / dependency-direction[全プラグイン]) を配線。

### Changed
- `plugins/prompt-creator/scripts/*.js` 8 本を `plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/*.py` へ移植 (byte 等価, PEP 723 frontmatter 付与)。
- `agents/prompt-creator-{interview-user,generate-prompt,review-prompt}.md` の `context:` 指定を `isolation:` (skill-creator 仕様の正典キー) に統一。
- `run-prompt-create/scripts/evaluate-create-gates.py` に PEP 723 frontmatter (`# /// script ... # ///`) を追加し `lint-script-frontmatter` を充足。

### Removed
- 旧 `plugins/prompt-creator/scripts/` ディレクトリ (JS 8 本) を削除。

### Pending
- 移行 6 スクリプト (`merge-layers` / `verify-completeness` / `scaffold-prompt` / `generate-sheet` / `convert-format` / `log-usage`) は `lint-script-naming` の許可動詞外。`PENDING_RENAME_PATHS` に登録済み。後続 Change Governance PR で SKILL.md / agent / manifest 参照と同時にリネーム予定。
