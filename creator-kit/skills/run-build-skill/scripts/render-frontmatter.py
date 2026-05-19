#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Render a skill template by substituting {{var}} placeholders.

Usage: render-frontmatter.py --name <skill-name> --kind <kind> --template <path>
Prints rendered SKILL.md to stdout.
"""
from __future__ import annotations
import argparse
import datetime
import json
import sys
from pathlib import Path

OS_PREAMBLE = "!`uname -s 2>/dev/null || ver`"


def render(template: str, mapping: dict[str, str]) -> str:
    out = template
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def is_true(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def apply_dynamic_context_contract(content: str, mapping: dict[str, str]) -> str:
    """Apply 14章 OS preamble contract from brief fields to rendered SKILL.md."""
    needs_preamble = is_true(mapping.get("cross_platform")) or is_true(
        mapping.get("os_preamble_required")
    )
    if not needs_preamble:
        return content

    if not content.startswith("---"):
        return f"{OS_PREAMBLE}\n\n{content}"

    end = content.find("---", 3)
    if end == -1:
        return f"{OS_PREAMBLE}\n\n{content}"

    frontmatter = content[: end + 3]
    body = content[end + 3 :]
    additions = []
    if "\ncross_platform:" not in frontmatter:
        additions.append("cross_platform: true")
    if "\nos_preamble_required:" not in frontmatter:
        additions.append("os_preamble_required: true")
    if additions:
        frontmatter = frontmatter[:-3] + "\n" + "\n".join(additions) + "\n---"

    if OS_PREAMBLE not in body.splitlines()[:30]:
        body = "\n\n" + OS_PREAMBLE + "\n" + body.lstrip("\n")
    return frontmatter + body


def brief_mapping(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    triggers = data.get("trigger_conditions") or []
    key_constraints = data.get("key_constraints") or []
    add_res = data.get("additional_resources") or []
    add_res_lines = []
    for item in add_res:
        if isinstance(item, dict):
            p = item.get("path", "").strip()
            w = item.get("when_to_read", "").strip()
            if p:
                add_res_lines.append(f"- `{p}`: {w}" if w else f"- `{p}`")
    return {
        "name": data.get("skill_name", ""),
        "kind": data.get("kind") or data.get("prefix", ""),
        "topic": data.get("skill_name", ""),
        "verb": data.get("verb", "Run"),
        "object": data.get("object", data.get("skill_name", "workflow")),
        "trigger1": triggers[0] if len(triggers) >= 1 else "the user asks",
        "trigger2": triggers[1] if len(triggers) >= 2 else "the workflow demands it",
        "trigger3": triggers[2] if len(triggers) >= 3 else "",
        "output_contract": data.get("output_contract", "TODO"),
        "boundary": data.get("boundary", "TODO"),
        "key_constraints": "\n".join(f"{i + 1}. {item}" for i, item in enumerate(key_constraints)) or "1. TODO",
        "role_suffix": data.get("role_suffix") or "none",
        "base_skill": data.get("base_skill") or "none",
        "delegate_agent": data.get("delegate_agent") or "none",
        "cross_platform": str(bool(data.get("cross_platform", False))).lower(),
        "os_preamble_required": str(
            bool(data.get("os_preamble_required", data.get("cross_platform", False)))
        ).lower(),
        "additional_resources": "\n".join(add_res_lines),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--kind", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--owner", default="team-skills")
    ap.add_argument("--brief", help="skill-brief.json path; values override placeholder defaults")
    args = ap.parse_args()

    tpath = Path(args.template)
    if not tpath.exists():
        print(f"template not found: {tpath}", file=sys.stderr)
        return 2
    prefix = args.name.split("-", 1)[0] if "-" in args.name else ""
    if prefix and prefix != args.kind:
        print(f"name/kind mismatch: name prefix '{prefix}' != kind '{args.kind}'", file=sys.stderr)
        return 2
    if tpath.stem != args.kind:
        print(f"template/kind mismatch: template '{tpath.stem}' != kind '{args.kind}'", file=sys.stderr)
        return 2
    text = tpath.read_text(encoding="utf-8")

    today = datetime.date.today().isoformat()
    mapping = {
        "name": args.name,
        "kind": args.kind,
        "owner": args.owner,
        "date": today,
        "verb": "Do",
        "object": "thing",
        "topic": args.name,
        "trigger1": "the user asks",
        "trigger2": "the workflow demands it",
        "artifact": "artifact",
        "evaluator": f"assign-{args.name}-evaluator",
        "generator": f"run-{args.name}-generator",
        "upstream-rubric": "ref-skill-design-rubric",
        "external-tool": "tool",
        "tool": "tool",
        "subagent": "general-purpose",
        "output_contract": "TODO",
        "boundary": "TODO",
        "key_constraints": "1. TODO",
        "role_suffix": "none",
        "base_skill": "none",
        "delegate_agent": "none",
        "additional_resources": "",
    }
    if args.brief:
        bpath = Path(args.brief)
        if not bpath.exists():
            print(f"brief not found: {bpath}", file=sys.stderr)
            return 2
        brief_values = brief_mapping(bpath)
        if brief_values.get("kind") and brief_values["kind"] != args.kind:
            print(f"brief/kind mismatch: brief '{brief_values['kind']}' != kind '{args.kind}'", file=sys.stderr)
            return 2
        if args.kind == "wrap" and brief_values.get("base_skill") in {"", "none"}:
            print("wrap requires base_skill in brief", file=sys.stderr)
            return 2
        if args.kind == "delegate" and brief_values.get("delegate_agent") in {"", "none"}:
            print("delegate requires delegate_agent in brief", file=sys.stderr)
            return 2
        mapping.update({k: v for k, v in brief_values.items() if v})
    sys.stdout.write(apply_dynamic_context_contract(render(text, mapping), mapping))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
