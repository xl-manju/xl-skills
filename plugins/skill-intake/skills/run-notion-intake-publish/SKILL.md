---
name: run-notion-intake-publish
description: 既存 intake 成果物を Notion へ再公開したいとき、ヒアリングをやり直さず Notion 側だけ更新したいときに使う。
allowed-tools:
  - Read
  - Write
  - Bash
kind: run
disable-model-invocation: true
user-invocable: true
effect: external-mutation
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-22
audit-trigger: monthly
hierarchy_level: L1
rubric_refs:
  - ../run-skill-intake-aggregator/references/quality-rubric.md
  - references/republish-contract.md
  - run-skill-intake-aggregator
role_suffix: publish
owner: team-platform
since: 2026-05-20
---

# run-notion-intake-publish

## Purpose & Output Contract

`run-skill-intake-aggregator` が生成済みの `output/<hint>/` 一式を、ヒアリングを
やり直さず **Notion 側だけ** 再公開するための薄い wrapper skill。
実体は `plugins/skill-intake/scripts/intake_publish_pipeline.py` (単一発火点) を
1 回呼ぶだけで、render / quality_gate / publish の重複実装は禁止する。

- 入力: `<skill-name-hint>` (前提: `output/<hint>/intake.json` と
  `output/<hint>/notion-manifest.json` が既に存在)
- 出力: pipeline が `output/<hint>/` 配下に書き出す
  `notion-blocks.json` / `notion-publish-result.json` / `notion-url.txt` /
  `notion-log.json`
- 完了条件: pipeline exit 0 かつ `notion-url.txt` に有効 URL が書かれていること
  (exit 1=safe-skip / 2=hard-fail は `references/republish-contract.md` 参照)

## 既存スキルとの責務境界

| Skill / Script | 責務 | 本スキルとの境界 |
|---|---|---|
| `run-skill-intake-aggregator` | ヒアリング・5 軸抽出・図解・初回 publish | 初回は aggregator phase11、本 skill は **再公開専用** |
| `run-notion-fidelity-guard` | 公開直前の構造粒度検証 | 本 skill は呼び出し元として fidelity-guard `verdict=pass` を前提 |
| `intake_publish_pipeline.py` | render → quality_gate → publish の単一発火点 | 本 skill は引数を整え 1 回呼ぶだけ |

## Key Rules

1. **単一発火点**: publish パイプは `intake_publish_pipeline.py` のみ。本 skill から
   `render_notion_page.py` / `publish_notion_page.py` を直接呼ばない。
2. **再公開専用**: ヒアリング・図解生成・JSON 整形はやらない (aggregator の責務)。
3. **All-or-Nothing**: `verify_notion_assets.py` 通過必須。PNG 1 枚でも欠ければ停止。
4. **Secret-Out-of-Repo**: トークンは Keychain からのみ取得。環境変数・CLI 引数禁止。
5. **読み取り専用 (入力側)**: `intake.json` / `notion-manifest.json` を書き換えない。
6. **Progressive Disclosure**: 詳細ルールは `references/` に分割。SKILL.md は 200 行以下。

## Responsibilities (1 layer / wrapper)

| ID | 名前 | スコープ | LLM responsibility |
|---|---|---|---|
| R1 | republish-dispatch | precheck 4 種 → `intake_publish_pipeline.py` 起動 → exit code を呼び出し元へ伝搬 | なし (pure script orchestration) |

wrapper skill のため `prompts/` は持たない。判断は全て script の exit code に従う。

## Steps

### Step 1: precondition 検査

```bash
HINT="$1"
test -f "output/$HINT/intake.json"          || { echo "intake.json not found";          exit 2; }
test -f "output/$HINT/notion-manifest.json" || { echo "notion-manifest.json not found"; exit 2; }
```

### Step 2: 副作用前検査 (Keychain / Schema / Assets)

```bash
python3 plugins/skill-intake/scripts/keychain_get_secret.py --check
python3 plugins/skill-intake/scripts/verify_notion_schema.py --on-conflict skip-warn
python3 plugins/skill-intake/scripts/verify_notion_assets.py "output/$HINT/notion-manifest.json"
```

いずれか exit !=0 ならその時点で停止。詳細な exit 規約は
`references/republish-contract.md`。

### Step 3: pipeline 起動 (唯一の publish 発火点)

```bash
python3 plugins/skill-intake/scripts/intake_publish_pipeline.py \
  --intake   "output/$HINT/intake.json" \
  --manifest "output/$HINT/notion-manifest.json"
```

pipeline 内部で render → quality_gate → publish を順 exec し、いずれか
exit !=0 で停止。トークンは `notion_http.py` が Keychain から都度取得 (環境変数渡し禁止)。

## Abstraction Variables (量産時の差し替え点)

| 変数 | 既定値 | 用途 |
|---|---|---|
| `sink_pipeline_script` | `plugins/skill-intake/scripts/intake_publish_pipeline.py` | 単一発火点 |
| `secret_keychain_label` | `notion-intake-token` | Keychain ラベル |
| `manifest_filename` | `notion-manifest.json` | sink 別アセット manifest |
| `on_schema_conflict` | `skip-warn` | スキーマ差分時挙動 ∈ {skip-warn,fail,auto-migrate} |

仕様は `references/abstraction-contract.md`。

## Gotchas

1. **初回 publish には使わない**: 初回は aggregator phase11 を通す
   (図解生成・JSON 整形を伴うため)。本 skill は manifest 確定後の **再** 公開専用。
2. **fidelity-guard を skip しない**: canonical 更新後は fidelity-guard `verdict=pass`
   を確認してから本 skill を呼ぶ。pipeline 側ではガードしない契約。
3. **トークンは Keychain のみ**: `.env` / CLI 引数 / shell history へ載せない。
   うっかり `NOTION_TOKEN=xxx python3 ...` と打つと監査で落ちる。
4. **silent-fail 禁止**: pipeline は失敗時も `notion-log.json` を書く。読まずに retry しない。

## Additional Resources (Progressive Disclosure)

| 用途 | パス | when_to_read |
|---|---|---|
| 入力前提と exit 規約 | `references/republish-contract.md` | 起動前の前提条件 / exit code を確認するとき |
| 量産差し替え点 | `references/abstraction-contract.md` | 別 sink (Confluence 等) に流用するとき |
| Notion API 正本 | `../run-skill-intake-aggregator/references/notion-integration.md` | Notion property 名 / 認可フローを確認するとき |
| Keychain セットアップ | `../run-skill-intake-aggregator/references/keychain-setup.md` | トークン登録手順を確認するとき |
| 読み順マップ | `references/resource-map.yaml` | references 全体の Progressive Disclosure 地図 |

## 関連スキル

- `run-skill-intake-aggregator` — 初回 publish 担当 (phase11 で同 pipeline を呼ぶ正本)
- `run-notion-fidelity-guard` — 公開直前の構造粒度ガード (本 skill 起動前に pass 必須)
