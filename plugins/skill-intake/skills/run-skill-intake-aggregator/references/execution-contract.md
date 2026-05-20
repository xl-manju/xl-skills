---
name: execution-contract
description: scripts/*.js 実行の正本契約。Claude Code / Codex / 手動 CLI / Bash hook の 4 経路で同一スクリプトが動くための前提・引数・終了コード規約。
type: reference
---

# 実行環境契約 (Execution Contract)

`plugins/skill-intake/scripts/*.js` は以下 4 経路で**同一コマンド・同一引数・同一終了コード**で動く。
SubAgent から `node plugins/skill-intake/scripts/<name>.js ...` と書かれている箇所はすべてこの契約に従う。

## 前提条件

| 項目 | 要件 |
|---|---|
| Node.js | 18.0.0 以上 (built-in `fetch` 利用のため必須) |
| OS | macOS (Keychain 経由のため; 他 OS は `keychain_get_secret.js` 差し替え必須) |
| cwd | リポジトリルート (`plugins/skill-intake/` ではなく `.../xl-skills/`) |
| 依存 | npm パッケージ無し。Node 標準のみ (`node:fs` / `node:path` / `node:child_process` / `node:crypto`) |
| トークン | macOS Keychain (service=`notion-api-key`, account=`skill-intake-interviewer`) のみ。`.env` / 環境変数経由禁止 |

## 実行経路マトリクス

| 経路 | 起動方法 | コマンド例 |
|---|---|---|
| Claude Code (Bash ツール) | agent の `allowed-tools: Bash` から | `node plugins/skill-intake/scripts/quality_gate.js output/foo/intake.json` |
| Claude Code (`!` プレフィックス) | ユーザーがチャット欄に `!` を付ける | `!node plugins/skill-intake/scripts/keychain_get_secret.js --check` |
| Codex (自然文 / exec) | shell ツール / `codex exec "..."` | `codex exec "node plugins/skill-intake/scripts/verify_notion_schema.js"` |
| 手動 CLI | ターミナル直叩き (shebang あり) | `./plugins/skill-intake/scripts/cross_check.js intake.json intake.md` |
| Bash hook (`PreToolUse`) | `plugin.json` で配線 | `pre-publish-secret-scrub.sh` が `output/` を走査 |

## 引数規約

新スクリプト群は**positional args 優先**で、フラグは長形式 (`--name value`)。旧 `--in / --out / --agent / --token-env` は使わない。

| パターン | 例 |
|---|---|
| 単一入力ファイル | `node validate_intake.js output/<hint>/intake.json` |
| 入力2つ (md + json 整合) | `node cross_check.js output/<hint>/intake.json output/<hint>/intake.md` |
| フラグ + 値 | `node verify_notion_schema.js --database-id 36607a0c... --on-conflict skip-warn` |
| dry-run 切替 | `--dry-run` (副作用なし) |
| 安全確認 | `keychain_get_secret.js --check` (本体非表示) / `--print-unsafe` (本体出力、共有端末禁止) |

## 終了コード規約

| code | 意味 |
|---|---|
| 0 | OK / PASS |
| 1 | FAIL (lint/検証で不整合検出) |
| 2 | INPUT_ERROR (引数不足、ファイル不在、未知のフラグ) |
| 3 | DEPENDENCY_ERROR (mmdc 等の外部ツール不在で hard-fail させたいケース) |
| 44 | KEYCHAIN_ERROR (macOS Keychain 取得失敗 / 空 / 非 macOS) |

orchestrator は exit≠0 を全て **次フェーズ中止**として扱う。44 は専用扱いで `references/keychain-setup.md` を案内して停止する。

## 出力規約

- 機械可読系 (`validate_intake.js` / `quality_gate.js` / `verify_notion_schema.js` 等) は **JSON を stdout 単独行** で出力。診断ログは stderr へ。
- ファイル副作用ありの script (`prepare_notion_assets.js` / `create_notion_database.js`) は処理サマリを stdout、生成パスを完全絶対パスで報告。
- `publish_notion_page.js` のみ Notion REST `POST /v1/pages` を発火する。それ以外の script は副作用なし or ローカル書き込みのみ。

## hook 連携

`plugin.json` の `hooks.PreToolUse` (matcher=Bash) で `pre-publish-secret-scrub.sh` が自動配線される。
これにより `output/` 以下に `ntn_*` / `secret_*` / `Bearer ...` パターンを含むファイルがあると Notion 公開 Bash 実行直前に exit 2 でブロックされる。

## 互換性メモ

- 旧 `doc/skill-intake-interviewer/scripts/` の `--in / --out / --agent` 引数は廃止。移行時は positional 形式に書き換える。
- `compose_slack_message.js` は意図的に未移植 (Slack はスコープ外)。
- `render_notion_page.js` は blocks JSON 生成のみで API 発火は **`publish_notion_page.js`** が単独責務。
