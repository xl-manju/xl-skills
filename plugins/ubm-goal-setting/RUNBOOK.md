# ubm-goal-setting Runbook

## Purpose

この runbook は、`ubm-goal-setting` plugin の個人利用運用で確認すべき入口、環境変数、保護境界、検証コマンドをまとめる。

## Entry Points

- `/ubm-goal-setting [weekly|monthly|bimonthly]`: 目標設定・振り返り対話を生成し、`validate-goal-output.py` で保存前検証する。
- `/ubm-knowledge-sync [--all] [--since YYYY-MM-DD] [--dry-run]`: L2 vault source の差分を検知し、knowledge JSON を同期する。

## Environment

- `UBM_VAULT_ROOT`: L2 raw vault source と Daily.md embed 更新先の root。未設定または未接続でも L1 curated knowledge は plugin 同梱 seed から読める。
- `CLAUDE_PLUGIN_ROOT`: hook と skill scripts の self-relative 解決に使う plugin root。

## Write Protection

`hooks/ubm-write-path-guard.py` は `UBM_VAULT_ROOT` 配下の Write/Edit/MultiEdit だけを検査する。

許可する vault write:

- `05_Project/UBM/目標設定/` 配下の目標設定ファイル保存
- `02_Configs/Templates/Daily.md` の embed 参照更新

保護対象外:

- vault 外の plugin 同梱 `knowledge/*.json`
- `UBM_VAULT_ROOT` 未設定時の任意 path
- Read など非 write tool

## Verification

```bash
python3 -m pytest plugins/ubm-goal-setting/tests -q
python3 plugins/ubm-goal-setting/skills/run-ubm-knowledge-sync/scripts/check-knowledge-split.py --dir plugins/ubm-goal-setting/knowledge
python3 -m json.tool plugins/ubm-goal-setting/.claude-plugin/plugin.json >/dev/null
python3 -m json.tool plugins/ubm-goal-setting/EVALS.json >/dev/null
```

## Acceptance Evidence

- C16: 週報/月報/期報を生成し、`validate-goal-output.py --type weekly|monthly|bimonthly` が PASS すること。
- C17: 既知の更新済み source で NEW/MODIFIED を検知し、knowledge-extractor が6カテゴリ分類と `router.json` / `registry.json` 同期を完了すること。
- C04: `UBM_VAULT_ROOT` 配下の許可外 path への Write/Edit/MultiEdit が exit 2 で阻止されること。

## Recovery

- `UBM_VAULT_ROOT` が未接続の場合、knowledge sync は 0件レポートとして正常終了する。vault を接続して再実行する。
- `check-knowledge-split.py` が 500行超過を検知した場合、25エントリ基準でサブテーマを設計し、`{category}-{subtopic}.json` へ分割する。
- 目標設定出力が validate に失敗した場合、未展開 `{{...}}`、全角数字、差分の `+/-`、やらないこと3項目、種別別必須見出しを優先して直す。
