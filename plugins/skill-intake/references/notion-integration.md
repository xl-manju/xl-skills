---
name: notion-integration
description: Notion REST API 直叩きによるページ作成とアセット添付の正本手順
type: reference
---

# Notion 連携手順

ヒアリング完了後、`skill-intake-notion-publisher` SubAgent が Notion REST API を直接呼んでページを作成する。MCP 経路は使わず REST 一本に統一する（環境非依存性・監査容易性のため）。Slack 通知は SubAgent からは行わず、必要時のみ公開後 hook で opt-in 配信する (詳細は末尾「公開後通知」節参照)。

## 全体フロー

```
intake.md / intake.json 完成
  ↓
[skill-intake-notion-publisher]
  ├─ scripts/keychain_get_secret.py notion    → トークン取得 (画面非表示)
  ├─ scripts/verify_notion_schema.py          → DB プロパティ検証
  ├─ scripts/prepare_notion_assets.py         → PNG/SVG manifest 生成
  ├─ scripts/verify_notion_assets.py          → All-or-Nothing 検証
  ├─ scripts/render_notion_page.py            → Notion ブロック JSON 生成
  ├─ scripts/publish_notion_page.py           → POST /v1/pages (notion_http 経由)
  └─ output/<hint>/notion-url.txt に URL 保存
```

## 認証

| 項目 | 既定値 | 上書き環境変数 |
|------|--------|----------------|
| Keychain service | `notion-api-key.xl-skills` | `INTAKE_KEYCHAIN_SERVICE` |
| Keychain account | `xl-skills` | `INTAKE_KEYCHAIN_ACCOUNT` |
| Notion DB ID | (必須・既定値なし) | `INTAKE_NOTION_DATABASE_ID` |
| Notion-Version | `scripts/notion_http.py` の `NOTION_VERSION` 定数を正本とする (現行 `2022-06-28`) | `INTAKE_NOTION_VERSION` |
| 認証種別 | PAT (`ntn_`) または Internal Integration (`secret_`) | — |

トークン取得は **必ず** `scripts/keychain_get_secret.py` 経由（内部で `/usr/bin/security find-generic-password` を呼ぶ唯一の窓口）。`INTAKE_NOTION_TOKEN` 等の環境変数からの直読みは禁止。コード／コミット履歴／`.env`／環境変数に平文を残さない。初回セットアップは `keychain-setup.md`。

`Notion-Version` ヘッダは `scripts/notion_http.py` の `NOTION_VERSION` で 1 箇所だけ定義しており、他スクリプトおよびドキュメントは必ずそこを参照する（重複定義禁止）。

## HTTP リクエスト例 (Python / REST)

通常は `scripts/publish_notion_page.py` を経由するため直接 HTTP を書く必要はない。下記は内部実装の参考（`notion_http.notion_fetch` が Authorization / Notion-Version / Content-Type を一元管理する）。

```python
# scripts/ 配下からの呼び出し例
from notion_http import notion_fetch, NotionHttpError
# トークンは notion_fetch 内で keychain_get_secret.get_secret() が解決する
res = notion_fetch(
    "/pages",
    method="POST",
    body={
        "parent": {"database_id": database_id},  # --database-id か INTAKE_NOTION_DATABASE_ID 経由
        "properties": {
            "名前": {"title": [{"type": "text", "text": {"content": skill_title_ja}}]}  # 日本語タイトル優先
        },
        "children": blocks,
    },
)
```

トークンを明示的に扱いたい場合のみ:

```python
from keychain_get_secret import get_secret
token = get_secret()  # service/account は INTAKE_KEYCHAIN_SERVICE / _ACCOUNT で上書き可
```

`urllib.request` / `requests` で直接 `https://api.notion.com/v1/...` を叩くコードを新規に書かないこと（`Notion-Version` の重複源を生むため）。必ず `notion_http.notion_fetch` を経由する。

## 公開先データベース

DB スキーマは `notion-db-schema.json` の正本に従う。検索/絞り込みに必要な 6 プロパティのみを DB 列とし、それ以外の項目はページ本文 (children) の「メタ情報」セクションに rich_text / toggle で記述する。

| # | プロパティ | 型 | 内容 |
|---|------------|----|------|
| 1 | 名前 | title | スキルの日本語タイトル (30 字以内、記号 → で工程を示す。例: `商談文字起こし→契約書自動生成→Slack配信`)。`meta.skill_title_ja` 優先、未指定なら `purpose.verb_object` から自動生成、最終フォールバックのみ英語 `skill_name_hint` |
| 2 | ステータス | select | 下書き / レビュー中 / 引き渡し済み / 構築済み / アーカイブ |
| 3 | パターン | select | 量産型 / 自動化 / ナレッジ / レビュー / その他 |
| 4 | 真の課題 | rich_text | 5 軸 true_problem の短文サマリ (200 字以内、詳細は本文へ) |
| 5 | ナレッジ資産タグ | multi_select | 思考プロセス / 暗黙知 / 判断基準 / テンプレ / チェックリスト / その他 |
| 6 | 作成日時 | created_time | Notion 自動 |

### 本文 children に移した項目

`publish_notion_page.py:build_extra_body_blocks()` がページ先頭の「メタ情報 (DB プロパティ補完)」セクションに次の項目を rich_text / toggle で出力する。

- 出力先 / 情報源 / 共有相手 (5 軸の残り)
- 図解枚数 / 価値実現スコア
- 担当者 / 更新日時
- ユーザープロファイル (toggle)
- 未解決事項 (toggle)
- 外部連携 (toggle)

DB が存在しない場合は `scripts/create_notion_database.py --mode=create` で作成。既存 DB との差分は `scripts/verify_notion_schema.py --on-conflict skip-warn|overwrite|fail-stop` で扱う（既定: `skip-warn`、破壊回避）。

## ページ構造

| 順 | ブロック種別 | 内容 |
|----|--------------|------|
| 1 | heading_1 | スキル名候補 |
| 2 | callout | 一言サマリ (JTBD 要約) |
| 3 | heading_2 + image | 目的 + 図 |
| 4 | heading_2 + image | ユーザー像 + persona-card |
| 5 | heading_2 + image | 5 軸回答 + comparison-table |
| 6 | heading_2 + image | 外部連携 + icon-grid |
| 7 | heading_2 + image | 想定フロー + numbered-steps |
| 8 | heading_2 + image | 価値・KPI + before-after |
| 9 | heading_2 + image | ナレッジ資産 + flowchart |
| 10 | heading_2 | 未解決事項 |
| 11 | code | intake.json 全文 |

## 画像埋め込み

Notion は SVG ネイティブ表示が不安定なため **PNG を必須**とする。

1. Mermaid / 独自 SVG を `scripts/render_to_image.py` で PNG 化
2. PNG を一旦どこかにアップロード（Notion file_upload API またはユーザー指定 CDN）
3. `image` ブロックとして添付。`caption` には one_liner（60 字以内）

```python
blocks.append({
    "type": "image",
    "image": {
        "type": "external",
        "external": {"url": png_url},
        "caption": [{"type": "text", "text": {"content": one_liner}}],
    },
})
```

## All-or-Nothing 公開ルール

`scripts/verify_notion_assets.py` が `notion-manifest.json` を読み、PNG 1 枚でも欠ければ **公開停止**する（部分公開を許さない）。SVG は補助でも可、PNG は必須。

## dry-run モード

`--dry-run` 指定時:

- `scripts/render_notion_page.py` の出力 JSON を `output/<hint>/notion-blocks.json` に保存（API 呼ばず）
- HTTP は一切発生させない
- Keychain 取得もスキップ可（`--no-secret`）

## エラー時のリトライ

| HTTP | 対処 |
|------|------|
| 401 | Keychain 内のトークン失効。`keychain-setup.md` を案内し停止 |
| 403 | Integration が DB にシェアされていない。手順を案内し停止 |
| 409 | DB プロパティ衝突。`verify_notion_schema.py` で再判定 |
| 429 | `Retry-After` 秒待機して 3 回までリトライ |
| 5xx | 1 秒・3 秒・9 秒で指数バックオフ・3 回まで |

## Gotcha

- **SVG 直貼り禁止**: PNG 化必須
- **PAT のチーム共有非推奨**: 個人 PAT を共有すると監査ログ汚染。チーム本番運用は Internal Integration またはサービスアカウント
- **secret スキャン**: 公開前に `hooks/pre-publish-secret-scrub.sh` が intake.json / notion-blocks.json を走査

## 公開後通知 (Slack 連携)

Notion 公開成功後、`hooks/post-publish-notify.sh` (PostToolUse hook) が
`output/<hint>/notion-url.txt` を読み、Slack incoming webhook へ最小ペイロードを送信する。

- ペイロード: `{"text":"intake published: <hint> -> <notion-url>"}` (1行・サマリ本文は含めない)
- Webhook 取得経路: `scripts/keychain_get_secret.py --service slack-incoming-webhook --account xl-skills`
  経由のみ。`security find-generic-password` 直叩きは settings.json の `permissions.deny` で禁止する
  (二段防御)。
- 未設定時の挙動: Keychain に webhook が無ければ silent skip (exit 0)。Slack 連携は opt-in。

### Webhook URL の Keychain 登録 (初回のみ)

通常運用では `security add-generic-password` も deny されるため、**初回セットアップだけ**
ユーザーが手元のターミナルで直接実行する (Claude 経由ではなく):

```bash
security add-generic-password \
  -s slack-incoming-webhook \
  -a xl-skills \
  -w 'https://hooks.slack.com/services/XXX/YYY/ZZZ' \
  -U
```

登録後の検証:

```bash
python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/scripts/keychain_get_secret.py \
  --service slack-incoming-webhook --account xl-skills --check
```

詳細は `plugins/skill-intake/hooks/README.md` を参照。
