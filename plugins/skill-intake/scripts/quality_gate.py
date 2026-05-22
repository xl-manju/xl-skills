#!/usr/bin/env python3
"""validate / completeness / contradictions + blocks coverage を統合する quality gate。"""

import json
import sys

from validate_intake import validate
from check_completeness import check
from detect_contradictions import detect


def check_blocks(blocks):
    if isinstance(blocks, dict) and 'children' in blocks:
        arr = blocks['children']
    else:
        arr = blocks
    if not isinstance(arr, list):
        arr = []
    total = len(arr)
    mermaid = 0
    h2 = 0
    for b in arr:
        if not isinstance(b, dict):
            continue
        if b.get('type') == 'code' and isinstance(b.get('code'), dict) and b['code'].get('language') == 'mermaid':
            mermaid += 1
        if b.get('type') == 'heading_2':
            h2 += 1
    reasons = []
    if total < 20:
        reasons.append(f'blocks total {total} < 20')
    if mermaid < 1:
        reasons.append(f'mermaid code blocks {mermaid} < 1')
    if h2 < 5:
        reasons.append(f'heading_2 count {h2} < 5')
    return {'ok': len(reasons) == 0, 'total': total, 'mermaid': mermaid, 'h2': h2, 'reasons': reasons}


def gate(intake):
    v = validate(intake)
    c = check(intake)
    d = detect(intake)
    checks = {
        'validate_intake': {'ok': v['ok'], 'errors': v['errors']},
        'check_completeness': {'ok': c['ok'], 'placeholders': c['placeholders'], 'filled_axes': c['filled_axes']},
        'detect_contradictions': {'ok': d['ok'], 'count': d['count']},
    }
    ok = v['ok'] and c['ok'] and d['ok']
    return {'status': 'PASS' if ok else 'FAIL', 'checks': checks}


def parse_flag_args(argv):
    out = {'positional': []}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--intake':
            i += 1
            out['intake'] = argv[i]
        elif a == '--blocks':
            i += 1
            out['blocks'] = argv[i]
        elif a == '--out':
            i += 1
            out['out_file'] = argv[i]
        else:
            out['positional'].append(a)
        i += 1
    return out


def main(argv):
    args = parse_flag_args(argv[1:])
    intake_file = args.get('intake') or (args['positional'][0] if args['positional'] else None)
    out_file = args.get('out_file') or (args['positional'][1] if len(args['positional']) > 1 else None)
    if not intake_file:
        sys.stderr.write('usage: quality_gate.py [--intake] <intake.json> [--blocks <blocks.json>] [--out <out.json>]\n')
        return 2
    try:
        with open(intake_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    r = gate(data)

    blocks_failed = False
    if args.get('blocks'):
        try:
            with open(args['blocks'], 'r', encoding='utf-8') as f:
                blocks = json.load(f)
        except Exception as e:
            sys.stderr.write(f'--blocks read error: {e}\n')
            return 2
        bc = check_blocks(blocks)
        r['checks']['blocks_coverage'] = {
            'ok': bc['ok'], 'total': bc['total'], 'mermaid': bc['mermaid'],
            'heading_2': bc['h2'], 'reasons': bc['reasons'],
        }
        if not bc['ok']:
            for reason in bc['reasons']:
                sys.stderr.write(f'blocks-coverage: {reason}\n')
            r['status'] = 'FAIL'
            blocks_failed = True

    text = json.dumps(r, ensure_ascii=False, indent=2)
    if out_file:
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
    else:
        sys.stdout.write(text + '\n')
    if r['status'] == 'PASS':
        return 0
    if blocks_failed:
        return 2
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
