# タスク 06 — build-claude-symlinks.py 実装

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| タスク ID | 06 |
| タスク名称 | build-claude-symlinks.py 実装 |
| 種別 | 実装 |
| 担当 | AI 実装 + 人間レビュー |
| 期限 | Phase 0 完了の最低条件 |
| 依存タスク | 03 (CLI 仕様) |
| 後続タスク | 08 (試験移行で実行) |
| ステータス | 未着手 (タスク 03 完了後にのみ着手可) |
| 改訂履歴 | 2026-05-19 v1 initial |

## Section 2. 目的と背景

### 目的

タスク 03 で確定した CLI 契約を満たす `scripts/build-claude-symlinks.py` を Python stdlib のみで実装する。

### 背景

実装系は仕様凍結後にのみ着手する (README 実行ルール 7)。仕様逸脱は P1_structural 扱い。

### 根拠

- タスク 03 成果物 `doc/task/03-symlink-build-specification.md` Section 10 CLI 契約
- README ツール契約凍結原則

## Section 3. 用語集

| 用語 | 定義 |
|---|---|
| 仕様正本 | タスク 03 Section 10 |
| 逸脱 | 仕様と実装の不一致。テストで検出可能 |

## Section 4. スコープ

### 含む

- `scripts/build-claude-symlinks.py` 本体
- ユニットテスト (`tests/test_build_claude_symlinks.py`)
- `--check` を CI 統合する `.github/workflows/` 追記提案 (実装は別タスク)

### 含まない

- CLI 契約の追加・変更 (してはならない — タスク 03 で凍結)
- Windows ジャンクション対応

## Section 5. 前提条件

| # | 条件 | 確認 |
|---|---|---|
| 1 | タスク 03 完了済 | `test -f eval-log/task/03/review-approval.json` |
| 2 | Python 3.11+ | `python3 --version` |
| 3 | `plugins/` ディレクトリ (空でも可) | `mkdir -p plugins` |
| 4 | `.claude/{agents,skills,commands}/` 作成権限 | `mkdir -p .claude/{agents,skills,commands}` |

### 依存ツールCLI契約確認

仕様正本: タスク 03 Section 10。本タスク開始時に下記を再実行し相違ないことを確認:

```bash
diff <(grep -A 30 "^### ツール契約" doc/task/03-symlink-build-specification.md) eval-log/task/06/cli-contract-frozen.txt && echo "FROZEN OK"
```

## Section 6. 完了条件 (DoD)

| # | 条件 | 検証 |
|---|---|---|
| DoD-1 | `scripts/build-claude-symlinks.py` 実行可能 | `test -x scripts/build-claude-symlinks.py` |
| DoD-2 | `--help` 出力が仕様 (タスク 03 Section 7.1) と完全一致 | diff 比較 |
| DoD-3 | `--dry-run` で JSON 出力スキーマ準拠 | `python3 scripts/build-claude-symlinks.py --dry-run --json > /tmp/symlink-plan.json && python3 -c "import json; d=json.load(open('/tmp/symlink-plan.json')); assert 'plan' in d and 'summary' in d"` |
| DoD-4 | 冪等性: 2 回連続実行で `--check` exit 0 | `python3 scripts/build-claude-symlinks.py && python3 scripts/build-claude-symlinks.py --check` |
| DoD-5 | 名前衝突で exit 2 | テスト fixture で再現 |
| DoD-6 | symlink target が相対パス | `find .claude -type l -lname '/*' \| wc -l` が 0 |
| DoD-7 | ユニットテスト緑 | `python3 -m unittest tests/test_build_claude_symlinks.py` |
| DoD-8 | レビュー承認 | `python3 -c "import json; assert json.load(open('eval-log/task/06/review-approval.json')).get('approver')"` |

## Section 7. 実行手順

### Step 7.1 — 仕様契約の凍結ダンプ

```bash
mkdir -p eval-log/task/06
grep -A 30 "^### ツール契約" doc/task/03-symlink-build-specification.md > eval-log/task/06/cli-contract-frozen.txt
```

### Step 7.2 — スケルトン生成

`scripts/build-claude-symlinks.py` を Python stdlib (`argparse`, `pathlib`, `os`, `json`, `sys`) のみで実装。

### Step 7.3 — 主要関数

| 関数 | 責務 |
|---|---|
| `parse_args()` | タスク 03 Section 7.1 と完全一致する argparse |
| `discover_plugins(plugins_dir)` | `plugins/*/` を列挙 |
| `discover_items(plugin, kind)` | `plugin/<kind>/*` を列挙 |
| `compute_plan(plugins_dir, target_dir, kinds)` | plan list を返す |
| `apply_plan(plan, dry_run)` | symlink 作成/更新 |
| `check_drift(plan)` | drift があれば True |
| `main()` | 終了コード規約 (0/1/2/3/4) を遵守 |

### Step 7.4 — symlink 生成のコア

```python
src_rel = os.path.relpath(item_path, dst_path.parent)
dst_path.symlink_to(src_rel)
```

### Step 7.5 — ユニットテスト

`tests/test_build_claude_symlinks.py` で以下を網羅:

- 単一 plugin、単一 skill → create
- 既存 symlink、target 一致 → noop
- 既存 symlink、target 不一致 → update
- 同名 skill が 2 plugin に存在 → conflict + exit 2
- 既存 real file → conflict
- `--dry-run` で fs 変化なし
- 冪等性: 2 回実行で結果同一

### Step 7.6 — レビュー承認

`eval-log/task/06/review-approval.json` を生成。

## Section 8. 検証手順

DoD-1〜DoD-8 を順に検査。

## Section 9. リスクと対策

| ID | リスク | 対策 |
|---|---|---|
| R-01 | 仕様逸脱 | Step 7.1 で契約凍結ダンプ、Step 7.3 で関数粒度を契約に対応 |
| R-02 | 絶対パス symlink | `os.path.relpath` の使用を必須化 |
| R-03 | テスト未網羅 | Step 7.5 の 7 ケース必須 |
| R-04 | Windows 動作不明 | スコープ外明示、CI は POSIX のみ |

## Section 10. 成果物一覧

| ファイル | 責任者 |
|---|---|
| `scripts/build-claude-symlinks.py` | AI |
| `tests/test_build_claude_symlinks.py` | AI |
| `eval-log/task/06/cli-contract-frozen.txt` | AI |
| `eval-log/task/06/test-result.txt` | AI |
| `eval-log/task/06/review-approval.json` | 人間 |

### ツール契約

本タスクは契約の **消費側**。仕様正本はタスク 03 Section 10。

## Section 11. 参照ドキュメント

- タスク 03 (仕様正本)
- `creator-kit/install.sh` (参考実装パターン)

## Section 12. 中学生レベル概念説明

レシピ (= タスク 03 仕様) を見て料理 (= タスク 06 実装) を作る工程です。レシピに「塩 5 g」と書いてあれば、料理人が勝手に 10 g に増やしてはいけません。テストは「味見係」で、できあがった料理がレシピ通りかを毎回チェックします。

## Section 13. 実行者チェックリスト

- [ ] タスク 03 完了確認
- [ ] CLI 契約凍結ダンプ取得 (Step 7.1)
- [ ] argparse がタスク 03 Section 7.1 と完全一致
- [ ] 7 ケースのユニットテスト緑
- [ ] symlink が相対パスのみ
- [ ] 冪等性確認 (`--check` exit 0)
- [ ] DoD-1〜DoD-8 全 PASS

## 改訂履歴

| 日付 | バージョン | 改訂者 | 内容 |
|---|---|---|---|
| 2026-05-19 | v1 | initial | Section 1-13 構成で初版 |
