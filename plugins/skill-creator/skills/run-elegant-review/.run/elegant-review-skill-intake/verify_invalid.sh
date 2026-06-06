#!/usr/bin/env bash
# Phase3 修正後検証: 不正 page 識別子の fail-closed (independent review issue 1/2)
set -u
SCR=/Users/dm/dev/dev/xlocal/xl-skills/plugins/skill-intake/scripts
FIX=/Users/dm/dev/dev/xlocal/xl-skills/plugins/skill-intake/fixtures/intake-final-smoke/context.json
TMP=$(mktemp -d)
printf '%s\n' '{"children":[{"object":"block","type":"paragraph","paragraph":{"rich_text":[{"type":"text","text":{"content":"x"}}]}}]}' > "$TMP/blocks.json"
P="python3 $SCR/publish_notion_page.py --intake $FIX --blocks $TMP/blocks.json --database-id dummy-db"

echo "=== T7: --page-id 不正文字列 (期待 exit 2, fail-closed) ==="
$P --page-id "garbage-not-a-uuid" --dry-run >/dev/null 2>"$TMP/e"; echo "exit=$? / $(cat "$TMP/e" | head -1)"

echo "=== T8: --page-id 不正 + --require-update (期待 exit 2, 迂回51を許さない) ==="
$P --page-id "garbage" --require-update --dry-run >/dev/null 2>&1; echo "exit=$?"

echo "=== T9: --page-url に id無し (期待 exit 2, url_invalid) ==="
$P --page-url "https://www.notion.so/ws/JustATitleNoId" --dry-run >/dev/null 2>&1; echo "exit=$?"

echo "=== T10: 短いhex(31桁) は不正 (期待 exit 2) ==="
$P --page-id "1111222233334444555566667777888" --dry-run >/dev/null 2>&1; echo "exit=$?"

echo "=== T11(退行): 正常 32hex は依然 update (期待 exit 0 mode=update) ==="
$P --page-id 11112222333344445555666677778888 --dry-run 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print('exit_ok mode=',d['mode'],'source=',d['page_id_source'])"

echo "=== T12(退行): pipeline 不正 page-id + revise (期待 publish exit2 を伝搬, !=0) ==="
cp "$FIX" "$TMP/intake.json"
python3 "$SCR/intake_publish_pipeline.py" --intake "$TMP/intake.json" --revise --page-id "garbage" --dry-run >/dev/null 2>&1; echo "exit=$?"
rm -rf "$TMP"
