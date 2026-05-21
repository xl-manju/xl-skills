#!/usr/bin/env python3
"""Convert intake.md (front-matter + sections) to intake.json."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

AXIS_HEADINGS: dict[str, list[str]] = {
    'output_destination': ['出力先', 'Output Destination'],
    'info_source': ['情報源', 'Information Source'],
    'share_target': ['共有相手', 'Sharing Target'],
    'true_problem': ['真の課題', 'True Problem'],
    'knowledge_assets': ['ナレッジ資産', 'Knowledge Assets'],
}

_HEADING = re.compile(r'^#{1,4}\s+(.*?)\s*$')
_FRONTMATTER = re.compile(r'^---\n([\s\S]*?)\n---\n')
_FM_KV = re.compile(r'^(\w[\w_-]*)\s*:\s*(.*)$')


def parse_sections(md: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in md.splitlines():
        m = _HEADING.match(line)
        if m:
            if current is not None:
                sections[current] = '\n'.join(buf).strip()
            current = m.group(1)
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = '\n'.join(buf).strip()
    return sections


def pick_axis(sections: dict[str, str], keys: list[str]) -> str:
    for k in sections:
        if any(needle in k for needle in keys):
            return sections[k]
    return ''


def extract_frontmatter(md: str) -> tuple[dict[str, str], str]:
    m = _FRONTMATTER.match(md)
    if not m:
        return {}, md
    meta: dict[str, str] = {}
    for line in m.group(1).split('\n'):
        kv = _FM_KV.match(line)
        if kv:
            meta[kv.group(1)] = kv.group(2).strip().strip("'\"")
    return meta, md[m.end():]


def convert(md: str) -> dict[str, Any]:
    meta, body = extract_frontmatter(md)
    sections = parse_sections(body)
    five_axes = {k: pick_axis(sections, v) for k, v in AXIS_HEADINGS.items()}
    integrations_raw = meta.get('integrations', '')
    integrations = [s.strip() for s in re.split(r'\s*,\s*', integrations_raw)] if integrations_raw else []
    return {
        'skill_name_hint': meta.get('skill_name_hint') or meta.get('name') or '',
        'pattern': meta.get('pattern') or 'other',
        'user_profile': sections.get('User Profile') or sections.get('利用者プロファイル') or '',
        '5_axes': five_axes,
        'sections': sections,
        'open_questions': [],
        'integrations': integrations,
        'raw_meta': meta,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        sys.stderr.write('usage: convert_md_to_json.py <intake.md> [intake.json]\n')
        return 2
    file = argv[0]
    out_file = argv[1] if len(argv) > 1 else None
    try:
        md = Path(file).resolve().read_text(encoding='utf-8')
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    j = convert(md)
    text = json.dumps(j, ensure_ascii=False, indent=2)
    if out_file:
        Path(out_file).resolve().write_text(text + '\n', encoding='utf-8')
    else:
        sys.stdout.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
