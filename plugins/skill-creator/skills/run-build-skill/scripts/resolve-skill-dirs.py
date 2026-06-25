#!/usr/bin/env python3
# /// script
# name: resolve-skill-dirs
# purpose: Resolve skill creator directories without shell-specific source files.
# inputs:
#   - argv: --skill-name, --skill-dir-name
# outputs:
#   - stdout: resolved path JSON
#   - stderr: argument errors
# contexts: [A, B]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Resolve skill creator paths as JSON using only Python stdlib."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-name", default="")
    parser.add_argument("--skill-dir-name", default="run-build-skill")
    args = parser.parse_args()

    root = Path.cwd()
    out_base = os.environ.get("CLAUDE_SKILL_OUT_BASE")
    if not out_base:
        if (root / "plugins" / "skill-creator" / "skills").is_dir():
            out_base = "plugins/skill-creator/skills"
        else:
            out_base = ".claude/skills"

    skill_dir = os.environ.get("CLAUDE_SKILL_DIR")
    if not skill_dir:
        candidate = Path(out_base) / args.skill_dir_name
        if candidate.exists():
            skill_dir = str(candidate)
        elif (root / "plugins" / "skill-creator" / "skills" / args.skill_dir_name).exists():
            skill_dir = f"plugins/skill-creator/skills/{args.skill_dir_name}"
        else:
            skill_dir = f".claude/skills/{args.skill_dir_name}"

    result = {
        "project_root": str(root),
        "out_base": out_base,
        "skill_dir": skill_dir,
    }
    if args.skill_name:
        result["target_root"] = str(Path(out_base) / args.skill_name)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
