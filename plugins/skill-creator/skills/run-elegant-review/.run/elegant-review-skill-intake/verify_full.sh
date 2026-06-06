#!/usr/bin/env bash
set -u
SCR=/Users/dm/dev/dev/xlocal/xl-skills/plugins/skill-intake/scripts
RUN=/Users/dm/dev/dev/xlocal/xl-skills/.claude/skills/run-elegant-review/.run/elegant-review-skill-intake
FIX=/Users/dm/dev/dev/xlocal/xl-skills/plugins/skill-intake/fixtures/intake-final-smoke/context.json
RJ="$RUN/read_json.py"
PIPE="$SCR/intake_publish_pipeline.py"
QG="$SCR/quality_gate.py"
TMP=$(mktemp -d); cp "$FIX" "$TMP/intake.json"
PX=11112222-3333-4444-5555-666677778888

echo "=== A. pipeline 通常 create dry-run (--database-id無し → db_match skip) ==="
python3 "$PIPE" --intake "$TMP/intake.json" --dry-run >/dev/null 2>"$TMP/e0"; echo "exit=$?"
grep -E "publish: python3" "$TMP/e0" | sed 's#.*publish_notion_page.py#  pub_argv:#'

echo; echo "=== B. pipeline --revise --page-id (result無し) → publish 到達, mode/require-update 確認 ==="
rm -f "$TMP/notion-publish-result.json"
python3 "$PIPE" --intake "$TMP/intake.json" --revise --page-id $PX --dry-run >/dev/null 2>"$TMP/e1"; echo "exit=$?"
grep -E "publish: python3" "$TMP/e1" | sed 's#.*publish_notion_page.py#  pub_argv:#'

echo; echo "=== C. pipeline --revise --page-url → page-url 伝搬確認 ==="
python3 "$PIPE" --intake "$TMP/intake.json" --revise --page-url "https://www.notion.so/ws/Doc-aaaabbbbccccddddeeeeffff00001111" --dry-run >/dev/null 2>"$TMP/e2"; echo "exit=$?"
grep -E "publish: python3" "$TMP/e2" | sed 's#.*publish_notion_page.py#  pub_argv:#'

echo; echo "=== D. quality_gate 単体: page_id_consistency 配線 (ファイル経由) ==="
printf '{"page_id":"11112222-3333-4444-5555-666677778888","url":"u"}\n' > "$TMP/r.json"
python3 "$QG" --intake "$TMP/intake.json" --result-path "$TMP/r.json" --prev-page-id $PX --out "$TMP/g_match.json" 2>/dev/null
echo "  一致: $(python3 "$RJ" "$TMP/g_match.json" checks.page_id_consistency.ok) (期待 True)"
python3 "$QG" --intake "$TMP/intake.json" --result-path "$TMP/r.json" --prev-page-id 99999999-9999-9999-9999-999999999999 --out "$TMP/g_mis.json" 2>/dev/null
echo "  不一致: $(python3 "$RJ" "$TMP/g_mis.json" checks.page_id_consistency.ok) (期待 False)"
python3 "$QG" --intake "$TMP/intake.json" --out "$TMP/g_skip.json" 2>/dev/null
echo "  prev未指定: skipped=$(python3 "$RJ" "$TMP/g_skip.json" checks.page_id_consistency.skipped) (期待 True)"
rm -rf "$TMP"
