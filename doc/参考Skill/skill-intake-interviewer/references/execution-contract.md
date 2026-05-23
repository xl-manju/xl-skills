---
name: execution-contract
description: スクリプト実行の正本契約。Claude Code / Codex / 手動 CLI の 3 経路で同一スクリプトが動くための前提・コマンド・終了コード規約を定義する。
type: reference
---

# 実行環境契約（Execution Contract）

このスキルの全 `scripts/*.js` は、以下の 3 経路で同一に実行できる。
agent から `node scripts/xxx.js ...` と書かれている箇所は、すべてこの契約に従って起動する。

## 前提条件

| 項目 | 要件 |
|-----|-----|
| Node.js | 18.0.0 以上（推奨 20 LTS） |
| cwd（作業ディレクトリ） | スキルルート `.../skill-intake-interviewer/` |
| 実行権限 | 全 `scripts/*.js` に `chmod +x` 済み（shebang `#!/usr/bin/env node` あり） |
| 依存パッケージ | `package.json` 参照。標準ライブラリのみで動作するスクリプトが大半 |
| 環境変数 | Notion/Slack 連携時のみ MCP 経由（直接トークンを渡さない） |

## 実行経路マトリクス

| 経路 | 起動方法 | コマンド例 |
|------|---------|-----------|
| Claude Code（Bash ツール） | agent の `allowed-tools: Bash` で Bash ツールを呼び出す | `node scripts/quality_gate.js --agent interviewer --in output/foo/sheet.json` |
| Claude Code（`!` プレフィックス） | チャット欄に `!` を付けて手動実行（ユーザー側） | `!node scripts/check_completeness.js --in output/foo/intake.json` |
| Codex（自然文依頼） | ユーザーが自然文で依頼し、エージェントが shell ツールで実行 | 「`node scripts/quality_gate.js --in output/foo/sheet.json` を実行してください」 |
| Codex（exec モード） | `codex exec` で非対話ワンショット実行 | `codex exec "node scripts/quality_gate.js --in output/foo/sheet.json"` |
| 手動 CLI（直接実行） | shebang 経由で直接起動 | `./scripts/quality_gate.js --agent interviewer --in output/foo/sheet.json` |

すべての経路で同一コマンド・同一引数・同一終了コードになるよう設計する。

### Claude Code と Codex の起動差分

| 項目 | Claude Code | Codex |
|-----|------------|-------|
| ユーザー直叩きショートカット | 行頭 `!` プレフィックス | 無し（自然文でエージェントに依頼） |
| エージェント経由実行ツール | Bash ツール | shell ツール |
| 承認モード設定 | permission モード（accept/plan/dontAsk 等） | `--ask-for-approval`（`untrusted` / `on-failure` / `on-request` / `never`）+ `--sandbox`（`read-only` / `workspace-write` / `danger-full-access`） |
| 全自動化 | settings.json の permissions で許可 | `codex --ask-for-approval never --sandbox workspace-write` または `~/.codex/config.toml` |
| 非対話ワンショット | （該当無し・対話前提） | `codex exec "..."` |

Codex には「`!` 相当」のユーザー直叩きショートカット記法は存在しない。代わりに承認モード設定でカバーする。コマンド本体（`node scripts/...`）は両環境で完全に同一なのでコピペで通用する。

## 引数規約

```
node scripts/<name>.js [--in <input.json>] [--out <output.json>] [--agent <agent_name>] [--apply]
```

- `--in`: 入力 JSON ファイルパス（省略時は stdin）
- `--out`: 出力先 JSON ファイルパス（省略時は stdout）
- `--agent`: 対象 agent 名（agent 別ルールが必要なスクリプトのみ）
- `--apply`: 副作用を伴う適用フラグ（既定は dry-run）

## 終了コード規約

| code | 意味 | 振る舞い |
|------|-----|---------|
| 0 | PASS | 後続処理続行 |
| 1 | FAIL（検証エラー） | agent はユーザーに差戻し |
| 2 | INPUT_ERROR | 引数・入力 JSON 不正。agent は再生成 |
| 3 | DEPENDENCY_ERROR | Node/外部ツール不足。LLM フォールバックを試行 |
| ≥10 | スクリプト固有 | 各スクリプトの README/冒頭コメント参照 |

## エージェント記述テンプレート（必須）

agent の Layer 4「思考プロセス」に `node scripts/...` を書く場合、必ず次のテンプレートに従う:

```markdown
### スクリプト実行（実行環境契約準拠）

実行経路:
- Claude Code: Bash ツールで実行
- Codex: shell で同コマンド実行
- 手動: `./scripts/<name>.js ...`（shebang 直叩き）

コマンド:
\`\`\`bash
node scripts/<name>.js --in <input> --out <output>
\`\`\`

期待される終了コード: 0（PASS）。1 以上なら停止しユーザーに報告。
依存: Node.js ≥18、`references/execution-contract.md`。
```

## LLM フォールバック（Codex で Node 不在時）

`exit code = 3 (DEPENDENCY_ERROR)` または `node` コマンドが見つからない場合:

1. agent は当該スクリプトの参照ルール（例: `references/quality-rubric.md`）を直接読み込む
2. LLM が同等判定を実施
3. 結果に `"fallback": "llm-soft-judge"` を付与して下流に渡す
4. `recommended_next.mode` を `verify-only` に格下げし、人間レビューを強制

## 環境セットアップ（新規環境クローン時）

```bash
cd .claude/skills/skill-intake-interviewer
node --version   # ≥18 を確認
chmod +x scripts/*.js   # クローン直後のみ
node scripts/quality_gate.js --selftest   # 動作確認
```

## 禁止事項

- 絶対パス・ホストパスの埋め込み禁止（`/Users/...` を agent 内に書かない）
- shell 固有構文（zsh の `**`, fish の `$status` 等）禁止。POSIX sh 互換のみ
- `sudo` 要求禁止
- ネットワーク依存スクリプトは MCP 経由のみ（curl/wget 直接禁止）
