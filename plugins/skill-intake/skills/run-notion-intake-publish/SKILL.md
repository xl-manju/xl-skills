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

## Purpose & Output Contract

`run-skill-intake-aggregator` で生成済みの `output/<hint>/` 一式 (`intake.md`, `intake.json`, `visuals/`, `notion-manifest.json`) を Notion DB に **再公開** する sibling skill (kind=run)。

ヒアリングをやり直さずに Notion 公開だけ再実行したい場合 (Notion DB プロパティ追加後、トークン更新後、Notion 側でページを誤削除した後など) に使う。非冪等な REST API 呼び出しを内包するため kind=run として独立。

**入力**: `<skill-name-hint>` (`output/<hint>/` 配下が完成している前提)

**出力**:
- `output/<hint>/notion-url.txt` (上書き)
- `output/<hint>/notion-log.json` (上書き、`status: success|partial|failed`)

## Key Rules

1. **再公開専用**: ヒアリング・図解生成・JSON 整形は一切やらない。あくまで Notion REST API 呼び出しの run skill。
2. **All-or-Nothing**: PNG 1 枚でも欠ければ停止。`verify_notion_assets.py` 必須通過。
3. **Secret-Out-of-Repo**: トークンは Keychain からのみ取得。`plugins/skill-intake/scripts/keychain_get_secret.py` 経由 (環境変数渡し禁止、`notion_http.py` が内部で都度取得)。
4. **既存ページ非破壊**: `notion-log.json.page_id` が既存なら追記モード (PATCH children)、新規作成は明示 `--mode=new` のみ。

## Steps

```bash
HINT="$1"
test -d "output/$HINT" || { echo "intake artifacts not found"; exit 2; }

python3 plugins/skill-intake/scripts/keychain_get_secret.py --check
python3 plugins/skill-intake/scripts/verify_notion_schema.py \
  --database-id "${INTAKE_NOTION_DATABASE_ID:?INTAKE_NOTION_DATABASE_ID is required}" \
  --on-conflict skip-warn
python3 plugins/skill-intake/scripts/verify_notion_assets.py "output/$HINT/notion-manifest.json"
python3 plugins/skill-intake/scripts/render_notion_page.py "output/$HINT/intake.json" > "output/$HINT/notion-blocks.json"
python3 plugins/skill-intake/scripts/publish_notion_page.py \
  --intake "output/$HINT/intake.json" \
  --blocks "output/$HINT/notion-blocks.json" \
  > "output/$HINT/notion-publish-result.json"
```

`publish_notion_page.py` は `notion_http.py` 経由で都度 Keychain から取得し、シェル変数や環境変数にトークンが乗らない (`process.env.INTAKE_NOTION_TOKEN` への代入は禁止)。

## Gotchas

1. **`run-skill-intake-aggregator` のフェーズ 11 (Notion publish) と同じスクリプトを呼ぶ**: 再実装はしない。共有 `plugins/skill-intake/scripts/` を参照。
2. **DB スキーマ変更後は必ず `verify_notion_schema.py` を通す**: 既存ページが新プロパティに対応していないと public_url 取得後にカラム空のまま見える場合がある。
3. **PAT vs Integration の切替時はメモを残す**: `notion-log.json.auth_method` が前回と異なれば warning。

## Additional Resources

- `../run-skill-intake-aggregator/SKILL.md` — sibling (aggregator) skill
- `../run-skill-intake-aggregator/references/notion-integration.md` — Notion 連携正本
- `../run-skill-intake-aggregator/references/notion-db-schema.json` — DB スキーマ正本
- `../run-skill-intake-aggregator/references/keychain-setup.md` — Keychain セットアップ
