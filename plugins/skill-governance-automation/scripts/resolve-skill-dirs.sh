#!/usr/bin/env bash
# resolve-skill-dirs.sh
# ---------------------
# P0-4: run-build-skill Step2 で20行超を占めていたパス解決ロジックを分離。
# SKILL.md からは `source plugins/skill-governance-automation/scripts/resolve-skill-dirs.sh` で呼ぶだけにする。
#
# 確立する変数:
#   SKILL_DIR   - run-build-skill 本体ディレクトリ (scripts/templates/ の親)
#   OUT_BASE    - 出力先基底ディレクトリ (plugins/skill-creator/skills/ or .claude/skills/)
#
# 優先順序:
#   1. 環境変数 CLAUDE_SKILL_DIR / CLAUDE_SKILL_OUT_BASE が設定済みなら使用
#   2. plugins/skill-creator/skills/run-build-skill/ が存在すれば plugin 配置
#   3. .claude/skills/run-build-skill/ が存在すれば .claude 配置
#   4. BASH_SOURCE を使って自スクリプトの親を解決 (fallback)
#
# 使用例:
#   source plugins/skill-governance-automation/scripts/resolve-skill-dirs.sh
#   mkdir -p "$OUT_BASE/$SKILL_NAME"

set -euo pipefail

SKILL_DIR="${CLAUDE_SKILL_DIR:-}"
if [ -z "$SKILL_DIR" ]; then
  if [ -f "plugins/skill-creator/skills/run-build-skill/scripts/render-frontmatter.py" ]; then
    SKILL_DIR="plugins/skill-creator/skills/run-build-skill"
  elif [ -f ".claude/skills/run-build-skill/scripts/render-frontmatter.py" ]; then
    SKILL_DIR=".claude/skills/run-build-skill"
  else
    SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
  fi
fi

OUT_BASE="${CLAUDE_SKILL_OUT_BASE:-}"
if [ -z "$OUT_BASE" ]; then
  case "$SKILL_DIR" in
    plugins/skill-creator/*) OUT_BASE="plugins/skill-creator/skills" ;;
    *)             OUT_BASE=".claude/skills" ;;
  esac
fi

export SKILL_DIR OUT_BASE
