# doc/migration/phase3 — Phase 3 carry-over backlog

最終更新: 2026-05-20

## 目的

Phase 2 closure で `carry_over_items` として残した項目を、未判断の `deferred/` 置き場から Phase 3 の正本 backlog へ移管する。本ディレクトリの存在は Phase 2 未完了を意味しない。時間依存 gate と人間レビュー gate は Phase 3 内 backlog として扱う。

## carry-over 解決状況

| 項目 | Phase 2 状態 | Phase 3 取扱い | 証跡 |
|---|---|---|---|
| marketplace 連携 | carry-over | `.claude-plugin/marketplace.json` を正本として維持し、公開レビューは人間 gate | `.claude-plugin/marketplace.json` |
| classify_change CI 強制 | carry-over | `governance-check.yml` を Phase 2 後の `plugins/` 構成へ更新 | `.github/workflows/governance-check.yml` |
| 機能/コスト比 3ヶ月評価 | carry-over | 評価開始条件と観測項目を backlog 化 | `phase3-evaluation-baseline.md` |
| defer verdict 資産 2 件 | carry-over | `deferred/` から本ディレクトリへ移管済み。残る作業は editorial decision | `future-improvements.md`, `pending-frontmatter.md` |
| dirty worktree の整理 | carry-over | 変更は戻さず、Phase 2/3 証跡として記録 | `eval-log/task/phase3-carryover/` |

## 完了条件

- `deferred/` に Phase 2 由来の未判断ファイルが残っていない
- `creator-kit/` 参照が plugin skill の外部参照 inventory で 0
- marketplace manifest が JSON valid
- CI workflow が Phase 2 後の `plugins/` 構成を参照している

## eval-log 不変性ポリシー (Phase 2 closure 後の運用ルール)

closure 済 Phase 配下の eval-log (`eval-log/phase/<N>/closure.json`、`eval-log/task/<closed-task-id>/*`) は**事後変更しない**。closure 後に修正が必要になった場合は、次のいずれかで扱う:

- **集計の整合不整合**(本 review で検出した F-1 型): closure.json と PHASE-GATE-COMPLETION.md を 1 つの addendum commit で同期更新し、コミットメッセージに `(phase-gate-addendum)` を明記
- **証跡の実行ログ更新**(drift-check 再実行など): 新規 addendum task ID (例: `phase2-fix-01`) を発行し、`eval-log/task/<new-id>/` に分離記録。closure 済タスク配下は触らない
- **誤記訂正以外の変更**: 当該 Phase の re-open が必要。governance-log に re-open 理由を追記

本ポリシーは governance-check CI が前倒し整備される (F-7) までの暫定ルールとして適用する。
