# CHANGELOG

本ファイルは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に準拠し、`skill-creator` plugin の変更履歴を記録する。設計書 33 章 `change-governance` に紐付き、SemVer に従う。

## [Unreleased] - 2026-05-22

着手中。本 PR 完了後にバージョンを確定する。

### Added

- **Capability 統一抽象**: `Capability` / `CapabilityManifest` / `CapabilityBundle` の三層モデルを導入し、skill/agent/hook/command/prompt/workflow/plugin-composition を単一語彙で表現可能にした。
- **plugin-composition.yaml**: plugin 間の依存・公開 capability・consume 関係を宣言する composition manifest を新設。
- **target_type 7 種対応 rubric**: `skill` / `agent` / `hook` / `command` / `plugin-composition` / `prompt` / `workflow` の 7 種に対し、共通核 + kind 固有 addendum の rubric を提供。
- **governance/feedback hook 配線**: 7 種すべてに対し governance gate と feedback ループの hook を配線。
- **lessons-learned 自動記録**: review/executor 実行ログから lessons を抽出し自動追記する経路を実装。
- **EVALS → rubric 自動 PR 経路**: EVALS 結果から rubric の改訂 PR を自動生成するパイプラインを追加。
- **依存グラフ生成**: capability 間の依存を DAG として出力する仕組みを追加。
- **dogfooding メトリクス**: 自己適用率・rubric 充足率・lessons 反映率を計測する初期メトリクスを導入。

### Changed

- **rubric 構造再編**: 単一 rubric から「共通核 + kind 固有 addendum」構造へ再編し、target_type ごとに必要項目を最小化。
- **validate-build-trace.py 汎化**: skill 専用検証から kind 対応の汎用検証へリファクタし、7 種すべての build trace を検証可能にした。

### Status

着手中。本 PR マージ後に `0.x.0` を確定し本セクションを正式リリースへ昇格する。
