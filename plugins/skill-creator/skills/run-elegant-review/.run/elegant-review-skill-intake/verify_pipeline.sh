#!/usr/bin/env bash
# Phase3 検証: pipeline エンドツーエンド (revise / create / consistency)
set -u
SCR=/Users/dm/dev/dev/xlocal/xl-skills/plugins/skill-intake/scripts
FIX=/Users/dm/dev/dev/xlocal/xl-skills/plugins/skill-intake/fixtures/intake-final-smoke/context.json
PIPE="$SCR/intake_publish_pipeline.py"
TMP=$(mktemp -d)
cp "$FIX" "$TMP/intake.json"
PX=11112222333344445555666677778888

echo "=== PPT0: 通常 create dry-run (gate がfixtureで通るか確認) ==="
python3 "$PIPE" --intake "$TMP/intake.json" --database-id dummy-db --dry-run 2>&1 | tail -3
echo "exit=${PIPESTATUS[0]}"

echo; echo "=== PPT1: --revise (page-id無し, result無し) 期待 exit 51 ==="
rm -f "$TMP/notion-publish-result.json"
python3 "$PIPE" --intake "$TMP/intake.json" --database-id dummy-db --revise --dry-run >/dev/null 2>&1; echo "exit=$?"

echo; echo "=== PPT2: --revise --page-id (result無し) 期待 consistency skip + publish成功(exit0) ==="
python3 "$PIPE" --intake "$TMP/intake.json" --database-id dummy-db --revise --page-id $PX --dry-run >/dev/null 2>&1; echo "exit=$?"

echo; echo "=== PPT3: --revise --page-id, result既存 page_id一致 期待 exit0 ==="
printf '{"page_id":"11112222-3333-4444-5555-666677778888","url":"u"}\n' > "$TMP/notion-publish-result.json"
python3 "$PIPE" --intake "$TMP/intake.json" --database-id dummy-db --revise --page-id $PX --dry-run >/dev/null 2>&1; echo "exit=$?"

echo; echo "=== PPT4: --revise --page-id, result既存 page_id不一致 期待 gate FAIL(exit!=0, orphan検出) ==="
printf '{"page_id":"99999999-9999-9999-9999-999999999999","url":"u"}\n' > "$TMP/notion-publish-result.json"
python3 "$PIPE" --intake "$TMP/intake.json" --database-id dummy-db --revise --page-id $PX --dry-run >/dev/null 2>&1; echo "exit=$?"
echo "--- PPT4 の gate 出力 (page_id_consistency) ---"
python3 "$PIPE" --intake "$TMP/intake.json" --database-id dummy-db --revise --page-id $PX --dry-run 2>&1 | grep -iE "page_id|orphan|consistency|changed" | head -5
rm -rf "$TMP"
