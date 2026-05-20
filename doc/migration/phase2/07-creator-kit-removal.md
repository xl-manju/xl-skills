# タスク 07: creator-kit/ 物理削除

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| ID | phase2-07 |
| 名称 | creator-kit/ 物理削除 |
| 担当 | AI (実行) + solo_operator (削除承認) |
| 期限 | 06 完了から 3 営業日以内 |
| 依存タスク | phase2-06 |
| ステータス | 未着手 |

## Section 2. 目的と背景

06 で partition-plan の全 plugin が `plugins/` 配下に展開された。本タスクは `creator-kit/` ディレクトリの正本性を剥奪し、物理削除する。削除は不可逆性が極めて高いため:

- 01 inventory の `keep-non-plugin` 資産を別途保管先に退避
- `delete` 資産は plugin 側に同一 SHA256 が存在することを最終確認
- 削除前後で build CLI --check が exit 0 を維持
- git revert で復旧可能な単一 commit に削除をまとめる

を満たした上で削除する。

根拠: `doc/migration/phase2/01-residual-asset-inventory.md`、Phase 0 引き継ぎ事項#1「creator-kit/ 物理削除タイミング」。

## Section 3. 用語集 (本タスク固有)

| 用語 | 定義 |
|---|---|
| 退避 (relocate) | `keep-non-plugin` 資産を `creator-kit/` 外へ git mv する操作 |
| 削除確定 | `git rm -r creator-kit/` を実行し、build CLI --check が引き続き exit 0 であることを確認した状態 |
| 単一 revert commit | `creator-kit/` 削除を 1 commit に閉じ込め、`git revert <sha>` で復旧可能にする方針 |

共通用語は README 参照。

## Section 4. スコープ

含む:

- 01 verdict の最終確認 (`delete` が全件 plugin 側に同一 SHA256 で存在)
- `keep-non-plugin` 資産の `tools/` または `docs/` への退避
- `defer` 資産の解決はしないが、削除巻き込み防止のため `deferred/` へ退避し Phase 3 carry-over に残す
- `git rm -r creator-kit` の実行
- 削除前後の build CLI --check 比較
- 削除 commit を単一 commit にまとめる

含まない:

- `defer` verdict 資産の解決・再分類 (退避だけを本タスクで行い、判断は後続 Phase へ送る)
- 削除後の CONVENTIONS.md 改訂 (05 の責務)
- 統合検証 (08 の責務)

## Section 5. 前提条件

1. phase2-06 が DoD 全 PASS
2. `eval-log/task/phase2-01/residual-inventory.json` の `delete` 全件が plugin 側に存在
3. `keep-non-plugin` 資産の退避先を solo_operator が承認 (TODO(human))
4. `git status -s` が clean (06 終了時点の commit 済)

### 依存ツールCLI契約確認

- `git rm`、`git mv`、`git revert` の挙動確認
- Phase 0 frozen CLI と現状の help 一致

## Section 6. 完了条件 (DoD)

| DoD | 内容 | 機械検証 |
|---|---|---|
| DoD-1 | `creator-kit/` ディレクトリが物理的に存在しない | `test ! -d creator-kit` |
| DoD-2 | 削除 commit が単一で、変更 path が `creator-kit/` 削除と承認済み退避先だけに限定される | `git show --name-status --format= "$sha"` の path allow-list 検査 |
| DoD-3 | 削除前後で `build-claude-symlinks.py --check` exit 0 維持 | before/after JSON が conflicts 0 |
| DoD-4 | 削除前後で `build-claude-settings.py --check` invariants_checked >= 12 維持 | before/after JSON |
| DoD-5 | `keep-non-plugin` 資産が退避先に存在 (例: `tools/`、`docs/`、`installers/`) | 退避先 path で `test -f` |
| DoD-6 | `defer` verdict 資産が `deferred/` に存在し `creator-kit/` に残っていない | `python3 -c "import json,pathlib;inv=json.load(open('eval-log/task/phase2-01/residual-inventory.json'));[__import__('sys').exit(1) for r in inv['records'] if r['verdict']=='defer' and pathlib.Path(r['path']).exists()]"` |
| DoD-7 | inventory の `delete` 全件について plugin 側に同一 SHA256 が存在 | 集計スクリプト |
| DoD-8 | 削除 commit を `git revert <sha>` で巻き戻せる (dry-run) | `git revert --no-commit --no-edit <sha> && git revert --abort` |
| DoD-9 | review-approval.json が `decision == "approved"` | 内容検査 |
| DoD-10 | `git rm -r creator-kit` 直前に、`creator-kit/` に残る非 `delete` 資産が 0 件 | pre-delete gate スクリプト |

## Section 7. 実行手順

### Step 7.1 `delete` 全件最終確認

```bash
mkdir -p eval-log/task/phase2-07
python3 <<'PY' | tee eval-log/task/phase2-07/delete-final-check.log
import json, hashlib, pathlib
inv = json.loads(pathlib.Path('eval-log/task/phase2-01/residual-inventory.json').read_text())
missing = []
for r in inv['records']:
    if r['verdict'] != 'delete': continue
    rel = r['rel']
    found = list(pathlib.Path('plugins').rglob(rel.split('/', 1)[-1] if '/' in rel else rel))
    found_match = [f for f in found if hashlib.sha256(f.read_bytes()).hexdigest() == r['sha256']]
    if not found_match:
        missing.append(rel)
if missing:
    print('MISSING:', missing); raise SystemExit(2)
print('all delete records reproduced in plugins/')
PY
```

### Step 7.2 keep-non-plugin の退避先策定 (TODO(human))

solo_operator が退避先を承認:

- `_bootstrap/` → `installers/bootstrap/` ?
- `install.sh` / `install.ps1` → `installers/` ?
- `manifest.json` → `installers/` ?
- `CONVENTIONS.md` → 既に `CONVENTIONS.md` がリポジトリ root にある場合は内容統合済か確認

```bash
# 例 (退避先確定後):
git mv creator-kit/_bootstrap installers/bootstrap
git mv creator-kit/install.sh installers/
git mv creator-kit/install.ps1 installers/
git mv creator-kit/manifest.json installers/manifest.json
```

### Step 7.3 削除前 snapshot

```bash
python3 scripts/build-claude-symlinks.py --check --json > eval-log/task/phase2-07/before-symlinks-check.json
python3 scripts/build-claude-settings.py --check --json > eval-log/task/phase2-07/before-settings-check.json
git status -s > eval-log/task/phase2-07/before-git-status.txt
```

### Step 7.3b defer 資産の退避 (削除前必須)

`verdict == "defer"` 資産は本タスクで削除しない。`git rm -r creator-kit` は `defer` 資産も巻き込むため、削除前に必ず `deferred/` へ退避する:

```bash
# defer 資産を deferred/ へ git mv (巻き込み削除防止)
python3 <<'PY'
import json, pathlib, subprocess
inv = json.loads(pathlib.Path('eval-log/task/phase2-01/residual-inventory.json').read_text())
defer_records = [r for r in inv['records'] if r['verdict'] == 'defer']
if not defer_records:
    print('defer 資産なし: Step 7.3b スキップ')
else:
    pathlib.Path('deferred').mkdir(exist_ok=True)
    for r in defer_records:
        src = pathlib.Path(r['path'])
        dst = pathlib.Path('deferred') / r['rel']
        dst.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'mv', str(src), str(dst)], check=True)
        print(f'git mv {src} -> {dst}')
    print(f'{len(defer_records)} 件の defer 資産を deferred/ へ退避完了')
PY
```

退避後、`git status -s` で `deferred/` への move が記録されていることを確認してから Step 7.4 に進む。

### Step 7.3c 削除直前 pre-delete gate

`git rm -r creator-kit` の直前に、`creator-kit/` 配下へ残っている inventory 管理対象が `delete` verdict のみであることを検査する。`keep-non-plugin` または `defer` が残っている場合は削除へ進まない:

```bash
python3 <<'PY' | tee eval-log/task/phase2-07/pre-delete-gate.log
import json, pathlib
inv = json.loads(pathlib.Path('eval-log/task/phase2-01/residual-inventory.json').read_text())
bad = []
for r in inv['records']:
    p = pathlib.Path(r['path'])
    if p.exists() and r['verdict'] != 'delete':
        bad.append((r['rel'], r['verdict']))
if bad:
    print('NON_DELETE_REMAINING:', bad)
    raise SystemExit(2)
print('pre-delete gate OK: creator-kit only contains delete-verdict records')
PY
```

### Step 7.4 削除実行

```bash
git rm -r creator-kit
```

`creator-kit/_drafts/` などに残存していたが verdict が `delete` でも `migrate-to-plugin` でもないものがある場合、Step 7.1 で MISSING として検出されるはずだが、Step 7.4 前に再確認:

```bash
test ! -e creator-kit
```

(注: `git rm` 直後は worktree から消えるが commit 前)

### Step 7.5 単一 commit 化

```bash
git commit -m "chore(phase2): remove creator-kit/ after partition migration

- All delete-verdict assets reproduced in plugins/.
- keep-non-plugin assets relocated to installers/.
- Phase 0 frozen CLIs unchanged.

Refs: doc/migration/phase2/07-creator-kit-removal.md"
```

(`HEREDOC` 形式で commit を作る。実際の commit はユーザー承認時のみ実行。)

削除 commit SHA を保存し、単一 commit の変更 path を allow-list で検査する:

```bash
sha=$(git rev-parse HEAD)
echo "$sha" > eval-log/task/phase2-07/delete-commit.sha
git show --name-status --format= "$sha" > eval-log/task/phase2-07/delete-commit-name-status.txt
python3 <<'PY'
import pathlib, sys
allowed_prefixes = ('creator-kit/', 'installers/', 'deferred/')
bad = []
for line in pathlib.Path('eval-log/task/phase2-07/delete-commit-name-status.txt').read_text().splitlines():
    if not line.strip():
        continue
    parts = line.split()
    paths = parts[1:]
    for p in paths:
        if not p.startswith(allowed_prefixes):
            bad.append(p)
if bad:
    print('unexpected paths in delete commit:', bad)
    raise SystemExit(2)
PY
```

### Step 7.6 削除後 snapshot と整合確認

```bash
python3 scripts/build-claude-symlinks.py --check --json > eval-log/task/phase2-07/after-symlinks-check.json
python3 scripts/build-claude-settings.py --check --json > eval-log/task/phase2-07/after-settings-check.json
diff eval-log/task/phase2-07/before-symlinks-check.json eval-log/task/phase2-07/after-symlinks-check.json \
  || echo "expected: build CLI plan may shrink because creator-kit no longer exists; conflicts must remain 0"
```

### Step 7.7 revert dry-run

```bash
sha=$(git log --oneline -1 --pretty=%H -- creator-kit)
git revert --no-commit --no-edit "$sha" && git revert --abort
```

### Step 7.8 README ステータス更新 + レビュー承認

`doc/migration/phase2/README.md` を更新、`review-approval.json` 生成。

## Section 8. 検証手順

| 完了条件 | 検証コマンド |
|---|---|
| DoD-1 | `test ! -d creator-kit && echo PASS` |
| DoD-2 | `git show --name-status --format= "$(cat eval-log/task/phase2-07/delete-commit.sha)"` の path allow-list 検査 |
| DoD-3 | `jq -e '.summary.conflict == 0' eval-log/task/phase2-07/{before,after}-symlinks-check.json` |
| DoD-4 | `jq '.invariants_checked | length' eval-log/task/phase2-07/{before,after}-settings-check.json` 共に >= 12 |
| DoD-5 | `for p in installers/bootstrap installers/install.sh installers/install.ps1; do test -e "$p"; done` |
| DoD-6 | DoD 表 inline |
| DoD-7 | Step 7.1 のスクリプト exit 0 |
| DoD-8 | Step 7.7 のコマンド成功 |
| DoD-9 | review-approval.json |
| DoD-10 | `test -s eval-log/task/phase2-07/pre-delete-gate.log && grep -q "pre-delete gate OK" eval-log/task/phase2-07/pre-delete-gate.log` |

## Section 9. リスクと対策

| 失敗モード | 対策 | INV |
|---|---|---|
| `keep-non-plugin` を削除してしまう | Step 7.2 で退避を先に実施 | - |
| build CLI が creator-kit 参照を残したまま壊れる | Phase 0 build CLI は plugins/* のみ参照するため影響なし。Step 7.6 で確認 | - |
| 削除 commit を巨大化させ revert 困難 | 単一 commit ポリシー (Step 7.5)、`git rm -r creator-kit` 以外を含めない | - |
| `defer` verdict 資産を巻き込み削除 | Step 7.3b で `deferred/` へ退避し、Step 7.3c で非 delete 残存ゼロを機械確認 | - |

## Section 10. 成果物一覧

| 成果物 | パス | 責任者 |
|---|---|---|
| delete-final-check.log | `eval-log/task/phase2-07/delete-final-check.log` | AI |
| pre-delete-gate.log | `eval-log/task/phase2-07/pre-delete-gate.log` | AI |
| delete-commit.sha / delete-commit-name-status.txt | `eval-log/task/phase2-07/` | AI |
| before/after build CLI check JSON | `eval-log/task/phase2-07/{before,after}-{symlinks,settings}-check.json` | AI |
| 削除 commit | git log | AI (solo_operator 承認後に commit) |
| review-approval.json | `eval-log/task/phase2-07/review-approval.json` | solo_operator |

ツール契約 (凍結参照): 該当なし (git 操作と Phase 0 frozen CLI のみ使用)。

## Section 11. 参照ドキュメント

- `doc/migration/phase2/01-residual-asset-inventory.md`
- `doc/migration/phase2/06-per-plugin-migration-execution.md`
- `creator-kit/manifest.json` (削除直前まで参照)

## Section 12. 中学生レベル概念説明

引っ越しが終わったので、もう古い家 (= creator-kit) を返す日です。荷物が全部新居 (= plugins/) に移動済みであることを確認し、物置に置く小物 (= keep-non-plugin) は別の倉庫 (= installers/) に運び、それから古い家の鍵を返します。万一何か忘れても、鍵を返した記録 (= 削除 commit) を取り消す方法 (= git revert) は用意しておきます。

## Section 13. チェックリスト

- [ ] phase2-06 DoD 全 PASS
- [ ] Step 7.1 delete 全件再現確認 PASS
- [ ] Step 7.2 keep-non-plugin の退避先 solo_operator 承認
- [ ] Step 7.3 削除前 snapshot 保存
- [ ] Step 7.3b defer 資産を deferred/ へ git mv 退避 (defer 件数 > 0 の場合)
- [ ] Step 7.3c pre-delete gate PASS
- [ ] Step 7.4 `git rm -r creator-kit` 実行
- [ ] Step 7.5 単一 commit 作成
- [ ] Step 7.6 削除後 build CLI --check PASS
- [ ] Step 7.7 git revert dry-run PASS
- [ ] DoD-1〜10 全 PASS
- [ ] solo_operator 承認
