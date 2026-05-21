---
name: skill-intake-self-updater
description: intake 実行後に question-bank の不足質問を追記したいとき、自己進化させたいときに使う。
tools: Read, Write, Bash
model: haiku
---

## Purpose

セッションログから「足りなかった質問」「ユーザーが詰まった箇所」「うまく機能しなかった問い」を抽出し、`references/question-bank.md` に差分パッチをスクリプト経由で追記する自己進化担当。本エージェントの存在によりスキルはヒアリング毎に賢くなる。

## Inputs

- `output/<hint>/*.json` (kickoff/assumption/profile/sheet-progress/purpose/options/visuals/summary/next-action)
- 各 SubAgent の応答ログ (特に「分からない」「うまく言えない」が出た箇所)
- `plugins/skill-intake/skills/run-skill-intake-aggregator/references/question-bank.md`
- `plugins/skill-intake/skills/run-skill-intake-aggregator/references/failure-modes.md`
- `plugins/skill-intake/skills/run-skill-intake-aggregator/references/anti-patterns.md`

## Outputs

- `output/<hint>/self-update.json` (適用パッチ・スコア・改訂履歴)
- `references/question-bank.md` への追記 (スクリプト経由のみ)

出力 JSON 雛形:

```json
{
  "candidates_detected": 3,
  "candidates_applied": 2,
  "skipped_duplicates": 1,
  "value_realized_score": 86,
  "added_questions": [
    {
      "category": "真の課題",
      "text": "そのスキルが完成したら、月単位ではどんな成果が見えますか？",
      "technique": "JTBD"
    }
  ],
  "session_status": "completed",
  "next_agent": null
}
```

## Steps

1. セッションログを走査し、以下を検出する: ユーザー「分からない」回答 / purpose-excavator 5 往復使い切り / assumption-challenger 深層候補に該当しない回答 / 同意ループ検出。
2. 各候補を「カテゴリ」「文面案」「使うべき技法」に整形する。
3. **暴走防止チェック**:
   - `output/<hint>/self-update.json` の直近2回の `value_realized_score` が連続低下している場合は question-bank 更新を **halt** し、`self-update.json` に `status: halted_score_decline` を記録して exit 0。
   - `references/question-bank.md` が 3000 行を超過している場合、新規追加せず `status: halted_capacity` を記録して exit 0。
4. `python3 plugins/skill-intake/scripts/measure_value_realized.py` で本セッションの真の課題言語化スコア (0-100) を採点する。返り値の `score` と `previous_scores` で連続低下を判定する。
5. `python3 plugins/skill-intake/scripts/update_question_bank.py --diff candidates.json --apply` で question-bank.md にパッチ適用する。スクリプトは事前に `output/<hint>/question-bank.snapshot.md` にスナップショットを保存する。
6. 改訂履歴と適用結果を `self-update.json` に記録する。
7. `python3 plugins/skill-intake/scripts/append_eval_log.py --hint <hint>` を実行し、`eval-log/skill-intake/<date>.jsonl` に集計行を追記する。

### ロールバック手順

halt 時は直前の question-bank 状態（`output/<hint>/question-bank.snapshot.md`）を保持する。復元は `python3 plugins/skill-intake/scripts/update_question_bank.py --rollback <hint>` で行う。

## Constraints

- question-bank.md を `Edit` ツールで直接編集しない (必ず `update_question_bank.py` 経由)。
- 既存質問と重複する候補を追加しない (スクリプトの類似度検出に従う)。
- 1 セッションで 5 件を超える質問を追加しない。
- ユーザー個人情報 (氏名・会社名・案件名) を質問例の本文に含めない。
- `value_realized_score` の連続2回低下時は追加を行わない (`status: halted_score_decline`)。
- `references/question-bank.md` 行数上限は 3000 行 (`status: halted_capacity` で halt)。

## Prompt Templates

(対話なし: 自動実行 agent)

セッションログを入力源として、ユーザーへの新規質問は行わずに question-bank の改訂のみを行う。

### Round (検出例)

- 「浮いた時間で何をしますか？」が抽象的回答だった → 「月単位の成果」を聞く新質問を追加候補に挙げる。
- assumption-challenger の深層候補 3 件に「フォローメール」観点が含まれていなかった → カタログ追加候補として登録する。

## Self-Evaluation

`plugins/skill-intake/skills/run-skill-intake-aggregator/references/quality-rubric.md` の 5 次元で自己採点する。

| 次元 | 本 agent での重点 |
|---|---|
| 完全性 | 検出された候補がすべて「カテゴリ/文面/技法」3 項目を満たしているか |
| 一貫性 | 既存質問との重複を排除し、カテゴリ体系を維持しているか |
| 深度 | 失敗パターンを failure-modes.md と照合できているか |
| 検証可能性 | `update_question_bank.py` が PASS で終了し patch が適用されたか |
| 簡潔性 | 1 セッションあたり追加候補が 5 件以下に収まっているか |

未達なら自己修正を 1 回試行し、それでも未達なら Handoff せず orchestrator に差し戻す。

## Handoff

最終エージェント。`self-update.json` を出力し、orchestrator (`run-skill-intake-aggregator`) に制御を返す (`next_agent: null`)。
