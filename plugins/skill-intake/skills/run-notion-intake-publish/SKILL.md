---
name: run-notion-intake-publish
description: 既存 intake 成果物を Notion へ再公開したいとき、ヒアリングをやり直さず Notion 側だけ更新したいときに使う。
allowed-tools:
  - Read
  - Write
  - Bash
kind: run
disable-model-invocation: false
user-invocable: true
effect: external-mutation
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-21
audit-trigger: monthly
hierarchy_level: leaf
rubric_refs: [quality-rubric, sink-contract]
role_suffix: publish
owner: team-platform
since: 2026-05-20
---

# run-notion-intake-publish

## 責務 (薄い wrapper)

`run-skill-intake-aggregator` で生成済みの `output/<hint>/` 一式を Notion DB に **再公開** するためだけの薄いエイリアス skill。実体は `plugins/skill-intake/scripts/intake_publish_pipeline.py` (単一発火点) を 1 回呼ぶだけ。

**ロジックを書かない**: render / quality_gate / publish の重複実装は禁止。aggregator phase11 と同じ pipeline を共有する。

**入力**: `<skill-name-hint>` (`output/<hint>/intake.json` および `output/<hint>/notion-manifest.json` が完成している前提)

**出力**: pipeline 内部で書き出される `notion-blocks.json` / `notion-publish-result.json` / `notion-url.txt` / `notion-log.json`

## Steps

```bash
HINT="$1"
test -f "output/$HINT/intake.json" || { echo "intake.json not found"; exit 2; }

python3 plugins/skill-intake/scripts/keychain_get_secret.py --check
python3 plugins/skill-intake/scripts/verify_notion_schema.py --on-conflict skip-warn
python3 plugins/skill-intake/scripts/verify_notion_assets.py "output/$HINT/notion-manifest.json"
python3 plugins/skill-intake/scripts/intake_publish_pipeline.py \
  --intake "output/$HINT/intake.json" \
  --manifest "output/$HINT/notion-manifest.json"
```

`intake_publish_pipeline.py` が render → quality_gate → publish を順に exec し、いずれかが exit !=0 ならその時点で停止する。トークンは `notion_http.py` が内部で都度 Keychain から取得 (環境変数渡し禁止)。

## Key Rules

1. **単一発火点**: publish パイプは `intake_publish_pipeline.py` のみ。本 skill では `render_notion_page.py` / `publish_notion_page.py` を直接呼ばない。
2. **再公開専用**: ヒアリング・図解生成・JSON 整形はやらない。
3. **All-or-Nothing**: `verify_notion_assets.py` 必須通過。PNG 1 枚でも欠ければ停止。
4. **Secret-Out-of-Repo**: トークンは Keychain からのみ取得。

## Additional Resources

- `../run-skill-intake-aggregator/SKILL.md` — sibling (aggregator) skill。phase 11 で同じ pipeline を呼ぶ
- `../../scripts/intake_publish_pipeline.py` — 唯一の publish エントリ
- `../run-skill-intake-aggregator/references/notion-integration.md` — Notion 連携正本
- `../run-skill-intake-aggregator/references/keychain-setup.md` — Keychain セットアップ
