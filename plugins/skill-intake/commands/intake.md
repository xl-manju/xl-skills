---
name: intake
description: ヒアリングインタビューを起動 (run-skill-intake-aggregator, 11 phase / 12 SubAgent) — 5 軸ヒアリング・図解マスト・Notion 公開まで一気通貫
argument-hint: "[topic]"
---

# /intake

ユーザー要望 `$ARGUMENTS` を受け取り、`run-skill-intake-aggregator` スキルを起動する。引数省略時は kickoff フェーズで対話的に topic を確定する。

## 振る舞い

1. `Skill(run-skill-intake-aggregator, args="$ARGUMENTS")` を呼ぶ。
2. スキル側の 11 phase / 12 SubAgent (skill-intake-kickoff → … → skill-intake-self-updater。Phase 4 は interviewer ⇄ purpose-excavator のペア稼働) が順次起動する。
3. Gate A (summarizer) でユーザー承認を得てから Notion 公開に進む。
4. 完了後、Markdown 正本 / JSON 副本 / Notion URL のパスを返す。

## 事前条件

- macOS Keychain に Notion トークンが `service=notion-api-key, account=skill-intake` で登録されていること。未登録の場合は `plugins/skill-intake/skills/run-skill-intake-aggregator/references/keychain-setup.md` を参照。
- 対象 Notion DB (環境変数 `INTAKE_NOTION_DATABASE_ID` で指定) に PAT / Integration が Connections 追加されていること。

## 失敗時

- exit 44 (Keychain 未登録): `keychain-setup.md` を案内
- HTTP 401/403 (Notion 認証/権限): PAT/Integration の Connections 設定を確認
- verify_notion_assets FAIL: 図解 PNG 不足。再生成案内
