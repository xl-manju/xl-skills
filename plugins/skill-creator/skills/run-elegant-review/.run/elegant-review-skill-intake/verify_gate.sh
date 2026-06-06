#!/usr/bin/env bash
set -u
SCR=/Users/dm/dev/dev/xlocal/xl-skills/plugins/skill-intake/scripts
FIX=/Users/dm/dev/dev/xlocal/xl-skills/plugins/skill-intake/fixtures/intake-final-smoke/context.json
TMP=$(mktemp -d); cp "$FIX" "$TMP/intake.json"
PX=11112222-3333-4444-5555-666677778888

echo "=== PPT0 gate 失敗の原因 (どのcheckがFAILか) ==="
python3 "$SCR/intake_publish_pipeline.py" --intake "$TMP/intake.json" --database-id dummy-db --gate-out "$TMP/gate.json" --dry-run >/dev/null 2>&1
python3 "$SCR/../../../.claude/skills/run-elegant-review/.run/elegant-review-skill-intake/show_gate.py" "$TMP/gate.json" 2>/dev/null \
  || python3 - "$TMP/gate.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
print('status=',d['status'])
for k,v in d['checks'].items():
    if not v.get('ok'):
        print('  FAIL:',k,'=>',v.get('reason') or v.get('reasons') or v.get('missing'))
PY

echo; echo "=== quality_gate 単体: consistency 配線の分離検証 ==="
printf '{"page_id":"11112222-3333-4444-5555-666677778888","url":"u"}\n' > "$TMP/r.json"
run_gate () { python3 "$SCR/quality_gate.py" --intake "$TMP/intake.json" "$@" 2>/dev/null; }

echo "--- 一致 (prev==result): ok 期待 true ---"
run_gate --result-path "$TMP/r.json" --prev-page-id $PX | python3 - <<'PY'
import json,sys; d=json.load(sys.stdin); print('  ',d['checks']['page_id_consistency'])
PY
echo "--- 不一致 (prev!=result): ok 期待 false ---"
run_gate --result-path "$TMP/r.json" --prev-page-id 99999999-9999-9999-9999-999999999999 | python3 - <<'PY'
import json,sys; d=json.load(sys.stdin); print('  ',d['checks']['page_id_consistency'])
PY
echo "--- prev未指定: skip 期待 ---"
run_gate | python3 - <<'PY'
import json,sys; d=json.load(sys.stdin); print('  ',d['checks']['page_id_consistency'])
PY
rm -rf "$TMP"
