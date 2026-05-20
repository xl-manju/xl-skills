# タスク 04 — build-claude-settings.py 仕様策定

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| タスク ID | 04 |
| タスク名称 | build-claude-settings.py CLI 仕様策定 |
| 種別 | 仕様策定 |
| 担当 | AI 起案 + 人間承認 |
| 期限 | Phase 0 完了の最低条件 |
| 依存タスク | 02 (settings merge 仕様 / INV-1〜INV-12 / 管理メタデータ構文) |
| 後続タスク | 07 (実装) |
| ステータス | 完了 (2026-05-20) |
| 改訂履歴 | 2026-05-19 v1 initial |

## Section 2. 目的と背景

### 目的

タスク 02 で確定した INV-1〜12 と管理メタデータ構文、名前空間 preflight を実行する CLI `scripts/build-claude-settings.py` の機能・引数・終了コード・出力スキーマを確定する。

### 背景

ユーザー懸念「`.claude/settings.json` への自動マージが正しく反映されるか」を、実装前に CLI レベルで凍結する。INV-1 (user 管理値保存)、INV-8 (原子的書き込み)、INV-9〜12 (名前空間・構造・permissions・plan) は CLI 引数設計と直結する。

### 根拠

- タスク 02 成果物 `doc/ClaudeCodeスキルの設計書/34a-settings-merge-spec.md`
- 設計書 34 章 §3 Layer2 統合

## Section 3. 用語集

| 用語 | 定義 |
|---|---|
| マージ計画 (plan) | 入力 plugin と既存 settings から生成される予定差分の JSON 表現 |
| atomic write | tempfile に書いて rename(2) で置換する手法 |
| 管理メタデータ | INV-1 の境界台帳。top-level `_build_claude_settings` に置く |

## Section 4. スコープ

### 含む

- CLI 引数・終了コード・出力スキーマ
- マージ計画 (plan) の JSON スキーマ
- `--check` モードと CI 連携規約
- INV-1〜12 と CLI 動作のマッピング表
- skill/agent/command/hook/permission/plugin の名前空間 preflight report

### 含まない

- 実装そのもの (タスク 07)
- マージ規則・衝突規則の本体 (タスク 02 で確定済を参照)

## Section 5. 前提条件

| # | 条件 |
|---|---|
| 1 | タスク 02 完了、INV 確定、34a 章承認済 |
| 2 | `eval-log/task/02/review-approval.json` 存在 |

### 依存ツールCLI契約確認

本仕様自体が CLI 契約の正本。**他ツールへの依存なし** (Python stdlib のみ)。

## Section 6. 完了条件 (DoD)

| # | 条件 | 検証 |
|---|---|---|
| DoD-1 | CLI 契約が Section 10 に明記 | レビュアー確認 |
| DoD-2 | 終了コード規約 (0/1/2/3) あり | レビュアー確認 |
| DoD-3 | INV-1〜12 → CLI 動作対応表あり | `grep -c "^\| INV-[0-9]" doc/migration/phase0/04-settings-merge-cli-specification.md` ≥ 12 |
| DoD-4 | plan JSON スキーマ記載 | `grep -q "plan" doc/migration/phase0/04-settings-merge-cli-specification.md` |
| DoD-5 | atomic write 要件明記 | `grep -q "rename" doc/migration/phase0/04-settings-merge-cli-specification.md` |
| DoD-6 | レビュー承認ログ | `python3 -c "import json; assert json.load(open('eval-log/task/04/review-approval.json')).get('approver')"` |

## Section 7. 実行手順

### Step 7.1 — CLI 契約案

```
usage: build-claude-settings.py [-h]
                                [--plugins-dir PLUGINS_DIR]
                                [--target TARGET]
                                [--dry-run]
                                [--check]
                                [--print-user-section-hash]
                                [--json]
                                [--verbose]
```

| フラグ | 既定値 | 役割 |
|---|---|---|
| `--plugins-dir` | `plugins` | plugin.json/hooks/*.json 走査ルート |
| `--target` | `.claude/settings.json` | 書き換え対象 |
| `--dry-run` | false | マージ計画を stdout に出力、書き換えなし |
| `--check` | false | 生成 hook / permission と管理メタデータを現状と比較、差分あれば exit 1 |
| `--print-user-section-hash` | false | 34a の抽出規則に従い user 管理値の正規化 JSON SHA256 を stdout に出す |
| `--json` | false | レポートを JSON で stdout に出力 |
| `--verbose` | false | INV-N 違反箇所をログに残す |

終了コード: 0=success, 1=drift (check モード), 2=invariant violation / namespace conflict, 3=invalid input / invalid plugin layout。

### Step 7.2 — plan JSON スキーマ

```json
{
  "target": ".claude/settings.json",
  "plugins": ["skill-creator", ...],
  "management_format": "_build_claude_settings.managed_hooks",
  "namespace": {
    "plugins": [{"name": "skill-creator", "path": "plugins/skill-creator"}],
    "skills": [{"name": "run-build-skill", "from_plugin": "skill-creator", "verdict": "ok"}],
    "agents": [],
    "commands": [],
    "conflicts": []
  },
  "conflicts": [],
  "settings": {
    "hooks": [
      {"event": "PreToolUse", "matcher": "Write|Edit", "command": "...", "from_plugin": "skill-creator", "verdict": "add|keep|conflict"}
    ],
    "permissions": [
      {"scope": "deny", "rule": "Bash(rm -rf*)", "from_plugin": "skill-creator", "verdict": "add|dedupe|conflict"}
    ]
  },
  "user_values_preserved": true,
  "invariants_checked": ["INV-1","INV-2","INV-3","INV-4","INV-5","INV-6","INV-7","INV-8","INV-9","INV-10","INV-11","INV-12"],
  "summary": {"add": N, "keep": N, "dedupe": N, "conflict": N}
}
```

### Step 7.3 — INV → CLI 動作マッピング表

| INV | CLI 側の保証手段 |
|---|---|
| INV-1 user 管理値保存 | マージ前後で user 管理値の正規化 JSON SHA256 を比較、相違なら exit 2 |
| INV-2 決定的生成 | 入力に対して plan が同一 (test で固定入力→固定出力) |
| INV-3 冪等性 | 2 回連続実行で `--check` が exit 0 |
| INV-4 plugin 名辞書順 | sort 後に列挙 |
| INV-5 衝突 ERROR | 同一 event×matcher×command を多 plugin が出したら exit 2 |
| INV-6 未知キー保存 | 未知 top-level キーを通過 |
| INV-7 JSON 正規化 | indent=2, ensure_ascii=False, sort_keys=False (schema 順) |
| INV-8 原子的書き込み | tempfile + os.rename。失敗時は target 元状態維持 |
| INV-9 グローバル名前空間一意性 | plugin/skill/agent/command/hook/permission の namespace preflight で衝突なら exit 2 |
| INV-10 settings 構造検証 | 生成後 JSON の `permissions` / `hooks` 型と hook entry 構造を検査 |
| INV-11 permissions マージ安全性 | 完全一致は dedupe、decision 競合は exit 2 |
| INV-12 plan 完全性 | plan JSON に `namespace`, `settings`, `conflicts`, `invariants_checked` を必須化 |

### Step 7.4 — `--check` の CI 連携

```yaml
- name: settings drift check
  run: python3 scripts/build-claude-settings.py --check
```

exit 1 の場合、Pull Request で「再生成が必要」を示す。

### Step 7.5 — レビュー承認

`eval-log/task/04/review-approval.json` 生成。

## Section 8. 検証手順

DoD-1〜DoD-6 を順に検査。

## Section 9. リスクと対策

| ID | リスク | 対策 |
|---|---|---|
| R-01 | INV-1 違反で user 管理値を上書き | user 管理値の正規化 JSON SHA256 検証を CLI 内蔵 |
| R-02 | 書き込み中断で破損 | INV-8 atomic write |
| R-03 | drift を見落として本番に reflect 漏れ | `--check` を CI 必須化 |
| R-04 | 出力スキーマが将来変わる | `management_format` フィールドで version pin |
| R-05 | 同名 skill が dev短名 symlink で上書きされる | INV-9 で settings 書き込み前に namespace conflict として fail |
| R-06 | permissions が plugin 間で矛盾する | INV-11 で自動優先順位を禁止し、衝突として fail |

## Section 10. 成果物一覧

| ファイル | 責任者 |
|---|---|
| `doc/migration/phase0/04-settings-merge-cli-specification.md` (本書) | AI |
| `eval-log/task/04/cli-contract.txt` | AI |
| `eval-log/task/04/inv-cli-mapping.md` | AI |
| `eval-log/task/04/review-approval.json` | 人間 |

### ツール契約 (タスク 07 への引き継ぎ正本)

Section 7.1 の CLI 引数、Section 7.2 の plan JSON、Section 7.3 の INV マッピングが正本。実装はこれと相違してはならない。

## Section 11. 参照ドキュメント

- タスク 02 成果物 (34a 章)
- 設計書 34 章 §3

## Section 12. 中学生レベル概念説明

家計簿アプリを想像してください。**ロボットが書いた行は台帳に記録し、家族が手書きした行は消さないまま、ロボットの行だけを更新する計画書**です。更新前後で「家族の行のハッシュ値 (= 指紋)」を確認します。違ったらロボットは作業を中断して「壊しかけました」と報告します (= exit 2)。

## Section 13. 実行者チェックリスト

- [x] タスク 02 完了確認 (INV 確定済)
- [x] CLI 引数案レビュー
- [x] 終了コード規約承認
- [x] INV → CLI 動作マッピング 12 件確認
- [x] namespace preflight report の schema 確認
- [x] atomic write 要件確認
- [x] DoD-1〜DoD-6 全 PASS

## 改訂履歴

| 日付 | バージョン | 改訂者 | 内容 |
|---|---|---|---|
| 2026-05-19 | v1 | initial | Section 1-13 構成で初版 |
| 2026-05-19 | v2 | elegant-review | `--print-user-section-hash` を追加し、34aのuser管理領域抽出を消費可能にした |
| 2026-05-19 | v3 | elegant-review | INV-9〜12、namespace preflight、settings構造検証、permissions安全マージを追加 |
| 2026-05-20 | v4 | codex | plan 必須フィールド `conflicts` を top-level に明記し、DoD PASS 状態へ更新 |
