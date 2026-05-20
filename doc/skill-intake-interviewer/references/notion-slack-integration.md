---
name: notion-slack-integration
description: Notion ページ作成と Slack 通知の MCP 呼び出し正本手順
type: reference
---

# Notion / Slack 連携手順

ヒアリング完了後、`notion-publisher` agent が Notion ページを作成し、`slack-notifier` agent が固定チャンネルへ通知する。両者とも MCP ツール経由で動作する。

## 1. 全体フロー

```
intake.md/intake.json 完成
  ↓
[notion-publisher]
  ├─ scripts/render_notion_page.js で Notion ブロック JSON 生成
  ├─ mcp__claude_ai_Notion__* でページ作成
  └─ output/<hint>/notion-url.txt に URL 保存
  ↓
[slack-notifier]
  ├─ scripts/compose_slack_message.js で本文生成（URL 含む）
  ├─ mcp__claude_ai_Slack__slack_send_message で投稿
  └─ output/<hint>/slack-log.json に応答ログ保存
```

## 2. Notion 連携

### 2.1 認証

| ツール | 用途 |
|-------|-----|
| `mcp__claude_ai_Notion__authenticate` | 初回認証起動 |
| `mcp__claude_ai_Notion__complete_authentication` | コールバック完了 |

未認証時は `notion-publisher` が認証を促し、ユーザー操作完了後に再開する。

### 2.2 公開先データベース

```
固定 DB: "Skill Intake Reports"
プロパティ:
  - Name (title): skill_name_hint
  - Status (select): Draft / Reviewed / Adopted
  - Pattern (select): A / B / C / D / E
  - User Level (select): 非技術 / 中級 / 上級
  - Created (date): generated_at
  - JTBD (rich_text): purpose.jtbd 整形
```

DB が存在しない場合は親ページ配下にページとして作成（ID は環境変数 `NOTION_PARENT_PAGE_ID`）。

### 2.3 ページ構造

| ブロック順 | 内容 |
|---------|------|
| 1 | H1: スキル名候補 |
| 2 | callout: 一言サマリ（JTBD要約） |
| 3 | H2: 目的 + Mermaid 図 |
| 4 | H2: ユーザー像 + persona-card SVG |
| 5 | H2: 5軸回答 + comparison-table SVG |
| 6 | H2: 外部連携 + icon-grid SVG |
| 7 | H2: 想定フロー + flowchart SVG |
| 8 | H2: 価値・KPI + before-after SVG |
| 9 | H2: 未解決事項 |
| 10 | code: intake.json 全文 |

### 2.4 SVG 埋込形式

Notion は SVG 直貼りに弱いため以下の方針で埋め込む。

1. SVG を `image/svg+xml;base64,` のデータ URL に変換
2. それを `image` ブロックとして添付
3. 同時に PNG も生成し、フォールバックとして併置
4. `caption` に「言いたい一言」（60字以内）

```javascript
// render_notion_page.js 内の擬似コード
const svgDataUrl = `data:image/svg+xml;base64,${base64(svg)}`;
blocks.push({
  type: "image",
  image: {
    type: "external",
    external: { url: svgDataUrl },
    caption: [{ type: "text", text: { content: oneLiner } }]
  }
});
```

## 3. Slack 連携

### 3.1 固定チャンネル

| 設定キー | デフォルト |
|--------|---------|
| 環境変数 | `INTAKE_SLACK_CHANNEL` |
| デフォルト値 | `#skill-intake-reports` |
| フォールバック | `#general`（要 README 警告） |

チャンネル指定は **slack_send_message の `channel` 引数**にチャンネル名（`#`付き）または ID をそのまま渡す。

### 3.2 投稿フォーマット

```
:memo: 新しいスキル要件ヒアリングが完了しました
*スキル名候補*: <skill_name_hint>
*パターン*: A（対話生成）
*ユーザー*: 中級／個人事業主／業務
*JTBD*:
> When <when>
> I want to <want_to>
> So I can <so_i_can>
*真の課題*: <true_problem.answer>
*Notion*: <notion_url|ヒアリングシートを開く>
*次アクション*: skill-creator を fast-track モードで起動
```

絵文字は `:memo:` のみ Slack 標準絵文字を使う（FontAwesome ルールはあくまで生成図解側、Slack 通知は対象外）。本文には Markdown ではなく Slack mrkdwn を使用。

### 3.3 呼び出し例

```javascript
mcp__claude_ai_Slack__slack_send_message({
  channel: process.env.INTAKE_SLACK_CHANNEL || "#skill-intake-reports",
  text: composedMessage,
  unfurl_links: false
});
```

応答 JSON は `output/<hint>/slack-log.json` に保存。`ts`（タイムスタンプ）が後続のスレッドぶら下げに使える。

### 3.4 失敗時のリトライ

| エラー | 対処 |
|------|-----|
| channel_not_found | デフォルト #general へフォールバック＋警告 |
| not_authed | `slack-authenticator` で認証起動 |
| rate_limited | `Retry-After` 秒待機後リトライ（最大3回） |

## 4. dry-run モード

`--dry-run` 指定時は以下を実施。

- Notion: render_notion_page.js の出力 JSON を `output/<hint>/notion-blocks.json` に保存（API 呼ばず）
- Slack: compose_slack_message.js の本文を `output/<hint>/slack-message.txt` に保存（投稿せず）
