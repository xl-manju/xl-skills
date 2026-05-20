# タスク 05: CONVENTIONS.md の Phase 2 本番化追記

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| ID | phase2-05 |
| 名称 | CONVENTIONS.md の Phase 2 本番化追記 |
| 担当 | AI (執筆) + solo_operator (承認) |
| 期限 | 02 完了から 3 営業日以内 |
| 依存タスク | phase2-02 |
| ステータス | 完了 (2026-05-20) |

## Section 2. 目的と背景

`CONVENTIONS.md` は phase0 タスク 05 で三層モデル (層A=配布対象 / 層B=プロジェクト固有運用 / 層C=移行中 drift) を定義した。試験移行段階では層C (移行中 drift) が許容されていたが、Phase 2 本番完了 (creator-kit/ 物理削除) 後は層C を退役させ、層A/B 二層モデルに縮退する必要がある。本タスクは CONVENTIONS.md の Phase 2 本番対応セクションを発効待ち差分として追記し、層C 退役の条件と移行スケジュールを明文化する。07 完了前に旧三層定義を削除・置換しない。

根拠: `doc/migration/phase0/05-three-layer-model-documentation.md`、`CONVENTIONS.md` (層C 定義)。

## Section 3. 用語集 (本タスク固有)

| 用語 | 定義 |
|---|---|
| 層A | 配布対象。`plugins/<name>/` 配下が該当。Phase 2 本番完了後はここのみが正本 |
| 層B | プロジェクト固有運用。`.claude/` 配下の手編集領域 (settings.json user セクション、CLAUDE.md 等) |
| 層C | 移行中 drift。`creator-kit/` 配下。本 Phase で退役する一時層 |
| 退役 (retire) | 層 C の正本性を剥奪し、`CONVENTIONS.md` から定義を削除する操作 |
| 縮退 (degenerate) | 三層 → 二層への移行。本タスクで明文化 |

共通用語は README 参照。

## Section 4. スコープ

含む:

- CONVENTIONS.md への「Phase 2 本番セクション」追記
- 層C 退役条件 (Phase 2 タスク 07 完了) の明文化
- 層A/B 二層モデルへの縮退後の責務境界更新
- before / after スナップショットの保存

含まない:

- `creator-kit/` 物理削除実行 (07 の責務)
- 層C のうち `keep-non-plugin` 資産の保管先決定 (01 と 07)

## Section 5. 前提条件

1. phase2-02 完了 (partition-plan 確定)
2. `CONVENTIONS.md` が phase0 タスク 05 の三層定義を含む
3. `diff` コマンド利用可能

### 依存ツールCLI契約確認

- 本タスクは新規 CLI を導入しない
- `diff -u` の出力フォーマットに依存

## Section 6. 完了条件 (DoD)

| DoD | 内容 | 機械検証 |
|---|---|---|
| DoD-1 | CONVENTIONS.md に `## Phase 2 本番 (発効待ち` または同等見出しが追加される | `grep -E "^## .*Phase 2.*発効待ち" CONVENTIONS.md` |
| DoD-2 | 層C 退役条件 (Phase 2 タスク 07 完了) が明記 | `grep -E "層C.*(退役\|retire)" CONVENTIONS.md` |
| DoD-3 | 層A/B 縮退後の責務境界表が含まれる | `grep -E "^\| 層[AB] " CONVENTIONS.md` ≥ 2 |
| DoD-4 | before snapshot が `eval-log/task/phase2-05/CONVENTIONS.before.md` に保存 | `test -f` |
| DoD-5 | diff (before vs after) が `eval-log/task/phase2-05/CONVENTIONS.diff` に保存 | `test -s eval-log/task/phase2-05/CONVENTIONS.diff` |
| DoD-6 | review-approval.json が `approved` | 内容検査 |

## Section 7. 実行手順

### Step 7.1 before snapshot 取得

```bash
mkdir -p eval-log/task/phase2-05
cp CONVENTIONS.md eval-log/task/phase2-05/CONVENTIONS.before.md
```

### Step 7.2 追記文案策定

CONVENTIONS.md 末尾に以下を追記:

```markdown
## Phase 2 本番 (発効待ち: 層C 退役)

> **発効条件**: 本セクションは `doc/migration/phase2/07-creator-kit-removal.md` (タスク 07) の DoD 全 PASS をもって発効する。タスク 07 完了前にこのセクションの内容を運用に適用してはならない。旧三層定義は削除せず、本セクションは発効待ち差分として追記する。

| 項目 | 内容 |
|---|---|
| 適用条件 | `doc/migration/phase2/07-creator-kit-removal.md` DoD 全 PASS |
| 層C 退役後の正本 | `plugins/<name>/` (層A) のみ |
| 層B との関係 | 層B (= `.claude/settings.json` user セクション等) は不変 |
| 縮退後の参照ルール | 層A 内の plugin 間参照は禁止。層B から層A は symlink 経由でのみ参照 |

### 二層モデル縮退後の責務境界

| 層 | 配置 | 責務 |
|---|---|---|
| 層A | `plugins/<name>/` | 配布対象。skill / agent / command / hook の正本 |
| 層B | `.claude/` のうち手編集領域 | プロジェクト固有運用。settings.json user セクション、ローカル CLAUDE.md など |

### 層C 退役チェックリスト

- [x] `creator-kit/` が物理削除済 (`test ! -d creator-kit`)
- [x] `git log -- creator-kit/` が削除 commit を含む
- [x] CONVENTIONS.md の旧「層C」記述は本セクションへの参照に置換
```

### Step 7.3 CONVENTIONS.md 編集

上記文案を `CONVENTIONS.md` 末尾に追記。旧「層C」記述部は 07 完了まで残し、発効後に本セクションへのリンクへ置換する。

### Step 7.4 diff 保存

```bash
diff -u eval-log/task/phase2-05/CONVENTIONS.before.md CONVENTIONS.md > eval-log/task/phase2-05/CONVENTIONS.diff || true
test -s eval-log/task/phase2-05/CONVENTIONS.diff && echo "diff captured"
```

### Step 7.5 README ステータス更新

`doc/migration/phase2/README.md` のステータスを「完了 (YYYY-MM-DD)」に。

### Step 7.6 レビュー承認

solo_operator が `review-approval.json` 生成。

## Section 8. 検証手順

| 完了条件 | 検証コマンド |
|---|---|
| DoD-1 | `grep -E "^## .*Phase 2.*発効待ち" CONVENTIONS.md && echo PASS` |
| DoD-2 | `grep -E "層C.*(退役\|retire)" CONVENTIONS.md && echo PASS` |
| DoD-3 | `grep -cE "^\| 層[AB] " CONVENTIONS.md` |
| DoD-4 | `test -f eval-log/task/phase2-05/CONVENTIONS.before.md && echo PASS` |
| DoD-5 | `test -s eval-log/task/phase2-05/CONVENTIONS.diff && echo PASS` |
| DoD-6 | review-approval.json |

## Section 9. リスクと対策

| 失敗モード | 対策 |
|---|---|
| 旧「層C」記述と発効待ち差分が二重定義に見える | 見出しに「発効待ち」を含め、07 完了前は旧記述を正として残す |
| 追記文案が partition-plan.json と整合しない | Step 7.2 で partition-plan の plugin 名一覧を引用 |
| 縮退後の責務境界が層A の中で曖昧 | 02 partition-plan の責務サマリと一貫させる |
| Phase 2 本番未完で本仕様だけ先行適用 | DoD-1 適用条件に 07 完了を明記 |

## Section 10. 成果物一覧

| 成果物 | パス | 責任者 |
|---|---|---|
| CONVENTIONS.md (改訂後) | `CONVENTIONS.md` | AI |
| before snapshot | `eval-log/task/phase2-05/CONVENTIONS.before.md` | AI |
| diff | `eval-log/task/phase2-05/CONVENTIONS.diff` | AI |
| review-approval.json | `eval-log/task/phase2-05/review-approval.json` | solo_operator |

ツール契約 (凍結参照): 該当なし (文書作業)。

## Section 11. 参照ドキュメント

- `doc/migration/phase0/05-three-layer-model-documentation.md`
- `CONVENTIONS.md` 現行版
- `eval-log/task/05/three-layer-table.md` (phase0 三層モデル定義)

## Section 12. 中学生レベル概念説明

引っ越しの仕分けが進んで「中継地点」(層C = creator-kit) が要らなくなったので、家のルールブック (CONVENTIONS.md) から「中継地点はこう使う」という章を抜く作業です。代わりに「新しい家」(層A) と「自分の私物コーナー」(層B) の 2 つで運用する、と書き直します。

## Section 13. チェックリスト

- [x] phase2-02 DoD 全 PASS
- [x] before snapshot 保存
- [x] CONVENTIONS.md 追記
- [x] 旧「層C」記述置換確認
- [x] diff 保存
- [x] DoD 全 PASS
- [x] solo_operator 承認
