# タスク 04: rollback / drift 検証仕様

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| ID | phase2-04 |
| 名称 | rollback / drift 検証仕様 |
| 担当 | AI (草案) + solo_operator (承認) |
| 期限 | 02 完了から 5 営業日以内 |
| 依存タスク | phase2-02 |
| ステータス | 完了 (2026-05-20) |

## Section 2. 目的と背景

複数 plugin 投入の量産では、1 plugin の投入失敗が他 plugin の派生資源 (`.claude/skills/`、`.claude/settings.json`) を巻き込みやすい。試験移行 (phase0 タスク 08) では DoD-8 で rollback.sh の事前生成と `bash -n` PASS を要求していた。本タスクではこれを量産化し:

- 各 plugin 投入毎の `rollback-<plugin>.sh` を **自動生成**するアルゴリズム仕様
- `--check` を本番運用ループに組み込む drift 検証仕様
- 失敗時のロールバック手順 (中間状態へ戻す手順)

を確定する。これらが揃っていないと 06 (実行) を始められない。

根拠: `doc/migration/phase0/08-trial-migration-skill-creator.md` DoD-8、横断不安要素チェック表「rollback 不能な物理移行」。

## Section 3. 用語集 (本タスク固有)

| 用語 | 定義 |
|---|---|
| rollback.sh | ある plugin 投入直前の状態に戻すための shell スクリプト。`bash -n` PASS が前提 |
| drift | 期待状態 (build CLI plan) と実状態 (`.claude/` 派生) の差分 |
| pre-state snapshot | plugin 投入直前の `git status -s`、`settings.json` 全文、`find .claude -type l` 出力 |
| 自動生成 | snapshot から rollback.sh を機械生成。手書き不可 (再現性のため) |

共通用語は README 参照。

## Section 4. スコープ

含む:

- rollback.sh 生成アルゴリズム仕様 (snapshot → script の写像)
- drift 検証コマンド列 (per-plugin と Phase 全体)
- 失敗時の中間状態復旧手順
- 検証ログの保存パス規約

含まない:

- rollback スクリプトの実装コード (本仕様は記述のみ、生成は 06 実行時)
- drift 自動修復 (人間判断を介す)

## Section 5. 前提条件

1. phase2-02 完了 (partition-plan.json 確定)
2. Phase 0 凍結 CLI が `--check` exit 0
3. `bash >= 5` (macOS 系では `/usr/bin/env bash` を使う)
4. `git >= 2.30` (snapshot に `git stash` を使うため)

### 依存ツールCLI契約確認

- `git stash --help`、`git status --porcelain --help`、`bash -n --help` の存在
- Phase 0 frozen CLI の help 出力一致

## Section 6. 完了条件 (DoD)

| DoD | 内容 | 機械検証 |
|---|---|---|
| DoD-1 | `eval-log/task/phase2-04/rollback-generator-spec.md` が存在 | `test -f` |
| DoD-2 | rollback.sh のスケルトンサンプルが生成され `bash -n` PASS | `bash -n eval-log/task/phase2-04/rollback.template.sh` |
| DoD-3 | drift 検証コマンド列が明記され、シェル構文 PASS | `bash -n eval-log/task/phase2-04/drift-check.sh` |
| DoD-4 | 失敗時復旧フロー (sequence diagram or 番号付きリスト) が記載 | `grep -c "^[0-9]\." eval-log/task/phase2-04/rollback-generator-spec.md` ≥ 5 |
| DoD-5 | 検証ログ保存パス規約が `eval-log/task/phase2-06/<plugin>/` に固定 | spec 内に明記 |
| DoD-6 | `gen-rollback-spec.md` が存在し、`scripts/phase2/gen-rollback.py` の CLI 契約が明記される | `test -f eval-log/task/phase2-04/gen-rollback-spec.md && grep -q "scripts/phase2/gen-rollback.py" eval-log/task/phase2-04/gen-rollback-spec.md` |
| DoD-7 | rollback fixture/sandbox 検証方針が記載され、pre-state 復旧検査を gate 化している | `grep -q "pre-state" eval-log/task/phase2-04/rollback-generator-spec.md && grep -q "fixture" eval-log/task/phase2-04/rollback-generator-spec.md` |
| DoD-8 | review-approval.json が `approved` | 内容検査 |

## Section 7. 実行手順

### Step 7.1 rollback.sh テンプレート設計

テンプレート構造:

```bash
#!/usr/bin/env bash
# Auto-generated rollback for plugin: <plugin>
# Pre-state snapshot: <snapshot-id>
set -euo pipefail

# 1. .claude/ 派生を削除 (build CLI が再生成するため)
find .claude/skills -lname '*plugins/<plugin>/*' -delete
find .claude/agents -lname '*plugins/<plugin>/*' -delete

# 2. plugins/<plugin>/ を git restore
git restore --staged --worktree plugins/<plugin>/ 2>/dev/null || rm -rf plugins/<plugin>

# 3. creator-kit/ 内の移動元を git restore
for path in <moved-paths>; do
  git restore --staged --worktree "$path"
done

# 4. settings.json を pre-state に戻す
cp eval-log/task/phase2-06/<plugin>/settings.before.json .claude/settings.json

# 5. build-claude-* --check で整合確認
python3 scripts/build-claude-symlinks.py --check
python3 scripts/build-claude-settings.py --check
```

### Step 7.2 snapshot → script 写像アルゴリズム

```
input:
  - plugin name
  - moved files list (from migration-order.json の plugin エントリ)
  - settings.before.json snapshot
output:
  - rollback-<plugin>.sh
algorithm:
  1. snapshot 取得時刻と plugin 名をヘッダに記載
  2. moved files から `git restore` 行を生成
  3. settings.before.json の差し戻し行を生成
  4. .claude/ 派生の plugin 由来 symlink 削除行を生成
  5. build CLI --check 実行行を末尾に付与
  6. `bash -n` で構文検証
```

### Step 7.3 drift 検証コマンド列定義

```bash
# drift-check.sh (per-plugin 投入後、および Phase 全体の最終確認に使用)
set -euo pipefail
out_dir="${1:?usage: drift-check.sh <eval-log-output-dir>}"
mkdir -p "$out_dir"
python3 scripts/build-claude-symlinks.py --check --json > "$out_dir/drift-symlink.json"
python3 scripts/build-claude-settings.py --check --json > "$out_dir/drift-settings.json"
jq -e '.summary.conflict == 0 and ([.plan[] | select(.action != "noop")] | length == 0)' "$out_dir/drift-symlink.json" > /dev/null
jq -e '(.conflicts | length) == 0 and (.invariants_checked | length) >= 12' "$out_dir/drift-settings.json" > /dev/null
echo "drift OK"
```

### Step 7.4 失敗時復旧フロー記述

```
1. 投入対象 plugin の rollback-<plugin>.sh 実行
2. drift-check.sh 実行 (exit 0 確認)
3. 失敗した plugin を migration-order.json から除外、もしくは原因修正
4. 02 partition-plan.json の境界見直し (必要なら P0_breaking 手続き)
5. 06 を再開
```

### Step 7.5 spec 文書化

`eval-log/task/phase2-04/rollback-generator-spec.md` に上記を集約。fixture/sandbox ではサンプル plugin 投入前の pre-state snapshot を保存し、rollback 実行後に `git status -s`、`.claude/` symlink 集合、settings user section hash が pre-state と一致することを復旧 gate として記載する。

### Step 7.6 テンプレートの構文検証

```bash
bash -n eval-log/task/phase2-04/rollback.template.sh
bash -n eval-log/task/phase2-04/drift-check.sh
```

### Step 7.7 レビュー承認

solo_operator が `review-approval.json` 生成。

## Section 8. 検証手順

| 完了条件 | 検証コマンド |
|---|---|
| DoD-1 | `test -f eval-log/task/phase2-04/rollback-generator-spec.md && echo PASS` |
| DoD-2 | `bash -n eval-log/task/phase2-04/rollback.template.sh && echo PASS` |
| DoD-3 | `bash -n eval-log/task/phase2-04/drift-check.sh && echo PASS` |
| DoD-4 | `grep -c "^[0-9]\." eval-log/task/phase2-04/rollback-generator-spec.md` |
| DoD-5 | spec 内に該当パス記載 |
| DoD-6 | `test -f eval-log/task/phase2-04/gen-rollback-spec.md && grep -q "scripts/phase2/gen-rollback.py" eval-log/task/phase2-04/gen-rollback-spec.md` |
| DoD-7 | `grep -q "pre-state" eval-log/task/phase2-04/rollback-generator-spec.md && grep -q "fixture" eval-log/task/phase2-04/rollback-generator-spec.md` |
| DoD-8 | review-approval.json |

## Section 9. リスクと対策

| 失敗モード | 対策 | INV |
|---|---|---|
| rollback.sh が pre-state を取りこぼし元状態に戻らない | Step 7.2 アルゴリズムで snapshot を機械生成 | INV-1 |
| drift 検証が `.claude/` 派生のみで partition-plan 側を見逃す | drift-check.sh で plugins/ 配下も同時に検査 | INV-9 |
| `bash -n` PASS でも実行時にエラー | Step 7.6 と 06 の dry-run 二段構成で補強 | - |
| 失敗復旧フローが運用者に伝わらない | spec に番号付き手順を必須化 (DoD-4) | - |

## Section 10. 成果物一覧

| 成果物 | パス | 責任者 |
|---|---|---|
| rollback-generator-spec.md | `eval-log/task/phase2-04/rollback-generator-spec.md` | AI |
| rollback.template.sh | `eval-log/task/phase2-04/rollback.template.sh` | AI |
| drift-check.sh | `eval-log/task/phase2-04/drift-check.sh` | AI |
| gen-rollback-spec.md | `eval-log/task/phase2-04/gen-rollback-spec.md` | AI |
| review-approval.json | `eval-log/task/phase2-04/review-approval.json` | solo_operator |

`gen-rollback-spec.md` には `scripts/phase2/gen-rollback.py` の CLI 仕様 (引数: `--plugin <name>` `--out <path>`、exit コード: 0=生成成功/1=snapshot 欠落/2=構文エラー、stdout: rollback スクリプトパス) を明記する。06 はこの仕様を「凍結済」として参照する。

ツール契約 (凍結参照): Phase 0 `scripts/build-claude-*.py` の `--check --json` 出力スキーマに依存。スキーマ変更時は本仕様も再策定。

## Section 11. 参照ドキュメント

- `doc/migration/phase0/08-trial-migration-skill-creator.md` DoD-8 と Step 群
- `eval-log/task/08/rollback.sh` (試験移行で生成された実例)
- `eval-log/task/phase2-02/partition-plan.json`

## Section 12. 中学生レベル概念説明

引っ越しで「家具を運び損なって元の場所に戻したいとき」のための手順書を作る作業です。各家具ごとに「どの順番でどこへ戻すか」のメモを事前に作っておけば、運送中に問題が起きてもすぐ元の家に戻せます。さらに、家具が運ぶ前と同じ位置にあるかをチェックする「ものさし」(= drift-check.sh) も用意しておきます。

## Section 13. チェックリスト

- [x] phase2-02 DoD 全 PASS
- [x] rollback.template.sh と drift-check.sh の `bash -n` PASS
- [x] spec md に番号付き失敗復旧フロー >= 5 項目
- [x] gen-rollback-spec.md と fixture/sandbox 復旧 gate を明記
- [x] review-approval.json 生成
