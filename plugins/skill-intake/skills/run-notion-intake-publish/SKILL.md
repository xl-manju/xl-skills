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
  - ../../references/quality-rubric.md
  - references/republish-contract.md
responsibility_refs:
  - references/republish-contract.md
  - references/abstraction-contract.md
schema_refs: []
manifest: references/resource-map.yaml
role_suffix: null
owner: team-platform
since: 2026-05-20
version: 0.1.0
---

# run-notion-intake-publish

## Purpose & Output Contract

`run-skill-intake` が生成済みの `output/<hint>/` 一式を、ヒアリングを
やり直さず **Notion 側だけ** 再公開するための薄い wrapper skill。
実体は `plugins/skill-intake/scripts/intake_publish_pipeline.py` (単一発火点) を
1 回呼ぶだけで、render / quality_gate / publish の重複実装は禁止する。

**起動形態 (disable-model-invocation wrapper 特性)**: 本 skill は
`disable-model-invocation: true` のため LLM 自律起動は不可。呼び出し元 (人間 or
上位 skill) が **Bash script 経由** で直接 dispatch する。LLM 判断面は持たないため
`prompts/` および `schemas/` は意図的に保持しない (R1 は pure script orchestration)。

- 入力: `<skill-name-hint> [--page-url <url>|--page-id <id>] [--database-id <db_id>]` (前提: `output/<hint>/intake.json` と
  `output/<hint>/notion-manifest.json` が既に存在)
- 出力: pipeline が `output/<hint>/` 配下に書き出す
  `notion-blocks.json` / `notion-publish-result.json` / `notion-url.txt` /
  `notion-log.json`
- 完了条件: pipeline exit 0 かつ `notion-url.txt` に有効 URL が書かれていること
  (exit 1=safe-skip / 2=hard-fail は `references/republish-contract.md` 参照)

## 既存スキルとの責務境界

| Skill / Script | 責務 | 本スキルとの境界 |
|---|---|---|
| `run-skill-intake` | ヒアリング・5 軸抽出・図解・初回 publish | 初回は run-skill-intake phase11、本 skill は **再公開専用** |
| `run-notion-fidelity-guard` | 公開直前の構造粒度検証 | 本 skill は呼び出し元として fidelity-guard `verdict=pass` を前提 |
| `intake_publish_pipeline.py` | render → quality_gate → publish の単一発火点 | 本 skill は引数を整え 1 回呼ぶだけ |

## Key Rules

1. **単一発火点**: publish パイプは `intake_publish_pipeline.py` のみ。本 skill から
   `render_notion_page.py` / `publish_notion_page.py` を直接呼ばない。単一発火点の SSOT 定義は `../run-skill-intake/SKILL.md` 「単一発火点」項 (ゴールシークループ内) を参照。
2. **再公開専用**: ヒアリング・図解生成・JSON 整形はやらない (aggregator の責務)。
3. **All-or-Nothing**: `verify_notion_assets.py` 通過必須。PNG 1 枚でも欠ければ停止。
4. **Secret-Out-of-Repo**: トークンは Keychain からのみ取得。環境変数・CLI 引数禁止。
5. **読み取り専用 (入力側)**: `intake.json` / `notion-manifest.json` を書き換えない。
6. **Progressive Disclosure**: 詳細ルールは `references/` に分割し、SKILL.md 本体は
   起動契約 (入出力 / Steps / ゴールシーク) に絞る。

## Responsibilities (1 layer / wrapper)

| ID | 名前 | スコープ | LLM responsibility |
|---|---|---|---|
| R1 | republish-dispatch | precheck 4 種 → `intake_publish_pipeline.py` 起動 → exit code を呼び出し元へ伝搬 | なし (pure script orchestration) |

wrapper skill のため `prompts/` は持たない。判断は全て script の exit code に従う。

## Steps

### Step 0: 引数正規化

```bash
HINT=""
PAGE_ID=""
PAGE_URL=""
DATABASE_ID=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --page-id) shift; PAGE_ID="${1:-}" ;;
    --page-url) shift; PAGE_URL="${1:-}" ;;
    --database-id) shift; DATABASE_ID="${1:-}" ;;
    --*) echo "unknown option: $1" >&2; exit 2 ;;
    *) if [ -z "$HINT" ]; then HINT="$1"; else echo "unexpected arg: $1" >&2; exit 2; fi ;;
  esac
  shift
done
test -n "$HINT" || { echo "skill-name-hint is required"; exit 2; }
```

### Step 1: precondition 検査

```bash
test -f "output/$HINT/intake.json"          || { echo "intake.json not found";          exit 2; }
test -f "output/$HINT/notion-manifest.json" || { echo "notion-manifest.json not found"; exit 2; }
```

### Step 2: 副作用前検査 (Keychain / Schema / Assets)

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}"
python3 "$PLUGIN_ROOT/scripts/keychain_get_secret.py" --check
python3 "$PLUGIN_ROOT/scripts/verify_notion_schema.py" --on-conflict skip-warn ${DATABASE_ID:+--database-id "$DATABASE_ID"}
python3 "$PLUGIN_ROOT/scripts/verify_notion_assets.py" "output/$HINT/notion-manifest.json"
```

いずれか exit !=0 ならその時点で停止。詳細な exit 規約は
`references/republish-contract.md`。

### Step 3: pipeline 起動 (唯一の publish 発火点)

```bash
# 再公開は update 専用。明示 URL が無い場合だけ既存 notion-url.txt を使い、--revise で create を禁止する
# (page_id 解決不能なら pipeline が exit 51。新規ページ量産を構造的に封鎖)。
if [ -z "$PAGE_URL" ]; then
  PAGE_URL="$(cat "output/$HINT/notion-url.txt" 2>/dev/null || true)"
fi
EXTRA_ARGS=()
[ -n "$DATABASE_ID" ] && EXTRA_ARGS+=(--database-id "$DATABASE_ID")
[ -n "$PAGE_ID" ] && EXTRA_ARGS+=(--page-id "$PAGE_ID")
[ -n "$PAGE_URL" ] && EXTRA_ARGS+=(--page-url "$PAGE_URL")
python3 "$PLUGIN_ROOT/scripts/intake_publish_pipeline.py" \
  --intake   "output/$HINT/intake.json" \
  --manifest "output/$HINT/notion-manifest.json" \
  --revise \
  "${EXTRA_ARGS[@]}"
```

pipeline 内部で render → quality_gate → publish を順 exec し、いずれか
exit !=0 で停止。トークンは `notion_http.py` が Keychain から都度取得 (環境変数渡し禁止)。
publish 前に `run-notion-fidelity-guard/scripts/validate-notion-fidelity.py` を必ず実行し、`verdict=pass` 以外は Notion API mutation へ進まない。
`--revise` により既存 `notion-publish-result.json` の page_id が期待値 (notion-url.txt) と
一致するか quality_gate で検査され (page_id_consistency)、別ページへの化け (orphan) を publish 前に FAIL させる。

## Abstraction Variables (量産時の差し替え点)

| 変数 | 既定値 | 用途 |
|---|---|---|
| `sink_pipeline_script` | `plugins/skill-intake/scripts/intake_publish_pipeline.py` | 単一発火点 |
| `secret_keychain_label` | `notion-intake-token` | Keychain ラベル |
| `manifest_filename` | `notion-manifest.json` | sink 別アセット manifest |
| `on_schema_conflict` | `skip-warn` | スキーマ差分時挙動 ∈ {skip-warn,fail,auto-migrate} |

仕様は `references/abstraction-contract.md`。

## ゴールシーク実行

呼び出し元 (人間 or 上位 skill) が「再公開を完遂できたか」を自己判定するための
3 層プロトコル。本 skill は wrapper のため LLM の自由裁量は持たず、各層は
script exit code と成果物ファイル存在で機械判定する。

### Goal (達成すべきゴール)

`output/<hint>/notion-url.txt` に有効な Notion URL が書かれ、`notion-log.json` の
`status` が `published` で、対応する Notion ページが update mode で同一 `page_id`
を保ったまま最新 intake/manifest を反映していること。再公開は **冪等** であり、
同一 intake/manifest で複数回起動しても新規ページを増やさず既存ページを更新する。

### Why (なぜそのゴールか)

intake 成果物は canonical source として `output/<hint>/` 配下で管理され、Notion は
読み手向けの **派生 view**。view を作り直すたびに `page_id` を変えると外部参照
リンクが破壊されるため、再公開は常に「同一 page を update する」契約を採る。
これにより canonical 修正 → 再公開のループが安全に回り、ヒアリング工程を再消費
しない (aggregator 責務との重複排除)。

### Checklist (機械判定可能な完了条件)

| # | 検査 | 合格基準 |
|---|---|---|
| 1 | pipeline exit code | `intake_publish_pipeline.py` が exit 0 |
| 2 | URL ファイル | `output/<hint>/notion-url.txt` が非空かつ `https://www.notion.so/` で始まる |
| 3 | ログ status | `output/<hint>/notion-log.json` の `status == "published"` |
| 4 | page_id 不変 | `notion-publish-result.json.page_id` が前回値と一致 (初回除く) |
| 5 | precheck 全 pass | Keychain / schema / assets の 3 検査が全て exit 0 |
| 6 | 再公開拒否ルール非該当 | `references/republish-contract.md` の拒否条件全て非該当 |

いずれか不合格なら exit code (1=skip / 2=hard-fail) を呼び出し元へ伝搬し停止。

## Gotchas

1. **初回 publish には使わない**: 初回は run-skill-intake phase11 を通す
   (図解生成・JSON 整形を伴うため)。本 skill は manifest 確定後の **再** 公開専用。
2. **fidelity-guard を skip しない**: pipeline 内で fidelity-guard を必ず実行し、
   `verdict=pass` 以外は Notion API mutation へ進まない。
3. **トークンは Keychain のみ**: `.env` / CLI 引数 / shell history へ載せない。
   うっかり `NOTION_TOKEN=xxx python3 ...` と打つと監査で落ちる。
4. **silent-fail 禁止**: pipeline は失敗時も `notion-log.json` を書く。読まずに retry しない。

## Additional Resources (Progressive Disclosure)

| 用途 | パス | when_to_read |
|---|---|---|
| 入力前提と exit 規約 | `references/republish-contract.md` | 起動前の前提条件 / exit code を確認するとき |
| 量産差し替え点 | `references/abstraction-contract.md` | 別 sink (Confluence 等) に流用するとき |
| Notion API 正本 | `../../references/notion-integration.md` | Notion property 名 / 認可フローを確認するとき |
| Keychain セットアップ | `../../references/keychain-setup.md` | トークン登録手順を確認するとき |
| 読み順マップ | `references/resource-map.yaml` | references 全体の Progressive Disclosure 地図 |

## 関連スキル

- `run-skill-intake` — 初回 publish 担当 (phase11 で同 pipeline を呼ぶ正本)
- `run-notion-fidelity-guard` — 公開直前の構造粒度ガード (本 skill 起動前に pass 必須)
