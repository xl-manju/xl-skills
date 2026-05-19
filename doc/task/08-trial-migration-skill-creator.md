# タスク 08 — 試験移行 (creator-kit → plugins/skill-creator/)

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| タスク ID | 08 |
| タスク名称 | creator-kit/ から plugins/skill-creator/ への試験移行 |
| 種別 | 実行 |
| 担当 | AI 実行 + 人間レビュー |
| 期限 | 34章 Phase 2 試験移行ゲート |
| 依存タスク | 05, 06, 07 + 34章 Phase 1→2 gate PASS |
| 後続タスク | 09 (Phase gate 完了報告) |
| ステータス | 未着手 |
| 改訂履歴 | 2026-05-19 v1 initial |

## Section 2. 目的と背景

### 目的

Phase 0/1 で整備・レビューした 2 本の CLI (`build-claude-symlinks.py`, `build-claude-settings.py`) を実証するため、**1 plugin に限定して**物理移行を実行する。試験対象は `skill-creator` (最重要 plugin)。

### 背景

34 章 Phase 2 は試験 plugin 1 件のみの物理移行を要求する。本タスクは Phase 2 の実行タスクであり、Phase 0 全タスク完了、Phase 1 完了、公式制約5点 PASS が揃うまで実行してはならない。

### 根拠

- 設計書 34 章 Phase 2
- README タスク一覧 (08 行)
- ユーザー要求「最終的に動くものを生成」

## Section 3. 用語集

| 用語 | 定義 |
|---|---|
| 試験 plugin | 物理移行の最初の対象。`plugins/skill-creator/` |
| 並走期間 | 旧 `creator-kit/` と新 `plugins/skill-creator/` が同時に存在する期間 (本タスク中のみ) |
| 切り替え点 | 並走→新側 only への切り替えのチェックポイント |

## Section 4. スコープ

### 含む

- `plugins/skill-creator/.claude-plugin/plugin.json` 作成
- `creator-kit/skills/*` → `plugins/skill-creator/skills/*` の物理コピー
- `creator-kit/agents/*` → `plugins/skill-creator/agents/*` の物理コピー
- `build-claude-symlinks.py` 実行で `.claude/` 再生成
- `build-claude-settings.py` 実行で `.claude/settings.json` 再生成
- INV-1〜INV-12 の事前/事後比較
- 旧 `creator-kit/` の保持 (削除は本タスクに含めない)

### 含まない

- `creator-kit/` の物理削除
- 他 plugin の移行 (34章 Phase 3 以降)

## Section 5. 前提条件

| # | 条件 | 確認 |
|---|---|---|
| 1 | タスク 06 完了 | `test -f eval-log/task/06/review-approval.json` |
| 2 | タスク 07 完了 | `test -f eval-log/task/07/review-approval.json` |
| 3 | タスク 05 完了 | `test -f eval-log/task/05/review-approval.json` |
| 4 | 34章 Phase 1→2 gate PASS | `eval-log/phase/1/closure.json` |
| 5 | 公式制約5点 PASS | 34章チェックリスト |
| 6 | git working tree clean | `git status --porcelain` 空 |
| 7 | `.claude/settings.json` SHA256 取得済 | `eval-log/task/08/settings.before.sha256` |
| 8 | タスク 01 inventory.json の `migrate` verdict が反映済 | 手動確認 |

### 依存ツールCLI契約確認

- `scripts/build-claude-symlinks.py --help` の出力をタスク 03 Section 7.1 と diff、相違なし
- `scripts/build-claude-settings.py --help` の出力をタスク 04 Section 7.1 と diff、相違なし

## Section 6. 完了条件 (DoD)

| # | 条件 | 検証 |
|---|---|---|
| DoD-1 | `plugins/skill-creator/.claude-plugin/plugin.json` 存在 | `test -f plugins/skill-creator/.claude-plugin/plugin.json` |
| DoD-2 | `plugins/skill-creator/skills/` 配下が `creator-kit/skills/` と内容等価 (除外パスを除く) | diff コマンド |
| DoD-3 | `build-claude-symlinks.py --check` exit 0 | 直接実行 |
| DoD-4 | `build-claude-settings.py --check` exit 0 | 直接実行 |
| DoD-5 | INV-1: user セクション SHA256 が事前と一致 | `diff eval-log/task/08/settings.before.usersection.sha eval-log/task/08/settings.after.usersection.sha` |
| DoD-6 | `.claude/skills/<name>` が `plugins/skill-creator/skills/<name>` を指す相対 symlink | `readlink` 検査 |
| DoD-7 | Claude Code 起動で skill が認識される (手動確認) | チェックリスト |
| DoD-8 | rollback.sh が事前生成され構文検査済み | `bash -n eval-log/task/08/rollback.sh` |
| DoD-9 | レビュー承認 | `python3 -c "import json; assert json.load(open('eval-log/task/08/review-approval.json')).get('approver')"` |

## Section 7. 実行手順

### Step 7.1 — 事前計測

```bash
mkdir -p eval-log/task/08 plugins/skill-creator/.claude-plugin
cp .claude/settings.json eval-log/task/08/settings.before.json
shasum -a 256 .claude/settings.json > eval-log/task/08/settings.before.sha256
python3 scripts/build-claude-settings.py --target .claude/settings.json --print-user-section-hash > eval-log/task/08/settings.before.usersection.sha
cat > eval-log/task/08/rollback.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cp eval-log/task/08/settings.before.json .claude/settings.json
rm -rf .claude/skills .claude/agents
mv eval-log/task/08/claude-skills.before .claude/skills
mv eval-log/task/08/claude-agents.before .claude/agents
rm -rf plugins/skill-creator
SH
bash -n eval-log/task/08/rollback.sh
```

### Step 7.2 — plugin.json 作成

`plugins/skill-creator/.claude-plugin/plugin.json` を最低限のフィールドで作成:

```json
{
  "name": "skill-creator",
  "version": "1.0.1",
  "description": "Claude Code Skill を作る/評価する/承認する/出力先にルーティングするためのメタスキル群",
  "skills_dir": "skills",
  "agents_dir": "agents",
  "hooks_dir": "hooks"
}
```

実行前 gate: この `plugin.json` の必須 schema は 34章 Phase 1→2 gate で確定済みでなければならない。未確定の場合は本タスクを開始しない。

### Step 7.3 — 物理コピー

`creator-kit/manifest.json` の `skills`, `agents` を読んで `plugins/skill-creator/` 配下にコピー:

```bash
python3 - <<'PY'
import json, shutil, pathlib
m = json.load(open('creator-kit/manifest.json'))
dst_root = pathlib.Path('plugins/skill-creator')
(dst_root / 'skills').mkdir(parents=True, exist_ok=True)
(dst_root / 'agents').mkdir(parents=True, exist_ok=True)
for s in m['skills']:
    src = pathlib.Path('creator-kit/skills') / s['name']
    if src.exists():
        shutil.copytree(src, dst_root / 'skills' / s['name'], dirs_exist_ok=True)
for a in m['agents']:
    src = pathlib.Path('creator-kit') / a['source']
    if src.exists():
        shutil.copy(src, dst_root / 'agents' / src.name)
PY
```

### Step 7.4 — 古い `.claude/` の symlink を一掃 (バックアップ後)

```bash
test -f eval-log/task/08/rollback.sh
bash -n eval-log/task/08/rollback.sh
mv .claude/skills eval-log/task/08/claude-skills.before
mv .claude/agents eval-log/task/08/claude-agents.before
mkdir -p .claude/skills .claude/agents
```

### Step 7.5 — build-claude-symlinks.py 実行

```bash
python3 scripts/build-claude-symlinks.py --plugins-dir plugins --target-dir .claude --json > eval-log/task/08/symlinks-result.json
python3 scripts/build-claude-symlinks.py --check && echo "DoD-3 PASS"
```

### Step 7.6 — build-claude-settings.py 実行

```bash
python3 scripts/build-claude-settings.py --plugins-dir plugins --target .claude/settings.json --json > eval-log/task/08/settings-result.json
python3 scripts/build-claude-settings.py --check && echo "DoD-4 PASS"
```

### Step 7.7 — INV-1 事後検証

```bash
python3 -c "
import subprocess
subprocess.run(['python3','scripts/build-claude-settings.py','--target','.claude/settings.json','--print-user-section-hash'], check=True)
" > eval-log/task/08/settings.after.usersection.sha
diff eval-log/task/08/settings.before.usersection.sha eval-log/task/08/settings.after.usersection.sha && echo "INV-1 PASS"
```

### Step 7.8 — Claude Code 認識確認 (手動)

Claude Code を起動して `/skills` または同等コマンドで `skill-creator` 系 skill が一覧表示されることを確認。スクリーンショットを `eval-log/task/08/screenshot.png` に保存。

### Step 7.9 — レビュー承認

`eval-log/task/08/review-approval.json` を生成。

## Section 8. 検証手順

DoD-1〜DoD-9 を順に検査。

## Section 9. リスクと対策

| ID | リスク | 対策 |
|---|---|---|
| R-01 | INV-1 違反で user 設定消失 | Step 7.1 で SHA256 取得、Step 7.7 で照合 |
| R-02 | 旧 `.claude/skills/` を消して復元不能 | Step 7.4 で `mv` でバックアップ |
| R-03 | plugin.json schema 不整合 | Section 5 の 34章 Phase 1→2 gate で schema 確定を必須化 |
| R-04 | symlink 相対化失敗 | DoD-6 で `readlink` 検査 |
| R-05 | Claude Code が skill を認識しない | Step 7.8 で手動確認、失敗時はロールバック |
| R-06 | ロールバック手順未整備 | `eval-log/task/08/rollback.sh` を Step 7.1 で生成し、Step 7.4 前に `bash -n` |

### ロールバック手順

```bash
# Step 7.1 で eval-log/task/08/rollback.sh を生成しておく
cp eval-log/task/08/settings.before.json .claude/settings.json
rm -rf .claude/skills .claude/agents
mv eval-log/task/08/claude-skills.before .claude/skills
mv eval-log/task/08/claude-agents.before .claude/agents
rm -rf plugins/skill-creator
```

## Section 10. 成果物一覧

| ファイル | 責任者 |
|---|---|
| `plugins/skill-creator/.claude-plugin/plugin.json` | AI |
| `plugins/skill-creator/skills/**` | AI (copy) |
| `plugins/skill-creator/agents/**` | AI (copy) |
| `eval-log/task/08/settings.before.json` | AI |
| `eval-log/task/08/settings.before.sha256` | AI |
| `eval-log/task/08/symlinks-result.json` | AI |
| `eval-log/task/08/settings-result.json` | AI |
| `eval-log/task/08/screenshot.png` | 人間 |
| `eval-log/task/08/rollback.sh` | AI |
| `eval-log/task/08/review-approval.json` | 人間 |

### ツール契約

本タスクは契約の **消費側**。仕様正本: タスク 03 / 04。**実行前に Section 5 の依存ツール CLI 契約確認を必ず実施**。

## Section 11. 参照ドキュメント

- 34 章 Phase 2
- `doc/ClaudeCodeスキルの設計書/34a-settings-merge-spec.md`
- タスク 03 / 04 / 06 / 07

## Section 12. 中学生レベル概念説明

引っ越しの「お試し移動」です。**まず段ボール 1 個 (= skill-creator) だけを新居 (= plugins/) に運んで、電気がつくか・水道が出るかを確認**します。古い家のものは残したまま (creator-kit/ 保持) なので、もし新居に不具合があれば 1 コマンド (rollback.sh) で元に戻せます。家族 (= user セクション) の貴重品は引っ越し前後で指紋 (SHA256) を取り、一切手を触れていないことを毎回確認します。

## Section 13. 実行者チェックリスト

- [ ] タスク 06 / 07 完了確認
- [ ] git clean 確認
- [ ] settings.json バックアップ・SHA256 取得
- [ ] plugin.json schema を 34 章で確定
- [ ] 物理コピー実行
- [ ] 古い `.claude/skills,agents` を退避
- [ ] symlink CLI 実行 + `--check` PASS
- [ ] settings CLI 実行 + `--check` PASS
- [ ] INV-1 事後検証 PASS
- [ ] Claude Code 手動確認 + スクリーンショット
- [ ] DoD-1〜DoD-9 全 PASS
- [ ] ロールバック手順を試走 (空打ち → 元に戻る)

## 改訂履歴

| 日付 | バージョン | 改訂者 | 内容 |
|---|---|---|---|
| 2026-05-19 | v1 | initial | Section 1-13 構成で初版 |
| 2026-05-19 | v2 | elegant-review | Phase 2 gate 後の実行へ後退し、05依存・rollback事前生成・user section hash契約を追加 |
