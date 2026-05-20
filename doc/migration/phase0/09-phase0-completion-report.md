# タスク 09 — Phase gate 完了報告書 + eval-log

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| タスク ID | 09 |
| タスク名称 | Phase gate 完了報告書 (eval-log 含む) |
| 種別 | 文書 |
| 担当 | AI 起案 + 人間最終承認 |
| 期限 | 対象 Phase の移行ゲート |
| 依存タスク | 対象 Phase の全タスク |
| 後続タスク | 次 Phase の開始判断 |
| ステータス | 完了 (2026-05-20) |
| 改訂履歴 | 2026-05-19 v1 initial |

## Section 2. 目的と背景

### 目的

対象 Phase の成果物・残課題・次 Phase への引き継ぎ事項を集約した完了報告書を作成し、ユーザー (solo_operator) の承認をもって Phase gate を閉じる。

### 背景

34 章は Phase 移行ごとに「完了宣言」を要求する。本タスクで宣言を行わない限り、次 Phase には進めない。

### 根拠

- 34 章 Phase 表
- README タスク一覧 (09 行)

## Section 3. 用語集

| 用語 | 定義 |
|---|---|
| 完了宣言 | 対象 Phase の DoD 集計+人間承認の合体ドキュメント |
| 残課題 | 対象 Phase で完了せず次 Phase へ持ち越す案件 (タスク 01 の `defer` verdict 等) |
| Phase ゲート | 次 Phase 開始の許可判定 |

## Section 4. スコープ

### 含む

- 対象 Phase の DoD 集計表
- タスク 01 の `defer` 案件一覧
- 次 Phase への引き継ぎ事項
- 完了宣言と承認

### 含まない

- 次 Phase のタスク仕様 (別途設計)
- `creator-kit/` 削除 (34章 Phase gate に従う)

## Section 5. 前提条件

| # | 条件 | 確認 |
|---|---|---|
| 1 | 対象 Phase のタスクがすべて完了 | `for i in <target-task-ids>; do test -f eval-log/task/$i/review-approval.json; done` |
| 2 | 全 DoD PASS の証跡が揃う (`not_run` は引き継ぎ表へ収録) | 各 eval-log を grep。`not_run` 件が残る場合は Section 7 で carry-over に必ず登録 |
| 3 | git working tree clean | `git status --porcelain` 空。clean 化できない場合は本タスクで「未充足クローズ根拠」を Section 7.6 に明示 |

### 依存ツールCLI契約確認

文書タスクのため CLI 依存なし。

## Section 6. 完了条件 (DoD)

| # | 条件 | 検証 |
|---|---|---|
| DoD-1 | `doc/migration/phase0/PHASE-GATE-COMPLETION.md` 生成 | `test -f doc/migration/phase0/PHASE-GATE-COMPLETION.md` |
| DoD-2 | 対象 Phase の DoD 集計表あり | レビュアー確認 |
| DoD-3 | 失敗 DoD 件数が 0、かつ `not_run` 件は引き継ぎ表に収録済み | `dod_fail_count == 0` を closure.json で確認。`dod_not_run_count > 0` の場合は `carry_over_items` に対応エントリを必須化 |
| DoD-4 | `defer` 案件が 0 件または次 Phase 引き継ぎ表に収録 | `carry_over_count == 0` または引き継ぎ表あり |
| DoD-5 | `eval-log/phase/<phase>/closure.json` 生成 | `python3 -m json.tool eval-log/phase/<phase>/closure.json` |
| DoD-6 | ユーザー (solo_operator) の最終承認 | closure JSON の `approver` が `solo_operator` |

## Section 7. 実行手順

### Step 7.1 — 全 eval-log を走査

```bash
mkdir -p eval-log/phase/0
for i in 01 02 03 04 05 06 07 08; do
  test -d eval-log/task/$i && ls eval-log/task/$i > eval-log/phase/0/inventory-$i.txt
done
```

### Step 7.2 — DoD 集計表生成

`doc/migration/phase0/PHASE-GATE-COMPLETION.md` を生成:

```
# Phase gate 完了報告

## DoD 集計

| タスク | 名称 | DoD 数 | PASS | 失敗 | 残課題 |
|---|---|---|---|---|---|
| 01 | 外部参照棚卸し | 8 | 8 | 0 | defer N 件 |
| 02 | settings merge 仕様 | 7 | 7 | 0 | - |
| 03 | symlink CLI 仕様 | 6 | 6 | 0 | - |
| 04 | settings CLI 仕様 | 6 | 6 | 0 | - |
| 05 | 三層モデル CONVENTIONS | 5 | 5 | 0 | - |
| 06 | symlink CLI 実装 | 8 | 8 | 0 | - |
| 07 | settings CLI 実装 | 8 | 8 | 0 | - |
| 08 | 試験移行 | 8 | 8 | 0 | - |

## defer 案件一覧 (タスク 01 由来)

(タスク 01 の `verdict==defer` を行ごとに転記)

## 次 Phase への引き継ぎ事項

1. defer 案件の verdict 確定
2. `creator-kit/` 物理削除タイミング
3. 試験移行 1 件以外の plugin 移行
4. CI への `--check` 統合本格化

## 完了宣言

対象 Phase を 2026-MM-DD に閉じる。次 Phase 着手の可否は承認結果に従う。

承認: <name>
```

### Step 7.3 — defer 案件の転記

```bash
python3 - <<'PY' >> doc/migration/phase0/PHASE-GATE-COMPLETION.md
import json
data = json.load(open('eval-log/task/01/inventory.json'))
defers = [x for x in data.get('violations', []) if x.get('verdict') == 'defer']
if not defers:
    print('(該当なし: defer 0 件)')
for item in defers:
    print(f"- {item.get('source')} -> {item.get('raw_target')} ({item.get('reviewer_note', '')})")
PY
```

### Step 7.4 — Phase ゲート承認

```bash
phase="<phase-number>"
mkdir -p "eval-log/phase/${phase}"
cat > "eval-log/phase/${phase}/closure.json" <<EOF
{
  "phase": ${phase},
  "closed_at": "$(date -Iseconds)",
  "approver": "solo_operator",
  "task_pass_count": <N>,
  "task_fail_count": 0,
  "carry_over_count": <N>,
  "next_phase": <N>
}
EOF
```

`approver` は `solo_operator` 固定。別承認者にする場合は README の承認者正本を先に更新する。

### Step 7.5 — README 更新

`doc/migration/phase0/README.md` のステータス列を対象 Phase 分だけ "完了" に更新。改訂履歴に「Phase gate closed」を追記。

### Step 7.6 — 未充足前提のクローズ根拠 (該当時のみ)

Section 5 前提条件のいずれかが未充足のまま Phase gate を閉じる場合、`PHASE-GATE-COMPLETION.md` に「未充足前提のクローズ根拠」節を追加し、以下を明記する。

- どの前提が未充足か
- 未充足のまま閉じる正当化 (リスク受容判断、引き継ぎ範囲)
- 次 Phase 開始時の追加チェック項目

該当が無ければ本節は省略してよい。

## Section 8. 検証手順

DoD-1〜DoD-6 を順に検査。

## Section 9. リスクと対策

| ID | リスク | 対策 |
|---|---|---|
| R-01 | 失敗 DoD を見落として閉じる | Step 7.1 で全 eval-log を集計、DoD-3 で 0 を強制 |
| R-02 | defer 案件が Phase 1 で忘れられる | 引き継ぎ表で必須収録、DoD-4 検証 |
| R-03 | 承認なしで次 Phase 着手 | DoD-6 で承認者必須 |
| R-04 | README ステータス未更新で混乱 | Step 7.5 必須 |

## Section 10. 成果物一覧

| ファイル | 責任者 |
|---|---|
| `doc/migration/phase0/PHASE-GATE-COMPLETION.md` | AI |
| `eval-log/phase/0/closure.json` | 人間最終承認 |
| `eval-log/phase/0/inventory-*.txt` | AI |
| `doc/migration/phase0/README.md` (改訂) | AI |

### ツール契約

文書タスクのため CLI 契約なし。

## Section 11. 参照ドキュメント

- 全タスク 01〜08 成果物
- 34 章 Phase 表

## Section 12. 中学生レベル概念説明

対象 Phase が終わった後の **完了報告書**です。各部屋 (= 対象タスク) の点検チェック表をまとめて、引っ越し業者 (= ユーザー) のサインをもらいます。**サインがない限り、次の段階には進めません**。「あとで決める」と保留した荷物 (defer 案件) は、次 Phase の最初の議題として持ち越されます。

## Section 13. 実行者チェックリスト

- [x] タスク 01〜08 完了確認 (全 review-approval.json 存在)
- [x] DoD 集計表生成
- [x] defer 案件の転記
- [x] 次 Phase 引き継ぎ事項記載
- [x] closure.json 生成
- [x] approver が `solo_operator`
- [x] README ステータス全件 "完了" 更新
- [x] DoD-1〜DoD-6 全 PASS

## 改訂履歴

| 日付 | バージョン | 改訂者 | 内容 |
|---|---|---|---|
| 2026-05-19 | v1 | initial | Section 1-13 構成で初版 |
| 2026-05-19 | v2 | elegant-review | Phase 0 固定表現を Phase gate 汎用に修正し、defer 0件と solo_operator 承認を明確化 |
| 2026-05-20 | v3 | gate-audit | not_run の引き継ぎ必須化 (DoD-3 / 前提2)、Step 7.3 の defer 0件ガード追加、Step 7.6「未充足前提のクローズ根拠」節を新設 |
| 2026-05-20 | v4 | codex | Task 08 の実行可能性証跡を反映し、DoD 全 PASS の完了報告へ同期 |
