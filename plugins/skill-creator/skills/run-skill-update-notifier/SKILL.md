---
name: run-skill-update-notifier
description: Skill 実行末尾に最新版有無を1行通知するとき、ユーザーが意識せず最新版の存在に気づける仕組みが欲しいときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Bash(python3 *)]
kind: run
prefix: run
owner: team-platform
since: 2026-05-21
source: internal
source-tier: internal
last-audited: 2026-05-21
audit-trigger: quarterly
role_suffix: none
---

# run-skill-update-notifier

## Purpose & Output Contract

**入力**: なし (hook 経由で自動起動) / 明示起動時はオプションで `--check-only` / `--refresh`。
**出力**: Skill 実行末尾に 1 行付記 `(installed: vX.Y.Z / latest: vA.B.C — /skill-update で更新)`。同一/未提供/オフライン時は無出力。
**副作用**: `~/.cache/xl-skills/version-snapshot.json` の更新のみ。plugin manifest は変更しない。
**完了条件**: cache 比較が完了 (差分有無を問わず) し、通知出力 or no-op を決定したとき。

## Boundary

通知のみ。実際の pull/install/apply/rollback はやらない。version 重複解消もやらない (Stage 0/2 の別 Skill に分離)。既存 plugin.json / marketplace.json / bundles.json / skill-intake-self-updater は一切変更しない。

## Key Rules

1. **非破壊**: 既存 manifest を touch しない (read-only)。
2. **graceful degradation**: CHANGELOG.md 不在 / オフライン / cache 不在 / 権限不足のいずれも静かに no-op。エラーで Skill 実行を妨げない。
3. **Python stdlib のみ**: 外部依存ゼロ (json, pathlib, urllib.request, os, datetime のみ)。
4. **24h TTL**: cache 鮮度判定は 24 時間。それ未満は再 scan しない。
5. **PostToolUse filter**: hook は `tool_name == "Skill"` のときだけ通知発火。Bash/Read 等の末尾には付かない。
6. **抑制フラグ**: 環境変数 `XL_SKILLS_NOTIFY=off` で完全無効化。

## Hook Integration Map

| Hook Event | Script | 役割 | exit |
|---|---|---|---|
| UserPromptExpansion | `scripts/hook-cache-refresh.py` | 24h TTL で cache 再 scan (バックグラウンド準同期) | 0固定 |
| PostToolUse | `scripts/hook-notify-skill-end.py` | `tool_name == "Skill"` のとき末尾 1 行付記 | 0固定 |

settings.json マージ案は `references/hook-wiring.md` 参照。自動 merge はしない (人間承認)。

## Responsibilities (brief 由来)

- **R1 changelog-cache-check**: 各 plugin の `CHANGELOG.md` を読み、cache と差分検出 (`scripts/notifier-check.py`)
- **R2 notification-formatting**: 差分時の 1 行通知整形 (出力規約は `references/output-format.md`)
- **R3 graceful-degradation-guard**: 例外を握りつぶし no-op に倒す保護層

## Steps

### Step 1: cache 鮮度確認

```bash
python3 scripts/notifier-check.py --mode cache-status
```
- 出力: `fresh` / `stale` / `absent`。`fresh` なら Step 2 を skip。

### Step 2: plugin scan と cache 更新

```bash
python3 scripts/notifier-check.py --mode refresh --plugins-root plugins/
```
- 各 `plugins/*/CHANGELOG.md` から最新 version を抽出 (semver 一致なくとも文字列保持)。
- `~/.cache/xl-skills/version-snapshot.json` に書き出す (atomic rename)。
- 例外時は no-op (exit 0)。

### Step 3: 通知文字列生成

```bash
python3 scripts/notifier-check.py --mode notify --plugin "$PLUGIN_NAME"
```
- installed (= plugin.json) vs latest (= cache) を比較。
- 一致 / cache 未提供 / installed 未取得 → 空文字列。
- 差分あり → `(installed: vX.Y.Z / latest: vA.B.C — /skill-update で更新)` を stdout。
- `XL_SKILLS_NOTIFY=off` のとき強制 no-op。

### Step 4: PostToolUse hook 連携

`hook-notify-skill-end.py` が `tool_name == "Skill"` を判定し、Step 3 の出力を Skill 実行末尾に付記。1 セッション内で同一 plugin の通知は重複させない (cache に `last_notified_at` を記録)。

## Constraints

- 実行中スキルの自己書換禁止 (`PreToolUse` 等で deny は不要、本 Skill は write しないため)。
- ネットワーク取得は行わない (cache はローカルファイルのみ)。将来 Stage 2 で git fetch を別 Skill に分離。
- 出力フォーマットの変更は `references/output-format.md` を Edit し、本 SKILL は touch しない。

## Gotchas

- **PostToolUse 全 tool 発火事故**: filter を忘れると Read/Bash 末尾にも通知が付き UX 大破壊。`hook-notify-skill-end.py` の matcher 必須。
- **cache 不在初回**: 起動直後は cache 空。Step 2 が走るまで Step 3 は無出力 (graceful)。
- **24h TTL の挙動**: `last_refreshed_at` が cache に無いと毎回 refresh して負荷増。`fresh` 判定は時刻欠落時 `stale` 扱い。
- **マルチプロジェクト共用 cache**: `~/.cache/xl-skills/` は user-global。複数 worktree で同じ plugin を見ても整合する設計。

## Additional Resources

- `scripts/notifier-check.py` — cache 比較ロジック (CLI 単体実行可)
- `references/output-format.md` — 通知文字列規約
- `references/hook-wiring.md` — settings.json hook 配線案
- 設計書 10 章 §7 — Hook 競合解決
- 関連 Stage: Stage 0 `lint-version-singletruth` (将来) / Stage 2 `run-skill-update-apply` (将来)
