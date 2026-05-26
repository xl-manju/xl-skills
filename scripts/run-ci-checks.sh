#!/usr/bin/env bash
# CI と同等の機械チェックをローカルで一括実行する。
# pre-push hook / 手動実行 (bash scripts/run-ci-checks.sh) の双方から呼ばれる SSOT。
# 内容の良し悪し (LLM 自由度領域) は判定対象外。構造・命名・SSOT・symlink drift のみ。
#
# 失敗したチェックを蓄積して全て表示するため、最初の失敗で抜けず continue する。
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FAILED=()
PASSED=()

run() {
  local label="$1"; shift
  if "$@"; then
    PASSED+=("$label")
  else
    FAILED+=("$label")
  fi
}

# ── 構造・命名・frontmatter ──
run "lint-script-naming"                   python3 scripts/lint-script-naming.py
run "lint-skill-description (skill-creator)" python3 scripts/lint-skill-description.py
run "lint-dependency-direction (skill-creator)" python3 scripts/lint-dependency-direction.py --skills-dir plugins/skill-creator/skills
run "lint-dependency-direction (all)"      python3 scripts/lint-dependency-direction.py --skills-dir plugins
run "lint-external-refs"                   python3 scripts/lint-external-refs.py --skills-dir plugins/skill-creator/skills --allowed-prefix .claude/ --allowed-prefix eval-log/ --allowed-prefix references/ --allowed-prefix plugins/ --allowed-prefix scripts/ --allowed-prefix doc/ --fail-on-external

# ── SSOT / drift ──
run "lint-feedback-protocol --strict"      python3 scripts/lint-feedback-protocol.py --strict
run "check-scripts-drift"                  bash scripts/check-scripts-drift.sh
run "build-claude-symlinks --check"        python3 scripts/build-claude-symlinks.py --check
run "lint-ssot-duplication --strict"       python3 plugins/skill-creator/skills/run-build-skill/scripts/lint-ssot-duplication.py --plugin-dir plugins/skill-creator --strict
run "lint-goal-seek --self-test"           python3 plugins/skill-creator/skills/run-build-skill/scripts/lint-goal-seek.py --self-test
run "lint-goal-seek conformance"           python3 plugins/skill-creator/skills/run-build-skill/scripts/lint-goal-seek.py --skills-dir plugins/skill-creator/skills

# ── completeness / frontmatter (skill-creator + prompt-creator) ──
run "lint-skill-completeness (skill-creator)" python3 plugins/skill-governance-lint/scripts/lint-skill-completeness.py --skills-dir plugins/skill-creator/skills
run "validate-frontmatter --self-test"     python3 plugins/skill-governance-lint/scripts/validate-frontmatter.py --self-test
run "validate-frontmatter (skill-creator)" python3 plugins/skill-governance-lint/scripts/validate-frontmatter.py --skills-dir plugins/skill-creator/skills
run "validate-frontmatter (prompt-creator)" python3 plugins/skill-governance-lint/scripts/validate-frontmatter.py --skills-dir plugins/prompt-creator/skills
run "lint-skill-name (prompt-creator)"     python3 plugins/skill-governance-lint/scripts/lint-skill-name.py --skills-dir plugins/prompt-creator/skills
run "lint-skill-description (prompt-creator)" python3 plugins/skill-governance-lint/scripts/lint-skill-description.py --skills-dir plugins/prompt-creator/skills
run "lint-skill-completeness (prompt-creator)" python3 plugins/skill-governance-lint/scripts/lint-skill-completeness.py --skills-dir plugins/prompt-creator/skills

# ── knowledge loop ──
run "lint-knowledge-loop --self-test"      python3 plugins/skill-creator/skills/run-build-skill/scripts/lint-knowledge-loop.py --self-test
run "lint-knowledge-loop --store-only"     python3 plugins/skill-creator/skills/run-build-skill/scripts/lint-knowledge-loop.py plugins/skill-creator --store-only --strict

# ── manifest sanity (jq) ──
if command -v jq >/dev/null 2>&1; then
  run "marketplace.json plugins>=8" jq -e '.plugins | length >= 8' .claude-plugin/marketplace.json
  for manifest in plugins/*/.claude-plugin/plugin.json; do
    run "manifest:$manifest" jq -e '.name and .version and .description' "$manifest"
  done
else
  echo "[WARN] jq 未インストールにつき manifest 検証 skip"
fi

# ── サマリ ──
echo
echo "========================================"
echo "PASS: ${#PASSED[@]} / FAIL: ${#FAILED[@]}"
echo "========================================"
if (( ${#FAILED[@]} > 0 )); then
  echo "Failed checks:"
  for f in "${FAILED[@]}"; do echo "  - $f"; done
  exit 1
fi
echo "All CI-equivalent checks passed."
exit 0
