---
name: run-intake-visualize
description: ヒアリング結果に図解を配置したいとき、Mermaid 12 と独自 SVG 8 から各セクションに 1〜3 図を選択して visuals.json と PNG を生成したいときに使う。
allowed-tools:
  - Read
  - Write
  - Bash
kind: run
user-invocable: true
effect: local-artifact
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-22
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
role_suffix: null
owner: team-platform
since: 2026-05-22
responsibility_refs:
  - prompts/main.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
---

# run-intake-visualize

## Purpose & Output Contract

Phase 7 担当。sheet.md / purpose.json を読み、Mermaid 12 + SVG 8 のカタログから各セクション (§0〜§11) に 1〜3 図を **決定論的に**配置する。SVG は PNG 化し Notion 互換にする。

**入力**: sheet.md, purpose.json, options.json, アセットカタログ (`plugins/skill-intake/assets/`)
**出力**:
- `output/<hint>/visuals.json` (section→図 mapping)
- `output/<hint>/visuals/*.png` (PNG 群)

**完了条件**: 全セクションに 1 図以上配置 + `scripts/verify-visuals.py` PASS。

## Key Rules

1. **図解マスト 8 ルール強制**: `references/visualization-mandatory-pointer.md` 経由で旧 aggregator のルールを適用。
2. **SVG は必ず PNG 化**: Notion は SVG ネイティブ非対応。`render_to_image.py` 経由のみ。
3. **LLM 創作禁止**: カタログ外の新規図を生成しない。

## Steps

### Step 1: 入力読込

sheet.md / purpose.json / options.json を Read。

### Step 2: セクション×図マッピング決定

`references/section-figure-mapping.md` の決定表に従い各セクションに 1〜3 図を割り当てる。

### Step 3: PNG レンダリング

```bash
python3 plugins/skill-intake/scripts/render_to_image.py --input output/<hint>/visuals.json --out output/<hint>/visuals/
```

### Step 4: 検証

```bash
python3 plugins/skill-intake/skills/run-intake-visualize/scripts/verify-visuals.py output/<hint>/visuals.json output/<hint>/visuals/
```

## Gotchas

1. **PNG 欠落で停止**: 1 枚でも欠けたら Phase 11 で停止する (All-or-Nothing)。本 phase で全 PNG 生成を保証。
2. **カタログ拡張は別 phase**: 新規図種が必要な場合は本 phase で生成せず TODO 起票。

## Additional Resources

- `references/section-figure-mapping.md` — §0〜§11 と図種の対応表
- `references/visualization-mandatory-pointer.md` — 図解マスト 8 ルールの参照ガイド
- `scripts/verify-visuals.py` — visuals.json + PNG 群の整合検証
