---
last_fetched: pending
source_urls:
  - https://docs.claude.com/en/docs/claude-code/skills
  - https://docs.claude.com/en/docs/claude-code/settings
update_cadence: weekly
owner: team-skills
status: pending-fetch
---

# Claude Code 公式 YAML frontmatter 仕様キャッシュ

本ファイルは Claude Code 公式 frontmatter 仕様の **週次キャッシュ** である。SKILL.md frontmatter で参照される唯一のローカル正本。

## 取得方針

- 自動化は意図的に見送り (2026-05-18 判断)。公式が機械可読配布 (llms.txt / 公開 API) を提供していないため、目視取得 + 差分記録の人手プロセスを公式運用とする。
- 週次レビュー担当者 (`owner: team-skills`) が `ref-yaml-spec-fetcher/SKILL.md` の「手動取得手順」に従って本ファイルを更新する。
- 30 日経過しても更新が無い場合は `last_fetched:` のみ更新し「変更なし確認」と記録する。

## 本文 (pending-fetch)

初回取得は `ref-yaml-spec-fetcher` の手動取得手順 Step 1〜2 に従い、上記 `source_urls` から frontmatter 仕様セクションを目視取得して本セクションに転記すること。転記後は frontmatter の `last_fetched:` を当日 ISO 日付に更新する。

差分が発生した場合は `spec-diff-history.md` に追記する (日付・変更要約・出典 URL)。
