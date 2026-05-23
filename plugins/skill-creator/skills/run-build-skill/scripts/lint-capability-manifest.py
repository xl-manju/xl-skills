#!/usr/bin/env python3
# 発火: PostToolUse:Edit|Write hook (Claude Code)
# 副作用境界: stderr に lint 結果のみ。ファイル変更なし。常に exit 0(非ブロック)。
# 想定 input: {"tool_input": {"file_path": "..."}} 形式 JSON。
# 対象: SKILL.md / commands|agents の *.md / plugin-composition.yaml。
"""CapabilityManifest schema で frontmatter を検証する lint hook (非ブロック)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import jsonschema  # type: ignore

    HAS_JSONSCHEMA = True
except Exception:
    HAS_JSONSCHEMA = False

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "references"
    / "capability-manifest.schema.json"
)


def _read_stdin_json() -> dict:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def _is_target(path: Path) -> bool:
    name = path.name
    if name == "SKILL.md":
        return True
    if name == "plugin-composition.yaml":
        return True
    if path.suffix == ".md":
        parts = {p.lower() for p in path.parts}
        if "commands" in parts or "agents" in parts:
            return True
    return False


def _extract_frontmatter(text: str) -> dict | None:
    # YAML frontmatter (--- ... ---) を抽出し、簡易 key:value パース
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return None
    block = m.group(1)
    data: dict = {}
    for line in block.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line or line.startswith(" "):
            # ネスト/リストはスタブでは無視
            continue
        key, _, val = line.partition(":")
        data[key.strip()] = val.strip().strip('"').strip("'")
    return data


def _load_schema() -> dict | None:
    try:
        if SCHEMA_PATH.exists():
            return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _fallback_check(fm: dict) -> list[str]:
    # jsonschema 無しでも最低限の必須キーを確認
    errors = []
    for key in ("name", "description"):
        if key not in fm or not fm[key]:
            errors.append(f"missing required key: {key}")
    return errors


def main() -> int:
    try:
        payload = _read_stdin_json()
        tool_input = payload.get("tool_input") or {}
        file_path_str = tool_input.get("file_path") or ""
        if not file_path_str:
            return 0
        path = Path(file_path_str)
        if not _is_target(path) or not path.exists():
            return 0

        text = path.read_text(encoding="utf-8", errors="ignore")
        fm = _extract_frontmatter(text)
        if fm is None:
            sys.stderr.write(
                json.dumps(
                    {
                        "hook": "lint-capability-manifest",
                        "file": str(path),
                        "error": "frontmatter not found",
                    },
                    ensure_ascii=False,
                )
            )
            return 0

        schema = _load_schema()
        errors: list[str] = []
        if HAS_JSONSCHEMA and schema:
            try:
                jsonschema.validate(fm, schema)
            except jsonschema.ValidationError as e:  # type: ignore
                errors.append(str(e.message))
            except Exception as e:
                errors.append(f"validator error: {e}")
        else:
            errors.extend(_fallback_check(fm))

        if errors:
            sys.stderr.write(
                json.dumps(
                    {
                        "hook": "lint-capability-manifest",
                        "file": str(path),
                        "errors": errors,
                        "schema_used": bool(HAS_JSONSCHEMA and schema),
                    },
                    ensure_ascii=False,
                )
            )
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
