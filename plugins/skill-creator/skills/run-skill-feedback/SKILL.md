---
name: run-skill-feedback
description: 既存スキルへの「こう直してほしい」要望を受け取って Notion 改善要望 DB にプッシュしたいとき、利用者発端のフィードバックループを起動したいときに使う。
triggers:
  - "skill改善要望"
  - "プラグイン要望"
  - "skill feedback"
  - "こう直してほしい"
  - "改善提案"
disable-model-invocation: false
user-invocable: true
argument-hint: "[plugin] [skill-name?]"
arguments: [plugin, skill_name]
allowed-tools:
  - Read
  - Bash(python3 *)
  - Bash(security *)
kind: run
prefix: run
effect: external-write
owner: team-platform
since: 2026-05-25
version: 0.1.0
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-25
audit-trigger: on-change
manifest: workflow-manifest.json
---

# run-skill-feedback

## Purpose & Output Contract

利用者が既存スキルに対して「こう直してほしい」と感じた瞬間に発火し、構造化フィードバックを Notion 改善要望 DB へ N:1 relation 付きでプッシュする。スキル一覧の `未対応要望数` rollup が自動更新され、優先度判断シグナルになる。

**入力**:
- `plugin` (必須): 対象プラグイン名。スキル一覧 DB の TITLE と一致すること
- `skill_name` (任意): プラグイン内の個別スキル名

**出力**: Notion 改善要望 DB の新規ページ 1 件 (URL を返す)

**冪等性**: 改善要望はタイトルが重複しても別レコードとして扱う(時系列ログとしての性質)。重複除去は人手で実施。

## Step 1: 要望収集 (対話)

以下を順に質問し、回答を構造化する:

1. **要望タイトル** (30字目安、何を直したいかを1行で)
2. **要望種別**: `バグ` / `機能追加` / `プロンプト改善` / `ドキュメント` / `挙動変更` の中から1つ
3. **やってほしいこと**: "こう直してほしい" を一段落で
4. **背景・困っていること**: なぜそれが必要か (任意)
5. **優先度**: `高` / `中` / `低` (デフォルト中)
6. **重要度**: `高` / `中` / `低` (デフォルト中)
7. **関連 PR/コミット URL** (任意)

## Step 2: 対象プラグインの存在確認

```bash
# スキル一覧 DB に対象プラグインが登録済みか確認
python3 scripts/notion-submit-improvement.py --plugin <plugin> --dry-run \
  --title "<title>" --type <type> --desire "<desire>"
```

存在しない場合は `run-build-skill --notion-register` を先に走らせる旨を案内して中断。

## Step 3: 改善要望投入

```bash
python3 scripts/notion-submit-improvement.py \
  --plugin "<plugin>" --skill-name "<skill_name>" \
  --title "<title>" --type "<type>" \
  --desire "<desire>" --background "<background>" \
  --priority "<priority>" --importance "<importance>" \
  --pr-url "<pr-url>"
```

token は macOS Keychain `notion-api-key` または環境変数 `NOTION_TOKEN` から取得 (スクリプト内で自動)。

## Step 4: 完了通知

投入された Notion ページ ID を提示し、起票者・担当者プロパティは Notion UI 側で人手追加するよう案内 (people 型は API 経由でメール宛指定不可のため)。

## 関連

- 上流: 利用者の口頭・Slack・PR コメントなど任意の発火源
- 下流: スキル一覧 DB の `未対応要望数` rollup → `skill-improve` skill による着手判断
- スキーマ正本: `doc/notion-schema/improvement-request.schema.json`
- 物理スクリプト: `scripts/notion-submit-improvement.py`
- 1:1 で生成元を辿りたい場合は `紐づくヒアリングシート` → `Skillヒアリングシート` DB
