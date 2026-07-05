---
name: run-cross-deck-review
description: 複数の deck/report をシリーズ横断で用語/意匠/構成の整合性検証したいとき、用語ゆれ・意匠差・構成不整合を網羅検出したいときに使う。
kind: run
prefix: run
version: 0.1.0
user-invocable: true
disable-model-invocation: false
argument-hint: "[series-dir?]"
arguments: [series_dir]
allowed-tools:
  - Read
  - Bash(node *)
  - Task
  - Glob
  - Grep
effect: conversation-output
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
feedback_contract: # per-skill 受入基準(purpose-acceptance)。横断分析の網羅性 verdict と突合し汎用ゲート言い換えへ退化させない
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: cross-deck-consistency で横断対象 deck/report の用語・意匠辞書を突合し分析入力の欠落が0件
      verify_by: script
    - id: OUT1
      loop_scope: outer
      text: 既知の不整合(用語ゆれ/意匠差)を注入したシリーズで cross-deck-reviewer が全件検出し網羅性を受入テストが確認する
      verify_by: test
---

# run-cross-deck-review

> **役割**: 複数の deck ／ report を**シリーズ横断**で整合検証する独立起動 skill (移植元 P5 = cross-deck-reviewer 相当)。単一成果物では見えない**シリーズ全体の整合崩れ** (用語ゆれ・意匠差・構成不整合) を、3 並列分析 × 4 条件で網羅検出する。plugin root = `$CLAUDE_PLUGIN_ROOT`、実行パスは全てここ起点 (repo-root ハードコード禁止)。個別成果物の修正は `run-slide-report-modify` の責務。

## 目的と出力契約

複数 deck ／ report のシリーズ横断で**用語／意匠／構成の整合性**を検証し、用語ゆれ・意匠差・構成不整合が**網羅的に検出された状態**を作る。

- **入力**: 複数成果物 (シリーズディレクトリ ／ deck・report 群)。
- **出力**: **横断レポート** (用語ゆれ一覧 ＋ 意匠差一覧 ＋ 構成不整合一覧 ＋ 網羅率)。
- **完了条件**: (1) 横断対象の deck ／ report を収集し `cross-deck-consistency.js` で用語・意匠辞書を突合、(2) 用語／意匠／構成の 3 並列分析を実行、(3) 不整合を網羅検出して報告 (4 条件: 矛盾なし／漏れなし／整合性／依存関係整合)。

## ワークフロー (R1 → R2 → R3・worker は Task で name 起動)

### R1: 横断対象の収集と観点確定

横断対象の deck ／ report 群と整合観点をヒアリングして確定する。シリーズディレクトリ配下の成果物を Glob で列挙し、比較の基準 (共通用語・共通意匠 SSOT・章立て構成) を明示する。

### R2: 3 並列分析

まず機械的チェックで用語・意匠辞書を突合する:

```bash
node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/cross-deck-consistency.js" <series-dir> --check all
```

FAIL／WARN 項目について `Task` で **cross-deck-reviewer** を起動 (`isolation: fork`)。**3 並列 SubAgent**で用語／意匠／構成の観点を多角分析し、**4 条件** (矛盾なし／漏れなし／整合性／依存関係整合) で判定する。用語ゆれ (メタファー・専門語の不一致)・意匠差 (配色・レイアウト・shared-spec の乖離)・構成不整合 (章立て・粒度・難易度段階の崩れ) を洗い出す。

### R3: 網羅検出結果の報告

3 並列分析の結果を統合し、不整合の網羅検出結果を横断レポート (用語ゆれ一覧 ＋ 意匠差一覧 ＋ 構成不整合一覧 ＋ 網羅率) として返す。修正が必要な項目は `run-slide-report-modify` への委譲として提示する (本 skill は検証のみ・修正しない)。

## 決定論チェック (deterministic_checks)

```bash
# シリーズ横断整合性の機械チェック (shared-spec/URL/CSS変数/GSAP/印刷)
node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/cross-deck-consistency.js" <series-dir> --check all
# 個別成果物の統一感検証 (テーマ・スタイル整合)
node "$CLAUDE_PLUGIN_ROOT/vendor/scripts/check-consistency.js" <deck-dir>
```

## ゴールシークと受入基準 (combinators)

`with-goal-seek`(max_loops 5) + `with-feedback-contract`。ループ本体は `Task` で SubAgent へ fork し、親へは横断レポートのみ返す。受入基準は当該 skill の goal／checklist 由来の受入条件 (purpose-acceptance):

- **IN1 (inner・script)**: `cross-deck-consistency` で横断対象 deck ／ report の用語・意匠辞書を突合し分析入力の欠落が 0 件。
- **OUT1 (outer・test)**: 既知の不整合 (用語ゆれ／意匠差) を注入したシリーズで `cross-deck-reviewer` が全件検出し網羅性を受入テストが確認する。

未達は最大 3 周 (inner) / 5 loops (goal-seek) で findings を反映し再実行する。網羅率が閾値未満なら分析観点を追加して再走する。

## 境界

- 入力 = 複数成果物／出力 = 横断整合レポート (read-only 分析・成果物を書き換えない)。
- **個別成果物の修正は `run-slide-report-modify` へ委譲**する (本 skill は検証・検出のみ)。
- 新規生成は `run-slide-report-generate` の責務。

## 注意 (Gotchas)

- **配置非依存**: 全実行パスは `$CLAUDE_PLUGIN_ROOT/vendor/scripts/…` 起点。repo-root 直書き禁止。
- **read-only 分析**: 成果物を書き換えない (`allowed-tools` に Write/Edit を持たない)。検出のみで、修正は委譲。
- **3 並列 × 4 条件を省略しない**: 用語／意匠／構成の 3 観点を並列分析し、4 条件 (矛盾なし／漏れなし／整合性／依存関係整合) で判定する。単一観点に縮退させない。
- **網羅性が受入基準**: 既知不整合の全件検出 (OUT1) が purpose。一部検出で PASS 扱いにしない。
- **agent は name 参照**: `cross-deck-reviewer` はファイルパス依存でなく Task の name 起動。

## 配置先

| 用途 | 出力先 |
|---|---|
| 本 skill 資産 | `plugins/slide-report-generator/skills/run-cross-deck-review/` |
| 横断レポート | 呼び出し時に指定 (既定は series-dir 直下の分析レポート) |

## 追加リソース

- `vendor/scripts/cross-deck-consistency.js` — シリーズ横断整合性の機械チェック。
- `vendor/scripts/check-consistency.js` — 個別成果物の統一感検証。
