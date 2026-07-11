# session-record-format.md — 相談セッション記録の形式と置き場契約

`run-ubm-consult` の出力契約（OUT1）と、相談記録の置き場を定める正本。
実データは build では書かない（形式のみ固定）。

## 記録の4要素（OUT1）

相談セッション transcript / 記録は、以下の4要素を必ず含む（`feedback_contract` OUT1 の検出対象）。

1. **考え方/思考フレームの提示**: `references/consult-frames.md` の GF-xxx を **選択肢＋適用視点** で提示した記録（出典 ID: PR-xxx / MS-xxx / 事例）。処方的な単一解ではない。
2. **引き出し質問**: 各ターンで文脈・制約・価値観・既試行を外在化した問い（スタンス不変条件2）。
3. **ユーザー自身の言葉での解決策言語化**: 解決策の主語はユーザー。AI の代弁でない引用ベースの言語化（スタンス不変条件3）。
4. **ゴール指向の次の一歩**: 現状→ゴール→ギャップ→次の一歩の行動計画。次の一歩は「誰に・何を・いつまで・何件」を含む物理的行動（スタンス不変条件4）。

## セッション記録スキーマ（handoff）

`goal_seek.handoff`（`handoff-run-ubm-consult.json`）に以下の形で記録する。

```json
{
  "consult_type": "other",
  "issue_statement": "ユーザーの言葉で確認済みの本質課題1文",
  "elicited": {
    "context": "現状・フェーズ・登場人物",
    "constraints": ["時間/資源/関係/譲れない条件"],
    "values": ["大事にしたいこと・避けたいこと"],
    "prior_attempts": ["既試行とその結果"]
  },
  "frames_presented": [
    {"frame_id": "GF-01", "name": "ゴール指向分解", "viewpoint": "適用の問い", "source_ids": ["PR-xxx", "MS-xxx"]},
    {"frame_id": "GF-04", "name": "因果深掘り", "viewpoint": "適用の問い", "source_ids": ["PR-032"]}
  ],
  "user_solution": "ユーザー自身の言葉で言語化した解決策（引用ベース）",
  "action_plan": {
    "current": "現状",
    "goal": "ゴール",
    "gap": "ギャップ",
    "next_step": "誰に・何を・いつまで・何件を含む物理的行動"
  },
  "stance_self_check": {
    "no_prescription": true,
    "elicit_question_each_turn": true,
    "user_verbalized": true,
    "goal_oriented_closure": true
  },
  "consult_evidence": "consult script / router.json デュアルパスの参照ポインタ（zero-hit 時はその旨）",
  "open_issues": []
}
```

`frames_presented` は2件以上（R3 の選択肢提示）。`stance_self_check` の4フラグは IN1/OUT1 の自己検証結果。

## 置き場契約（重要）

- **正本の記録先は eval-log 配下の handoff（vault 外・固定パス）**: `eval-log/ubm-goal-setting/run-ubm-consult/handoff-run-ubm-consult.json`（repo root 起点の相対）。goal-seek の progress / intermediate も同ディレクトリ。このパスは唯一の規約であり、consumer（下記）はこの固定パスだけを読む。
- **consumer（相談→目標設定のループ辺）**: `agents/info-collector.md` の Phase1-2-collect が本 handoff を **read-only** で参照し、直近の相談の `issue_statement` / `user_solution` / `action_plan.next_step` を目標設定対話（Phase 3）の文脈に引き継ぐ。不在なら graceful skip する（相談を一度もしていない初回でも壊れない）。相談の帰結を目標へ機械配線する唯一の辺。
- **vault へは書かない**: `run-ubm-goal-setting` の出力規約では vault 内書込は `ubm-write-path-guard` により `05_Project/UBM/目標設定/` 配下と `02_Configs/Templates/Daily.md` のみ許可される。相談記録はどちらにも該当しないため、guard に fail-closed で阻まれる。本 skill は vault へ相談記録を書かない（意味的にも 目標設定 ≠ 相談 で衝突を避ける）。
- **vault へ残したい場合**: ユーザー自身の操作（手動保存）に委ねる。本 skill の write scope 外とする。
- **目標設定へ接続する場合**: 相談の帰結（次の一歩）が週報/月報/期報の目標に発展するなら、`run-ubm-goal-setting` を起動して正式な目標設定ファイルを作る（責務境界）。本 skill の handoff はその入力メモとして参照できる。

## 決定論と非後退

- 記録形式は本ファイルが唯一の正本。SKILL.md / prompts は本ファイルを参照し、二重定義しない。
- 既存 capability A（21項目）/ B（6カテゴリ）の成果物・knowledge 実データを変更しない（additive）。
