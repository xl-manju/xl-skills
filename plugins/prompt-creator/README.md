# prompt-creator

7 層プロンプトアーキテクチャ (Role / Context / Principles / Workflow / Constraints / Output / Evaluation) で SubAgent 向けプロンプト YAML を生成する Claude Code plugin です。`skill-creator` の `run-build-skill` Step 7.5 からループ呼び出しされ、生成された SubAgent `.md` の **Prompt Templates** と **Self-Evaluation** セクションを自動充填します。単体でも `/prompt-creator:run-prompt-creator-7layer` として起動できます。

---

## 目次

1. [動作要件](#1-動作要件)
2. [インストール (ローカル marketplace 経由)](#2-インストール-ローカル-marketplace-経由)
3. [インストール (GitHub 経由・チーム共有)](#3-インストール-github-経由チーム共有)
4. [インストール確認](#4-インストール確認)
5. [使い方](#5-使い方)
6. [skill-creator との連携](#6-skill-creator-との連携)
7. [構成ファイル一覧](#7-構成ファイル一覧)
8. [スクリプト一覧](#8-スクリプト一覧)
9. [トラブルシューティング](#9-トラブルシューティング)
10. [アップデート / アンインストール](#10-アップデート--アンインストール)
11. [メンテナ・ライセンス](#11-メンテナライセンス)

---

## 1. 動作要件

事前に次がインストール済みであること。バージョン確認コマンドを実行して結果が返れば OK です。

| ツール       | 必須バージョン | 確認コマンド          |
| ------------ | -------------- | --------------------- |
| Claude Code  | 最新           | `claude --version`    |
| Git          | 2.30+          | `git --version`       |
| Node.js      | 18.0+          | `node --version`      |
| GitHub CLI   | (任意) 2.0+    | `gh --version`        |

> **どれか欠けている場合**
> - Claude Code: https://claude.com/claude-code からインストール
> - Git: https://git-scm.com/downloads
> - Node.js: https://nodejs.org/ (LTS 推奨)

---

## 2. インストール (ローカル marketplace 経由)

ローカルに clone した状態で試す手順です。**まずこちらで動作確認することを推奨します**。

### 手順 2-1. リポジトリを clone

```bash
git clone git@github.com:xl-manju/xl-skills.git
cd xl-skills
```

(SSH 鍵未設定なら HTTPS でも可)

```bash
git clone https://github.com/xl-manju/xl-skills.git
cd xl-skills
```

### 手順 2-2. Claude Code で marketplace を追加

Claude Code の対話セッション内で次を実行します。

```text
/plugin marketplace add /絶対パス/to/xl-skills
```

> 例 (macOS):
> ```text
> /plugin marketplace add /Users/yourname/dev/xl-skills
> ```

### 手順 2-3. prompt-creator を install

```text
/plugin install prompt-creator@xl-skills
```

### 手順 2-4. 依存 plugin を install (推奨)

prompt-creator は `skill-creator` から呼ばれる前提のため、合わせて install してください。

```text
/plugin install skill-creator@xl-skills
/plugin install skill-governance-lint@xl-skills
```

---

## 3. インストール (GitHub 経由・チーム共有)

チーム全員に同じ plugin を配布する場合の手順です。

### 手順 3-1. GitHub repository から直接 marketplace 追加

```text
/plugin marketplace add xl-manju/xl-skills --scope project
```

| scope オプション | 効果                                                             |
| ---------------- | ---------------------------------------------------------------- |
| `--scope project` | `.claude/settings.json` に記録され、リポジトリを clone したチーム全員に共有 |
| `--scope user`   | 自分のユーザー設定にのみ記録 (個人利用)                           |
| `--scope local`  | このマシンの該当プロジェクトでのみ有効 (一時利用)                 |

### 手順 3-2. install

```text
/plugin install prompt-creator@xl-skills --scope project
/plugin install skill-creator@xl-skills --scope project
/plugin install skill-governance-lint@xl-skills --scope project
```

### 手順 3-3. チームメンバー側の作業

`main` を pull すれば `.claude/settings.json` に marketplace 情報が同期されているので、各自の Claude Code が自動で marketplace を認識します。各メンバーは手動 install 不要 (自動有効化されない場合のみ `/plugin install ...` を実行)。

---

## 4. インストール確認

Claude Code 内で次を実行し、`prompt-creator` 関連のエントリが見えれば成功です。

```text
/plugin list
```

```text
/skill
```

`run-prompt-creator-7layer` が一覧に出ていれば OK。出ていない場合は [9. トラブルシューティング](#9-トラブルシューティング) を参照。

---

## 5. 使い方

### 5-1. 単体で起動

```text
/prompt-creator:run-prompt-creator-7layer
```

対話が始まり、次の 5 フェーズが順次進みます。

| Phase | 役割                                       | 主な SubAgent                  |
| ----- | ------------------------------------------ | ------------------------------ |
| 1     | ヒアリング (7 層分の入力収集)              | `prompt-creator-interview-user` |
| 2     | シート生成 (`generate_sheet.js`)           | (script)                       |
| 3     | プロンプト生成 (7 層マージ)                | `prompt-creator-generate-prompt` |
| 4     | レビュー & 整形 (validate/verify/convert)  | `prompt-creator-review-prompt` |
| 5     | 完了・LOGS.md 記録 (`log_usage.js`)        | (script)                       |

### 5-2. 出力物

- `tmp/sheet.yaml`: 中間シート (7 層分の生入力)
- `tmp/prompt.yaml`: 最終プロンプト YAML
- `LOGS.md`: 実行ログ (自動追記)

---

## 6. skill-creator との連携

`skill-creator` の `run-build-skill` Step 7.5 で `--with-prompts` フラグ付き呼び出しがあると、本 plugin がループ起動し、生成中の SubAgent `.md` の **Prompt Templates** と **Self-Evaluation** セクションを自動充填します。手動操作は不要です。

連携が動作しているかは次のログで確認できます。

```bash
tail -n 20 plugins/prompt-creator/LOGS.md
```

---

## 7. 構成ファイル一覧

```text
plugins/prompt-creator/
├── .claude-plugin/
│   └── plugin.json                       # plugin manifest
├── README.md                             # 本ファイル
├── LOGS.md                               # 実行ログ (自動更新)
├── agents/
│   ├── prompt-creator-interview-user.md
│   ├── prompt-creator-generate-prompt.md
│   └── prompt-creator-review-prompt.md
├── scripts/                              # 8 本の Node スクリプト
│   ├── merge_layers.js
│   ├── validate_prompt.js
│   ├── verify_completeness.js
│   ├── convert_format.js
│   ├── generate_sheet.js
│   ├── validate_sheet.js
│   ├── scaffold_prompt.js
│   └── log_usage.js
└── skills/
    └── run-prompt-creator-7layer/
        ├── SKILL.md
        ├── references/                   # Progressive Disclosure 参照群
        │   ├── resource-map.yaml
        │   ├── seven-layer-format.md
        │   ├── quality-criteria.md
        │   ├── workflow-guide.md
        │   ├── writing-style-principles.md
        │   └── prompt-sheet-template.md
        └── schemas/
            └── hearing-result.schema.json
```

---

## 8. スクリプト一覧

すべて Node.js 標準ライブラリのみで動作 (外部依存ゼロ)。

| script                  | 役割                                                | 終了コード       |
| ----------------------- | --------------------------------------------------- | ---------------- |
| `generate_sheet.js`     | ヒアリング結果から 7 層シート YAML を生成           | 0=成功 / 1=失敗  |
| `validate_sheet.js`     | シート YAML のスキーマ検証                          | 0=valid          |
| `scaffold_prompt.js`    | シート→プロンプト雛形変換                           | 0=成功           |
| `merge_layers.js`       | 7 層をマージし最終プロンプト生成                    | 0=成功           |
| `validate_prompt.js`    | 最終プロンプトの構造検証                            | 0=valid          |
| `verify_completeness.js`| 7 層すべてが充足しているか確認                      | 0=完全           |
| `convert_format.js`     | YAML ⇄ Markdown ⇄ JSON 相互変換                     | 0=成功           |
| `log_usage.js`          | 実行結果を LOGS.md に追記                           | 0=記録完了       |

手動実行例:

```bash
node plugins/prompt-creator/scripts/generate_sheet.js --help
node plugins/prompt-creator/scripts/log_usage.js --result success --phase manual
```

---

## 9. トラブルシューティング

### Q1. `/plugin install prompt-creator@xl-skills` で plugin が見つからない

```text
/plugin marketplace list
```

で marketplace が登録されているか確認。出ない場合は [手順 2-2](#手順-2-2-claude-code-で-marketplace-を追加) を再実行。

### Q2. `/skill` に `run-prompt-creator-7layer` が出ない

Claude Code を再起動 (`Ctrl+C` → `claude`) して `/plugin list` で `prompt-creator: enabled` を確認。

### Q3. script 実行で `Error: Cannot find module`

`node --version` で 18 以上であることを確認。

### Q4. ローカル開発で symlink が動作しない

`.claude/skills/run-prompt-creator-7layer` が `plugins/prompt-creator/skills/run-prompt-creator-7layer` を指している必要があります。

```bash
readlink -f .claude/skills/run-prompt-creator-7layer
```

正本パスが返らない場合は再作成:

```bash
ln -sf ../../plugins/prompt-creator/skills/run-prompt-creator-7layer .claude/skills/run-prompt-creator-7layer
ln -sf ../../plugins/prompt-creator/agents/prompt-creator-interview-user.md .claude/agents/prompt-creator-interview-user.md
ln -sf ../../plugins/prompt-creator/agents/prompt-creator-generate-prompt.md .claude/agents/prompt-creator-generate-prompt.md
ln -sf ../../plugins/prompt-creator/agents/prompt-creator-review-prompt.md .claude/agents/prompt-creator-review-prompt.md
```

### Q5. LOGS.md が更新されない

`scripts/log_usage.js` の実行権限と書き込み権限を確認:

```bash
ls -l plugins/prompt-creator/LOGS.md plugins/prompt-creator/scripts/log_usage.js
```

---

## 10. アップデート / アンインストール

### アップデート

```bash
cd /path/to/xl-skills
git pull
```

Claude Code 内で:

```text
/plugin marketplace update xl-skills
/plugin update prompt-creator@xl-skills
```

### アンインストール

```text
/plugin uninstall prompt-creator@xl-skills
/plugin marketplace remove xl-skills
```

---

## 11. メンテナ・ライセンス

- **メンテナ**: team-platform (`plugin.json` `owner` 参照)
- **since**: 2026-05-20 (`doc/prompt-creator/` から移植)
- **source of truth**: `plugins/prompt-creator/` (旧 `doc/prompt-creator/` は deprecated)
- **ライセンス**: リポジトリルートの `LICENSE` に従う

---

## 参考リンク

- Claude Code Plugin docs: https://code.claude.com/docs/en/plugins
- Plugin reference: https://code.claude.com/docs/en/plugins-reference
- Marketplace docs: https://code.claude.com/docs/en/plugin-marketplaces
- xl-skills root README: `../../README.md`
- skill-creator: `../skill-creator/`
