#!/usr/bin/env python3
"""intake.json を intake.schema.json (Draft 2020-12) で検証する pre-publish hook.

Usage:
  python3 validate_intake_schema.py <intake.json path>
  echo '{"intake_json": "..."}' | python3 validate_intake_schema.py  # hook stdin mode

Exit codes:
  0  PASS
  1  schema validation error
  2  file not found / IO error
  3  schema file missing
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = PROJECT_ROOT / "plugins" / "skill-intake" / "skills" / "run-skill-intake-aggregator" / "references" / "intake.schema.json"


def _read_target_path(argv: list[str]) -> Path:
    if len(argv) >= 2:
        return Path(argv[1]).resolve()
    # hook stdin: {"tool_input": {"file_path": "..."}} or {"intake_json": "..."}
    payload = json.load(sys.stdin)
    candidate = (
        payload.get("intake_json")
        or payload.get("tool_input", {}).get("file_path")
        or payload.get("path")
    )
    if not candidate:
        print("ERROR: target path not provided (argv or stdin)", file=sys.stderr)
        sys.exit(2)
    return Path(candidate).resolve()


def main(argv: list[str]) -> int:
    if not SCHEMA_PATH.exists():
        print(f"ERROR: schema not found at {SCHEMA_PATH}", file=sys.stderr)
        return 3

    try:
        target = _read_target_path(argv)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid stdin payload: {exc}", file=sys.stderr)
        return 2

    if not target.exists():
        print(f"ERROR: intake.json not found: {target}", file=sys.stderr)
        return 2

    try:
        import jsonschema
    except ImportError:
        print("ERROR: jsonschema package required. install with: pip install jsonschema", file=sys.stderr)
        return 3

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    instance = json.loads(target.read_text(encoding="utf-8"))

    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))

    if not errors:
        print(f"PASS: {target} conforms to intake.schema.json", file=sys.stderr)
        return 0

    print(f"FAIL: {target} has {len(errors)} schema violations", file=sys.stderr)
    for err in errors[:20]:
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        print(f"  - [{loc}] {err.message}", file=sys.stderr)
    if len(errors) > 20:
        print(f"  ... and {len(errors) - 20} more", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
