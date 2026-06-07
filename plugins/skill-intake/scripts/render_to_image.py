#!/usr/bin/env python3
"""Render a Mermaid source to PNG via the external `mmdc` CLI; fall back to a placeholder."""
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


def placeholder_png(output_path: Path, note: str = '') -> None:
    txt = (
        f"# mmdc not installed\n"
        f"# placeholder for {output_path.name}\n"
        f"# note: {note}\n"
    )
    (output_path.parent / (output_path.name + '.placeholder.txt')).write_text(txt, encoding='utf-8')


def render(input_path: Path, output_path: Path, opts: dict[str, Any] | None = None) -> dict[str, Any]:
    opts = opts or {}
    fmt = opts.get('format') or ('svg' if str(output_path).endswith('.svg') else 'png')
    if not has_mmdc():
        placeholder_png(output_path, f'format={fmt}')
        return {'ok': True, 'mode': 'placeholder', 'output': str(output_path)}
    args = ['mmdc', '-i', str(input_path), '-o', str(output_path), '-b', 'white']
    if opts.get('width'):
        args += ['-w', str(opts['width'])]
    if opts.get('height'):
        args += ['-H', str(opts['height'])]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        return {'ok': False, 'mode': 'mmdc', 'stderr': r.stderr}
    return {'ok': True, 'mode': 'mmdc', 'output': str(output_path), 'format': fmt}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write('usage: render_to_image.py <input.mmd> <output.png>\n')
        return 2
    inp = Path(argv[0])
    out = Path(argv[1])
    if not inp.exists():
        sys.stderr.write(f'input missing: {inp}\n')
        return 2
    r = render(inp.resolve(), out.resolve(), {'width': 1200})
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0 if r.get('ok') else 3


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
