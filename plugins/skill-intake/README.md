# skill-intake plugin

skill-creator の前段ヒアリングを **非技術者にも開く** Claude Code plugin。「スキルを作りたい」という曖昧な要望から、本人も言語化できていない真の課題を引き出し、**Markdown 正本 + JSON 副本 + Notion ページ**の3成果物を一括生成します。さらに公開後の追加要望は `/intake-revise` で同一 Notion ページに PATCH 反映できます。

このREADMEは **上から順に手順を実行するだけで導入完了**するよう構成されています。途中スキップせず、各ステップ末尾の **✅ 確認** を必ず通してから次へ進んでください。

---

## Non-Secrets（漏洩可情報）

このプラグインは **複数 repository に symlink で共有される前提** のため、リポジトリ固有の Notion DB ID は
プラグイン内に直書きせず **`<repo-root>/.notion-config.json` (gitignore対象)** に分離している。
セットアップ手順は **[references/notion-per-repo-setup.md](references/notion-per-repo-setup.md)** 参照（symlink で skill-creator/references/ と共有）。

| 項目 | 値 | 格納場所 | 漏洩可否 |
|---|---|---|---|
| Notion Database ID | per-repo 設定 | `<repo-root>/.notion-config.json#databases.hearing-sheet.db_id` (gitignore) | OK |
| Keychain service 名（既定） | `notion-api-key` | `.notion-config.json#keychain_service` / env `INTAKE_KEYCHAIN_SERVICE` で上書き可 | OK |
| Keychain account 名（既定） | `skill-intake` | `.notion-config.json#keychain_account` / env `INTAKE_KEYCHAIN_ACCOUNT` で上書き可 | OK |
| Notion-Version ヘッダ | `2022-06-28` | `scripts/notion_http.py` / env `INTAKE_NOTION_VERSION` で上書き可 | OK |

DB ID 解決順: `--database-id` CLI > env `INTAKE_NOTION_DATABASE_ID` > `<repo-root>/.notion-config.json` > schema `database_id_default` (= null)。

### 機密情報（Keychain のみ）との対比

以下は **絶対にコード/コミット/環境変数/ログに残さない**。Keychain（ローカル）のみで保管:

| 項目 | 格納場所 | 漏洩可否 |
|---|---|---|
| Notion API トークン本体（`secret_xxx...`） | macOS Keychain (service=`notion-api-key`, account=`skill-intake`) | **NG** |
| Slack Incoming Webhook URL | macOS Keychain (service=`slack-incoming-webhook`, account=`skill-intake`) | **NG** |

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
8. [既存 intake の再公開・追加修正](#8-既存-intake-の再公開追加修正)
9. [トラブルシューティング](#9-トラブルシューティング)
10. [構成リファレンス](#10-構成リファレンス)

---

## 1. 前提条件チェック

| 項目 | 確認コマンド | 期待値 |
|---|---|---|
| macOS | `uname` | `Darwin` |
| Python 3 (macOS 標準) | `/usr/bin/python3 --version` | `Python 3.9` 以上（外部 pip パッケージ不要） |
| Claude Code CLI | `claude --version` | バージョン表示 |
| Git | `git --version` | バージョン表示 |
| Notion アカウント | https://notion.so にログイン可能 | — |

✅ **確認**: 上記すべて満たしている。

---

## 2. Notion 側の準備

### 2-1. Notion Internal Integration を作成

1. https://www.notion.so/profile/integrations → 「**+ New integration**」
2. **Name**: `skill-intake`、**Type**: `Internal`、ワークスペース選択
3. 「**Save**」→「**Internal Integration Secret**」を **コピーして安全な場所にメモ**（実値は README に書き残さない）

✅ **確認**: シークレットを手元にメモした。

### 2-2. Notion データベースを作成

1. 新規ページ → `/database` → `Database - Full page`
2. 名前は「**Skill Intake**」など任意。プロパティは後で `verify_notion_schema.py` が自動補完
3. DB を開き 右上「**...**」→「**Connections**」→ 先ほどの `skill-intake` Integration を Connect

✅ **確認**: データベースに Integration が Connect されている。

### 2-3. データベース ID を取得

```
https://www.notion.so/<workspace>/<32文字の英数字>?v=...
                                   └─ これが Database ID ─┘
```

`?v=` 直前の 32 文字をメモ（実値は README に書き残さない）。

✅ **確認**: 32文字の Database ID を手元にメモした。

### 2-4. (任意) Slack 公開通知

公開成功時に Slack 通知を受け取りたい場合のみ:

1. https://api.slack.com/apps → 「**Create New App**」→「**From scratch**」
2. App name: `skill-intake-notifier`
3. 左メニュー「**Incoming Webhooks**」→ ON → 「**Add New Webhook to Workspace**」
4. 通知先チャンネルを選び「**Allow**」→ Webhook URL をメモ

✅ **確認**: Slack を使わない場合はスキップしてOK（自動で no-op）。

---

## 3. macOS Keychain にシークレット登録

**重要**: シークレットは Keychain にのみ保管します。`.env`・コード・コミット履歴・環境変数には絶対に置きません。

### 3-1. Notion PAT を登録

```bash
security add-generic-password \
  -s notion-api-key \
  -a skill-intake \
  -T '' -U
```

プロンプトに **2-1 でメモした Notion Integration Secret** を貼り付けて Enter（画面には表示されません）。

### 3-2. (任意) Slack Webhook を登録

```bash
security add-generic-password \
  -s slack-incoming-webhook \
  -a skill-intake \
  -T '' -U
```

プロンプトに Webhook URL を貼り付けて Enter。

### 3-3. 取得テスト

```bash
python3 plugins/skill-intake/scripts/keychain_get_secret.py --check
# → OK: トークン取得成功 が出れば成功（トークン本体は表示されません）
```

✅ **確認**: Notion トークンが Keychain から取得できる。

---

## 4. plugin インストール

3つの方式があります。**A方式（Marketplace経由）が推奨**です。

### 方式A: GitHub Marketplace から install（推奨）

Claude Code セッション内で:

```
/plugin marketplace add xl-manju/xl-skills
/plugin install skill-intake@xl-skills
```

これで agents/commands/hooks/skills すべて自動有効化されます。

### 方式B: ローカル開発（clone してそのまま使う）

```bash
git clone https://github.com/xl-manju/xl-skills.git
cd xl-skills
claude
```

Claude Code 起動後:

```
/plugin marketplace add ./
/plugin install skill-intake@xl-skills
```

### 方式C: symlink で連結（既に worktree 内で開発中）

このリポジトリ内で開発作業をしている場合、`.claude/` 配下に既に symlink が貼られています。追加作業不要で `/intake` などが使えます。

新規 worktree でセットアップする場合は:

```bash
cd .claude/skills && \
  for d in ../../plugins/skill-intake/skills/*/; do ln -sfn "$d" "$(basename $d)"; done && \
cd ../agents && \
  for f in ../../plugins/skill-intake/agents/skill-intake-*.md; do ln -sfn "$f" "$(basename $f)"; done && \
cd ../commands && \
  for f in ../../plugins/skill-intake/commands/*.md; do ln -sfn "$f" "$(basename $f)"; done
```

✅ **確認**: `/help` で `/intake`・`/intake-publish`・`/intake-revise`・`/intake-status` が表示される。

---

## 5. Claude Code 設定の適用

### 5-1. 環境変数（任意・上書き用）

**通常運用では設定不要です。** `schema.json` の `database_id_default` と `keychain_get_secret.py` の既定値がそのまま使われます。

env による override は **CI/staging 限定の用途**:

```bash
# 任意（CI/staging 限定）
# export INTAKE_NOTION_DATABASE_ID="<別環境の 32文字 Database ID>"
# export INTAKE_KEYCHAIN_SERVICE="notion-api-key"      # 既定値そのまま
# export INTAKE_KEYCHAIN_ACCOUNT="skill-intake"        # 既定値そのまま
# export INTAKE_NOTION_VERSION="2022-06-28"            # 既定値そのまま
```

### 5-2. permissions.deny を有効化（二段防御）

Keychain への `security` コマンド直叩きを禁止します（Claude が誤ってシークレットを読み出すのを防止）。

`plugins/skill-intake/.claude/settings.json.example` を見本に、`~/.claude/settings.json` または プロジェクトの `.claude/settings.json` に **以下のキーをマージ**:

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

> 💡 **なぜ deny するの？**: Notion トークンや Slack Webhook の取得は `scripts/keychain_get_secret.py` 経由のみに集約する設計です。Bash 経路を塞ぎ、シークレットがログ/履歴に漏れる経路を物理的に排除します。

✅ **確認**: `cat ~/.claude/settings.json | grep -A2 deny` で `security` 行が存在する。

---

## 6. 動作確認テスト

### 6-1. Keychain 取得

```bash
python3 plugins/skill-intake/scripts/keychain_get_secret.py --check
```
→ `OK: トークン取得成功`。`exit 44` ならステップ3に戻る。

### 6-2. Notion DB スキーマ検証

```bash
python3 plugins/skill-intake/scripts/verify_notion_schema.py \
  --database-id "<2-3 でメモした 32文字 ID>" \
  --on-conflict skip-warn
```
→ 200 OK + プロパティ列挙が出れば成功。403 なら 2-2 の Connections を見直し。

### 6-3. Slack hook テスト（任意）

```bash
python3 plugins/skill-intake/scripts/keychain_get_secret.py \
  --service slack-incoming-webhook --account skill-intake --check
```
→ `OK` なら Slack 通知も自動で有効。`exit 44` でも公開フローは silent skip で続行。

✅ **確認**: 6-1, 6-2 が成功した。Slack 利用者は 6-3 も成功した。

---

## 7. 初回ヒアリング実行

Claude Code セッション内で:

```
/intake デイリーレポート生成スキルを作りたい
```

メイン orchestrator は `run-skill-intake-aggregator` skill。以下の **11 phase / 12 SubAgent** (Phase 4 は interviewer ⇄ purpose-excavator のペア稼働で 1 phase) を順次実行:

| Phase | SubAgent / 補助 skill | 役割 |
|---|---|---|
| 1 | `skill-intake-kickoff` / `run-intake-kickoff` | パターン・深度・痛点 3 軸確定 |
| 2 | `skill-intake-assumption-challenger` | 表層要望を仮説扱い・対立案提示 |
| 3 | `skill-intake-user-profiler` | 熟練度・語彙 tier 推定 |
| 4 | `skill-intake-interviewer` ⇄ `skill-intake-purpose-excavator` / `run-intake-interview` | 5 軸ヒアリング（最大 5 往復） |
| 5 | `skill-intake-option-presenter` / `ref-intake-option-catalog` | 外部連携カタログ提示 |
| 6 | `skill-intake-visualizer` / `run-intake-visualize` | Mermaid 12 + SVG 8 から 1〜3 図/セクション配置 |
| 7 | `skill-intake-summarizer` | Gate A サマリ → 承認依頼 |
| 8 | `skill-intake-next-action-advisor` / `run-intake-next-action` | skill-creator 引き渡しモード A/B/C/D/E 判定 |
| 9 | `skill-intake-handoff` / `run-intake-finalize` | intake.md + intake.json + quality_gate + cross_check |
| 10 | `skill-intake-notion-publisher` | Notion REST API でページ作成 (`intake_publish_pipeline.py`) |
| 11 | `skill-intake-self-updater` | question-bank 自己更新 |
| 12 | — | cross-check + 公開完了 |

完了後 `output/<hint>/` に生成されるファイル:

| ファイル | 用途 |
|---|---|
| `intake.md` | 人間向けヒアリングシート（正本） |
| `intake.json` | skill-creator 入力用 |
| `notion-url.txt` | 公開済み Notion ページ URL |
| `notion-manifest.json` | アセット SHA-256 マニフェスト |
| `notion-blocks.json` | publisher 中間生成物 |
| `self-update.json` | question-bank 更新証跡 |
| `internal-analysis.json` | ユーザー意図の内部解析（非表示） |

---

## 8. 既存 intake の再公開・追加修正

### 8-1. 再公開のみ（内容変更なし）

```
/intake-publish <hint>
```

`run-notion-intake-publish` skill が `scripts/intake_publish_pipeline.py` を **単一発火点** (定義は `skills/run-skill-intake-aggregator/SKILL.md` 「単一発火点」項を参照) として呼ぶ。render / quality_gate / publish の重複実装はない。

### 8-2. 追加要望・改善を反映（PATCH 更新）

```
/intake-revise <hint>          # 通常実行
/intake-revise <hint> --dry-run # Notion API を呼ばず差分だけ表示
```

フロー: 既存読み込み → AskUserQuestion で差分聴取 → `analyze_user_intent.py` 再解析 → 差分プレビュー → **Gate R**（`apply` / `re-revise` / `cancel`） → `intake_publish_pipeline.py --revise --page-id ...` で **同一 Notion ページを PATCH 更新**（新規ページ作成しない）。

- 最大 5 revision まで（超過時 exit 60、新規 hint で `/intake` 推奨）
- 失敗時はロールバック JSON を `output/<hint>/notion-rollback-<rev>.json` に保存
- `output/<hint>/revision-log.jsonl` に毎回追記

### 8-3. 進行状況の確認

```
/intake-status [<hint>]
```

---

## 9. トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `/intake` が表示されない | plugin 未認識 | ステップ4の方式A/B/Cを再実施 |
| `exit 44` Keychain | トークン未登録 | ステップ3を再実施 |
| 403 Forbidden (Notion API) | DB に Integration 未 Connect | ステップ2-2 Connections 追加 |
| `INTAKE_NOTION_DATABASE_ID is required` | schema.json 不在かつ env 未設定 | 通常は schema.json の `database_id_default` が使われる。CI/staging では env を明示 export |
| Slack 通知が来ない | Webhook 未登録 or URL 誤り | ステップ3-2 で再登録。silent skip 仕様のため公開は止まらない |
| `security` コマンドが Bash で拒否 | 二段防御が効いている | 正常。`scripts/keychain_get_secret.py` 経由でアクセス |
| `halted_score_decline` | 値実現スコア2回連続低下 | `output/<hint>/question-bank.snapshot.md` から `--rollback` |
| `halted_capacity` | question-bank が 3000 行超過 | 質問銀行を手動で精査・整理 |
| Notion ページ作成中に PNG が欠落 | `verify_notion_assets.py` の All-or-Nothing 停止 | `assets/` 配下の Mermaid/SVG 生成を再実行 |
| `/intake-revise` exit 51 | notion-url.txt と DB のページ ID 不一致 | 新規 hint で `/intake` を起動 |
| `/intake-revise` exit 60 | revision 5 回超過 | 新規 hint へ移行 |

詳細: [`hooks/README.md`](hooks/README.md) / [`scripts/README.md`](scripts/README.md) / [`skills/run-skill-intake-aggregator/references/failure-modes.md`](skills/run-skill-intake-aggregator/references/failure-modes.md)

---

## 10. 構成リファレンス

### ディレクトリ構造

```
plugins/skill-intake/
├── .claude-plugin/plugin.json         # plugin メタデータ + hooks 配線
├── .claude/settings.json.example      # permissions.deny の見本
├── commands/                          # スラッシュコマンド (4個)
│   ├── intake.md                      # /intake [topic]
│   ├── intake-publish.md              # /intake-publish <hint>
│   ├── intake-revise.md               # /intake-revise <hint> [--dry-run]
│   └── intake-status.md               # /intake-status [<hint>]
├── agents/                            # SubAgent (12個) — skill-intake-*.md
├── hooks/                             # PreToolUse / PostToolUse / 手動 (4本)
│   ├── pre-publish-secret-scrub.sh    # 公開前 secret 走査 (exit 2 でブロック)
│   ├── pre-publish-schema-validate.py # 公開前スキーマ検証
│   ├── post-publish-notify.sh         # Slack 通知 (任意, silent skip)
│   ├── post-keychain-add.sh           # Keychain 登録直後の検証 (手動)
│   └── README.md
├── scripts/                           # 共有スクリプト (34本 plugin 直下 + 3本 skills/<name>/scripts/ 配下 = 計 37本, Python 3 標準ライブラリのみ)
│   ├── keychain_get_secret.py         # Keychain アクセスの唯一経路
│   ├── notion_http.py                 # Notion REST wrapper
│   ├── intake_publish_pipeline.py     # publish/republish/revise の単一発火点
│   ├── analyze_user_intent.py         # /intake-revise の意図解析
│   ├── render-intake-final.py / render_notion_page.py
│   ├── verify_notion_schema.py / verify_notion_assets.py
│   ├── validate_intake.py / quality_gate.py / cross_check.py
│   ├── select_diagram_type.py / compose_diagram.py / validate_mermaid.py
│   ├── render_to_svg.py / render_to_image.py / enforce_visualization_rules.py
│   ├── update_question_bank.py        # question-bank パッチ (--apply / --rollback)
│   ├── append_eval_log.py / measure_value_realized.py
│   ├── ci_dogfooding_retest.py / dogfooding_regression.py
│   ├── notion_limits.json
│   └── README.md                      # 全スクリプトの責務一覧
├── fixtures/                          # テスト用例データ (4ディレクトリ)
│   ├── example-data-quality-survey/   # 例: データ品質調査
│   ├── example-team-onboarding/       # 例: チームオンボーディング
│   ├── info-collector-agent/          # SubAgent プロンプト検証用
│   └── intake-final-smoke/            # 最終版 render の smoke test
└── skills/                            # スキル (11個)
    ├── run-skill-intake-aggregator/   # メイン: 12 phase orchestrator
    │   ├── SKILL.md
    │   ├── references/                # 24 本 (handoff-contract, intake.schema.json,
    │   │                              #         mermaid-visualization-guide, failure-modes 等)
    │   ├── schemas/                   # handoff / findings / intake-final
    │   └── assets/                    # Mermaid templates 12 + samples 8 + SVG 8
    ├── run-skill-intake/              # 軽量 orchestrator (11 段階)
    ├── run-intake-kickoff/            # Phase 1 補助
    ├── run-intake-interview/          # Phase 4 補助
    ├── run-intake-visualize/          # Phase 6 補助
    ├── run-intake-finalize/           # Phase 9 補助 (統合 + quality_gate)
    ├── run-intake-next-action/        # Phase 8 決定論 (引き渡しモード判定)
    ├── run-notion-intake-publish/     # 再公開専用 (intake_publish_pipeline.py の薄い wrapper)
    ├── run-notion-fidelity-guard/     # Notion 公開前粒度検証
    ├── run-intake-revise/             # 追加要望 PATCH 反映 (Gate R + revision-log)
    └── ref-intake-option-catalog/     # 外部連携カタログ参照
```

### コマンド一覧

| コマンド | 用途 | 引数 |
|---|---|---|
| `/intake` | 新規ヒアリング起動（11 phase / 12 SubAgent） | `[topic]` |
| `/intake-publish` | 既存 intake の再公開（内容変更なし） | `<hint>` |
| `/intake-revise` | 追加要望を Notion ページに PATCH 反映 | `<hint> [--dry-run]` |
| `/intake-status` | 進行状況（phase / 5 軸充足 / 図解枚数） | `[<hint>]` |

### Hooks 配線

| イベント | 実行 hook | 役割 |
|---|---|---|
| PreToolUse (Bash) | `pre-publish-secret-scrub.sh` | `output/` 配下を走査し Notion PAT / Bearer / 汎用キー混入を検知 (exit 2 でブロック) |
| PreToolUse (Bash) | `pre-publish-schema-validate.py` | intake/notion-blocks の JSON Schema 検証 |
| PostToolUse (Bash) | `post-publish-notify.sh` | Notion 公開成功後に Slack webhook 送信（opt-in） |

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
| `INTAKE_NOTION_DATABASE_ID` | `schema.json` の `database_id_default` | 任意（CI/staging のみ） | Notion DB ID (32文字)。通常運用では schema.json 既定値 |
| `INTAKE_KEYCHAIN_SERVICE` | `notion-api-key` | 任意 | Keychain service 名 |
| `INTAKE_KEYCHAIN_ACCOUNT` | `skill-intake` | 任意 | Keychain account 名 |
| `INTAKE_NOTION_VERSION` | `2022-06-28` | 任意 | Notion-Version ヘッダ |

### eval-log 集計

`/intake` 実行ごとに `eval-log/skill-intake/<YYYY-MM-DD>.jsonl` に1行追記（value_realized_score / sections_count / questions_added / status）。横串集計用。詳細: [`eval-log/skill-intake/README.md`](../../eval-log/skill-intake/README.md)

### Skill design 原則

1. **Problem First** — 表層要望を仮説扱いし、本質的問題を最優先で発掘
2. **Structure-Reduces-Drift** — 「言語化されているのは1割」を前提に、問い構造で誤り訂正
3. **Script First** — 決定論処理はすべて `scripts/*.py`（Python 3 標準ライブラリのみ）、LLM 判断は補助
4. **Single Publication Entry** — publish/republish/revise はすべて `intake_publish_pipeline.py` 経由
5. **Visualization Mandatory** — 全セクションに 1〜3 図、非エンジニア対応マスト 8 ルール強制
6. **Self-Evolving** — question-bank がヒアリング毎に成長（連続低下時は自動 halt）
7. **Secret-Out-of-Repo** — シークレットは Keychain のみ。`.env`/環境変数/コード禁止
8. **5 軸必須** — 出力先・情報源・共有相手・真の課題・ナレッジ資産
9. **All-or-Nothing 公開** — PNG 1 枚でも欠けたら停止

---

## ライセンス・所有

- **owner**: team-platform
- **since**: 2026-05-20
- **version**: 0.1.0
