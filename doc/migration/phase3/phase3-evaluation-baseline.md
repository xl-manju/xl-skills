# Phase 3 evaluation baseline

開始日: 2026-05-20

## 目的

Phase 2 の plugin 化後、3ヶ月評価に必要な観測項目を固定する。評価期間そのものは時間経過を必要とするため、本ファイルでは開始条件、観測項目、合格基準を確定する。

## 観測項目

| 項目 | 測定方法 | 合格基準 |
|---|---|---|
| build symlink drift | `python3 scripts/build-claude-symlinks.py --check` | exit 0 |
| settings drift | `python3 scripts/build-claude-settings.py --check` | exit 0 |
| plugin manifest validity | `jq` over `plugins/*/.claude-plugin/plugin.json` | 全件 JSON valid |
| marketplace manifest validity | `jq -e '.plugins | length >= 8' .claude-plugin/marketplace.json` | PASS |
| creator-kit stale reference | `lint-external-refs.py` inventory | external_ref_count 0 under configured prefixes |
| CI guard viability | `guard-change-category.py --base HEAD --report` | policy load succeeds |

## 評価判定

機能/コスト比は、上記 gate が維持され、plugin 運用で発生した手戻りが従来運用より少ない場合に `>= 1` と判定する。期間満了前に marketplace 公開は行わない。
