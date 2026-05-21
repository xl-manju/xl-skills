#!/usr/bin/env python3
"""Render a Mermaid source to SVG via `mmdc`; fall back to a placeholder SVG."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def has_mmdc() -> bool:
    if shutil.which('mmdc') is None:
        return False
    try:
        r = subprocess.run(['mmdc', '--version'], capture_output=True, text=True)
        return r.returncode == 0
    except Exception:
        return False


def render(input_path: Path, output_path: Path) -> dict[str, Any]:
    if not has_mmdc():
        placeholder = (
            '<?xml version="1.0"?>\n'
            f'<!-- mmdc not installed; placeholder for {input_path.name} -->\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="80">'
            '<text x="10" y="40">mermaid placeholder</text></svg>\n'
        )
        output_path.write_text(placeholder, encoding='utf-8')
        return {'ok': True, 'mode': 'placeholder', 'output': str(output_path)}
    r = subprocess.run(
        ['mmdc', '-i', str(input_path), '-o', str(output_path), '-b', 'transparent'],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return {'ok': False, 'mode': 'mmdc', 'stderr': r.stderr}
    return {'ok': True, 'mode': 'mmdc', 'output': str(output_path)}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write('usage: render_to_svg.py <input.mmd> <output.svg>\n')
        return 2
    inp = Path(argv[0])
    out = Path(argv[1])
    if not inp.exists():
        sys.stderr.write(f'input missing: {inp}\n')
        return 2
    r = render(inp.resolve(), out.resolve())
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0 if r.get('ok') else 3


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
