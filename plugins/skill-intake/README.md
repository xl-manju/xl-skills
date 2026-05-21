# skill-intake plugin

skill-creator の前段ヒアリングを **非技術者にも開く** Claude Code plugin。「スキルを作りたい」という曖昧な要望から、本人も言語化できていない真の課題を引き出し、**Markdown 正本 + JSON 副本 + Notion ページ**の3成果物を一括生成します。

このREADMEは **上から順に手順を実行するだけで導入完了**するよう構成されています。途中スキップせず、各ステップ末尾の **✅ 確認** を必ず通してから次へ進んでください。

---

## Non-Secrets（漏洩可情報）

以下は **スキル内・コード・README に直書きしてよい** 情報です。毎回ユーザーに問い合わせるのを回避するため、`schema.json` や設定ファイルに同梱されています。万一漏洩しても単体では不正利用できません。

| 項目 | 値（例） | 格納場所 | 漏洩可否 |
|---|---|---|---|
| Notion Database ID | `36607a0cd18c80bf9effc74aa736645c` | `schema.json` の `database_id_default` | OK |
| Keychain service 名 | `INTAKE_NOTION_TOKEN`（旧名: `notion-api-key`） | コード/設定に直書き | OK |
| Keychain account 名 | `skill-intake` | コード/設定に直書き | OK |
| Notion-Version ヘッダ | `2022-06-28` | コード/設定に直書き | OK |

**これらはスキル内に直書きしてよい。毎回の問い合わせを回避するため。**

### 機密情報（Keychain のみ）との対比

以下は **絶対にコード/コミット/環境変数/ログに残さない**。Keychain（ローカル）のみで保管:

| 項目 | 格納場所 | 漏洩可否 |
|---|---|---|
| Notion API トークン本体（`secret_xxx...`） | macOS Keychain | **NG** |
| Slack Incoming Webhook URL | macOS Keychain | **NG** |

Non-Secrets は「どの DB か」「どの Keychain エントリか」を指す **ポインタ** であり、機密実体は常に Keychain 側にあります。

---

## 📋 目次

1. [前提条件チェック](#1-前提条件チェック)
2. [Notion 側の準備](#2-notion-側の準備)
3. [macOS Keychain にシークレット登録](#3-macos-keychain-にシークレット登録)
4. [plugin インストール](#4-plugin-インストール)
5. [Claude Code 設定の適用](#5-claude-code-設定の適用)
6. [動作確認テスト](#6-動作確認テスト)
7. [初回ヒアリング実行](#7-初回ヒアリング実行)
8. [トラブルシューティング](#8-トラブルシューティング)
9. [構成リファレンス](#9-構成リファレンス)

---

## 1. 前提条件チェック

以下が揃っていることを確認してください。

| 項目 | 確認コマンド | 期待値 |
|---|---|---|
| macOS | `uname` | `Darwin` |
| Python 3 (macOS 標準) | `/usr/bin/python3 --version` | `Python 3.9` 以上（外部 pip パッケージ不要） |
| Claude Code CLI | `claude --version` | バージョン表示 |
| Git | `git --version` | バージョン表示 |
| Notion アカウント | https://notion.so にログイン可能 | — |

✅ **確認**: 上記すべて満たしている。満たさない場合は各公式サイトでインストール。

---

## 2. Notion 側の準備

### 2-1. Notion Internal Integration を作成

1. https://www.notion.so/profile/integrations を開く
2. 「**+ New integration**」をクリック
3. 以下を入力:
   - **Name**: `skill-intake`（任意）
   - **Associated workspace**: 利用するワークスペースを選択
   - **Type**: `Internal`
4. 「**Save**」をクリック
5. 表示された「**Internal Integration Secret**」を **コピーして安全な場所にメモ**。あとで Keychain に登録します（実値はこの README には絶対書き残さないでください）。

✅ **確認**: シークレットを手元にメモした。

### 2-2. Notion データベースを作成

1. Notion ワークスペースで新規ページを作成
2. ページ内で `/database` と入力 → `Database - Full page` を選択
3. データベース名を「**Skill Intake**」(任意) に設定
4. デフォルトのプロパティはそのままでOK。後で `verify_notion_schema.py` が必要に応じて追加します
5. データベースを開いた状態で、右上「**...**」→「**Connections**」→「**+ Add connections**」→ 先ほど作成した `skill-intake` Integration を選択して接続

✅ **確認**: データベースに Integration が Connect されている。

### 2-3. データベース ID を取得

データベースをフルページで開き、URL を確認:

```
https://www.notion.so/<workspace>/<32文字の英数字>?v=...
                                   └─ これが Database ID ─┘
```

URL の `?v=` 直前の **32文字の英数字** が Database ID です。コピーしておいてください（実値はこの README には絶対書き残さないでください）。

✅ **確認**: 32文字の Database ID を手元にメモした。

### 2-4. (任意) Slack 公開通知を使う場合

公開成功時に Slack 通知を受け取りたい場合のみ:

1. Slack ワークスペースで https://api.slack.com/apps から「**Create New App**」→「**From scratch**」
2. App name: `skill-intake-notifier`、ワークスペース選択
3. 左メニュー「**Incoming Webhooks**」→ ON にして「**Add New Webhook to Workspace**」
4. 通知先チャンネルを選び「**Allow**」
5. 生成された Webhook URL (`https://hooks.slack.com/services/...`) をメモ

✅ **確認**: Slack を使わない場合はスキップしてOK（自動で no-op）。

---

## 3. macOS Keychain にシークレット登録

**重要**: シークレットは Keychain にのみ保管します。`.env`・コード・コミット履歴・環境変数には絶対に置きません。

### 3-1. Notion PAT を登録

ターミナルで以下を実行:

```bash
security add-generic-password \
  -s notion-api-key \
  -a skill-intake \
  -T '' -U
```

パスワードプロンプトに **2-1 でメモした Notion Integration Secret** を貼り付けて Enter（画面には表示されません）。

### 3-2. (任意) Slack Webhook を登録

2-4 で Webhook を作成した場合のみ:

```bash
security add-generic-password \
  -s slack-incoming-webhook \
  -a skill-intake \
  -T '' -U
```

プロンプトに Webhook URL を貼り付けて Enter。

### 3-3. 取得テスト

```bash
security find-generic-password -s notion-api-key -a skill-intake -w >/dev/null && echo OK || echo NG
# → OK と表示されれば取得成功（トークン本体は画面に出しません）
```

✅ **確認**: Notion トークンが Keychain から取得できる。

---

## 4. plugin インストール

3つの方式があります。**A方式（Marketplace経由）が推奨**です。

### 方式A: GitHub Marketplace から install（推奨）

リポジトリが公開されている前提。Claude Code セッション内で:

```
/plugin marketplace add <GITHUB_OWNER>/<REPO_NAME>
/plugin install skill-intake@xl-skills
```

例（このリポジトリの場合）:
```
/plugin marketplace add xl-manju/xl-skills
/plugin install skill-intake@xl-skills
```

これで agents/commands/hooks/skills すべて自動有効化されます。

### 方式B: ローカル開発（リポジトリを clone してそのまま使う）

```bash
git clone https://github.com/<GITHUB_OWNER>/<REPO_NAME>.git
cd <REPO_NAME>
# .claude-plugin/marketplace.json が同梱されているので、Claude Code 起動時に自動検出
claude
```

Claude Code 起動後、セッション内で:
```
/plugin marketplace add ./
/plugin install skill-intake@xl-skills
```

### 方式C: symlink で連結（既に worktree 内で開発中の場合）

このリポジトリ内で開発作業をしている場合、`.claude/` 配下に既に symlink が貼られています。追加作業不要で `/intake` などが使えます。

新規 worktree でセットアップする場合は:

```bash
cd .claude/skills && \
  ln -sfn ../../plugins/skill-intake/skills/run-skill-intake-aggregator run-skill-intake-aggregator && \
  ln -sfn ../../plugins/skill-intake/skills/run-notion-intake-publish run-notion-intake-publish && \
cd ../agents && \
  for f in ../../plugins/skill-intake/agents/skill-intake-*.md; do ln -sfn "$f" "$(basename $f)"; done && \
cd ../commands && \
  for f in ../../plugins/skill-intake/commands/*.md; do ln -sfn "$f" "$(basename $f)"; done
```

✅ **確認**: Claude Code セッションで `/help` を実行し、`/intake`・`/intake-publish`・`/intake-status` が表示される。

---

## 5. Claude Code 設定の適用

### 5-1. 環境変数（任意・上書き用）

**通常運用では設定不要です。** `schema.json` の `database_id_default` がそのまま使われます。

`INTAKE_NOTION_DATABASE_ID` などの環境変数による override は **CI/staging 限定の用途** です（本番 DB と切り分けたい場合）。通常の開発・ローカル運用では schema.json の既定値で動作します。

CI/staging で上書きしたい場合のみ、シェルプロファイル（`~/.zshrc` 等）または CI 環境で:

```bash
# 任意（CI/staging 限定）: 本番と異なる DB / Keychain / Notion-Version を使う場合
# export INTAKE_NOTION_DATABASE_ID="<別環境の 32文字 Database ID>"
# export INTAKE_KEYCHAIN_SERVICE="notion-api-key"
# export INTAKE_KEYCHAIN_ACCOUNT="skill-intake"
# export INTAKE_NOTION_VERSION="2022-06-28"
```

### 5-2. permissions.deny を有効化（二段防御）

Keychain への security コマンド直叩きを禁止します（Claude が誤ってシークレットを読み出すのを防止）。

`plugins/skill-intake/.claude/settings.json.example` を見本に、お使いの `~/.claude/settings.json` または プロジェクトの `.claude/settings.json` に **以下のキーをマージ**してください:

```json
{
  "permissions": {
    "deny": [
      "Bash(security find-generic-password:*)",
      "Bash(security add-generic-password:*)"
    ]
  }
}
```

既存の `permissions.deny` 配列がある場合は要素追加。なければキーごと追加。

> 💡 **なぜ deny するの？**: Notion トークンや Slack Webhook の取得は `scripts/keychain_get_secret.py` 経由のみに集約する設計です。Claude が直接 `security` コマンドを実行できるとシークレットがログ/履歴に漏れる可能性があるため、Bash 経路を塞ぎます。

✅ **確認**: `cat ~/.claude/settings.json | grep -A2 deny` で `security` 行が存在する。

---

## 6. 動作確認テスト

順番に実行し、すべて成功することを確認してください。

### 6-1. Keychain 取得

```bash
python3 plugins/skill-intake/scripts/keychain_get_secret.py --check
```
→ `OK: トークン取得成功` が出れば成功（トークン本体や prefix は表示されません）。`exit 44` ならステップ3に戻る。

### 6-2. Notion DB スキーマ検証

```bash
python3 plugins/skill-intake/scripts/verify_notion_schema.py \
  --database-id "$INTAKE_NOTION_DATABASE_ID" \
  --on-conflict skip-warn
```
→ 200 OK + プロパティ列挙が出れば成功。403 なら 2-2 の Connections 設定を見直し。

### 6-3. Slack hook テスト（任意）

3-2 で Slack を登録した場合:

```bash
python3 plugins/skill-intake/scripts/keychain_get_secret.py \
  --service slack-incoming-webhook --account skill-intake --check
```
→ `OK` なら Slack 通知も自動で有効。`exit 44` でも公開フローは silent skip で続行されます。

✅ **確認**: 6-1, 6-2 が成功した。Slack 利用者は 6-3 も成功した。

---

## 7. 初回ヒアリング実行

Claude Code セッション内で:

```
/intake デイリーレポート生成スキルを作りたい
```

12 phase が順次実行されます:

1. `skill-intake-kickoff` — パターン選択・深度確認
2. `skill-intake-assumption-challenger` — 仮説扱い・表層を疑う
3. `skill-intake-user-profiler` — 熟練度推定
4. `skill-intake-interviewer` ⇄ `skill-intake-purpose-excavator` — 対話（最大5往復）
5. `skill-intake-option-presenter` — 外部連携カタログ提示
6. `skill-intake-visualizer` — 1〜3図/セクション配置
7. `skill-intake-summarizer` — Gate A サマリ → 承認依頼
8. `skill-intake-next-action-advisor` — skill-creator 引き渡しモード判定
9. `skill-intake-handoff` — Markdown 正本 + JSON 副本生成
10. `skill-intake-notion-publisher` — Notion REST API でページ作成
11. `skill-intake-self-updater` — question-bank 自己更新
12. cross-check + 公開完了

完了後、`output/<hint>/` に以下が生成されます:

| ファイル | 用途 |
|---|---|
| `intake.md` | 人間向けヒアリングシート |
| `intake.json` | skill-creator 入力用 |
| `notion-url.txt` | 公開済み Notion ページ URL |
| `notion-blocks.json` | publisher 中間生成物 |
| `self-update.json` | question-bank 更新証跡 |

### 既存intakeの再公開のみしたい場合

```
/intake-publish <hint>
```

`run-notion-intake-publish` skill (sibling) が起動し、aggregator phase 11 と同じ `scripts/intake_publish_pipeline.py` を **単一発火点** として呼ぶ。sibling 側は薄い wrapper でロジックを持たず、render / quality_gate / publish の重複実装は無い。

### 進行状況の確認

```
/intake-status <hint>
```

---

## 8. トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `/intake` が表示されない | plugin 未認識 | ステップ4の方式A/B/Cを再実施 |
| `exit 44` Keychain | トークン未登録 | ステップ3を再実施 |
| 403 Forbidden (Notion API) | DB に Integration が Connect されていない | ステップ2-2 Connections 追加 |
| `INTAKE_NOTION_DATABASE_ID is required` | schema.json 不在かつ env 未設定 | 通常は schema.json の `database_id_default` が使われる。CI/staging では env を明示 export |
| Slack 通知が来ない | Webhook 未登録 or URL誤り | ステップ3-2 で再登録。silent skip 仕様のため公開は止まらない |
| `security` コマンドが Bash で拒否 | 二段防御が効いている | これは正常。`scripts/keychain_get_secret.py` 経由でアクセス |
| `halted_score_decline` | 値実現スコア2回連続低下 | `output/<hint>/question-bank.snapshot.md` から `--rollback` |
| `halted_capacity` | question-bank が3000行超過 | 質問銀行を手動で精査・整理 |
| Notion ページ作成中に PNG が欠落 | `verify_notion_assets.py` が All-or-Nothing 停止 | `assets/` 配下の Mermaid/SVG 生成を再実行 |

詳細: [`hooks/README.md`](hooks/README.md) / [`skills/run-skill-intake-aggregator/references/failure-modes.md`](skills/run-skill-intake-aggregator/references/failure-modes.md)

---

## 9. 構成リファレンス

### ディレクトリ構造

```
plugins/skill-intake/
├── .claude-plugin/plugin.json     # plugin メタデータ + hooks 配線
├── .claude/settings.json.example  # permissions.deny の見本
├── commands/                       # スラッシュコマンド (3個)
│   ├── intake.md                   # /intake [topic]
│   ├── intake-publish.md           # /intake-publish <hint>
│   └── intake-status.md            # /intake-status [<hint>]
├── agents/                         # SubAgent (12個)
│   └── skill-intake-*.md
├── hooks/                          # secret scrub / 公開後通知 / keychain検証
│   ├── pre-publish-secret-scrub.sh
│   ├── post-publish-notify.sh      # Slack 通知 (任意)
│   ├── post-keychain-add.sh
│   └── README.md
├── scripts/                        # 共有スクリプト (27本, 標準ライブラリのみ)
│   └── README.md                   # 全スクリプトの責務一覧
└── skills/
    ├── run-skill-intake-aggregator/  # メインスキル (12 phase orchestrator)
    │   ├── SKILL.md
    │   ├── references/             # 18 本の参照ドキュメント
    │   └── assets/                 # Mermaid 12 + SVG 8 + samples 8
    └── run-notion-intake-publish/    # Notion 再公開専用 sibling skill (intake_publish_pipeline.py の薄い wrapper)
        └── SKILL.md
```

### 既存スキルとの差分

| Skill | 対象 | 図解 | Notion 公開 |
|---|---|---|---|
| `run-skill-elicit` (skill-creator plugin) | 技術者 | ❌ | ❌ |
| **`run-skill-intake-aggregator`** (本 plugin) | **非技術者対応** | ✅ Mermaid 12+SVG 8 | ✅ Keychain × REST API |
| `run-skill-create` (skill-creator plugin) | スキル本体生成 | — | — |

`run-skill-create` から Step 1 を呼ぶ際、ヒアリング対象が非技術者なら本 plugin の `run-skill-intake-aggregator` を起動。

### 環境変数一覧

| 変数 | 既定値 | 必須 | 用途 |
|---|---|---|---|
| `INTAKE_NOTION_DATABASE_ID` | `schema.json` の `database_id_default` | 任意（CI/staging のみ） | Notion DB ID (32文字)。通常運用では schema.json 既定値が使われる。CI/staging で別 DB を指す場合のみ設定 |
| `INTAKE_KEYCHAIN_SERVICE` | `notion-api-key` | 任意 | Keychain service 名 |
| `INTAKE_KEYCHAIN_ACCOUNT` | `skill-intake` | 任意 | Keychain account 名 |
| `INTAKE_NOTION_VERSION` | `2022-06-28` | 任意 | Notion-Version ヘッダ |

### eval-log 集計

`/intake` 実行ごとに `eval-log/skill-intake/<YYYY-MM-DD>.jsonl` に1行追記されます（value_realized_score / sections_count / questions_added / status）。横串集計用。詳細: [`eval-log/skill-intake/README.md`](../../eval-log/skill-intake/README.md)

### Skill design 原則

1. **Problem First** — 表層要望を仮説扱いし、本質的問題を最優先で発掘
2. **Structure-Reduces-Drift** — 「言語化されているのは1割」を前提に、問い構造で誤り訂正
3. **Script First** — 決定論処理はすべて `scripts/*.py` (Python 3 標準ライブラリのみ)、LLM 判断は補助
4. **Visualization Mandatory** — 全セクションに 1〜3 図、非エンジニア対応マスト 8 ルール強制
5. **Self-Evolving** — question-bank がヒアリング毎に成長（連続低下時は自動 halt）
6. **Secret-Out-of-Repo** — シークレットは Keychain のみ。`.env`/環境変数/コード禁止
7. **5 軸必須** — 出力先・情報源・共有相手・真の課題・ナレッジ資産
8. **All-or-Nothing 公開** — PNG 1 枚でも欠けたら停止

---

## ライセンス・所有

- **owner**: team-platform
- **since**: 2026-05-20
- **version**: 0.1.0
