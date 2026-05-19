#!/usr/bin/env bash
# sync-skills-to-claude.sh — creator-kit/skills/ を正本として .claude/skills/ に同期する。
#
# 設計書10章§7.4 二段防御の前提として、creator-kit/skills/ と .claude/skills/ が
# 機械的に同期されていることを保証する。CI ではこのスクリプトを実行した直後の
# git diff がゼロであることを gate にする (creator-kit-ci.yml)。
#
# Usage:
#   bash scripts/sync-skills-to-claude.sh [--check|--apply]
#     --check  : 差分があれば exit 1 (CI gate 用)
#     --apply  : .claude/skills/ を creator-kit/skills/ に合わせて更新 (default)

set -euo pipefail

MODE="${1:---apply}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/creator-kit/skills"
DST="$ROOT/.claude/skills"

if [[ ! -d "$SRC" ]]; then
  echo "ERROR: $SRC not found" >&2
  exit 1
fi

mkdir -p "$DST"

# manifest.json から正規の skill 一覧を読む (stdlib python のみ)
SKILLS=$(python3 -c "
import json, pathlib
m = json.loads(pathlib.Path('$ROOT/creator-kit/manifest.json').read_text())
print('\n'.join(s['name'] for s in m['skills']))
")

case "$MODE" in
  --check)
    DIFF_FOUND=0
    while IFS= read -r skill; do
      [[ -z "$skill" ]] && continue
      if ! diff -rq "$SRC/$skill" "$DST/$skill" >/dev/null 2>&1; then
        echo "DRIFT: $skill (creator-kit/skills/ vs .claude/skills/)" >&2
        DIFF_FOUND=1
      fi
    done <<< "$SKILLS"
    # manifest外のskillが .claude/skills/ にあれば warn
    for d in "$DST"/*/; do
      name=$(basename "$d")
      if ! grep -q "\"name\": \"$name\"" "$ROOT/creator-kit/manifest.json"; then
        echo "ORPHAN: $name in .claude/skills/ but not in manifest" >&2
        DIFF_FOUND=1
      fi
    done
    exit $DIFF_FOUND
    ;;
  --apply)
    while IFS= read -r skill; do
      [[ -z "$skill" ]] && continue
      rm -rf "$DST/$skill"
      cp -R "$SRC/$skill" "$DST/$skill"
      echo "synced: $skill"
    done <<< "$SKILLS"
    # manifest外の skill / 不正ディレクトリを削除
    for d in "$DST"/*/; do
      name=$(basename "$d")
      if ! grep -q "\"name\": \"$name\"" "$ROOT/creator-kit/manifest.json"; then
        rm -rf "$d"
        echo "removed orphan: $name"
      fi
    done
    ;;
  *)
    echo "Usage: $0 [--check|--apply]" >&2
    exit 2
    ;;
esac
