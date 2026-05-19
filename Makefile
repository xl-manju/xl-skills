# Makefile — xl-skills ローカル開発補助
# 二重正本 drift 防止: creator-kit/skills/ 変更後に sync ターゲットを実行すること。
# CI では --check gate (creator-kit-ci.yml) が走るため二重防護となる。

.PHONY: sync sync-check lint test help

## sync: creator-kit/skills/ を .claude/skills/ に同期する（--apply）
sync:
	bash scripts/sync-skills-to-claude.sh --apply

## sync-check: 同期差分がないことを確認する（CI gate 相当、--check）
sync-check:
	bash scripts/sync-skills-to-claude.sh --check

## lint: スキル lint 一式を実行する
lint:
	python3 scripts/lint-skill-name.py
	python3 scripts/lint-skill-description.py
	python3 scripts/validate-frontmatter.py

## test: gate-phase0 + lint + sync-check を順に実行する
test: sync-check lint
	python3 scripts/gate-phase0.py

## help: このメッセージを表示する
help:
	@grep -E '^## ' Makefile | sed 's/## /  /'
