#!/usr/bin/env bash
# Phase3 検証: page_id 解決ロジック (島1封鎖点) の dry-run 確認
set -u
SCR=/Users/dm/dev/dev/xlocal/xl-skills/plugins/skill-intake/scripts
FIX=/Users/dm/dev/dev/xlocal/xl-skills/plugins/skill-intake/fixtures/intake-final-smoke/context.json
TMP=$(mktemp -d)
printf '%s\n' '{"children":[{"object":"block","type":"paragraph","paragraph":{"rich_text":[{"type":"text","text":{"content":"x"}}]}}]}' > "$TMP/blocks.json"
P="python3 $SCR/publish_notion_page.py --intake $FIX --blocks $TMP/blocks.json --database-id dummy-db"
PARSE="python3 -c import sys,json;d=json.load(sys.stdin);print('mode=',d['mode'],'source=',d.get('page_id_source'),'page_id=',d.get('page_id'))"

echo "FIX exists: $(test -f "$FIX" && echo yes || echo no)"

echo; echo "=== T1: --page-id 明示 (期待 mode=update source=arg) ==="
$P --page-id 11112222333344445555666677778888 --dry-run 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print('mode=',d['mode'],'source=',d.get('page_id_source'),'page_id=',d.get('page_id'))"

echo; echo "=== T2: --page-url (期待 source=url 32hex抽出) ==="
$P --page-url "https://www.notion.so/ws/MyPage-aaaabbbbccccddddeeeeffff00001111?pvs=4" --dry-run 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print('mode=',d['mode'],'source=',d.get('page_id_source'),'page_id=',d.get('page_id'))"

echo; echo "=== T3: 何も無し (期待 mode=create) ==="
$P --dry-run 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print('mode=',d['mode'],'source=',d.get('page_id_source'))"

echo; echo "=== T4: --require-update + page_id無し (期待 exit 51) ==="
$P --require-update --dry-run >/dev/null 2>&1; echo "exit=$?"

echo; echo "=== T5: --result-out 既存 (期待 source=result_file) ==="
printf '%s\n' '{"page_id":"99998888777766665555444433332222","url":"u"}' > "$TMP/r.json"
$P --result-out "$TMP/r.json" --dry-run 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print('mode=',d['mode'],'source=',d.get('page_id_source'),'page_id=',d.get('page_id'))"

echo; echo "=== T6: 明示 --page-id が result-out より優先 (期待 source=arg) ==="
$P --result-out "$TMP/r.json" --page-id 11112222333344445555666677778888 --dry-run 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print('mode=',d['mode'],'source=',d.get('page_id_source'),'page_id=',d.get('page_id'))"
rm -rf "$TMP"
