---
last_fetched: 2026-05-17
source_url: https://docs.claude.com/en/docs/claude-code/skills
schema_version: "1.0"
maintainer: team-skills
update_policy: manual-weekly
---

# yaml-spec-cache

Claude Code Skills YAML frontmatter 仕様の機械可読要約。
`ref-yaml-spec-fetcher` が参照する週次キャッシュ。
30日超過で `last_fetched` が古い場合は手動更新を行うこと（SKILL.md「手動取得手順」参照）。

## frontmatter フィールド一覧

| field | required | type | default | notes |
|---|---|---|---|---|
| `name` | No | string | directory name | lowercase, numbers, hyphens のみ。最大 64 文字 |
| `description` | Recommended | string | body first paragraph | `when_to_use` と合算で 1,536 文字 cap |
| `when_to_use` | No | string | — | `description` に append。1,536 文字 cap に含まれる |
| `argument-hint` | No | string | — | autocomplete 表示用ヒント。例: `[issue-number]` |
| `arguments` | No | string \| list | — | named positional arguments。`$name` で参照 |
| `disable-model-invocation` | No | boolean | false | true にすると Claude 自動呼び出し・subagent preload 両方を止める |
| `user-invocable` | No | boolean | true | false にすると `/` menu から非表示 |
| `allowed-tools` | No | string \| list | — | permission prompt なしで使える tools |
| `model` | No | string | session model | current turn のみ適用。`inherit` 可 |
| `effort` | No | string | — | `low` / `medium` / `high` / `xhigh` / `max` |
| `context` | No | string | — | `fork` で forked subagent として実行 |
| `agent` | No | string | general-purpose | `context: fork` 時の subagent type |
| `hooks` | No | object | — | Skill lifecycle scope の hooks |
| `paths` | No | string \| list | — | file glob による activation 制限 |
| `shell` | No | string | bash | `!` コマンドの shell。`powershell` も可（要環境変数） |

## 独自拡張フィールド（xl-skills プロジェクト運用）

以下は公式仕様外の xl-skills プロジェクト独自フィールド（frontmatter に記載するが公式 Claude Code は無視する）。

| field | type | default | notes |
|---|---|---|---|
| `kind` | string | — | `ref` / `run` / `wrap` / `assign` / `delegate`。prefix と一致が原則 |
| `effect` | string | — | `none` / `local-artifact` / `external`。副作用レベル |
| `owner` | string | — | 担当チーム識別子 |
| `since` | string | — | ISO 日付。Skill 作成日 |

## string substitution 変数

| variable | 意味 |
|---|---|
| `$ARGUMENTS` | invocation 時の全引数文字列 |
| `$ARGUMENTS[N]` | 0-based index で N 番目引数 |
| `$N` | `$ARGUMENTS[N]` の shorthand |
| `$name` | `arguments` リストで宣言した named 引数 |
| `${CLAUDE_SESSION_ID}` | current session ID |
| `${CLAUDE_EFFORT}` | current effort level |
| `${CLAUDE_SKILL_DIR}` | Skill directory 絶対パス |

## invocation control マトリクス

| 設定 | ユーザー呼び出し | Claude 自動呼び出し | context 読み込み |
|---|---|---|---|
| (default) | Yes | Yes | description 常時 context |
| `disable-model-invocation: true` | Yes | No | description context に載らない |
| `user-invocable: false` | No | Yes | description 常時 context |

## 配置場所

| 種類 | パス | 適用範囲 |
|---|---|---|
| Enterprise | managed settings | 組織全ユーザー |
| Personal | `~/.claude/skills/<name>/SKILL.md` | 全プロジェクト |
| Project | `.claude/skills/<name>/SKILL.md` | 現在プロジェクト |
| Plugin | `<plugin>/skills/<name>/SKILL.md` | plugin 有効時 |

## 更新履歴

| 日付 | 変更要約 | 担当 |
|---|---|---|
| 2026-05-17 | 初版投入（16章 frontmatter 仕様を機械可読要約に変換） | team-skills |
