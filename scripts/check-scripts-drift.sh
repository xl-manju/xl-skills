#!/usr/bin/env bash
# check-scripts-drift.sh — root scripts/ と creator-kit/scripts/ の drift 検出。
#
# 設計書09章 P0 deterministic / 10章 Hook command の依存パス不定問題を解消する。
# creator-kit/scripts/ を正本とし、root scripts/ はその展開先 (install.sh で同期)。
# diff があれば CI が block する。
#
# Usage:
#   bash scripts/check-scripts-drift.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/creator-kit/scripts"
DST="$ROOT/scripts"

DRIFT=0
for f in "$SRC"/*.py "$SRC"/*.sh; do
  [[ -f "$f" ]] || continue
  name=$(basename "$f")
  if [[ -f "$DST/$name" ]]; then
    if ! diff -q "$f" "$DST/$name" >/dev/null 2>&1; then
      echo "DRIFT: $name (creator-kit/scripts/ vs scripts/)" >&2
      DRIFT=1
    fi
  fi
done

if [[ $DRIFT -ne 0 ]]; then
  echo "" >&2
  echo "Resolution: creator-kit/scripts/ が正本。同期するには:" >&2
  echo "  bash creator-kit/install.sh --mode copy --force" >&2
  exit 1
fi
exit 0
