---
name: run-ubm-consult
description: 月間目標・目標設定以外も含む相談に乗ってほしいとき、具体解の処方でなく考え方・思考フレームを引き出し型の共創で提示しユーザー主導で解決策を言語化したいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "[相談内容]"
arguments: [topic]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Task
kind: run
prefix: run
effect: local-artifact
owner: xl-skills-maintainers
since: 2026-07-11
version: 0.1.0
manifest: workflow-manifest.json
trigger_conditions:
  - 相談したい
  - 壁打ち
  - 考え方を教えて
  - ubm-consult
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  engine: inline
  fork: subagent
  progress: eval-log/ubm-goal-setting/run-ubm-consult/goal-seek-progress.json
  intermediate: eval-log/ubm-goal-setting/run-ubm-consult/run-ubm-consult-intermediate.jsonl
  handoff: eval-log/ubm-goal-setting/run-ubm-consult/handoff-run-ubm-consult.json
  max_loops: 5
responsibility_refs:
  - prompts/R1-intake-issue.md
  - prompts/R2-elicit.md
  - prompts/R3-frame-consult.md
  - prompts/R4-cocreate-converge.md
subagent_refs:
  - phase3-coordinator
schema_refs:
  - ../../knowledge/schema.json
knowledge_loop:
  pattern: router-registry
  index: ../../knowledge/router.json
  consult_at: [runtime]
script_refs:
  - ../../scripts/consult-harness-artifact-graph.py
  - ../../scripts/validate-knowledge-graph.py
reference_refs:
  - references/consult-frames.md
  - references/session-record-format.md
  - references/resource-map.yaml
source: plugin-plans/ubm-goal-setting (改善計画 C09・user-request-consult-20260711) の設計
source-tier: internal
last-audited: 2026-07-11
audit-trigger: quarterly
feedback_contract:
  max_iterations: 5
  criteria:
    - id: IN1
      loop_scope: inner
      text: 相談 fixture で具体解を処方せず考え方/思考フレームを 1 件以上提示し、非処方スタンス不変条件(具体解押し付けゼロ)を自己検証する。
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 相談セッション transcript で考え方提示・引き出し質問・ユーザー自身の言葉での解決策言語化・ゴール指向の次の一歩の 4 要素を検出する。
      verify_by: test
---

# run-ubm-consult

月間目標・目標設定以外も含む相談に、**具体解を処方せず「考え方（思考フレーム）」を提示するコーチング型 orchestrator**。引き出し質問でユーザーの文脈・制約・価値観を外在化し、解決策の言語化はユーザー主導とし、AI は構造化と検証を担う。目標設定以外の相談にもゴール指向（現状→ゴール→ギャップ→次の一歩）を適用する。既存 capability A（`run-ubm-goal-setting` Phase3 対話原則「愛情ある厳しさ」・引き出し型）と knowledge 基盤（原則/マインドセット/事例）、C06/C07 の read-only グラフ consult を非後退（additive）で再利用する。

## Purpose & Output Contract

- **ゴール**: 相談に対し考え方/思考フレームを選択肢として提示し、ユーザー自身の言葉で言語化された解決策と、現状→ゴール→ギャップ→次の一歩の行動計画へ帰結した状態。`feedback_contract` の IN1（非処方スタンス）/ OUT1（transcript 4要素）を満たす。
- **出力契約**: 相談セッション記録（相談種別・引き出したユーザー文脈/制約/価値観/既試行・提示した考え方/思考フレーム（選択肢＋適用視点・出典 ID 付き）・ユーザー自身の言葉で言語化した解決策・現状→ゴール→ギャップ→次の一歩の行動計画）。**処方的な単一解は出力しない**。記録の形式と置き場は `references/session-record-format.md` が正本。
- **境界**: knowledge graph / harness artifact graph は read-only consult（C06/C07 経由・書込なし）。相談記録は eval-log 配下の handoff（vault 外・`ubm-write-path-guard` の対象外）へ書く。既存 capability A（21項目）/ B（6カテゴリ）の契約を破壊しない（非後退・additive）。**目標設定そのものの生成は `run-ubm-goal-setting` へ委譲する**。
- **正本**: 思考フレーム カタログ=`references/consult-frames.md`、セッション記録形式と置き場=`references/session-record-format.md`。

## End-to-End Flow

`workflow-manifest.json` が phase の機械可読正本。責務は以下 4 プロンプト（`prompts/R*.md`）が所有する。

| Phase | 責務 | 実行体 |
|---|---|---|
| R1-intake-issue | 相談を受理し相談種別を判定・本質課題の言語化を支援する（具体解を出さない）。目標設定相談なら `run-ubm-goal-setting` へ誘導 | 本 skill（`prompts/R1-intake-issue.md`） |
| R2-elicit | 引き出し質問でユーザーの文脈・制約・価値観・既試行を外在化する | 本 skill（`prompts/R2-elicit.md`） |
| R3-frame-consult | 考え方/思考フレームを選定・提示する（`consult-harness-artifact-graph.py` + `router.json` デュアルパス + 既存 knowledge の原則/マインドセット/事例）。処方でなく選択肢＋適用視点 | 本 skill（`prompts/R3-frame-consult.md`）＋ script |
| R4-cocreate-converge | 共創・収束。ユーザー自身の言葉で解決策を言語化させ、現状→ゴール→ギャップ→次の一歩の行動計画へ落とし記録する | 本 skill（`prompts/R4-cocreate-converge.md`） |

## スタンス不変条件

本 skill の全ターンで不変。逸脱は open_issues に残し差し戻す。

1. **具体解の押し付けゼロ** — 提案は「考え方・視点・フレーム」＋適用のための問いに留める。「あなたは○○すべき」という単一の処方解を出さない。
2. **各ターンで引き出し質問 ≥1** — 情報を返すだけで終えず、ユーザーの文脈を外在化する問いを最低1つ添える。
3. **解決策の言語化はユーザーの発話から** — 解決策の主語は常にユーザー。AI は構造化・要約・検証のみを担い、ユーザーの言葉を先取りして代弁しない。
4. **収束は「現状→ゴール→ギャップ→次の一歩」形式の行動計画** — 目標設定以外の相談でもこのゴール指向で締める。
5. **責務境界** — 週報/月報/期報の目標設定そのものを作りたい相談は `run-ubm-goal-setting へ誘導` し、本 skill では作成しない。

## ゴールシーク実行

固定手順を消化するのでなく、上記ゴールと `feedback_contract` を満たすまで反復する（engine=inline / fork=subagent / max_loops=5）。

### ゴール (Goal)

相談種別が特定され、ユーザー文脈が引き出しで外在化され、考え方/思考フレームが**選択肢＋適用視点**（出典付き）で提示され、ユーザー自身の言葉で解決策が言語化され、現状→ゴール→ギャップ→次の一歩の行動計画へ帰結・記録された状態。

### 目的・背景 (Why)

要望の本質は「具体例より考え方」を届け、解決策はユーザー側で作り上げる共創（コーチング型・非処方型）にある。固定 Q&A では相談種別の取り違え・引き出し不足・処方への逸脱が起きやすいため、非処方スタンス不変条件を都度自己検証しながら未達を埋める。knowledge/graph は read-only で参照し、AI が答えを断定しない。

### 完了チェックリスト (Checklist)

- [ ] 相談種別が判定され、本質課題がユーザーの言葉で1文に言語化されている（R1）。目標設定相談は `run-ubm-goal-setting` へ誘導した。
- [ ] 引き出し質問でユーザーの文脈・制約・価値観・既試行が外在化されている（R2・各ターン引き出し質問 ≥1）。
- [ ] 考え方/思考フレームが**複数の選択肢＋適用視点**として出典 ID（PR-xxx / MS-xxx / 事例）付きで提示され、具体解の処方をしていない（R3・IN1）。
- [ ] ユーザー自身の言葉で解決策が言語化され、現状→ゴール→ギャップ→次の一歩の行動計画へ帰結し記録された（R4・OUT1）。

### ゴールシークループ

正本 `../run-ubm-goal-setting` と同じく `goal_seek` 配線に従う。本 skill 固有の差分:

- `goal_seek.progress` に checklist 状態・iteration・`open_issues`・`status` を記録。各周回末の Anchor Step で `run-ubm-consult-intermediate.jsonl` に `original_goal`/`current_goal_snapshot`/`delta_from_original`/`merged_directive_for_next`/`drift_signal` を append-only。完了時に相談種別・提示フレーム ID・言語化解決策・行動計画を `handoff-run-ubm-consult.json` へ書く（`references/session-record-format.md` の形式）。
- ループ本体は SubAgent context で実行し、親へ返すのはセッション記録要約・handoff・未解決 `open_issues` のみ。
- **inner ループ (IN1)**: 各周回で「具体解を処方していないか（スタンス不変条件1）」「考え方/フレームを1件以上提示したか」を自己検証し、逸脱を検出したら R3 を再実行する。
- **outer ループ (OUT1)**: 相談セッション transcript に考え方提示・引き出し質問・ユーザー自身の言葉での解決策言語化・ゴール指向の次の一歩の4要素が揃うまで反復し、受入テストで確認する。
- `max_loops` 到達時は PASS 扱いせず、残チェックを `open_issues` に残して human review へ差し戻す。

## Key Rules

- **処方でなく考え方**: R3 は「あなたは○○すべき」でなく「こういう見方（フレーム）があります。あなたの場合はどう当てはまりますか？」の形で複数フレームを並べる。北原原則/マインドセットの引用は1対話あたり1〜2件までとし、必ず①原則を引き出す→②ユーザー状況に翻訳→③行動に落とす3ステップで届ける（phase3-coordinator の CONST_004/CONST_006 に準拠）。
- **引き出しファースト**: 情報提供の前後どちらでも、各ターンに引き出し質問を最低1つ置く。深掘りは1項目につき2回まで（追い詰めない）。
- **解決策はユーザーの言葉で**: 収束時、解決策は必ずユーザーの発話を引用・構造化して確定する。AI が代わりに解を書き下さない。長文回答は「つまり○○ということですね？」と1文へ要約確認する。
- **ゴール指向の締め**: 相談種別を問わず現状→ゴール→ギャップ→次の一歩で締める。次の一歩は「誰に・何を・いつまで・何件」を含む物理的行動にする。
- **read-only consult**: `consult-harness-artifact-graph.py`（C07）と knowledge/*.json は参照のみ。起動条件と fallback は `../../references/graph-consult-fallback-contract.md` が正本（knowledge graph があれば consult / harness graph は存在時のみ併用・不在なら knowledge 単独 / knowledge graph 不在は skip / exit2 破損は WARN skip → `router.json` デュアルパス。zero-hit は正常）。

## Gotchas

- **相談記録は vault へ書かない**: `ubm-write-path-guard` は vault 内書込を `05_Project/UBM/目標設定/` と `02_Configs/Templates/Daily.md` のみ許可する。相談記録はそれらに該当しないため、正本は eval-log 配下の handoff（vault 外）に置く。vault へ相談メモを残したいときはユーザー自身の操作に委ね、本 skill は書き込まない（`references/session-record-format.md` 参照）。
- **グラフは運用時生成**: `knowledge/knowledge-graph.json`（C06）と `knowledge/harness-artifact-graph.json`（C05）は本 build では作らない。R3 の consult は harness graph だけ不在なら `--harness-artifact-graph` を省いて knowledge 単独 consult に落とし、knowledge graph も不在のときだけ `router.json` → `knowledge/*.json` の Read デュアルパスへ skip する（AND 前提にしない。正本＝`../../references/graph-consult-fallback-contract.md`）。
- **目標設定との棲み分け**: 「今月の目標を作りたい」は本 skill の対象外。R1 で判定したら `run-ubm-goal-setting` を案内して終える（責務境界）。
- **思考法の名前は出さない**: フレームは質問の形で自然に適用する（phase3-coordinator CONST_003）。カタログ ID（GF-xxx）は記録・出典管理用で、対話中に技法名を振りかざさない。

## Additional Resources

- **prompts**: `prompts/R{1..4}-*.md` — 責務単位 7 層プロンプト正本（verify-completeness.py で 7 層+l5-contract 検証）。
- **agents**: `phase3-coordinator`（対話原則「愛情ある厳しさ」引き出し型の前例。R3/R4 の翻訳3ステップと回答パターン対応を参照）。plugin 直下 `agents/`。
- **scripts**: `../../scripts/consult-harness-artifact-graph.py`（C07・read-only グラフ consult）/ `../../scripts/validate-knowledge-graph.py`（C06・graph gate、グラフ健全性の参照）。
- **references**: `references/consult-frames.md`（思考フレーム カタログ正本）/ `references/session-record-format.md`（OUT1 4要素の記録形式＋置き場契約）/ `references/resource-map.yaml`（Progressive Disclosure 索引）。
- **knowledge**: plugin 直下 `knowledge/`（`router.json` → `*.json` をデュアルパス検索。原則 PR-xxx / マインドセット MS-xxx / 事例を出典として引く）。
