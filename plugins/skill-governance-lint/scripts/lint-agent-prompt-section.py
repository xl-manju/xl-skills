#!/usr/bin/env python3
# /// script
# name: lint-agent-prompt-section
# purpose: SubAgent files must declare Prompt Templates and Self-Evaluation sections.
# inputs:
#   - argv: agent .md path or --agents-dir <dir> or --plugins-root <dir>
# outputs:
#   - stdout: OK status
#   - stderr: violation findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Lint SubAgent markdown files for required sections.

Required sections (agent-template.md):
  - ## Prompt Templates
  - ## Self-Evaluation

Skip rule:
  If body contains the literal '(対話なし: 自動実行 agent)' then Prompt Templates
  section may omit a question example block (only the heading is required).

Usage:
  lint-agent-prompt-section.py path/to/agent.md
  lint-agent-prompt-section.py --agents-dir plugins/skill-intake/agents
  lint-agent-prompt-section.py --plugins-root plugins

Exit 0 = ok, 1 = violation, 2 = usage error.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

REQUIRED_HEADINGS = ("## Prompt Templates", "## Self-Evaluation")
DIMENSIONS = ("完全性", "一貫性", "深度", "検証可能性", "簡潔性")
AUTO_AGENT_MARKER = "(対話なし: 自動実行 agent)"


def find_section(text: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^{re.escape(heading)}\s*\n(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1) if m else None


def lint_file(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{path}: read error: {e}"]

    for heading in REQUIRED_HEADINGS:
        if heading not in text:
            findings.append(f"{path}: missing required heading '{heading}'")

    prompt_body = find_section(text, "## Prompt Templates")
    if prompt_body is not None and AUTO_AGENT_MARKER not in prompt_body:
        has_quote = re.search(r"^>\s*", prompt_body, re.MULTILINE) is not None
        has_round = re.search(r"^### ", prompt_body, re.MULTILINE) is not None
        if not (has_quote or has_round):
            findings.append(
                f"{path}: Prompt Templates section needs either a '> ' quote "
                "or '### Round' subheading, or marker '(対話なし: 自動実行 agent)'"
            )

    eval_body = find_section(text, "## Self-Evaluation")
    if eval_body is not None:
        if not any(d in eval_body for d in DIMENSIONS):
            findings.append(
                f"{path}: Self-Evaluation must reference at least one of "
                f"{'/'.join(DIMENSIONS)}"
            )

    return findings


def collect_targets(argv: list[str]) -> list[Path]:
    if not argv:
        return []
    if argv[0] == "--agents-dir":
        if len(argv) < 2:
            return []
        d = Path(argv[1])
        return sorted(d.glob("*.md")) if d.is_dir() else []
    if argv[0] == "--plugins-root":
        if len(argv) < 2:
            return []
        root = Path(argv[1])
        if not root.is_dir():
            return []
        return sorted(root.glob("*/agents/*.md"))
    return [Path(p) for p in argv]


def main(argv: list[str]) -> int:
    targets = collect_targets(argv)
    if not targets:
        sys.stderr.write(
            "usage: lint-agent-prompt-section.py <agent.md> | "
            "--agents-dir <dir> | --plugins-root <dir>\n"
        )
        return 2

    all_findings: list[str] = []
    for path in targets:
        all_findings.extend(lint_file(path))

    if all_findings:
        for f in all_findings:
            sys.stderr.write(f + "\n")
        return 1

    sys.stdout.write(f"OK: {len(targets)} agent file(s) passed\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
