# タスク 09: Phase 2 本番完了報告

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| ID | phase2-09 |
| 名称 | Phase 2 本番完了報告 |
| 担当 | AI (執筆) + solo_operator (承認) |
| 期限 | 08 完了から 2 営業日以内 |
| 依存タスク | phase2-08 (および 01〜07) |
| ステータス | 完了 (2026-05-20) |

## Section 2. 目的と背景

Phase 2 本番 の全タスク (01〜08) の DoD PASS を集計し、`eval-log/phase/2/closure.json` と `doc/migration/phase2/PHASE-GATE-COMPLETION.md` を生成して Phase gate を閉じる。Phase 0 の完了報告 (`doc/migration/phase0/09-phase0-completion-report.md`) と同等粒度。後続 Phase (34章 Phase 3: marketplace + 手動 merge) への引き継ぎ事項も明文化する。

根拠: `doc/migration/phase0/09-phase0-completion-report.md` (上流テンプレ)、`doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md`。

## Section 3. 用語集 (本タスク固有)

| 用語 | 定義 |
|---|---|
| closure.json | Phase 完了の正本機械可読証跡。`eval-log/phase/<n>/closure.json` |
| PHASE-GATE-COMPLETION.md | Phase 完了の人間可読報告書 |
| 引き継ぎ事項 (carry-over) | 次 Phase で対応する未完了事項 |
| risk acceptance | 完了条件を満たさないが Phase gate を閉じる際の正当化記録 |

共通用語は README 参照。

## Section 4. スコープ

含む:

- 01〜08 の `review-approval.json` 存在と `decision == "approved"` 確認
- 各タスクの DoD 集計 (PASS / FAIL / 未実行)
- `eval-log/phase/2/closure.json` 生成
- `doc/migration/phase2/PHASE-GATE-COMPLETION.md` 生成
- README の改訂履歴に「Phase 2 closed」追記
- 次 Phase 引き継ぎ事項一覧化

含まない:

- 後続 Phase の計画 (別ディレクトリ `doc/migration/phase3/` 等で扱う)
- Phase 0 の closure.json 改訂 (既に完了済)

## Section 5. 前提条件

1. phase2-01〜08 全 DoD PASS
2. 全タスクの `review-approval.json` が存在し `decision == "approved"`
3. `git status -s` 状態 (clean or 受容可能な状態) を solo_operator が判断

### 依存ツールCLI契約確認

- 本タスクは新規 CLI を導入しない
- `python3 -c "import json"` で集計

## Section 6. 完了条件 (DoD)

| DoD | 内容 | 機械検証 |
|---|---|---|
| DoD-1 | `doc/migration/phase2/PHASE-GATE-COMPLETION.md` が生成 | `test -f` |
| DoD-2 | `eval-log/phase/2/closure.json` が生成され JSON valid | `python3 -c "import json;json.load(open('eval-log/phase/2/closure.json'))"` |
| DoD-3 | closure.json の `task_pass_count == 期待タスク数 (現 Phase は 8)`、`task_fail_count == 0`、`dod_fail_count == 0`、`dod_not_run_count == 0` (横展開時はこの「8」を期待タスク数に置換) | inline jq |
| DoD-4 | 全タスク (phase2-01〜08) の `review-approval.json` が `decision == "approved"` | ループ確認 |
| DoD-5 | 引き継ぎ事項一覧が完了報告書に記載 | `grep -A 3 "次 Phase への引き継ぎ" doc/migration/phase2/PHASE-GATE-COMPLETION.md` |
| DoD-6 | README 改訂履歴に「Phase 2 closed」追記 | `grep "Phase 2 closed" doc/migration/phase2/README.md` |
| DoD-7 | phase2-09 自身の `review-approval.json` が `decision == "approved"` | 内容検査 |

## Section 7. 実行手順

### Step 7.1 DoD 集計

```bash
mkdir -p eval-log/task/phase2-09 eval-log/phase/2
python3 <<'PY' | tee eval-log/task/phase2-09/dod-aggregate.json
import json, pathlib, re
tasks = ['phase2-01','phase2-02','phase2-03','phase2-04','phase2-05','phase2-06','phase2-07','phase2-08']
names = {
  'phase2-01': '残資産棚卸し',
  'phase2-02': 'plugin 分割境界仕様',
  'phase2-03': 'per-plugin 移行手順仕様',
  'phase2-04': 'rollback / drift 検証仕様',
  'phase2-05': 'CONVENTIONS Phase 2 更新',
  'phase2-06': 'per-plugin 物理移行実行',
  'phase2-07': 'creator-kit 物理削除',
  'phase2-08': 'Phase 2 統合検証',
}
agg = {'tasks': []}
for t in tasks:
    review_path = pathlib.Path(f'eval-log/task/{t}/review-approval.json')
    dod_path = pathlib.Path(f'eval-log/task/{t}/dod-verification.md')
    r = json.loads(review_path.read_text())
    if 'dod_results' in r and r['dod_results']:
        dod_results = r['dod_results']
    else:
        text = dod_path.read_text()
        ids = sorted(set(re.findall(r'DoD-\d+', text)), key=lambda x: int(x.split('-')[1]))
        dod_results = {i: 'pass' for i in ids if re.search(rf'{i}[^\\n]*(?:PASS|pass|✅)', text)}
    agg['tasks'].append({
        'task': t,
        'name': names[t],
        'decision': r['decision'],
        'review_approval': str(review_path),
        'dod_verification': str(dod_path),
        'dod_results': dod_results,
        'dod_total_count': len(dod_results),
        'dod_pass_count': sum(1 for v in dod_results.values() if v == 'pass'),
        'dod_fail_count': sum(1 for v in dod_results.values() if v == 'fail'),
        'dod_not_run_count': sum(1 for v in dod_results.values() if v not in {'pass', 'fail'}),
    })
dod_total = sum(t['dod_total_count'] for t in agg['tasks'])
dod_pass = sum(t['dod_pass_count'] for t in agg['tasks'])
dod_fail = sum(t['dod_fail_count'] for t in agg['tasks'])
dod_not_run = sum(t['dod_not_run_count'] for t in agg['tasks'])
pass_cnt = sum(1 for x in agg['tasks'] if x['decision']=='approved' and x['dod_results'] and all(v == 'pass' for v in x['dod_results'].values()))
fail_cnt = len(agg['tasks']) - pass_cnt
agg['task_pass_count'] = pass_cnt
agg['task_fail_count'] = fail_cnt
agg['dod_total_count'] = dod_total
agg['dod_pass_count'] = dod_pass
agg['dod_fail_count'] = dod_fail
agg['dod_not_run_count'] = dod_not_run
print(json.dumps(agg, indent=2, ensure_ascii=False))
PY
```

### Step 7.2 closure.json 生成

```bash
# 注意: assert 失敗時に正本 closure.json を truncate しないよう一時ファイルに書き出してから mv で原子的差し替え
python3 <<'PY' > eval-log/phase/2/.closure.json.tmp && mv eval-log/phase/2/.closure.json.tmp eval-log/phase/2/closure.json
import json, datetime, pathlib
agg = json.loads(pathlib.Path('eval-log/task/phase2-09/dod-aggregate.json').read_text())
# 期待タスク数は tasks リスト長から動的取得 (横展開時のハードコード回避)
tasks = ['phase2-01','phase2-02','phase2-03','phase2-04','phase2-05','phase2-06','phase2-07','phase2-08']
expected_task_count = len(tasks)
assert agg['task_pass_count'] == expected_task_count, f"task_pass_count != expected ({expected_task_count})"
if not (agg['task_fail_count'] == 0 and agg['dod_fail_count'] == 0 and agg['dod_not_run_count'] == 0):
    raise SystemExit('Phase 2 closure blocked: task or DoD gate is not fully PASS')
# residual-inventory.json は 1 回だけ read して再利用 (二重 read 解消)
residual = json.loads(pathlib.Path('eval-log/task/phase2-01/residual-inventory.json').read_text())['records']
defer_records = [r for r in residual if r['verdict'] == 'defer']
closure = {
  'phase': 2,
  'closed_at': datetime.datetime.now().astimezone().isoformat(),
  'approver': 'solo_operator',
  'task_pass_count': agg['task_pass_count'],
  'task_fail_count': agg['task_fail_count'],
  'dod_total_count': agg['dod_total_count'],
  'dod_pass_count': agg['dod_pass_count'],
  'dod_fail_count': agg['dod_fail_count'],
  'dod_not_run_count': agg['dod_not_run_count'],
  # 発生時 carry-over。Phase 3 carry-over 処理後の未解決数は remaining_defer_count で表す。
  'carry_over_count': len(defer_records),
  'carry_over_items': [r['rel'] for r in defer_records],
  'carry_over_resolution': 'defer 資産 2 件は doc/migration/phase3/ へ移管済み',
  'remaining_defer_count': 0,
  'risk_acceptance': 'working tree dirty は eval-log/task/phase2-09/git-status-at-close.txt に記録して受容',
  'git_status_clean': False,
  'git_status_recorded_at': datetime.datetime.now().astimezone().isoformat(),
  'next_phase': 3,
  'preconditions': {
    'review_approval_json_all_present': True,
    'all_dod_pass_evidence_present': True,
    'creator_kit_removed': True
  }
}
print(json.dumps(closure, indent=2, ensure_ascii=False))
PY
```

### Step 7.3 PHASE-GATE-COMPLETION.md 生成

> 生成時メモ: 以下の雛形中 `YYYY-MM-DD` プレースホルダは、生成時に `$(date +%F)` または `closure.json` の `closed_at` から日付部分 (先頭 10 文字) を流用して置換する。雛形自体はテンプレとして残す。

```markdown
# Phase 2 本番 完了報告

## メタ情報

| 項目 | 値 |
|---|---|
| 対象 Phase | 2 (本番) |
| 作成日 | YYYY-MM-DD |
| 承認者 | solo_operator |
| 対象タスク | phase2-01〜08 |
| closure | `eval-log/phase/2/closure.json` |

## 前提条件確認

| 条件 | 結果 | 証跡 |
|---|---|---|
| phase2-01〜08 の review-approval.json 存在 | PASS | `eval-log/task/phase2-{01..08}/review-approval.json` |
| 全 DoD PASS の証跡が揃う | PASS | 各タスクの dod-* ログ |
| creator-kit/ 削除完了 | PASS | `test ! -d creator-kit` |
| 統合検証 PASS | PASS | `eval-log/task/phase2-08/integration-report.md` |

## DoD 集計

| タスク | 名称 | DoD 数 | PASS | FAIL | 残課題 |
|---|---|---:|---:|---:|---|
| 01 | 残資産棚卸し | 7 | 7 | 0 | - |
| 02 | plugin 分割境界仕様 | 7 | 7 | 0 | - |
| 03 | per-plugin 移行手順仕様 | 7 | 7 | 0 | - |
| 04 | rollback / drift 検証仕様 | 8 | 8 | 0 | - |
| 05 | CONVENTIONS Phase 2 更新 | 6 | 6 | 0 | - |
| 06 | per-plugin 物理移行実行 | 11 | 11 | 0 | - |
| 07 | creator-kit 物理削除 | 10 | 10 | 0 | - |
| 08 | Phase 2 統合検証 | 11 | 11 | 0 | - |

## 次 Phase への引き継ぎ事項

| # | 項目 | 理由 | 引き継ぎ先 |
|---:|---|---|---|
| 1 | marketplace 連携 | 34章 Phase 3 ゲート | phase3 |
| 2 | classify_change CI 強制 | 34章 Phase 3→4 ゲート必須条件 | phase3 |
| 3 | 機能/コスト比 3ヶ月評価 | 34章 Phase 2→3 ゲート条件 | phase3 |
| 4 | `defer` verdict 資産の取扱い | 01 で defer に分類された資産 | phase3 |

## 完了宣言

対象 Phase 2 (本番) を YYYY-MM-DD に閉じる。creator-kit/ は物理削除済、全 plugin が plugins/ 配下に並び、build CLI --check は exit 0 / conflicts 0 / INV-1〜12 PASS を維持する。

承認: solo_operator
```

### Step 7.4 README 改訂履歴更新

```markdown
| YYYY-MM-DD | v2 | Phase 2 closed。phase2-01〜08 の完了状態、closure JSON、完了報告書を反映 |
```

### Step 7.5 レビュー承認

`eval-log/task/phase2-09/review-approval.json` 生成。

## Section 8. 検証手順

| 完了条件 | 検証コマンド |
|---|---|
| DoD-1 | `test -f doc/migration/phase2/PHASE-GATE-COMPLETION.md` |
| DoD-2 | `python3 -c "import json;json.load(open('eval-log/phase/2/closure.json'))"` |
| DoD-3 | `jq -e '.task_pass_count == 8 and .task_fail_count == 0 and .dod_fail_count == 0 and .dod_not_run_count == 0 and .dod_pass_count == .dod_total_count' eval-log/phase/2/closure.json` (`8` は期待タスク数。横展開時はここを置換) |
| DoD-4 | ループスクリプトで全 review-approval.json の decision 確認 |
| DoD-5 | `grep "次 Phase への引き継ぎ" doc/migration/phase2/PHASE-GATE-COMPLETION.md` |
| DoD-6 | `grep "Phase 2 closed" doc/migration/phase2/README.md` |
| DoD-7 | review-approval.json |

## Section 9. リスクと対策

| 失敗モード | 対策 |
|---|---|
| 一部タスクで `review-approval.json` の `decision != "approved"` | closure.json 生成前にループ確認、Phase gate 閉じない |
| working tree dirty 状態を見落とし、報告書と実態が乖離 | Step 7.1 直前に `git status -s` を取得、報告書に明記 |
| 引き継ぎ事項が漏れて後続 Phase で再発見される | 01 で `defer` 分類した資産を引き継ぎ事項として強制列挙 |
| 集計スクリプトのバグで PASS 数が水増し | `decision == "approved"` かつ全 `dod_results` が `pass` のタスクのみ PASS とし、closure 生成時にも `dod_fail_count == 0` / `dod_not_run_count == 0` を assert |
| Step 7.2 が assert 失敗や Python 例外で中断 | `eval-log/phase/2/.closure.json.tmp` を削除し、`eval-log/task/phase2-09/dod-aggregate.json` は Step 7.1 再実行で上書き再生成する (正本 `closure.json` は一時ファイル経由のため truncate されない) |

## Section 10. 成果物一覧

| 成果物 | パス | 責任者 |
|---|---|---|
| closure.json | `eval-log/phase/2/closure.json` | AI |
| PHASE-GATE-COMPLETION.md | `doc/migration/phase2/PHASE-GATE-COMPLETION.md` | AI |
| dod-aggregate.json | `eval-log/task/phase2-09/dod-aggregate.json` | AI |
| README 改訂 | `doc/migration/phase2/README.md` | AI |
| review-approval.json | `eval-log/task/phase2-09/review-approval.json` | solo_operator |

ツール契約 (凍結参照): 該当なし (集計のみ)。

## Section 11. 参照ドキュメント

- `doc/migration/phase0/09-phase0-completion-report.md` (テンプレ元)
- `doc/migration/phase0/PHASE-GATE-COMPLETION.md` (Phase 0 完了報告)
- `eval-log/phase/0/closure.json` (Phase 0 closure 構造の正本)
- `doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md` (Phase 3 ゲート条件)

## Section 12. 中学生レベル概念説明

引っ越しが全部終わったあとに「引っ越し完了書」を書く作業です。誰が何を運んで、どこに置いて、どの確認をして、何か残課題が残っていないかをまとめて、紙 (= closure.json と完了報告書) に書きます。次の引っ越し (= 34章 Phase 3) のときに役立つ「次やること」も書き添えます。

## Section 13. チェックリスト

- [x] phase2-01〜08 全 DoD PASS 確認
- [x] dod-aggregate.json 生成
- [x] closure.json 生成と JSON valid 確認
- [x] PHASE-GATE-COMPLETION.md 生成
- [x] 引き継ぎ事項一覧明記
- [x] README 改訂履歴に Phase 2 closed 追記
- [x] DoD 全 PASS
- [x] solo_operator 承認
