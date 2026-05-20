# タスク 02 — settings.json マージ仕様策定

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| タスク ID | 02 |
| タスク名称 | settings.json マージ仕様策定 (34a 章新設) |
| 種別 | 仕様策定 |
| 担当 | AI 起案 + 人間 (solo_operator) 承認 |
| 期限 | Phase 0 完了の最低条件 |
| 依存タスク | 01 (外部参照棚卸し) |
| 後続タスク | 03 / 04 / 05 (本仕様を前提に並列着手可) |
| ステータス | 完了 |
| 改訂履歴 | 2026-05-19 v1 initial |

## Section 2. 目的と背景

### 目的

`plugins/<name>/.claude-plugin/plugin.json` および `plugins/<name>/{hooks,settings}/` から `.claude/settings.json` を自動生成する際に守るべき **不変条件 (INV-1〜INV-12)** を確定し、設計書 34a 章として執筆する。

### 背景

ユーザーの最重要懸念は「`.claude/settings.json` への自動マージが正しく反映されるか」である。34 章は plugin 三層モデル (Layer1 plugin.json / Layer2 hooks/*.json / Layer3 .claude/settings.json) を定義したが、**マージ規則を満たすべき不変条件が未確定**のため、実装 (07) より先に本仕様で凍結する。

### 根拠

- `doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md` §3「Layer2 Hook 統合」
- 既存 `.claude/settings.json` (top-level: `permissions`, `hooks` / hook events: PreToolUse, PostToolUse, SubagentStop, TaskCompleted, TaskCreated, FileChanged, PreCompact, PostCompact)

## Section 3. 用語集 (本タスク固有)

| 用語 | 定義 |
|---|---|
| 管理メタデータ | top-level `_build_claude_settings` に置く生成済み hook / permission の台帳 |
| user 管理値 | 管理メタデータに載っていない手編集領域。CLI 実行で意味的に保存されなければならない |
| INV-N | settings merge 不変条件識別子 (本仕様で定義) |
| マージ順序 | 複数 plugin 由来 hook の決定的並び (順序非依存にできない場合の規約) |
| 衝突 | 異なる plugin が同一 hook event×matcher×command を提供した状態 |

## Section 4. スコープ

### 含む

- `.claude/settings.json` 最上位 2 キー (`permissions`, `hooks`) のマージ規約
- 管理メタデータ方式の構文と挿入位置
- 衝突検出と解決規約
- 不変条件 INV-1〜INV-12 の定義文

### 含まない

- CLI 実装 (タスク 04 / 07)
- `plugin.json` フォーマット規約 (34 章本体に存在)
- `permissions.deny` の安全規則 (33 章で別途規定)

## Section 5. 前提条件

| # | 条件 | 確認 |
|---|---|---|
| 1 | タスク 01 完了済 (外部参照棚卸し PASS) | `test -f eval-log/task/01/review-approval.json` |
| 2 | 34 章本文を読了済 | チェックリスト |
| 3 | 現行 `.claude/settings.json` のバックアップ取得 | `cp .claude/settings.json eval-log/task/02/settings.before.json` |

### 依存ツールCLI契約確認

本タスクは仕様策定のみのため依存ツールなし。CLI 契約の正本はタスク 04 とし、本タスクは 34a の不変条件と管理メタデータ仕様を確定する。

## Section 6. 完了条件 (DoD)

| # | 条件 | 検証 |
|---|---|---|
| DoD-1 | 34a 章ドラフト `doc/ClaudeCodeスキルの設計書/34a-settings-merge-spec.md` 生成 | `test -f doc/ClaudeCodeスキルの設計書/34a-settings-merge-spec.md` |
| DoD-2 | INV-1〜INV-12 が個別の見出しで明文化 | `grep -cE "^## INV-[0-9]+ " doc/ClaudeCodeスキルの設計書/34a-settings-merge-spec.md` が 12 |
| DoD-3 | 管理メタデータ構文の Backus-Naur 風定義あり | `grep -q "_build_claude_settings" doc/ClaudeCodeスキルの設計書/34a-settings-merge-spec.md` |
| DoD-4 | 衝突検出ルールが擬似コードで記載 | `grep -q "衝突検出" doc/ClaudeCodeスキルの設計書/34a-settings-merge-spec.md` |
| DoD-5 | サンプル: 入力 plugin.json + 期待 .claude/settings.json を 1 組以上収録 | `grep -c "### 例" doc/ClaudeCodeスキルの設計書/34a-settings-merge-spec.md` ≥ 1 |
| DoD-6 | 全 INV について「機械検証手段」が一文以上記載 | レビュアー確認 |
| DoD-7 | `eval-log/task/02/review-approval.json` の `approver` 非空 | `python3 -c "import json; assert json.load(open('eval-log/task/02/review-approval.json')).get('approver')"` |

## Section 7. 実行手順

### Step 7.1 — INV 候補の確定

34a 章では INV-1〜INV-12 を採用する。INV-1〜8 は settings 生成の基本不変条件、INV-9〜12 は plugin 横断の名前空間、構造検証、permissions、plan 完全性を扱う。

| INV | 内容 |
|---|---|
| INV-1 | 管理メタデータに載っていない user 管理値を意味的に保存する |
| INV-2 | 生成 hook / permission と管理メタデータは決定的に生成される (入力が同じなら出力も同じ) |
| INV-3 | 冪等性: 同じ入力で 2 回実行しても結果が同一 |
| INV-4 | 順序: plugin 間 hook の並びは plugin name の辞書順 |
| INV-5 | 衝突: 同一 event×matcher×command が複数 plugin から出たら ERROR (silent merge 禁止) |
| INV-6 | フィールド保存: 未知トップレベルキーは保存される (forward-compat) |
| INV-7 | JSON 正規化: インデント 2、末尾改行あり、UTF-8、キー順は schema 順 |
| INV-8 | 失敗時の原子性: 書き込み失敗時 `.claude/settings.json` は元状態維持 |
| INV-9 | plugin / skill / agent / command / hook / permission の名前空間一意性 |
| INV-10 | settings JSON 構造検証 |
| INV-11 | permissions マージ安全性 |
| INV-12 | plan JSON 完全性 |

### Step 7.2 — INV-1〜INV-12 レビュー

レビュアーは 34a 章の INV-1〜INV-12 を確認する。修正・追加・削除が必要な場合は 34a とタスク 04 を同時に更新し、後続タスクには進まない。

### Step 7.3 — 管理メタデータ構文定義

JSON コメント不可、かつ Claude Code hooks では `hooks` 直下の key が hook event 名として扱われるため、`hooks` 配下に番兵キーを置かない。生成管理情報は top-level `_build_claude_settings` に分離する:

```json
"_build_claude_settings": {
  "managed_hooks": [
    {
      "event": "PreToolUse",
      "matcher": "Write|Edit",
      "command": "python3 ${CLAUDE_PROJECT_DIR}/plugins/skill-creator/scripts/hook-validate-skill-md.py",
      "from_plugin": "skill-creator"
    }
  ]
},
"hooks": {
  "PreToolUse": [...]
}
```

実 hook 定義は公式構造のまま `hooks` 配下に置く。次回生成時は `_build_claude_settings.managed_hooks` の normalized triple (`event`, `matcher`, `command`) に一致する既存 entry だけを置換し、台帳に載っていない user 管理 hook は保存する。

### Step 7.4 — 34a 章ドラフト執筆

`doc/ClaudeCodeスキルの設計書/34a-settings-merge-spec.md` を以下構成で執筆:

```
# 34a 章 settings.json マージ仕様

## §1 目的
## §2 三層モデル参照 (34章への参照)
## §3 管理メタデータ構文
## §4 マージアルゴリズム (擬似コード)
## §5 不変条件
   ## INV-1 ...
   ## INV-2 ...
   ...
   ## INV-8 ...
## §6 衝突検出
## §7 例
   ### 例 1: 単一 plugin
   ### 例 2: 複数 plugin マージ
   ### 例 3: 衝突 ERROR
## §8 機械検証手段
## §9 CLI 契約 (タスク 04/07 への引き継ぎ)
```

### Step 7.5 — レビュー記録

`eval-log/task/02/review-approval.json` に承認情報を保存。

## Section 8. 検証手順

DoD-1〜DoD-7 を順に検査。INV ごとの「機械検証手段」記載は人間レビュー。

## Section 9. リスクと対策

| ID | リスク | 対策 |
|---|---|---|
| R-01 | INV 不足で後続実装が漏れる | INV-1〜12 を漏れなく列挙、レビューで追加可 |
| R-02 | 管理メタデータが Claude Code hook schema と衝突 | `hooks` 配下へ番兵キーを置かず、top-level `_build_claude_settings` に分離 |
| R-03 | 衝突仕様が曖昧で silent merge を許す | INV-5 で ERROR 明記、CI で再現テスト |
| R-04 | user 管理値破壊 | INV-1 の意味的等価チェックを 04/07 の DoD に伝搬 |

## Section 10. 成果物一覧

| ファイル | 責任者 |
|---|---|
| `doc/ClaudeCodeスキルの設計書/34a-settings-merge-spec.md` | AI 起案 + 人間確定 |
| `eval-log/task/02/inv-draft.md` | AI |
| `eval-log/task/02/review-approval.json` | 人間 |

### CLI 契約ドラフト (後続タスク 04/07 への引き継ぎ)

本タスクでは `scripts/build-claude-settings.py` の CLI 契約案を記録する。**凍結済み CLI 契約の唯一正本はタスク 04 Section 10** とし、本節はタスク 04 の入力ドラフトに留める。

```
usage: build-claude-settings.py [-h]
                                [--plugins-dir PLUGINS_DIR]
                                [--target TARGET]
                                [--dry-run]
                                [--check]
```

- `--plugins-dir`: 既定 `plugins/`
- `--target`: 既定 `.claude/settings.json`
- `--dry-run`: 標準出力にマージ結果を吐くのみ
- `--check`: 生成 hook / permission と管理メタデータが最新と一致すれば exit 0、差分あれば exit 1

タスク 04 で凍結された契約と相違する実装は P1_structural 扱い。

## Section 11. 参照ドキュメント

- `doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md`
- `.claude/settings.json` (現行)

## Section 12. 中学生レベル概念説明

冷蔵庫を想像してください。**自販機が補充した品物には台帳シール (= `_build_claude_settings`) を貼り、家族が置いた品物には触らない**というルールです。次に補充するとき、ロボットは台帳に載っている品物だけを入れ替え、台帳にない家族の品物は残します。

```
冷蔵庫 = .claude/settings.json
├─ 台帳 (_build_claude_settings)
├─ 自販機が補充した品物 (managed hooks)
└─ 家族の品物 (user 管理 hook / permission)
```

不変条件 (INV) は「自販機が守るべき約束」で、たとえば「台帳にない家族の品物を残す (INV-1)」「同じ商品を同じ場所に毎回置く (INV-3 冪等)」など。

## Section 13. 実行者チェックリスト

- [x] タスク 01 完了確認
- [x] INV-1〜INV-12 をレビュアーと確認
- [x] 管理メタデータ構文が 34a と一致
- [x] 34a 章ドラフト執筆
- [x] DoD-1〜DoD-7 全 PASS
- [x] 後続 03/04/05 着手可能を宣言

## 改訂履歴

| 日付 | バージョン | 改訂者 | 内容 |
|---|---|---|---|
| 2026-05-19 | v1 | initial | Section 1-13 構成で初版 |
| 2026-05-19 | v2 | elegant-review | CLI 契約をタスク 04 に一本化し、本節をドラフトへ格下げ |
