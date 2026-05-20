---
name: notion-integration
description: Notion REST API 直叩きによるページ作成とアセット添付の正本手順
type: reference
---

# Notion 連携手順

ヒアリング完了後、`skill-intake-notion-publisher` SubAgent が Notion REST API を直接呼んでページを作成する。MCP は使わない（環境非依存性のため）。Slack 通知は本スキルのスコープ外。

## 全体フロー

```
intake.md / intake.json 完成
  ↓
[skill-intake-notion-publisher]
  ├─ scripts/keychain_get_secret.js notion    → トークン取得 (画面非表示)
  ├─ scripts/verify_notion_schema.js          → DB プロパティ検証
  ├─ scripts/prepare_notion_assets.js         → PNG/SVG manifest 生成
  ├─ scripts/verify_notion_assets.js          → All-or-Nothing 検証
  ├─ scripts/render_notion_page.js            → Notion ブロック JSON 生成
  ├─ fetch POST https://api.notion.com/v1/pages → ページ作成
  └─ output/<hint>/notion-url.txt に URL 保存
```

## 認証

| 項目 | 既定値 | 上書き環境変数 |
|------|--------|----------------|
| Keychain service | `notion-api-key` | `INTAKE_KEYCHAIN_SERVICE` |
| Keychain account | `skill-intake-interviewer` | `INTAKE_KEYCHAIN_ACCOUNT` |
| Notion DB ID | `36607a0cd18c80bf9effc74aa736645c` | `INTAKE_NOTION_DATABASE_ID` |
| Notion-Version | `2022-06-28` | `INTAKE_NOTION_VERSION` |
| 認証種別 | PAT (`ntn_`) または Internal Integration (`secret_`) | — |

トークンは **必ず** `scripts/keychain_get_secret.js` 経由で都度取得。コード／コミット履歴／`.env`／環境変数に平文を残さない。初回セットアップは `keychain-setup.md`。

## HTTP リクエスト例

```javascript
const token = await getSecretFromKeychain();  // /usr/bin/security 経由
const res = await fetch("https://api.notion.com/v1/pages", {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${token}`,
    "Notion-Version": process.env.INTAKE_NOTION_VERSION || "2022-06-28",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    parent: { database_id: process.env.INTAKE_NOTION_DATABASE_ID },
    properties: { Name: { title: [{ text: { content: skillNameHint } }] } },
    children: blocks
  })
});
```

## 公開先データベース

DB スキーマは `notion-db-schema.json` の正本に従う。

| プロパティ | 型 | 内容 |
|------------|----|------|
| Name | title | skill_name_hint |
| Status | select | Draft / Reviewed / Adopted |
| Pattern | select | A / B / C / D / E |
| User Level | select | 非技術 / 中級 / 上級 |
| Created | date | generated_at |
| JTBD | rich_text | purpose.jtbd 整形 |

DB が存在しない場合は `scripts/create_notion_database.js --mode=create` で作成。既存 DB との差分は `scripts/verify_notion_schema.js --on-conflict skip-warn|overwrite|fail-stop` で扱う（既定: `skip-warn`、破壊回避）。

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

1. Mermaid / 独自 SVG を `scripts/render_to_image.js` で PNG 化
2. PNG を一旦どこかにアップロード（Notion file_upload API またはユーザー指定 CDN）
3. `image` ブロックとして添付。`caption` には one_liner（60 字以内）

```javascript
blocks.push({
  type: "image",
  image: {
    type: "external",
    external: { url: pngUrl },
    caption: [{ type: "text", text: { content: oneLiner } }]
  }
});
```

## All-or-Nothing 公開ルール

`scripts/verify_notion_assets.js` が `notion-manifest.json` を読み、PNG 1 枚でも欠ければ **公開停止**する（部分公開を許さない）。SVG は補助でも可、PNG は必須。

## dry-run モード

`--dry-run` 指定時:

- `scripts/render_notion_page.js` の出力 JSON を `output/<hint>/notion-blocks.json` に保存（API 呼ばず）
- HTTP は一切発生させない
- Keychain 取得もスキップ可（`--no-secret`）

## エラー時のリトライ

| HTTP | 対処 |
|------|------|
| 401 | Keychain 内のトークン失効。`keychain-setup.md` を案内し停止 |
| 403 | Integration が DB にシェアされていない。手順を案内し停止 |
| 409 | DB プロパティ衝突。`verify_notion_schema.js` で再判定 |
| 429 | `Retry-After` 秒待機して 3 回までリトライ |
| 5xx | 1 秒・3 秒・9 秒で指数バックオフ・3 回まで |

## Gotcha

- **SVG 直貼り禁止**: PNG 化必須
- **PAT のチーム共有非推奨**: 個人 PAT を共有すると監査ログ汚染。チーム本番運用は Internal Integration またはサービスアカウント
- **secret スキャン**: 公開前に `hooks/pre-publish-secret-scrub.sh` が intake.json / notion-blocks.json を走査
