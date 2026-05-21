# skill-intake / hooks

## 一覧

| ファイル | 種別 | 目的 |
|---|---|---|
| `pre-publish-secret-scrub.sh` | PreToolUse hook | Notion 公開前に `output/` 配下に Notion PAT / Internal Integration Secret / 汎用 Bearer / `.env` 形式キーが混入していないかを走査。検知で exit 2 → Claude Code が公開をブロック。 |
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
            "command": "$CLAUDE_PLUGIN_ROOT/plugins/skill-intake/hooks/pre-publish-secret-scrub.sh"
          }
        ]
      }
    ]
  }
}
```

`$CLAUDE_PLUGIN_ROOT` は plugin がインストールされたルート。worktree や直接編集中は絶対パスに置換しても良い。

### 2. 実行権限

```bash
chmod +x plugins/skill-intake/hooks/*.sh
```

### 3. 手動検証

```bash
bash plugins/skill-intake/hooks/post-keychain-add.sh
# → OK: トークン取得成功 (長さ=64, prefix=ntn_...)
```

## 配線が必要ない場合

- **個人開発でリポジトリにシークレットを書く心配がない**: pre-publish-secret-scrub.sh は無効化可。ただしチーム共有リポジトリでは必ず有効化推奨。
- **macOS 以外**: post-keychain-add.sh は macOS 専用。Linux/Windows では Keychain helper を別実装に差し替える必要あり。

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `security: command not found` | macOS 以外 | Linux なら `pass` / `gnome-keyring`、Windows なら `cmdkey` を使う helper に差し替え |
| `FAIL: Keychain にトークンが登録されていません` | service/account 名違い、または未登録 | `references/keychain-setup.md` の登録コマンドを再実行 |
| PreToolUse hook が発火しない | settings.json のパス誤り、または matcher 不一致 | `claude --debug` で hook 発火ログを確認 |
