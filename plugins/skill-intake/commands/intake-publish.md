---
description: 既存 intake を Notion DB に再公開 (run-notion-intake-publish) — ヒアリングはやり直さず Notion API 呼び出しのみ
argument-hint: "<skill-name-hint>"
---

# /intake-publish

`output/<skill-name-hint>/` に完成済みの intake 一式があることを前提に、Notion REST API での再公開だけを実行する。

## 振る舞い

1. `Skill(run-notion-intake-publish, args="$ARGUMENTS")` を呼ぶ。
2. Keychain → トークン取得 → DB スキーマ検証 → PNG 検証 → REST API ページ作成 → URL 保存。
3. 既存ページがある場合は追記モード (PATCH children)。新規作成は `--mode=new` を明示。

## 用途

- Notion DB プロパティ追加後の再公開
- PAT 更新 / Integration 切替後の動作確認
- Notion 側でページ誤削除した後の復旧
