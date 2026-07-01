# CHANGELOG

本ファイルは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に準拠し、`skill-intake` plugin の変更履歴を記録する。skill-creator 設計書 33 章 `change-governance` に紐付き、SemVer に従う。

## [Unreleased] - 2026-07-01

### Added

- **plugin-composition.yaml**: skill-creator の CapabilityManifest 仕様 (kindPluginComposition) に準拠した composition manifest を新設。公開 capabilities(10 skills + 4 agents + 4 commands + 8 hook 配線)・11 phase の依存 DAG・contract invariant・governance を宣言し、`.claude-plugin/plugin.json` の entry_points / hooks と1対1対応させた。
- **ROADMAP.md**: 短期 / 中期 / 長期のロードマップを新設し、governance.roadmap の参照先を確立した。
- **EVALS.json**: 公開 capability の evaluation baseline を記録する eval_sink を新設した。

### Changed

- skill-creator ROADMAP 中期目標「全 plugin での plugin-composition.yaml 採用」に追従し、skill-intake を CapabilityBundle として宣言可能にした。

### Notes

- 命名規約・CapabilityManifest frontmatter・PKG-002〜008 パッケージ検査はいずれも既存で PASS 済み。本リリースは統治レイヤ(composition manifest + changelog/roadmap/evals)の追加により skill-creator 仕様へのフル準拠を達成する。
