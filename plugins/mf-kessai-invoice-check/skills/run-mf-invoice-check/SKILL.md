---
name: run-mf-invoice-check
description: 前月と今月の請求書発行漏れをチェックしたいとき、月次で請求発行状況を確認したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "[--month YYYY-MM]"
arguments: [month]
allowed-tools:
  - Read
  - Write
  - Bash(python3 *)
  - Task
kind: run
prefix: run
effect: external-mutation
owner: team-platform
since: 2026-06-19
version: 0.1.0
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-06-19
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-collect.md
  - prompts/R2-diff.md
  - prompts/R3-verify.md
  - prompts/R4-sink.md
schema_refs:
  - schemas/invoice-gap-result.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 発行漏れ候補が「前月発行−今月発行」の差集合として issue_date 帰属で正しく算出され、月またぎ発行(例 5月取引→6月発行)も誤判定しないことを pytest(test_invoice_diff の detect_gaps)で機械検証できる。
      verify_by: test
    - id: IN2
      loop_scope: inner
      text: 二段確認の物理境界が機構強制される——sink が確定リスト(mfk-gap-verified.json)不在では fail-closed(exit 2)で停止し、未検証候補の直結投入を防ぐことを test_check_invoice_gaps で機械検証できる。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: スキル全体がユーザ目的(発行漏れの早期発見・独立 context での誤検出排除・候補0件月も含む確認済み履歴の保全・参照専用の保証)を最適に反映し、collect→verify→finalize→sink と Notion 冪等 upsert の責務分割が目的に対し過不足ないこと。
      verify_by: elegant-review
---

# run-mf-invoice-check

## Purpose & Output Contract

前月発行・今月未発行の取引先（発行漏れ候補）を MF掛け払い API から差集合で洗い出し、商品名・前月/今月金額・取引先企業名を突合して Notion DB に冪等 upsert し、画面にも要確認リストを表示する。候補0件の月も `月次サマリ` 行とページ本文の実行履歴で確認済み月を残す。

**入力**: `month`（任意。既定は実行日の月。前月は自動算出）
**出力**: 発行漏れ候補が Notion DB に反映 + 月次サマリ行/ページ本文に実行履歴を追記 + 画面に要確認リスト。
**完了条件**: collect→verify(subagent)→sink が完了し、確定候補と月次サマリが Notion に upsert された状態。

## End-to-End Flow

```
[1 collect]  check_invoice_gaps.py --collect → eval-log/mfk-gap-candidates.json (未検証) + 画面サマリ
[2 diff]     lib/mfk_invoice_diff.detect_gaps (collect内, 純関数・pytest済)
[3 verify]   subagent mfk-gap-verifier (context:fork) で誤検出排除
[4 finalize] check_invoice_gaps.py --finalize [--exclude-ids …] → eval-log/mfk-gap-verified.json (確定)
[5 sink]     check_invoice_gaps.py --sink → 確定リスト + 月次サマリを Notion 冪等upsert、ページ本文へ履歴追記
             ↑ 確定リスト不在なら fail-closed(exit 2)。MF APIは全GET / 変更系は hook(guard-mfk-readonly.py)で遮断
```

詳細は `workflow-manifest.json`、責務は `prompts/R1-R4`。collect 出力(未検証)と finalize 出力(確定)を
別ファイルに分離し、sink が確定リストを fail-closed で要求することで二段確認を機構強制する。

## ゴールシーク実行

### ゴール (Goal)
前月発行−今月発行の差集合（発行漏れ候補）が商品名/金額/取引先企業名つきで Notion DB に冪等 upsert され、独立 context の subagent で誤検出を排除した要確認リストが画面に提示された状態。

### 目的・背景 (Why)
発行漏れの早期発見。チェック漏れは取引先との信頼低下に直結するため、月次で機械的に差集合を洗い出す。契約終了等の除外は API で判別できないため人が請求要否列で管理し、機械では消さない。誤検出を防ぐため候補は独立 context で二段確認する。

### 責務サマリと完了条件の正本

各責務の**完了条件の詳細は `prompts/Rn` の L5.3 完了チェックリストを正本 (SSOT)** とする (片側更新ドリフトを避けるため SKILL 側で再定義しない)。本節は俯瞰用の責務サマリのみ示す。

- **R1 collect** (`prompts/R1-collect.md`): 前月・今月の `/billings/qualified` を全ページ取得する。
- **R2 diff** (`prompts/R2-diff.md`): 取得集合を `発行漏れ候補/継続発行/今月新規` に差集合分類し金額変動を検出する。
- **R3 verify** (`prompts/R3-verify.md`): subagent `mfk-gap-verifier` が独立 context で誤検出を排除する。
- **R4 sink** (`prompts/R4-sink.md`): customer_id×対象年月キーで Notion DB に冪等 upsert する (重複行を作らず管理列に触れない)。`__monthly_summary__×対象年月` の月次サマリ行とページ本文追記で確認済み履歴を残す。

横断不変条件 (各 Rn の L1/L4 が担保): 契約終了等の除外は機械で消さず請求要否列で人が管理。MF API への POST/PATCH/DELETE は hook で遮断され参照専用が保証される。

### 完了チェックリスト (Checklist)
> 各責務の停止条件詳細は `prompts/Rn` の L5.3 を正本 (SSOT) とする。本節は俯瞰用の二値チェックのみ。
- [ ] `--collect` が前月/今月の qualified billing を全ページ取得し未検証候補 JSON を出力した (R1/R2)
- [ ] subagent `mfk-gap-verifier` が独立 context で誤検出を排除した (R3)
- [ ] `--finalize` が確定リスト `eval-log/mfk-gap-verified.json` を物質化した (二段確認の物理境界)
- [ ] `--sink` が確定リストを customer_id×対象年月キーで冪等 upsert した (管理列不可侵, R4)
- [ ] `--sink` が月次サマリ行を作成/更新し、ページ本文へ実行履歴を追記した (候補0件月も確認済み記録を残す)
- [ ] 運用者が任意の過去月の確認済み状態と件数を Notion 上 (対象年月ソート/レコード種別フィルタ) で参照できる (見方は README『過去月の状態を確認する』参照)
- [ ] `database_id` 未設定時は db-setup へ差し戻した

### ゴールシークループ
1. `--collect` で現状取得→差集合→突合し未検証候補JSONを得る（`R1`/`R2`）。
2. subagent で二段確認し誤検出を排除（`R3`）。
3. `--finalize [--exclude-ids …]` で確定リストへ昇格（`R3`）。確定リスト不在では次へ進めない。
4. `--sink` で確定リストを Notion へ冪等 upsert（`R4`）。確定リスト不在なら fail-closed。
5. 全 checklist 充足で完了。`database_id` 未設定なら db-setup へ差し戻す。

### ゴールシーク配線
複数月の遡及 (backfill) や verify FAIL 時の再試行で多周回す場合の周回状態とドリフト圧縮の配線。周回末に `eval-log/run-mf-invoice-check-intermediate.jsonl` へ `{iteration, original_goal, current_goal_snapshot, delta_from_original, merged_directive_for_next, drift_signal}` を1行追記する。`original_goal` は全周回で不変 (SHA-256 を `eval-log/run-mf-invoice-check-progress.json` の `original_goal_hash` に固定し毎周回照合)。次周回の手順生成は直前の `merged_directive_for_next` と `original_goal` を必須入力として読む (AI 単独再導出禁止)。重い周回は `Skill(run-goal-seek)` に fork 委譲する。単発の当月チェックでは1周で完了し本配線は no-op。

```bash
# 中間成果物アンカーの機械検査 (run-goal-seek/SKILL.md と同型 SSOT)
python3 - "$PWD/eval-log/run-mf-invoice-check-progress.json" "$PWD/eval-log/run-mf-invoice-check-intermediate.jsonl" <<'PY'
import json, os, sys, hashlib
prog_path, inter_path = sys.argv[1], sys.argv[2]
required_keys = {"iteration","original_goal","current_goal_snapshot","delta_from_original","merged_directive_for_next","drift_signal"}
if not os.path.exists(inter_path):
    print("intermediate.jsonl 未生成 (ループ未実行)"); sys.exit(0)
prog = json.load(open(prog_path, encoding="utf-8")) if os.path.exists(prog_path) else {}
lines = [l for l in open(inter_path, encoding="utf-8").read().splitlines() if l.strip()]
first = None
for i, line in enumerate(lines):
    e = json.loads(line)
    assert not (required_keys - e.keys()), f"intermediate[{i}] 必須キー不足"
    if i == 0:
        first = e["original_goal"]
        h = hashlib.sha256(first.encode()).hexdigest()
        assert prog.get("original_goal_hash") in (None, h), "original_goal_hash drift"
    assert e["original_goal"] == first, f"intermediate[{i}] anchor 不変性違反"
print(f"anchor OK: {len(lines)} 行 / 不変 / hash 一致")
PY
```

## Key Rules

1. **参照専用（二層で機械保証）**: 第1層=`hooks/guard-mfk-readonly.py`（PreToolUse）が Bash 経由の MF 変更系コマンドを遮断。第2層=`lib/mfk_api.py` は GET 専用で POST/PATCH/DELETE 関数を構造的に持たない。指示でなく仕組みで担保。
2. **一覧は qualified**: インボイスモードで `/billings` は空。`/billings/qualified` を使う。
3. **冪等 upsert**: customer_id×対象年月キー。事実列・監査メタ列のみ書き、管理列は触らない。
4. **月次完了履歴**: 毎回 `顧客ID=__monthly_summary__` の月次サマリ行を対象年月ごとに upsert し、ページ本文に実行履歴を追記する。候補0件でも完了月を残す。
5. **二段確認必須（機構強制）**: collect は未検証候補、finalize が確定リストを別ファイルに物質化。sink は確定リストを fail-closed で要求し、未検証投入は `--force-unverified` 明示時のみ。verify をスキップした直結投入を仕組みで防ぐ（Sycophancy/誤検出防止）。
6. **除外は人**: 契約終了等の請求不要判断は機械で消さず Notion 請求要否列へ。

## Gotchas

1. `database_id` 未設定なら `run-mf-invoice-db-setup` を先に実行。
2. MF APIキーと Notion トークンは別 Keychain entry。
3. `updated_at` は無いので更新日は `created_at` で代替。
4. 月をまたぐ発行（5月取引→6月発行）があるため判定軸は必ず `issue_date`。
5. 過去月の見方・要対応ビューの作り方は README『過去月の状態を確認する』節を参照。件数はDBプロパティ (発行漏れ件数等) とページ本文の両方で確認可。

## Additional Resources

- `workflow-manifest.json` — collect/diff/verify/sink の Step 定義 + hook guard
- `scripts/check_invoice_gaps.py` — collect/finalize/sink 実行スクリプト (出力先は env MFK_OUTPUT_DIR > CLAUDE_PROJECT_DIR > CWD で解決)
- `prompts/R1-collect.md`〜`R4-sink.md` — 責務プロンプト
- `../ref-mf-kessai-api/` — API仕様・判定アルゴリズム正本
- `../../lib/` — mfk_api / mfk_keychain / mfk_invoice_diff / notion_invoice_sink
- `../../hooks/guard-mfk-readonly.py` — 参照専用ガード
- `../../agents/mfk-gap-verifier.md` — 二段確認 subagent
