---
name: run-intake-interview
description: ヒアリングシートの 5 軸空欄を順次埋めたいとき、run-skill-intake から phase 4 として呼ばれて sheet.md と interview.json を生成したいときに使う。
allowed-tools:
  - Read
  - Write
  - Edit
  - AskUserQuestion
kind: run
user-invocable: true
effect: local-artifact
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-24
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
role_suffix: null
owner: team-platform
since: 2026-05-22
version: 0.1.0
responsibility_refs:
  - prompts/R1-main.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 5 軸シート充足の停止条件が機械検証可能である——five_axes_complete=true かつ validate-interview-json.py(interview.json の schema 準拠)と check-five-axes-coverage.py(sheet.md の 5 軸 coverage)双方が exit 0 で揃って初めて完了とみなされ、空欄や [?] 残存が PASS をすり抜けないこと。
      verify_by: lint
    - id: IN2
      loop_scope: inner
      text: 抽象回答と個人情報の扱いが機構で担保される——abstract-answer-patterns.md 該当回答は abstract_answers[] に {axis,answer,reason} で印付けし needs_excavation=true を立てて最終確定せず Phase 5 に委ね、社名・個人名は interview.json 本文に直書きせず {{var_*}} へ変数化されていることが schema/script で検査できること。
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: スキル全体が「5 軸シート充足・抽象フラグ付け・interview.json emit」というユーザ目的を過不足なく反映し、深掘り(Phase 5)・仮説検証(Phase 2)・要約(Phase 8)・3 軸確定(run-intake-kickoff)へ越境せず、vocabulary_tier 固定と AskUserQuestion 1 問直列・5 軸優先順位といった責務境界が目的に対し最適であること。
      verify_by: elegant-review
---

# run-intake-interview

## Purpose & Output Contract

intake セッションの Phase 4 担当。ヒアリングシート `sheet.md` の空欄および `[?]` マーカーを **5 軸 (出力先 / 情報源 / 共有相手 / 真の課題 / ナレッジ資産) 優先順位**で `AskUserQuestion` により順次充足し、`interview.json` を emit する。本スキルは「5 軸シート充足・抽象回答フラグ付け・interview.json emit」に責務を絞り、深掘り (Phase 5 `purpose-excavator`)・仮説検証 (Phase 2)・要約 (Phase 8)・3 軸確定 (`run-intake-kickoff`) は行わない。`run-intake-kickoff` との境界は「kickoff=3 軸 (pattern/depth/pain)、interview=5 軸シート」で確定。

**入力**:
- `output/<hint>/profile.json` (`vocabulary_tier` を含む。Phase 3 が確定)
- `output/<hint>/sheet.md` (空欄および `[?]` を含む 5 軸シート)
- `references/question-bank-pointer.md` 経由の質問雛形
- `references/abstract-answer-patterns.md` (抽象回答検出規則)
- `references/five-axes-priority.md` (軸の処理順)

**出力**:
- `output/<hint>/sheet.md` (空欄を埋めた更新済シート)
- `output/<hint>/interview.json` (`schemas/output.schema.json` 準拠。`filled_ratio` / `five_axes_complete` / `unresolved` / `needs_excavation` / `abstract_answers` を保持)

**完了条件**: 5 軸すべて非空 (`five_axes_complete=true`) + `scripts/validate-interview-json.py` PASS + `scripts/check-five-axes-coverage.py` PASS。

## Key Rules

1. **5 軸シート充足のみ**: 深掘り (excavation) / 仮説検証 / 要約 / 3 軸確定は越境しない。それぞれ Phase 5 / 2 / 8 / `run-intake-kickoff` の責務。
2. **AskUserQuestion 1 問ずつ**: 並列・束ね質問禁止。最大 3 択 + 自由入力。
3. **vocabulary_tier 固定**: `profile.json` の tier (beginner|intermediate|expert) をセッション中変更しない。質問雛形はその tier に合わせて言い換える。
4. **抽象回答はフラグのみ**: `references/abstract-answer-patterns.md` に合致したら `abstract_answers[]` に追記し `needs_excavation=true` を立てて次軸へ進む。再質問・深掘りはしない (Phase 5 の責務)。
5. **5 軸優先順位固定**: 出力先 → 情報源 → 共有相手 → 真の課題 → ナレッジ資産。
6. **個人情報の変数化**: 社名・個人名は `interview.json` 本文に転記せず、`{{var_*}}` で抽象化する。

## ゴールシーク実行

### ゴール (Goal)

`profile.json` と `sheet.md` を入力に、`output/<hint>/sheet.md` の 5 軸空欄および `[?]` がすべて充足され、`output/<hint>/interview.json` が `schemas/output.schema.json` 準拠で生成され、`scripts/validate-interview-json.py` と `scripts/check-five-axes-coverage.py` 双方が exit 0、`five_axes_complete=true` かつ抽象回答は `abstract_answers[]` に印付け + `needs_excavation=true` で記録された状態になっている。

### 目的・背景 (Why)

5 軸シートが空欄のまま後続 phase (Phase 5 深掘り / `run-intake-visualize` / `run-intake-finalize`) に進むと、深掘り対象の特定と可視化の判断材料を欠き、再ヒアリングで手戻りする。固定手順では `profile.vocabulary_tier` 差・空欄分布・抽象回答頻度に脆く、未充足軸を都度埋めるゴールシークが必要。本スキルはあくまで「シート充足の機械検証可能化」に限定し、深掘り判断は `needs_excavation` フラグで Phase 5 に委ねる。

### 完了チェックリスト (Checklist)

- [ ] `profile.json` を読み `vocabulary_tier` をセッション開始時に確定し、以降変更していない
- [ ] `sheet.md` の空欄および `[?]` を 5 軸別に走査し未回答リストを生成済み
- [ ] 5 軸優先順位 (出力先 → 情報源 → 共有相手 → 真の課題 → ナレッジ資産) で各軸を順に処理
- [ ] 各軸の質問は `references/question-bank-pointer.md` 経由で雛形を引き、`vocabulary_tier` に合わせて言い換え済み
- [ ] `AskUserQuestion` を 1 問ずつ直列で発行 (3 択 + 自由入力、並列禁止)
- [ ] 回答を `sheet.md` に Edit で反映し、`[?]` を解消済み
- [ ] `references/abstract-answer-patterns.md` 該当回答は `abstract_answers[]` に `{axis, answer, reason}` で追記し `needs_excavation=true`
- [ ] 5 軸すべて非空となり `five_axes_complete=true`、未解消があれば `unresolved[]` に列挙
- [ ] `output/<hint>/interview.json` が `schemas/output.schema.json` 準拠 (`filled_ratio` / `five_axes_complete` / `unresolved` / `needs_excavation` / `abstract_answers` 全充足)
- [ ] `python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/skills/run-intake-interview/scripts/validate-interview-json.py output/<hint>/interview.json` exit 0
- [ ] `python3 ${CLAUDE_PLUGIN_ROOT:-plugins/skill-intake}/skills/run-intake-interview/scripts/check-five-axes-coverage.py output/<hint>/sheet.md` exit 0
- [ ] 個人情報を `interview.json` 本文に直書きせず変数化済み
- [ ] 責務外 (深掘り再質問・仮説検証・要約・3 軸確定) に踏み込んでいない

### ゴールシークループ

固定手順ではなく、上記チェックリストを唯一の停止条件とする。未充足軸を `five-axes-priority.md` 順で特定 → `question-bank-pointer.md` から該当軸の質問雛形を引き `vocabulary_tier` に整形 → `AskUserQuestion` で 1 問発行 → 回答を `sheet.md` に反映 → `abstract-answer-patterns.md` で抽象判定 → checklist 自己評価、を反復する (上限は `prompts/R1-main.md` Layer 4 の反復回数)。`workflow-manifest.json` の phase 順 P1-load-sheet → P2-fill-by-axis → P3-flag-abstract → P4-emit に従い、各 phase の `fatal_exit_codes` 検出時は即停止して未充足軸を stderr に列挙する。`run-intake-kickoff` で確定済の 3 軸 (pattern/depth/pain) は前提として読み取るのみ、再確定しない。

## Gotchas

1. **深掘りに踏み込まない**: 「なぜ?」を 3 回以上重ねたら Phase 5 (`purpose-excavator`) の領域。本 phase は 1 問で次軸へ進み `needs_excavation=true` を立てるのみ。
2. **抽象語の最終確定禁止**: 「効率化」「最適化」「いい感じに」をそのまま記録しない。`abstract_answers[]` に reason 付きで残し Phase 5 に委ねる。
3. **vocabulary_tier 変更禁止**: セッション中の tier 変更は回答品質低下と語彙混乱を招く。Phase 3 で固定した値を尊重する。
4. **kickoff との重複質問禁止**: pattern / depth / pain は `run-intake-kickoff` で確定済。本 phase で再質問するとユーザーに同意ループを誘発する。
5. **AskUserQuestion 並列発行禁止**: 認知負荷が高く回答品質が落ちる。必ず 1 問ずつ直列。
6. **validate スクリプト自動修正禁止**: FAIL 時は不足項目をユーザー提示し、LLM 判断で勝手に埋めない。

## Additional Resources

- `workflow-manifest.json` — P1-load-sheet → P2-fill-by-axis → P3-flag-abstract → P4-emit phase 定義・dependsOn・entryHook/exitHook・fatal_exit_codes
- `prompts/R1-main.md` — R1-five-axes-sheet-fill 7 層プロンプト (Layer 1-7)
- `schemas/output.schema.json` — `interview.json` 正本スキーマ (`filled_ratio` / `five_axes_complete` / `unresolved` / `needs_excavation` / `abstract_answers`)
- `references/five-axes-priority.md` — 5 軸の処理順序とスキップ条件
- `references/abstract-answer-patterns.md` — `needs_excavation` を立てる判定基準
- `references/question-bank-pointer.md` — 旧 aggregator `references/question-bank.md` への参照ガイド
- `references/resource-map.yaml` — machine-readable リソース一覧
- `scripts/validate-interview-json.py` — `interview.json` の schema validate
- `scripts/check-five-axes-coverage.py` — 5 軸 coverage の機械検証
- 前後 phase: `run-intake-kickoff` (3 軸 pattern/depth/pain), `purpose-excavator` (Phase 5 深掘り), `run-intake-visualize`, `run-intake-finalize`
