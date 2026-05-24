# skill-intake / hooks

## 一覧

| ファイル | 種別 | 目的 |
|---|---|---|
| `pre-publish-secret-scrub.sh` | PreToolUse hook | Notion 公開前に `output/` 配下に Notion PAT / Internal Integration Secret / 汎用 Bearer / `.env` 形式キーが混入していないかを走査。検知で exit 2 → Claude Code が公開をブロック。 |
| `post-publish-notify.sh` | PostToolUse hook | Notion 公開成功後に Slack incoming webhook へ最小ペイロード (`intake published: <hint> -> <url>`) を送信。Webhook 未登録時は silent skip。Webhook 取得は `scripts/keychain_get_secret.py` 経由 (security 直叩き禁止)。 |
| `post-keychain-add.sh` | 手動実行 | Keychain 登録直後に `security find-generic-password` で取得可否を検証。本体は表示せず長さと prefix のみ出力。 |

## 配線方法

### 1. PreToolUse hook (Bash 経由の Notion 公開を保護)

`~/.claude/settings.json` (グローバル) または `.claude/settings.json` (project) に追記:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PLUGIN_ROOT/hooks/pre-publish-secret-scrub.sh"
          }
        ]
      }
    ]
  }
}
```

`$CLAUDE_PLUGIN_ROOT` は **個別 plugin の installed root** (`<...>/plugins/skill-intake/`) を指す (Claude Code 公式仕様)。よって hook command は `$CLAUDE_PLUGIN_ROOT/hooks/<file>` の形で記述する (リポジトリルートからの相対ではない)。worktree や直接編集中は絶対パスに置換しても良い。

### 2. 実行権限

```bash
chmod +x plugins/skill-intake/hooks/*.sh
```

### 3. 手動検証

```bash
bash plugins/skill-intake/hooks/post-keychain-add.sh
# → OK: トークン取得成功 (長さ=64, prefix=ntn_...)
```

### 4. PostToolUse hook (Slack 通知)

`post-publish-notify.sh` を PostToolUse / Bash matcher に配線する。`.claude/settings.json.example` に
ひな型あり。プラグインインストール時は `.claude-plugin/plugin.json` の hooks 経由で自動配線される。

#### Slack Webhook の Keychain 登録 (初回セットアップのみ)

通常運用では `Bash(security add-generic-password:*)` は permissions.deny で禁止する。
**初回セットアップ時のみ**、ユーザーが手元のターミナルで以下を実行する (Claude 経由ではなく直接):

```bash
security add-generic-password \
  -s slack-incoming-webhook \
  -a skill-intake \
  -w 'https://hooks.slack.com/services/XXX/YYY/ZZZ' \
  -U
```

登録後は `python3 plugins/skill-intake/scripts/keychain_get_secret.py \
  --service slack-incoming-webhook --account skill-intake --check`
で取得可否を確認する。

#### no-op 条件

`post-publish-notify.sh` は次の場合に何もせず exit 0 する (公開フローを止めない):

- `output/<hint>/notion-url.txt` が存在しない / 空
- Slack Webhook が Keychain 未登録
- Webhook 取得失敗 / curl 失敗 / Slack 応答が non-200 (WARN を stderr に出すのみ)

つまり Slack 連携は **opt-in**。設定しなければ skill-intake は従来通り Notion 公開だけで完結する。

## 配線が必要ない場合

- **個人開発でリポジトリにシークレットを書く心配がない**: pre-publish-secret-scrub.sh は無効化可。ただしチーム共有リポジトリでは必ず有効化推奨。
- **macOS 以外**: post-keychain-add.sh は macOS 専用。Linux/Windows では Keychain helper を別実装に差し替える必要あり。

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `security: command not found` | macOS 以外 | Linux なら `pass` / `gnome-keyring`、Windows なら `cmdkey` を使う helper に差し替え |
| `FAIL: Keychain にトークンが登録されていません` | service/account 名違い、または未登録 | `references/keychain-setup.md` の登録コマンドを再実行 |
| PreToolUse hook が発火しない | settings.json のパス誤り、または matcher 不一致 | `claude --debug` で hook 発火ログを確認 |
