# Makefile — xl-skills ローカル開発補助
# 二重正本 drift 防止: creator-kit/skills/ 変更後に sync ターゲットを実行すること。
# CI では --check gate (creator-kit-ci.yml) が走るため二重防護となる。

.PHONY: sync sync-check lint plugin-package-check contract-intake vendored-ssot test help

## sync: creator-kit/skills/ を .claude/skills/ に同期する（--apply）
sync:
	bash scripts/sync-skills-to-claude.sh --apply

## sync-check: 同期差分がないことを確認する（CI gate 相当、--check）
sync-check:
	bash scripts/sync-skills-to-claude.sh --check

## lint: スキル lint 一式 + skill-intake contract test + vendored SSOT 検証を実行する
lint: contract-intake vendored-ssot
	python3 scripts/lint-skill-name.py --skills-dir plugins/skill-creator/skills
	python3 scripts/lint-skill-description.py --skills-dir plugins/skill-creator/skills
	python3 scripts/validate-frontmatter.py --skills-dir plugins/skill-creator/skills

## vendored-ssot: skill-intake 同梱 SSOT (notion_config.py) が skill-creator 正本と byte 一致か検証
vendored-ssot:
	python3 scripts/lint-intake-vendored-ssot.py

## contract-intake: skill-intake の enum SSOT / 軸分離 / 二重定義検出 contract test
contract-intake:
	python3 scripts/contract-intake-enum-ssot.py

## plugin-package-check: plugin package completeness check を実行する
plugin-package-check:
	python3 scripts/validate-plugin-package.py

## test: sync-check + lint (contract-intake 含む) + plugin-package-check + gate-phase0 を順に実行する
test: sync-check lint plugin-package-check
	python3 scripts/gate-phase0.py

## help: このメッセージを表示する
help:
	@grep -E '^## ' Makefile | sed 's/## /  /'
