#!/usr/bin/env python3
"""5 軸 + user_profile の必須キー存在を検証。"""

import json
import sys

REQUIRED_AXES = ['output_target', 'info_source', 'share_target', 'true_problem', 'knowledge_assets']
AXIS_FALLBACK = {'output_target': 'output_destination'}


def axis_value_text(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and isinstance(v.get('answer'), str):
        return v['answer']
    return None


def validate(intake):
    errors = []
    if not isinstance(intake, dict):
        return {'ok': False, 'errors': ['intake is not an object']}
    if '5_axes' not in intake and 'five_axes' not in intake:
        errors.append('missing top-level key: 5_axes (or five_axes)')
    if 'user_profile' not in intake:
        errors.append('missing top-level key: user_profile')
    axes = intake.get('5_axes') or intake.get('five_axes')
    if not isinstance(axes, dict):
        errors.append('5_axes missing or not an object')
    else:
        for k in REQUIRED_AXES:
            fb = AXIS_FALLBACK.get(k)
            present = (k in axes) or (fb and fb in axes)
            if not present:
                errors.append(f'5_axes.{k} missing')
                continue
            raw = axes[k] if k in axes else axes[fb]
            text = axis_value_text(raw)
            if text is None or text.strip() == '':
                errors.append(f'5_axes.{k} empty')
    up = intake.get('user_profile')
    if up is not None and not isinstance(up, (dict, str)):
        errors.append('user_profile invalid type')
    return {'ok': len(errors) == 0, 'errors': errors}


def main(argv):
    if len(argv) < 2:
        sys.stderr.write('usage: validate_intake.py <intake.json>\n')
        return 2
    try:
        with open(argv[1], 'r', encoding='utf-8') as f:
            intake = json.load(f)
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    r = validate(intake)
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0 if r['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
