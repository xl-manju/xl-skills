#!/usr/bin/env python3
"""Score each intake section for completeness and placeholder hygiene."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_PLACEHOLDER_RE = re.compile(r'(TBD|未定|要確認|\?{2,})', re.IGNORECASE)


def check_section(name: str, body: Any) -> dict[str, Any]:
    text = str(body or '').strip()
    word_count = len([w for w in re.split(r'\s+', text) if w])
    has_placeholder = bool(_PLACEHOLDER_RE.search(text))
    has_content = word_count >= 20
    ok = has_content and not has_placeholder
    return {
        'section': name,
        'ok': ok,
        'word_count': word_count,
        'has_heading': True,
        'has_placeholder': has_placeholder,
    }


def check_all(sections: dict[str, Any]) -> dict[str, Any]:
    results = [check_section(k, sections[k]) for k in sections]
    failed = [r for r in results if not r['ok']]
    return {'ok': len(failed) == 0, 'results': results, 'failed_count': len(failed)}


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        sys.stderr.write('usage: section_quality_check.py <intake.json>\n')
        return 2
    try:
        data = json.loads(Path(argv[0]).resolve().read_text(encoding='utf-8'))
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    r = check_all(data.get('sections') or {})
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0 if r['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
