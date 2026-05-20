#!/usr/bin/env bash
# drift-check.sh
# 用途: per-plugin 投入後、および Phase 全体の最終確認に使用する drift 検証。
# 凍結 CLI (scripts/build-claude-symlinks.py / build-claude-settings.py) の
# `--check --json` 出力に対して invariant を検査する。
set -euo pipefail

out_dir="${1:?usage: drift-check.sh <eval-log-output-dir>}"
mkdir -p "$out_dir"

python3 scripts/build-claude-symlinks.py --check --json > "$out_dir/drift-symlink.json"
python3 scripts/build-claude-settings.py --check --json > "$out_dir/drift-settings.json"

# symlink drift: conflict == 0 かつ noop 以外の plan が無い
jq -e '.summary.conflict == 0 and ([.plan[] | select(.action != "noop")] | length == 0)' \
  "$out_dir/drift-symlink.json" > /dev/null

# settings drift: conflicts なし かつ invariant 検査が 12 件以上
jq -e '(.conflicts | length) == 0 and (.invariants_checked | length) >= 12' \
  "$out_dir/drift-settings.json" > /dev/null

# plugins/ 配下 worktree の drift も検査 (partition-plan 側の取りこぼし防止)
if [ -n "$(git status --porcelain plugins/ 2>/dev/null || true)" ]; then
  echo "[drift-check][ERROR] uncommitted change under plugins/" >&2
  git status --porcelain plugins/ >&2
  exit 2
fi

echo "drift OK"
