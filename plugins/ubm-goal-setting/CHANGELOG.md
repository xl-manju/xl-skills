# Changelog

## Unreleased - 2026-07-05

elegant-review (harness-creator 仕様準拠監査) による改善 (version 0.1.0 据置・dev 未リリース):

- F1: plugin-composition.yaml の責務プロンプト tier を schema enum 非含の `supporting` から `ref` へ是正 (C08-C12)。
- F2: run-ubm-knowledge-sync の劣化重複 `prompts/R1-knowledge-extract.md` を削除。抽出責務の 7層正本は agents/knowledge-extractor.md が単独所有し completeness_exempt 宣言と実体を一致化。
- F3: references/package-contract.json の pkg_checks に PKG-009〜015 を実走 ground truth で追記し false-green を解消。
- F4: 両 SKILL.md に knowledge_loop 記述子 (pattern=router-registry) を追加し自己記述を補完。
- F5: 両 workflow-manifest.json の宙吊り `gate_order` (G1/G2/G3 は phase gate に非存在) を削除。
- F6: router 非参照かつ entries=0 の空 tombstone 7 件 (principles/consultation/phase-advice/action-guides/mindset/case-studies/principles-business.json) を掃除。

## 0.1.0 - 2026-07-04

- Ported UBM goal-setting and review dialogue into one plugin with two run skills.
- Added UBM knowledge sync with registry-based MD5 detection and six-category extraction guidance.
- Added 10 agent prompts, 2 slash commands, 3 stdlib Python scripts, and the vault write-path guard hook.
- Seeded L1 curated knowledge JSON, shared schema/router, registry, and empty sync log.
- Added pytest coverage for deterministic scripts and write-path guard behavior.
