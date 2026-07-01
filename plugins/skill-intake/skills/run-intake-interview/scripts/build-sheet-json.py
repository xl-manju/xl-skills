#!/usr/bin/env python3
"""Build deterministic sheet.json five_axes from the Phase 4 sheet.md."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


AXES = ["出力先", "情報源", "共有相手", "真の課題", "ナレッジ資産"]
DEPTH_TO_ROW_DEPTH = {
    "light": "shallow",
    "quick": "shallow",
    "standard": "standard",
    "detailed": "deep",
    "deep": "deep",
}


def _pick_axis(text: str, axis: str) -> str:
    match = re.search(rf"#+\s*{re.escape(axis)}\s*\n(.+?)(?=\n#+\s|\Z)", text, re.S)
    if not match:
        return ""
    lines = [line.strip(" \t-") for line in match.group(1).splitlines()]
    value = " / ".join(line for line in lines if line.strip())
    return value.strip()


def build(sheet_text: str, depth: str) -> dict:
    row_depth = DEPTH_TO_ROW_DEPTH.get(depth, "standard")
    rows = []
    for axis in AXES:
        content = _pick_axis(sheet_text, axis)
        if not content or "[?]" in content:
            raise ValueError(f"axis incomplete: {axis}")
        row = {"name": axis, "content": content, "depth": row_depth}
        if axis == "ナレッジ資産":
            row["must"] = True
        rows.append(row)

    knowledge = next(r["content"] for r in rows if r["name"] == "ナレッジ資産")
    source = next(r["content"] for r in rows if r["name"] == "情報源")
    output = next(r["content"] for r in rows if r["name"] == "出力先")
    return {
        "five_axes": {
            "rows": rows,
            "pipeline": {
                "ingest": source,
                "analysis": "Phase 5 purpose-excavator で抽象回答を深掘り",
                "storage": knowledge,
                "retrieval": output,
                "update": "on-demand",
            },
        }
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sheet")
    parser.add_argument("--depth", default="standard")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    try:
        payload = build(Path(args.sheet).read_text(encoding="utf-8"), args.depth)
    except Exception as exc:
        print(f"FAIL build-sheet-json: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
