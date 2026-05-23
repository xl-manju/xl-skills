---
description: 既存 intake 結果に Claude Code チャット上で追加要望・改善を聞き取り、確定後に Notion ページを上書き反映する
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - AskUserQuestion
argument-hint: <hint> [--dry-run]
---

# /intake-revise <hint>

既に公開済みの intake (`output/<hint>/intake.md` + Notion ページ) に対して、ユーザーから追加要望・改善点を Claude Code チャット内で対話的に聞き取り、合意確定後に Notion ページを上書き反映するコマンド。

## フロー

1. **既存読み込み**: `output/<hint>/intake.json` / `intake.md` / `notion-url.txt` / `internal-analysis.json` をロード。Notion ページ ID を抽出。
2. **差分ヒアリング (Claude Code チャット内)**:
   - AskUserQuestion で「どの章に対する変更ですか？」(§1〜§11 の選択肢)
   - 「変更内容を一言で」(自由記述)
   - 「変更理由 (元の記述で何が不足だったか)」
   - 必要に応じて 5 軸 (出力先 / 情報源 / 共有相手 / 真の課題 / ナレッジ資産) の再確認
3. **内部解析**: `python3 plugins/skill-intake/scripts/analyze_user_intent.py output/<hint>` を再実行し、新しい `internal-analysis.json` を生成 (ユーザー入力の真意を裏で再抽出)。
4. **差分プレビュー**: 変更前後の該当章のテキスト / 図解 / パラメーターを diff 形式で Claude Code チャット上に提示。
5. **Gate R (Revise Gate)**: AskUserQuestion で `apply` / `re-revise` / `cancel` を選択。
6. **Notion 反映**:
   - `apply` → `python3 plugins/skill-intake/scripts/render-intake-final.py output/<hint>` で正本再生成
   - `python3 plugins/skill-intake/scripts/intake_publish_pipeline.py --intake output/<hint>/intake.json --manifest output/<hint>/notion-manifest.json --revise --page-id <既存ページ ID>` で **同一 Notion ページを PATCH 更新** (新規ページ作成しない)
   - `--dry-run` 指定時は Notion API 呼び出しを行わず差分のみ表示
7. **revision-log 追記**: `output/<hint>/revision-log.jsonl` に `{revision_no, timestamp, target_section, user_request, applied_changes, notion_page_url}` を 1 行追加。
8. **self-updater 連動**: `skill-intake-self-updater` を再起動し、本回 revision で出た「足りなかった質問」を question-bank に追記。

## 制約

- 同一 hint に対する revision は最大 5 回 (5 回を超えたら新規 hint で `/intake` 推奨)。
- Notion 公開フローと同じ All-or-Nothing 原則: PNG / mermaid が 1 つでも欠けたら旧版を維持。
- 既存ページの上書きは PATCH (delete-then-insert ではなく block 単位の update)。失敗時はロールバック JSON を `output/<hint>/notion-rollback-<rev>.json` に保存。
- ユーザーには内部解析 (`internal-analysis.json`) を直接見せない。ただし要約済みの「あなたの追加要望をこう理解しました」テキストは Gate R 直前に必ず提示。

## エラー処理

| exit | 意味 | 対処 |
|---|---|---|
| 0 | 正常反映 | revision-log に追記済み |
| 2 | Gate R で cancel | 既存ページ不変、ローカル変更も巻き戻し |
| 44 | Keychain Notion トークン取得失敗 | `keychain-setup.md` 参照 |
| 51 | Notion ページ ID 不一致 (notion-url.txt と DB のページ未一致) | 新規 hint で `/intake` を案内 |
| 60 | revision 回数上限超過 (>5) | 新規 hint へ移行 |

## related

- `/intake <topic>`: 新規ヒアリング
- `/intake-publish <hint>`: 既存 intake の再公開 (内容変更なし、再 render のみ)
- `/intake-status <hint>`: 現状確認
