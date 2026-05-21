#!/usr/bin/env python3
"""Render a section template by substituting {{var}} placeholders."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_TEMPLATE = """## {{title}}

**ねらい**: {{purpose}}

**現状**: {{current}}

**期待**: {{expected}}

{{diagram_block}}

**未解決**: {{open_questions}}
"""

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def fill(tpl: str, vars: dict[str, Any]) -> str:
    def _sub(m: re.Match[str]) -> str:
        v = vars.get(m.group(1))
        return '' if v is None else str(v)
    return _PLACEHOLDER.sub(_sub, tpl)


def diagram_block(diagrams: Any) -> str:
    if not isinstance(diagrams, list) or not diagrams:
        return ''
    return ''.join(f"\n```mermaid\n{str(d).strip()}\n```\n" for d in diagrams)


def apply(template: str | None, vars: dict[str, Any]) -> str:
    v = dict(vars)
    if isinstance(v.get('diagrams'), list):
        v['diagram_block'] = diagram_block(v['diagrams'])
    return fill(template or DEFAULT_TEMPLATE, v)


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        sys.stderr.write('usage: apply_section_template.py <vars.json> [template.md]\n')
        return 2
    vars_file = argv[0]
    template_file = argv[1] if len(argv) > 1 else None
    try:
        vars = json.loads(Path(vars_file).resolve().read_text(encoding='utf-8'))
        tpl = DEFAULT_TEMPLATE
        if template_file:
            tpl = Path(template_file).resolve().read_text(encoding='utf-8')
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    sys.stdout.write(apply(tpl, vars))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
