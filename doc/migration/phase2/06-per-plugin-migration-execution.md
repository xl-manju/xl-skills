# タスク 06: per-plugin 物理移行 (実行)

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| ID | phase2-06 |
| 名称 | per-plugin 物理移行実行 |
| 担当 | AI (実行) + solo_operator (gate 承認) |
| 期限 | 03, 04, 05 完了から 10 営業日以内 |
| 依存タスク | phase2-03, phase2-04, phase2-05 |
| ステータス | 未着手 |

## Section 2. 目的と背景

01〜05 で確定した仕様 (inventory / partition / per-plugin procedure / rollback / CONVENTIONS) を実行する。本タスクが Phase 2 本番の最大変更ステップであり、`plugins/` 配下に複数 plugin が物理的に並ぶ最終状態を作る。試験移行 (phase0 タスク 08) の量産版。

根拠: `doc/migration/phase2/03-per-plugin-migration-procedure.md`、phase0 08 試験移行の成功証跡。

## Section 3. 用語集 (本タスク固有)

| 用語 | 定義 |
|---|---|
| 投入 (deploy) | 1 plugin 分の git mv + plugin.json 生成 + build CLI --check PASS までの一連操作 |
| 投入順 | `eval-log/task/phase2-03/migration-order.json` で確定した順序 |
| gate | 各 plugin 投入完了時点で solo_operator が次 plugin へ進む承認を出す関門 |
| dry-run | `--check` のみ実行する非破壊的事前確認 |

共通用語は README 参照。

## Section 4. スコープ

含む:

- partition-plan の各 plugin を `plugins/<name>/` へ git mv
- 各 plugin の `plugin.json` をテンプレートから生成
- 各 plugin 投入後の build CLI --check PASS 確認
- 各 plugin の rollback-<plugin>.sh を 04 仕様に従って自動生成
- 各 plugin の検証ログを `eval-log/task/phase2-06/<plugin>/` に保存

含まない:

- creator-kit ディレクトリの物理削除 (07 の責務)
- partition 設計の変更 (02 の責務、変更時は P0_breaking 経由)
- Phase 2 統合検証 (08 の責務)

## Section 5. 前提条件

1. phase2-03, phase2-04, phase2-05 が DoD 全 PASS
2. `eval-log/task/phase2-03/migration-order.json` 確定済
3. `eval-log/task/phase2-04/rollback.template.sh` の `bash -n` PASS
4. 開始時点で `git status -s` を保存 (Phase 2 本番開始 snapshot)
5. `scripts/build-claude-symlinks.py --check` と `scripts/build-claude-settings.py --check` が exit 0

### 依存ツールCLI契約確認

- Phase 0 凍結 frozen contract と現状の `--help` 出力が完全一致
- `git mv`、`bash`、`python3`、`jq` 利用可能

## Section 6. 完了条件 (DoD)

| DoD | 内容 | 機械検証 |
|---|---|---|
| DoD-1 | partition-plan の全 plugin が `plugins/<name>/` 配下に存在 | `for p in $(jq -r '.partitions[].name' eval-log/task/phase2-02/partition-plan.json); do test -d "plugins/$p"; done` |
| DoD-2 | 全 plugin の `.claude-plugin/plugin.json` が JSON valid | 各 plugin で `jq . plugins/$p/.claude-plugin/plugin.json` |
| DoD-3 | 全 plugin 投入後、`build-claude-symlinks.py --check --json` の plan 全件 noop & conflicts 0 | drift-check.sh PASS |
| DoD-4 | 全 plugin 投入後、`build-claude-settings.py --check --json` の conflicts 0 & invariants_checked >= 12 | drift-check.sh PASS |
| DoD-5 | 全 plugin について `eval-log/task/phase2-06/<plugin>/rollback-<plugin>.sh` 存在し `bash -n` PASS | 全件ループ確認 |
| DoD-6 | `.claude/settings.json` user セクション SHA256 が Phase 2 開始前後で一致 | `diff` |
| DoD-7 | partition-plan に無い skill / agent が `plugins/` に混入していない | 集合比較 |
| DoD-8 | 各 plugin 投入毎に `eval-log/task/phase2-06/<plugin>/dod-per-plugin.md` が PASS 記録 | 全件確認 |
| DoD-9 | review-approval.json が `decision == "approved"` | 内容検査 |
| DoD-10 | 補助ツール `scripts/phase2/deploy-plugin.sh` と `scripts/phase2/gen-rollback.py` が存在し、凍結済 CLI 仕様に従って実行可能 | `test -x scripts/phase2/deploy-plugin.sh && python3 scripts/phase2/gen-rollback.py --help > /dev/null` |

## Section 7. 実行手順

### Step 7.1 Phase 2 開始 snapshot

```bash
mkdir -p eval-log/task/phase2-06
git status -s > eval-log/task/phase2-06/phase2-start.git-status.txt
cp .claude/settings.json eval-log/task/phase2-06/settings.phase2-start.json
find plugins -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort > eval-log/task/phase2-06/phase2-start.plugins.txt
python3 -c "
import hashlib, json, pathlib
s = json.load(open('.claude/settings.json'))
# user セクション = マーカー区間外
# ここでは settings 全体 hash を取り、INV-1 検査は build CLI に委ねる
print(hashlib.sha256(pathlib.Path('.claude/settings.json').read_bytes()).hexdigest())
" > eval-log/task/phase2-06/settings.phase2-start.sha256
# user section hash 専用 snapshot を取得 (08 DoD-5 との同種比較に使用)
python3 scripts/build-claude-settings.py --print-user-section-hash > eval-log/task/phase2-06/user-section-start.sha256
```

### Step 7.2 per-plugin ループ

`migration-order.json` の rank 昇順で各 plugin を投入:

```bash
for plugin in $(jq -r '.order | sort_by(.rank) | .[].plugin' eval-log/task/phase2-03/migration-order.json); do
  echo "=== deploying $plugin ==="
  mkdir -p "eval-log/task/phase2-06/$plugin"
  bash scripts/phase2/deploy-plugin.sh "$plugin" || { echo "FAILED $plugin"; exit 1; }
  python3 scripts/build-claude-symlinks.py --check --json > "eval-log/task/phase2-06/$plugin/symlinks-check.json"
  python3 scripts/build-claude-settings.py --check --json > "eval-log/task/phase2-06/$plugin/settings-check.json"
  bash eval-log/task/phase2-04/drift-check.sh "eval-log/task/phase2-06/$plugin"
done
```

`scripts/phase2/deploy-plugin.sh` は本タスクで新規導入する **per-plugin プレイブック実装**。中身は 03 の Step P-1〜P-9 を忠実に踏襲。

### Step 7.3 deploy-plugin.sh 実行

`scripts/phase2/deploy-plugin.sh` の CLI 仕様は `eval-log/task/phase2-03/deploy-plugin-spec.md` で凍結済。本タスクはその仕様に従って実行するのみ。

各 plugin の投入は以下で行う:

```bash
bash scripts/phase2/deploy-plugin.sh "$plugin"
```

deploy-plugin.sh 内部は 03 のプレイブック Step P-1〜P-9 を忠実に踏襲する。`plugin.json` の `name` フィールドは `jq` で置換し、description 等の他フィールドを誤置換しない (03 Step 7.4 の方針に従う)。実装の詳細は `eval-log/task/phase2-03/deploy-plugin-spec.md` を唯一の正本とする。

`scripts/phase2/gen-rollback.py` の CLI 仕様は `eval-log/task/phase2-04/gen-rollback-spec.md` で凍結済。rollback.sh の生成は 04 仕様のアルゴリズムに従う。

### Step 7.4 投入後の DoD 記録

各 plugin 毎に `eval-log/task/phase2-06/<plugin>/dod-per-plugin.md` を生成:

```markdown
# plugin: <plugin> deploy DoD

| 項目 | 結果 |
|---|---|
| symlinks-check.json conflicts | 0 |
| settings-check.json conflicts | 0 |
| settings-check.json invariants_checked | 12 |
| rollback-<plugin>.sh bash -n | PASS |
| 投入時刻 | <timestamp> |
```

### Step 7.5 user セクション SHA256 検証

各 plugin 投入後、`build-claude-settings.py --print-user-section-hash` を Phase 2 開始時のスナップショット (Step 7.1 で保存) と同種比較する:

```bash
current_sha=$(python3 scripts/build-claude-settings.py --print-user-section-hash)
start_sha=$(cat eval-log/task/phase2-06/user-section-start.sha256)
if [ "$current_sha" != "$start_sha" ]; then
  echo "ERROR: user セクション SHA256 変化 ($start_sha -> $current_sha)"
  exit 1
fi
echo "user section SHA256 unchanged: $current_sha"
```

### Step 7.6 全 plugin 完了確認

partition-plan.json の全 plugin 名と `plugins/` の実在ディレクトリを **双方向** で比較する。試験移行済 plugin など Phase 2 開始前から存在した plugin は Step 7.1 の `phase2-start.plugins.txt` を除外基準にする:

```bash
# partition-plan の全 plugin 名 (期待値)
expected=$(jq -r '.partitions[].name' eval-log/task/phase2-02/partition-plan.json | sort)

# plugins/ 配下の実在ディレクトリから Phase 2 開始前 plugin を除外
actual=$(python3 -c "
import pathlib
start = set(pathlib.Path('eval-log/task/phase2-06/phase2-start.plugins.txt').read_text().splitlines())
dirs = sorted(d.name for d in pathlib.Path('plugins').iterdir() if d.is_dir() and d.name not in start)
print('\\n'.join(dirs))
")

diff <(echo "$expected") <(echo "$actual") && echo "all deployed (双方向一致)"
```

### Step 7.7 README ステータス更新 + レビュー承認

`doc/migration/phase2/README.md` のステータス更新と `eval-log/task/phase2-06/review-approval.json` 生成。

## Section 8. 検証手順

| 完了条件 | 検証コマンド |
|---|---|
| DoD-1 | DoD 表 inline |
| DoD-2 | `for p in plugins/*; do jq . "$p/.claude-plugin/plugin.json" > /dev/null; done` |
| DoD-3 | `python3 scripts/build-claude-symlinks.py --check --json | jq -e '.summary.conflict == 0 and ([.plan[] | select(.action!="noop")] | length == 0)'` |
| DoD-4 | `python3 scripts/build-claude-settings.py --check --json | jq '.conflicts | length, (.invariants_checked | length)'` で 0, ≥12 |
| DoD-5 | `for f in eval-log/task/phase2-06/*/rollback-*.sh; do bash -n "$f"; done` |
| DoD-6 | `user-section-start.sha256` と最終 `--print-user-section-hash` 出力を比較 |
| DoD-7 | 集合比較スクリプト Step 7.6 |
| DoD-8 | `ls eval-log/task/phase2-06/*/dod-per-plugin.md | wc -l` = partition 数 |
| DoD-9 | review-approval.json 内容 |
| DoD-10 | `test -x scripts/phase2/deploy-plugin.sh && python3 scripts/phase2/gen-rollback.py --help > /dev/null` |

## Section 9. リスクと対策

| 失敗モード | 対策 | INV |
|---|---|---|
| 投入順序の前提が壊れて中間状態 drift | 各 plugin 投入後に drift-check.sh を必ず実行 | INV-Mid-1, INV-Mid-2 |
| `git mv` でファイル属性が変わる | git の挙動により mode 変化なし。`git diff` で確認 | - |
| plugin.json schema mismatch | テンプレートは試験移行で認識実証済 | - |
| user セクション破壊 | INV-1 hash 比較 | INV-1 |
| 試験移行済 skill-creator を巻き込み | partition-plan に skill-creator を含めない (DoD-6 of 02) | INV-9 |

## Section 10. 成果物一覧

| 成果物 | パス | 責任者 |
|---|---|---|
| `plugins/<name>/` ツリー | リポジトリ直下 | AI |
| 各 plugin の plugin.json | `plugins/<name>/.claude-plugin/plugin.json` | AI |
| 各 plugin の rollback-<plugin>.sh | `eval-log/task/phase2-06/<plugin>/rollback-<plugin>.sh` | AI |
| 各 plugin の symlinks-check.json | `eval-log/task/phase2-06/<plugin>/symlinks-check.json` | AI |
| 各 plugin の settings-check.json | `eval-log/task/phase2-06/<plugin>/settings-check.json` | AI |
| 各 plugin の dod-per-plugin.md | `eval-log/task/phase2-06/<plugin>/dod-per-plugin.md` | AI |
| Phase 2 開始 snapshot | `eval-log/task/phase2-06/phase2-start.*` | AI |
| review-approval.json | `eval-log/task/phase2-06/review-approval.json` | solo_operator |
| deploy-plugin.sh | `scripts/phase2/deploy-plugin.sh` | AI |
| gen-rollback.py | `scripts/phase2/gen-rollback.py` | AI |

ツール契約 (凍結参照): `scripts/build-claude-symlinks.py`、`scripts/build-claude-settings.py` を Phase 0 frozen contract のまま使用。`scripts/phase2/deploy-plugin.sh` と `scripts/phase2/gen-rollback.py` は本 Phase 用補助ツールで、CLI 仕様は 03/04 で凍結。

## Section 11. 参照ドキュメント

- `doc/migration/phase2/03-per-plugin-migration-procedure.md`
- `doc/migration/phase2/04-rollback-and-drift-specification.md`
- `doc/migration/phase0/08-trial-migration-skill-creator.md` (試験移行成功例)
- `eval-log/task/08/dod-verification.md`

## Section 12. 中学生レベル概念説明

引っ越し本番の実行日です。荷物 (= plugin の中身) を、運送順マニュアル (= migration-order.json) と運び方マニュアル (= 03 プレイブック) に従って、1 箱ずつ新居 (= plugins/) に運び込みます。1 箱運び終わるたびに「途中で家具が傾いていないか」(= drift-check.sh) を確認し、「もし戻したくなったら戻せるか」(= rollback.sh) を必ず準備します。途中で問題が起きたら次の箱に進まず一旦止めます。

## Section 13. チェックリスト

- [ ] phase2-03 / 04 / 05 全 DoD PASS
- [ ] Phase 2 開始 snapshot 保存
- [ ] migration-order.json の rank 順に全 plugin 投入
- [ ] 各 plugin 投入後 drift-check.sh PASS
- [ ] 各 plugin の rollback.sh `bash -n` PASS
- [ ] 全 plugin の dod-per-plugin.md PASS
- [ ] user セクション SHA256 不変
- [ ] DoD-1〜10 全 PASS
- [ ] solo_operator 承認
