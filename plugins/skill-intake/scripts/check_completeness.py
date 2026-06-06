#!/usr/bin/env python3
"""5 軸の placeholder 検出と filled 軸数のカウント。"""

import json
import re
import sys

AXES = ['output_target', 'info_source', 'share_target', 'true_problem', 'knowledge_assets']
AXIS_FALLBACK = {'output_target': 'output_destination'}
# v2 five_axes.rows[] の日本語 name → 内部 key (validate_intake / convert_v1_to_v2_context と一致)。
AXIS_JA_TO_KEY = {
    '出力先': 'output_target',
    '情報源': 'info_source',
    '共有相手': 'share_target',
    '真の課題': 'true_problem',
    'ナレッジ資産': 'knowledge_assets',
}
PLACEHOLDER_PATTERNS = [
    re.compile(r'\bTBD\b', re.IGNORECASE),
    re.compile(r'未定'),
    re.compile(r'\?{2,}'),
    re.compile(r'^\s*[-—]\s*$'),
    re.compile(r'要確認'),
    re.compile(r'後で決め'),
]


def axis_value_text(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and isinstance(v.get('answer'), str):
        return v['answer']
    if isinstance(v, dict) and isinstance(v.get('content'), str):
        return v['content']
    return None


def normalize_axes(intake):
    """v1 flat (5_axes.output_target) と v2 (five_axes.rows[]) を {key: text} に正規化。"""
    raw = (intake.get('5_axes') if isinstance(intake, dict) else None) or \
        (intake.get('five_axes') if isinstance(intake, dict) else None) or {}
    rows = raw.get('rows') if isinstance(raw, dict) else None
    if isinstance(rows, list):
        flat = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = AXIS_JA_TO_KEY.get(str(row.get('name', '')).strip())
            if key:
                flat[key] = axis_value_text(row)
        return flat
    return raw if isinstance(raw, dict) else {}


def is_placeholder(s):
    if not isinstance(s, str):
        return True
    v = s.strip()
    if len(v) < 4:
        return True
    return any(p.search(v) for p in PLACEHOLDER_PATTERNS)


def check(intake):
    axes = normalize_axes(intake)
    filled = {}
    placeholders = []
    count = 0
    for k in AXES:
        fb = AXIS_FALLBACK.get(k)
        if k in axes:
            raw = axes[k]
        elif fb and fb in axes:
            raw = axes[fb]
        else:
            raw = None
        text = axis_value_text(raw)
        ok = not is_placeholder(text)
        filled[k] = ok
        if ok:
            count += 1
        else:
            placeholders.append(k)
    return {
        'ok': count == len(AXES),
        'filled_axes': count,
        'total_axes': len(AXES),
        'detail': filled,
        'placeholders': placeholders,
    }


def main(argv):
    if len(argv) < 2:
        sys.stderr.write('usage: check_completeness.py <intake.json>\n')
        return 2
    try:
        with open(argv[1], 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    r = check(data)
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0 if r['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
