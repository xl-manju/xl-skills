---
name: run-slide-report-modify
description: 既存のスライドデッキ/レポートを output_mode を保ったまま指定箇所だけ部分修正したいとき、意匠/技術コアと非対象箇所を壊さず修正後の再評価で視覚崩れ0にしたいときに使う。
kind: run
prefix: run
version: 0.1.0
user-invocable: true
disable-model-invocation: false
argument-hint: "[target-dir?] [--mode slide|report]"
arguments: [target_dir, mode]
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash(node *)
  - Bash(python3 *)
  - Task
  - Glob
  - Grep
effect: local-artifact
owner: xl-skills maintainers
since: 2026-07-05
last-audited: 2026-07-05
output_language: ja
prompt_layer: 7layer
combinators:
  - with-goal-seek
  - with-feedback-contract
goal_seek:
  engine: inline
  fork: subagent
  max_loops: 5
feedback_contract: # per-skill 受入基準(purpose-acceptance)。修正後の生成後評価 verdict と突合し汎用ゲート言い換えへ退化させない
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: validate-output-mode で既存成果物の output_mode を判定し修正対象の mode と reportType の値域整合を送信前検証し欠落が0件
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 指定箇所のみが修正され意匠/技術コアと非対象箇所が不変で、修正後の生成後評価が視覚崩れ0で PASS することを受入テストが確認する
      verify_by: test
---

# run-slide-report-modify

> **役割**: 既存の slide deck ／ report の**局所修正**を独立起動で行う skill (移植元 P4 = slide-modifier 相当)。生成し直さず、`output_mode` を保ったまま**指定箇所だけ**を部分修正し、意匠／技術コアと非対象箇所を壊さない。plugin root = `$CLAUDE_PLUGIN_ROOT`、実行パスは全てここ起点 (repo-root ハードコード禁止)。新規生成は `run-slide-report-generate`、シリーズ横断検証は `run-cross-deck-review` の責務。

## 目的と出力契約

既存の slide deck ／ report を `output_mode` を保ったまま指定箇所だけ部分修正し、**意匠／技術コアと非対象箇所を壊さず**、修正後の生成後評価で**視覚崩れ 0** の状態を作る。

- **入力**: 既存成果物 (slide deck ディレクトリ ／ report HTML) と修正指示。任意 `--mode slide|report` (省略時は成果物から自動判定)。
- **出力**: **修正レポート** (修正箇所一覧 ＋ 変更差分 ＋ 再評価スコア)。
- **完了条件**: (1) 修正対象と `output_mode` を特定し `validate-output-mode.py` で値域整合を検証、(2) 指定箇所のみを部分修正 (非対象・意匠コア不変)、(3) 修正後の生成後評価が視覚崩れ 0 で PASS。

## mode 判定 (slide / report)

独立起動のため、まず修正対象成果物の `output_mode` を判定する。

- `index.html` (＋ `styles.css` / `scripts.js` / `structure.*`) を持つ → **slide** (deck 成果物)。
- `report.html` (＋ `report-structure.*`) を持つ → **report**。
- 曖昧な場合は `--mode` 引数を優先し、`validate-output-mode.py` で値域整合を検証する (IN1)。判定した mode を修正 worker へ伝播する。

## ワークフロー (R1 → R2 → R3・worker は Task で name 起動)

### R1: 修正対象と指示の確定

修正対象の既存成果物 (パス)・`output_mode`・修正指示をヒアリングして確定する。既存成果物を Read し、修正が及ぶ範囲 (対象要素) と**触れてはならない意匠／技術コア・非対象箇所**を明示する。

### R2: 局所修正

`Task` で **slide-report-modifier** を起動 (`isolation: fork`)。判定した mode (slide ／ report) に応じ、**指定箇所のみ**を部分修正する。

- 意匠 SSOT (Kanagawa 配色・16:9・最小 1.4rem・印刷 CSS・letterbox 等) と非対象セクションは**不変**に保つ。
- slide deck は `index.html`／`styles.css`／`scripts.js` と `structure.*` の同期を維持する。report は `report.html` と `report-structure.*` の整合を維持する。
- 全書き換え禁止 (Edit 差分のみ)。修正箇所と変更差分を記録する。

### R3: 再評価

`Task` で **slide-report-modifier** の修正後、生成後評価を再実行し**視覚崩れ 0** を確認する (下記 deterministic_checks)。未達なら R2 へ差し戻し、修正レポート (修正箇所一覧 ＋ 変更差分 ＋ 再評価スコア) を返す。

## 決定論チェック (deterministic_checks)

```bash
# 既存成果物の output_mode 判定と値域整合 (送信前・fail-closed)
python3 "$CLAUDE_PLUGIN_ROOT/scripts/validate-output-mode.py" --mode <slide|report> [--report-type <enum>]
# 修正後の UI 品質検証 (テキスト切れ・改行・16:9 比率・非対象箇所の崩れ検出)
node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/verify-slides.js" ./index.html --check-ratio
```

修正が意匠コア・印刷レイアウトに及ぶ場合は `evaluate-deck.js`／`validate-print.js` も併用して視覚崩れ 0 を確認する。

## ゴールシークと受入基準 (combinators)

`with-goal-seek`(max_loops 5) + `with-feedback-contract`。ループ本体は `Task` で SubAgent へ fork し、親へは修正レポートのみ返す。受入基準は当該 skill の goal／checklist 由来の受入条件 (purpose-acceptance):

- **IN1 (inner・script)**: `validate-output-mode` で既存成果物の `output_mode` を判定し修正対象の mode と `reportType` の値域整合を送信前検証し欠落が 0 件。
- **OUT1 (outer・test)**: 指定箇所のみが修正され意匠／技術コアと非対象箇所が不変で、修正後の生成後評価が視覚崩れ 0 で PASS することを受入テストが確認する。

未達は最大 3 周 (inner) / 5 loops (goal-seek) で findings を反映し再実行する。

## 境界

- 入力 = 既存成果物と修正指示／出力 = 局所修正済み HTML。
- **新規生成は `run-slide-report-generate` へ委譲**する (本 skill は既存成果物の局所修正のみ・ゼロから作らない)。
- **シリーズ横断の整合検証は `run-cross-deck-review` へ委譲**する。

## 注意 (Gotchas)

- **配置非依存**: 全実行パスは `$CLAUDE_PLUGIN_ROOT` 起点 (`vendor/scripts/…` ／ `scripts/…`)。repo-root 直書き禁止。
- **局所性を守る**: 指定箇所以外・意匠 SSOT・印刷 CSS には触れない。全書き換えでなく Edit 差分。
- **mode を保つ**: slide を report へ (逆も) 変換しない。`output_mode` は入力成果物のものを維持する。
- **同期維持**: slide deck は `index.html`⇔`structure.*`、report は `report.html`⇔`report-structure.*` の整合を崩さない。
- **完成判定は実体で**: 修正後は Read／署名／スクショ目視で確認し、"PASS" 文字列で完成判断しない。
- **agent は name 参照**: `slide-report-modifier` はファイルパス依存でなく Task の name 起動。

## 配置先

| 用途 | 出力先 |
|---|---|
| 本 skill 資産 | `plugins/slide-report-generator/skills/run-slide-report-modify/` |
| 修正対象・出力 | 既存成果物ディレクトリ (in-place 局所修正) |

## 追加リソース

- `scripts/validate-output-mode.py` — output_mode 判定・値域検証 (plugin-root glue)。
- `vendor/scripts/verify-slides.js` / `evaluate-deck.js` / `validate-print.js` — 修正後の視覚崩れ検証。
