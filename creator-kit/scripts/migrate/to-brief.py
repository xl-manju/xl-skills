#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""audit.py の出力 JSON から run-build-skill 起動用 brief を生成する。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def to_brief(audit: dict) -> list[dict]:
    briefs = []
    for sec in audit["sections"]:
        if sec["suggested_skill_name"] is None:
            continue
        briefs.append({
            "skill_name": sec["suggested_skill_name"],
            "kind": sec["classification"],
            "origin_heading": sec["heading"],
            "source": audit["input_file"],
            "source-tier": "internal",
            "rationale": sec["rationale"],
            "owner": "{{owner}}",
        })
    return briefs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-json", required=True)
    ap.add_argument("--output", default="-")
    args = ap.parse_args()

    audit = json.loads(Path(args.audit_json).read_text(encoding="utf-8"))
    briefs = to_brief(audit)

    payload = json.dumps({"briefs": briefs, "count": len(briefs)}, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(payload)
    else:
        Path(args.output).write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
