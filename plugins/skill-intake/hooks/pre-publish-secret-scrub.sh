#!/usr/bin/env bash
# pre-publish-secret-scrub.sh
#
# Notion 公開前に intake 成果物にトークン/シークレットが混入していないかを走査する。
# 検知パターン:
#   - Notion PAT       : ntn_[A-Za-z0-9]{40,}
#   - Notion Integration : secret_[A-Za-z0-9]{40,}
#   - 汎用 Bearer       : Bearer\s+[A-Za-z0-9_\-\.]{20,}
#   - .env 形式         : (NOTION|API|TOKEN|SECRET)_[A-Z_]*=[A-Za-z0-9_\-]+
#
# 配線: ~/.claude/settings.json または .claude/settings.json に以下を追加:
# {
#   "hooks": {
#     "PreToolUse": [
#       {
#         "matcher": "Bash",
#         "hooks": [
#           {
#             "type": "command",
#             "command": "$CLAUDE_PLUGIN_ROOT/plugins/skill-intake/hooks/pre-publish-secret-scrub.sh"
#           }
#         ]
#       }
#     ]
#   }
# }
#
# 終了コード:
#   0 = clean (公開許可)
#   2 = secret detected (公開停止 — Claude Code が自動でブロック)
set -euo pipefail

TARGET_DIRS=(
  "output"
)

PATTERNS=(
  'ntn_[A-Za-z0-9]{40,}'
  'secret_[A-Za-z0-9]{40,}'
  'Bearer[[:space:]]+[A-Za-z0-9_\-\.]{20,}'
  '(NOTION|API|TOKEN|SECRET)_[A-Z_]*=[A-Za-z0-9_\-]{16,}'
)

found=0
for dir in "${TARGET_DIRS[@]}"; do
  [[ -d "$dir" ]] || continue
  for pattern in "${PATTERNS[@]}"; do
    if grep -REn --include='*.json' --include='*.md' --include='*.txt' "$pattern" "$dir" 2>/dev/null; then
      echo "FAIL: secret-like pattern detected in $dir matching: $pattern" >&2
      found=1
    fi
  done
done

if [[ $found -ne 0 ]]; then
  cat >&2 <<EOF
[skill-intake] PRE-PUBLISH SECRET SCRUB FAILED.
公開を停止しました。検知された行を修正してから再実行してください。
詳細: plugins/skill-intake/skills/run-skill-intake-aggregator/references/keychain-setup.md
EOF
  exit 2
fi

exit 0
