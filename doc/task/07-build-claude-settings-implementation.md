# タスク 07 — build-claude-settings.py 実装

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| タスク ID | 07 |
| タスク名称 | build-claude-settings.py 実装 |
| 種別 | 実装 |
| 担当 | AI 実装 + 人間レビュー |
| 期限 | Phase 0 完了の最低条件 |
| 依存タスク | 04 (CLI 仕様)、間接的に 02 (INV 確定) |
| 後続タスク | 08 (試験移行) |
| ステータス | 実装完了 (2026-05-20) |
| 改訂履歴 | 2026-05-19 v1 initial |

## Section 2. 目的と背景

### 目的

タスク 02 で確定した INV-1〜INV-12 と、タスク 04 で確定した CLI 契約を満たす `scripts/build-claude-settings.py` を Python stdlib のみで実装する。

### 背景

ユーザー最重要懸念「`.claude/settings.json` への自動マージが正しく反映されるか」を、実装の DoD で機械検証する。INV-1 (user 管理領域保存)、INV-8 (原子的書き込み)、INV-9〜12 (名前空間・構造・permissions・plan) を **テストで毎回検証**する。

### 根拠

- タスク 02 成果物 (INV-1〜INV-12)
- タスク 04 成果物 (CLI 契約)

## Section 3. 用語集

| 用語 | 定義 |
|---|---|
| 凍結契約 | タスク 04 Section 10 |
| user セクション SHA256 | INV-1 検証のための指紋 |

## Section 4. スコープ

### 含む

- `scripts/build-claude-settings.py`
- `tests/test_build_claude_settings.py` (INV-1〜INV-12 を逐条テスト)
- CI 用 `--check` 統合提案

### 含まない

- CLI 契約の改変 (してはならない)
- マージ規則本体 (タスク 02 で確定済)

## Section 5. 前提条件

| # | 条件 |
|---|---|
| 1 | タスク 02 完了 (INV 確定) |
| 2 | タスク 04 完了 (CLI 契約確定) |
| 3 | Python 3.11+ |
| 4 | 現行 `.claude/settings.json` バックアップ取得 |

### タスク 04 仕様凍結状況 (2026-05-20 確認)

タスク 04 は DoD-1〜DoD-6 全 PASS で承認済 (`eval-log/task/04/review-approval.json`, approver=`solo_operator`)。本タスク着手前の追加検証として以下を実施済:

- 前提条件 1 (タスク 02 承認ログ): `eval-log/task/02/review-approval.json` 存在確認 OK
- DoD-3: `grep -c "^| INV-[0-9]" doc/task/04-...md` = 12 (要件 ≥12)
- DoD-4: `plan` 9 件 / DoD-5: `rename` 3 件
- 成果物 4 件 (`cli-contract.txt`, `inv-cli-mapping.md`, `dod-verification.md`, `review-approval.json`) 揃い
- Section 13 チェックリスト 7 項目すべて `[x]`

**重要**: 仕様→実装の乖離検証は本タスク (07) 着手時に再度実施する。Step 7.1 の契約凍結ダンプを取得した直後、`scripts/build-claude-settings.py --help` 出力と Section 7.1 の usage、`--dry-run --json` 出力と Section 7.2 の plan JSON スキーマ、ユニットテスト 12 件と Section 7.3 の INV マッピングを diff ベースで突合する。

### 依存ツールCLI契約確認

仕様正本: タスク 04 Section 10。本タスク開始時に下記でフリーズ確認:

```bash
diff <(awk '/^### Step 7\.1/{flag=1} /^### Step 7\.3/{flag=0} flag' doc/task/04-settings-merge-cli-specification.md) eval-log/task/07/cli-contract-frozen.txt && echo "FROZEN OK"
```

## Section 6. 完了条件 (DoD)

| # | 条件 | 検証 |
|---|---|---|
| DoD-1 | スクリプト実行可能 | `test -x scripts/build-claude-settings.py` |
| DoD-2 | `--help` がタスク 04 Section 7.1 と一致 | diff |
| DoD-3 | INV-1 (user 管理領域保存) テスト緑 | `python3 -m unittest tests/test_build_claude_settings.py` |
| DoD-4 | INV-2〜INV-8 テスト緑 | `python3 -m unittest tests/test_build_claude_settings.py` で全 INV テスト PASS |
| DoD-5 | 冪等性: 2 回連続で `--check` exit 0 | shell test |
| DoD-6 | 衝突検出 → exit 2 | fixture test |
| DoD-7 | atomic write: 書き込み中断シミュレーションで target 元状態維持 | mock test |
| DoD-8 | レビュー承認 | `python3 -c "import json; assert json.load(open('eval-log/task/07/review-approval.json')).get('approver')"` |

## Section 7. 実行手順

### Step 7.1 — 契約凍結ダンプ

```bash
mkdir -p eval-log/task/07
awk '/^### Step 7\.1/{flag=1} /^### Step 7\.3/{flag=0} flag' doc/task/04-settings-merge-cli-specification.md > eval-log/task/07/cli-contract-frozen.txt
cp .claude/settings.json eval-log/task/07/settings.before.json
```

### Step 7.2 — スケルトン生成

`scripts/build-claude-settings.py` を `argparse, json, hashlib, tempfile, os, sys, pathlib` のみで実装。

### Step 7.3 — 主要関数

| 関数 | 責務 | 対応 INV |
|---|---|---|
| `parse_args()` | タスク 04 Section 7.1 と完全一致 | — |
| `load_target(path)` | 既存 settings.json 読み込み、マーカー外を保存 | INV-1, INV-6 |
| `user_section_sha256(data)` | user セクションの正規化済 SHA256 | INV-1 |
| `discover_plugins(plugins_dir)` | plugin.json と hooks/*.json を列挙、辞書順 | INV-4 |
| `merge_hooks(user, plugins)` | マージ計画を生成、衝突は ERROR | INV-2, INV-5 |
| `serialize(data)` | indent=2, ensure_ascii=False, 末尾改行 | INV-7 |
| `atomic_write(path, content)` | tempfile + os.rename | INV-8 |
| `check_mode(target, plan)` | マーカー区間と plan を比較 | INV-3 |
| `main()` | 終了コード 0/1/2/3 を遵守 | — |

### Step 7.4 — INV-1 検証コア

```python
before_hash = user_section_sha256(load_target(target))
# ... マージ書き込み ...
after_hash = user_section_sha256(load_target(target))
assert before_hash == after_hash, "INV-1 violation"
```

### Step 7.5 — atomic write コア

```python
def atomic_write(path, content):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(content, encoding='utf-8')
    os.rename(tmp, path)
```

### Step 7.6 — ユニットテスト (INV ごと 1 件以上)

`tests/test_build_claude_settings.py`:

- `test_inv1_user_section_byte_equality`
- `test_inv2_deterministic_output`
- `test_inv3_idempotent`
- `test_inv4_plugin_name_lex_order`
- `test_inv5_conflict_raises_exit2`
- `test_inv6_unknown_top_level_preserved`
- `test_inv7_json_normalization`
- `test_inv8_atomic_write_failure_keeps_original`

### Step 7.7 — レビュー承認

`eval-log/task/07/review-approval.json` 生成。

## Section 8. 検証手順

DoD-1〜DoD-8 を順に検査。

## Section 9. リスクと対策

| ID | リスク | 対策 |
|---|---|---|
| R-01 | INV-1 違反で user セクション破壊 | SHA256 比較を CLI 内蔵、テスト必須 |
| R-02 | 書き込み中断で破損 | INV-8 atomic write + テスト |
| R-03 | JSON キー順 drift で diff ノイズ | INV-7 schema 順固定 |
| R-04 | 衝突を silent merge | INV-5 exit 2 + fixture test |
| R-05 | 仕様逸脱 | Step 7.1 で契約凍結ダンプ |

## Section 10. 成果物一覧

| ファイル | 責任者 |
|---|---|
| `scripts/build-claude-settings.py` | AI |
| `tests/test_build_claude_settings.py` | AI |
| `eval-log/task/07/cli-contract-frozen.txt` | AI |
| `eval-log/task/07/settings.before.json` | AI |
| `eval-log/task/07/test-result.txt` | AI |
| `eval-log/task/07/review-approval.json` | 人間 |

### ツール契約

本タスクは契約の **消費側**。仕様正本はタスク 04 Section 10。

## Section 11. 参照ドキュメント

- タスク 02 (INV 正本)
- タスク 04 (CLI 契約正本)
- `doc/ClaudeCodeスキルの設計書/34a-settings-merge-spec.md`

## Section 12. 中学生レベル概念説明

家計簿アプリ (タスク 04) の **作り方を実際に書くプログラマの段階**。家族の行 (user セクション) の指紋 (SHA256) を取って、ロボットが手を入れた後に同じ指紋が出るかを毎回テストします。書き込みは「下書きに書いて、最後に一気に置き換える」(atomic write) で、途中で電源が切れても元の家計簿が無傷で残ります。

## Section 13. 実行者チェックリスト

- [x] タスク 02 / 04 完了確認
- [x] CLI 契約凍結ダンプ取得
- [x] settings.json バックアップ
- [x] argparse が契約と完全一致
- [x] INV-1〜INV-12 のテスト 12 件緑
- [x] atomic write テスト緑
- [x] DoD-1〜DoD-8 全 PASS

## 改訂履歴

| 日付 | バージョン | 改訂者 | 内容 |
|---|---|---|---|
| 2026-05-19 | v1 | initial | Section 1-13 構成で初版 |
| 2026-05-20 | v2 | claude-verify | タスク 04 DoD 全 PASS の確認結果を Section 5 に追記し、着手時の仕様→実装乖離検証手順を明文化 |
| 2026-05-20 | v3 | codex | build-claude-settings.py 実装、INV-1〜INV-12 テスト、DoD 検証ログを追加 |
| 2026-05-20 | v4 | claude-verify | Step 7.1 / Section 5 の凍結ダンプ抽出コマンドを `awk` 節境界方式に修正し、`cli-contract-frozen.txt` を再生成で再現可能化 |
