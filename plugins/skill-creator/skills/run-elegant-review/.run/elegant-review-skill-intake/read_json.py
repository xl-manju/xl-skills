import json, sys
d = json.load(open(sys.argv[1]))
path = sys.argv[2].split('.') if len(sys.argv) > 2 else None
if path:
    v = d
    for k in path:
        v = v[k]
    print(v)
else:
    print('status=', d.get('status'))
    for k, val in d.get('checks', {}).items():
        if isinstance(val, dict) and not val.get('ok'):
            print('  FAIL:', k, '=>', val.get('reason') or val.get('reasons') or val.get('missing'))
