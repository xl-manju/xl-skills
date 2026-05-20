# gen-rollback.py CLI 契約凍結仕様 (phase2-04)

本書は `scripts/phase2/gen-rollback.py` の CLI 契約を凍結する。**本実装は Phase2-06 の責務** であり、本タスクでは契約のみを確定する。Phase2-06 はこの契約を「凍結済」として参照し、逸脱があれば P0_breaking 手続きを起動する。

## 1. スクリプトパス

`scripts/phase2/gen-rollback.py`

## 2. 引数

| 引数 | 必須 | 型 | 説明 |
|---|---|---|---|
| `--plugin <name>` | yes | str | partition-plan.json の plugin 名 (例: `skill-governance-lint`) |
| `--out <path>` | yes | path | 生成する `rollback-<plugin>.sh` の絶対パス |
| `--snapshot-dir <path>` | no | path | pre-state snapshot dir。省略時は `eval-log/task/phase2-06/<plugin>/` |
| `--partition <path>` | no | path | partition-plan.json パス。省略時は `eval-log/task/phase2-02/partition-plan.json` |
| `--migration-order <path>` | no | path | migration-order.json パス。省略時は `eval-log/task/phase2-02/migration-order.json` |
| `--dry-run` | no | flag | 生成内容を stdout に出すのみ、ファイル書き出しなし |

## 3. exit codes

| code | 意味 |
|---|---|
| 0 | 生成成功 (rollback スクリプトを `--out` に書き出し、`bash -n` PASS) |
| 1 | snapshot 欠落 (settings.before.json / git-status.before.txt / claude-symlinks.before.txt のいずれか不在) |
| 2 | 構文エラー (生成スクリプトに対する `bash -n` が失敗) |
| 3 | 引数不正 (plugin 名が partition-plan.json に未登録、out パスが書き込み不可 等) |

## 4. stdout / stderr

- stdout: 生成された rollback スクリプトの絶対パスを 1 行だけ出力する (例: `/Users/.../rollback-skill-governance-lint.sh`)
- stderr: 進捗ログ、エラー詳細
- `--dry-run` 時のみ stdout に生成内容そのものを出力する

## 5. 入力

- pre-state snapshot dir (Section 5.1 の 4 ファイル)
- `eval-log/task/phase2-02/partition-plan.json` (plugin と moved paths の対応)
- `eval-log/task/phase2-02/migration-order.json` (投入順序、依存)
- `eval-log/task/phase2-04/rollback.template.sh` (本タスクで凍結したテンプレ)

## 6. 出力

- `<out>` パスへ `rollback-<plugin>.sh` を書き出し、`chmod +x` を付与
- gate: 書き出し直後に `bash -n <out>` を実行し、失敗時は出力ファイルを削除して exit 2

## 7. 不変条件

- 生成スクリプトは `rollback.template.sh` の 5 step 構造を逸脱してはならない
- 生成後の `bash -n` PASS が無い限り exit 0 にならない
- snapshot 欠落時は **必ず exit 1** で停止し、部分生成を残さない
- 同じ入力 (plugin, snapshot, partition) に対して **同一バイト列を生成** する (再現性)

## 8. Phase2-06 における利用

Phase2-06 の plugin 投入手順内で、各 plugin 投入直前に以下を実行する:

```
python3 scripts/phase2/gen-rollback.py \
  --plugin <name> \
  --out eval-log/task/phase2-06/<name>/rollback-<name>.sh
```

exit 0 を確認してから plugin の物理移行に進む。本契約からの逸脱は許容しない。
