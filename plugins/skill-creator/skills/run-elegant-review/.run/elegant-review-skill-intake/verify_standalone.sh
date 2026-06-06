#!/usr/bin/env bash
# 単独インストールシミュレーション: skill-intake を skill-creator 無しの隔離環境にコピーし
# Notion publish コアフローが自己完結動作するか検証する。
set -u
ROOT=/Users/dm/dev/dev/xlocal/xl-skills
RUN="$ROOT/.claude/skills/run-elegant-review/.run/elegant-review-skill-intake"

echo "=== 0. vendored SSOT lint (notion_config.py byte一致) ==="
python3 "$ROOT/scripts/lint-intake-vendored-ssot.py"; echo "lint exit=$?"

echo; echo "=== 1. 隔離環境構築 (skill-intake のみ。skill-creator は存在しない) ==="
ISO=$(mktemp -d)
mkdir -p "$ISO/plugins"
cp -RL "$ROOT/plugins/skill-intake" "$ISO/plugins/skill-intake" 2>/dev/null
echo "skill-creator 存在: $(test -d "$ISO/plugins/skill-creator" && echo 'あり(NG)' || echo 'なし(OK=単独想定)')"
echo "vendored notion_config.py: $(test -f "$ISO/plugins/skill-intake/scripts/notion_config.py" && echo '実体あり(OK)' || echo '欠落(NG)')"
echo "dangling symlink 数: $(find "$ISO/plugins/skill-intake" -type l 2>/dev/null | wc -l | tr -d ' ')"

echo; echo "=== 2. 隔離環境で notion_config import が成立するか ==="
python3 -c "import sys; sys.path.insert(0, '$ISO/plugins/skill-intake/scripts'); import notion_config; print('  import OK / get_db_id 関数:', hasattr(notion_config, 'get_db_id'))" 2>&1 | head -3

echo; echo "=== 3. 隔離環境で publish dry-run (page_id解決=自己完結コア) ==="
FIX="$ISO/plugins/skill-intake/fixtures/intake-final-smoke/context.json"
B="$ISO/blocks.json"
printf '%s\n' '{"children":[{"object":"block","type":"paragraph","paragraph":{"rich_text":[{"type":"text","text":{"content":"x"}}]}}]}' > "$B"
python3 "$ISO/plugins/skill-intake/scripts/publish_notion_page.py" \
  --intake "$FIX" --blocks "$B" --database-id iso-db \
  --page-id 11112222333344445555666677778888 --dry-run 2>"$ISO/err" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('  publish dry-run OK: mode=',d['mode'],'source=',d['page_id_source'])" \
  || { echo '  publish FAILED:'; cat "$ISO/err" | head -3; }
rm -rf "$ISO"
