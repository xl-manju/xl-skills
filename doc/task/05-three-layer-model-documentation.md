# タスク 05 — 三層モデル CONVENTIONS.md 追記

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| タスク ID | 05 |
| タスク名称 | 層A/B/C 責務境界の CONVENTIONS.md 追記 |
| 種別 | 仕様策定 + 実行 (文書追記) |
| 担当 | AI 起案 + 人間承認 |
| 期限 | Phase 0 完了の最低条件 |
| 依存タスク | 02 (settings merge 仕様) |
| 後続タスク | 08 (試験移行で参照) |
| ステータス | 未着手 |
| 改訂履歴 | 2026-05-19 v1 initial |

## Section 2. 目的と背景

### 目的

`creator-kit/`・`scripts/`・`references/`・`.claude/` の責務境界を **層 A (配布対象 plugin 本体) / 層 B (プロジェクト固有運用) / 層 C (移行中 drift)** の 3 区分で確定し、`CONVENTIONS.md` (リポジトリ直下) に追記する。

### 背景

ユーザー懸念「scripts/ と references/ を creator-kit に統合すべきか」の本質は、**責務境界が文書化されていない**ことに起因する。本タスクで境界を明文化することで、以降の改変が「どの層に属するか」一意に判定できる。

### 根拠

- 設計書 34 章 §5「配布対象の層分け」
- README タスク一覧 (05 行)
- ユーザー指摘「scripts/references/ の所属が不明瞭」

## Section 3. 用語集

| 用語 | 定義 |
|---|---|
| 層 A | 配布対象 plugin 本体。`plugins/<name>/` 配下、marketplace 配布物 |
| 層 B | プロジェクト固有運用。`.claude/`, `scripts/` のうち plugin 化しないもの |
| 層 C | 移行中 drift。Phase 0〜2 の間だけ存在する暫定領域 (`creator-kit/`, 旧 `scripts/`) |
| 配布判定 | 「層 A に入れる/入れない」の二択を一意化する判定基準 |

## Section 4. スコープ

### 含む

- 3 層の定義と各層に属するパスの列挙
- 配布判定フローチャート
- `CONVENTIONS.md` への追記内容
- 層をまたぐ参照規則 (A→B, B→A, C→A/B)

### 含まない

- 具体ファイルの物理移動 (タスク 08)
- 移行スケジュール (34 章 Phase 表に従う)

## Section 5. 前提条件

| # | 条件 |
|---|---|
| 1 | タスク 02 完了 |
| 2 | リポジトリ直下に `CONVENTIONS.md` が存在 (なければ新規作成可) |

### 依存ツールCLI契約確認

文書タスクのため CLI 依存なし。

## Section 6. 完了条件 (DoD)

| # | 条件 | 検証 |
|---|---|---|
| DoD-1 | `CONVENTIONS.md` に「## 三層モデル」セクション追記 | `grep -q "## 三層モデル" CONVENTIONS.md` |
| DoD-2 | 各層に該当パスが ≥1 件列挙 | `grep -cE "^- \`.*\`" CONVENTIONS.md` ≥ 3 |
| DoD-3 | 層をまたぐ参照規則 4 種 (A→A, A→B 禁止, B→A 許容, C→任意) が明記 | レビュアー確認 |
| DoD-4 | 配布判定フローチャート (mermaid または ASCII) あり | `grep -q "配布判定" CONVENTIONS.md` |
| DoD-5 | レビュー承認ログ生成 | `python3 -c "import json; assert json.load(open('eval-log/task/05/review-approval.json')).get('approver')"` |

## Section 7. 実行手順

### Step 7.1 — 既存 CONVENTIONS.md の確認

```bash
test -f CONVENTIONS.md && cp CONVENTIONS.md eval-log/task/05/CONVENTIONS.before.md || echo "ない場合は新規作成"
```

### Step 7.2 — 3 層定義の起案

| 層 | 定義 | 例 |
|---|---|---|
| A 配布対象 | marketplace で配布する plugin 本体 | `plugins/skill-creator/` 一式 |
| B プロジェクト運用 | このリポジトリ固有の運用物 | `eval-log/`, `doc/`, `CONVENTIONS.md`, `.github/` |
| C 移行中 drift | Phase 0-2 中だけ存在する暫定領域 | `creator-kit/`, ルート `scripts/`, `references/` |

### Step 7.3 — 参照規則の起案

| from \ to | A | B | C |
|---|---|---|---|
| A | 同一 plugin 内のみ | **禁止** | **禁止** |
| B | OK (派生 symlink 経由) | OK | OK |
| C | OK | OK | OK (時限) |

Phase 0-2 では「A → B 禁止」の例外を作らない。例外が必要になった場合は P1_structural proposal として 33章 change governance に従う。

### Step 7.4 — 配布判定フローチャート起案 (ASCII)

```
変更対象ファイル X
   │
   ├── 他プロジェクトに持って行きたい? ──── Yes ──→ 層 A (plugins/)
   │                                              │
   │                                       Plugin 名は決まっている?
   │                                          ├── Yes → plugins/<name>/
   │                                          └── No  → タスク 08 で確定
   │
   └── No
       │
       ├── このリポジトリの運用ログ/設計書? ── Yes → 層 B
       │
       └── 旧構造 (creator-kit/, scripts/) ── Yes → 層 C (Phase 2 で除却)
```

### Step 7.5 — CONVENTIONS.md 追記

`CONVENTIONS.md` 末尾に「## 三層モデル」セクションを追加。Step 7.2-7.4 の表とフローチャートを転記。

### Step 7.6 — レビュー承認

`eval-log/task/05/review-approval.json` を生成。

## Section 8. 検証手順

DoD-1〜DoD-5 を順に検査。

## Section 9. リスクと対策

| ID | リスク | 対策 |
|---|---|---|
| R-01 | 層 C が永続化して移行が頓挫 | 34 章 Phase 4 で C 撤廃を明示、CI で C パス検出 |
| R-02 | A→B 例外で抜け道作られる | Phase 0-2 は例外なし。例外は P1_structural proposal 必須 |
| R-03 | 層判定が主観揺れ | 配布判定フローチャートに従う |
| R-04 | CONVENTIONS.md 上書きで他規約消失 | バックアップ (Step 7.1) |

## Section 10. 成果物一覧

| ファイル | 責任者 |
|---|---|
| `CONVENTIONS.md` (追記) | AI |
| `eval-log/task/05/CONVENTIONS.before.md` | AI |
| `eval-log/task/05/three-layer-table.md` | AI |
| `eval-log/task/05/review-approval.json` | 人間 |

### ツール契約

文書タスクのため CLI 契約なし。**ただし本仕様の「3 層定義」は、タスク 06/07/08 における判定の正本**となる。

## Section 11. 参照ドキュメント

- 設計書 34 章
- タスク 01 inventory.json (外部参照の所属判定材料)

## Section 12. 中学生レベル概念説明

部屋の片付けに例えます。

```
層 A: スーツケース (= plugins/)        ← 旅行に持っていく物だけ
層 B: 自分の部屋の本棚 (= .claude/, doc/)  ← この家で使う物
層 C: 引っ越し前の段ボール (= creator-kit/) ← 仕分け途中、いずれ空にする
```

**判定ルール**:「他の家でも使う?」と聞いて Yes ならスーツケース (A) へ、「この家だけで使う?」なら本棚 (B) へ、「まだ分けてない」なら段ボール (C) に残す。段ボールは引っ越し完了 (Phase 4) で空にする。

## Section 13. 実行者チェックリスト

- [ ] タスク 02 完了確認
- [ ] CONVENTIONS.md バックアップ
- [ ] 3 層定義表をレビュアーと確定
- [ ] 参照規則 (4 種) 確定
- [ ] A→B 例外なしを確認
- [ ] 配布判定フローチャートをレビュー
- [ ] CONVENTIONS.md 追記
- [ ] DoD-1〜DoD-5 全 PASS

## 改訂履歴

| 日付 | バージョン | 改訂者 | 内容 |
|---|---|---|---|
| 2026-05-19 | v1 | initial | Section 1-13 構成で初版 |
