#!/usr/bin/env bash
# phase2-03 executable spec: dry-run only frozen contract (phase2-06 will implement real path)
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: deploy-plugin.sh <plugin-name> [--dry-run]
       deploy-plugin.sh --help | -h

Arguments:
  <plugin-name>   Target plugin (must exist in migration-order.json .order[].plugin)

Options:
  --dry-run       Emit the frozen 9-line P-1..P-9 PASS contract and exit 0
  --help, -h      Show this help and exit 0

Exit codes:
  0  success (dry-run all checks PASS, or --help)
  1  verification failure (missing jq, or non-dry-run not yet implemented)
  2  configuration inconsistency (missing args, unknown plugin, missing inputs)
EOF
}

DRY_RUN=0
PLUGIN_NAME=""

for arg in "$@"; do
  case "$arg" in
    --help|-h)
      usage
      exit 0
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    -*)
      echo "deploy-plugin.sh: unknown option: $arg" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ -z "$PLUGIN_NAME" ]]; then
        PLUGIN_NAME="$arg"
      else
        echo "deploy-plugin.sh: unexpected extra argument: $arg" >&2
        usage >&2
        exit 2
      fi
      ;;
  esac
done

if [[ -z "$PLUGIN_NAME" ]]; then
  echo "deploy-plugin.sh: plugin-name is required" >&2
  usage >&2
  exit 2
fi

if [[ "$DRY_RUN" -ne 1 ]]; then
  echo "deploy-plugin.sh: not yet implemented (phase2-06 responsibility)" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "deploy-plugin.sh: jq not installed" >&2
  exit 1
fi

if ! REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "deploy-plugin.sh: not inside a git repository" >&2
  exit 2
fi

MIGRATION_ORDER="$REPO_ROOT/eval-log/task/phase2-03/migration-order.json"
PARTITION_PLAN="$REPO_ROOT/eval-log/task/phase2-02/partition-plan.json"

if [[ ! -f "$MIGRATION_ORDER" ]]; then
  echo "deploy-plugin.sh: migration-order.json not found: $MIGRATION_ORDER" >&2
  exit 2
fi

if ! jq -e --arg p "$PLUGIN_NAME" '.order[] | select(.plugin == $p)' "$MIGRATION_ORDER" >/dev/null 2>&1; then
  echo "deploy-plugin.sh: unknown plugin: $PLUGIN_NAME" >&2
  exit 2
fi

if [[ ! -f "$PARTITION_PLAN" ]]; then
  echo "deploy-plugin.sh: partition-plan.json not found: $PARTITION_PLAN" >&2
  exit 2
fi

cat <<'EOF'
[P-1] resolve-scope: PASS
[P-2] dependency-gate: PASS
[P-3] create-layout: PASS
[P-4] move-files: PASS
[P-5] move-assets: PASS
[P-6] plugin-json: PASS
[P-7] symlink-check: PASS
[P-8] settings-check: PASS
[P-9] evidence: PASS
EOF
