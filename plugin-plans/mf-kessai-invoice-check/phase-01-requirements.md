---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06]
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
「マネーフォワード掛け払いの前月↔今月発行状況比較レポート」改善構想を、6 component (C01 skill `run-mf-invoice-report` / C02 sub-agent `mfk-report-verifier` / C03 slash-command `run-mf-invoice-report` / C04 hook `guard-mfk-no-reinvent` (既存 in-place 拡張) / C05 script `mfk_period_report.py` (薄い差分エンジン) / C06 script `notion_report_sink.py` (月次レポート DB 冪等 sink)) の観点から目的ドリブンに要件化し、後続フェーズが参照する `goal-spec.json` (checklist C1〜C11) を確定させる。

## 背景
既存 `run-mf-invoice-reconcile` は当月双方向照合のみを担い、前月↔今月の時間軸比較・12 ヶ月遡りによるイレギュラー分類・月次レポート DB への冪等再実行という新次元を持たない。本改善はこの新次元を「対称に 5 種を 1 つずつ埋める」のでなく「改善デルタが要する機能クラスタ (収集/分類/検証/冪等 sink/再発明遮断)」を先に列挙し新規 or 既存改修でラベリングしてから 6 実体へ分解する (Goodhart 回避)。同一構想は常に同一 `plan_dir=plugin-plans/mf-kessai-invoice-check/` へ解決され (再現性アンカー)、以降のフェーズはこの goal-spec を唯一の起点にする。

## 前提条件
- プラグイン構想 (前月↔今月比較レポート・4 イレギュラー分類・冪等再実行・月次レポート DB) が入力として与えられている。
- 既存プラグイン資産 (`lib/mfk_reconcile.py` 照合エンジン・`lib/mfk_api.py` 参照専用 GET・`lib/notion_reconcile_sink.py` 非破壊 upsert パターン・請求確認シート) が利用可能で再利用対象と確認されている。
- 6 component の kind 割当 (skill×1/sub-agent×1/slash-command×1/hook×1(既存拡張)/script×2) が判明している。

## ドメイン知識
plan 全体の用語 (2 軸直交/component_kind 5 種/月帰属/イレギュラー4分類/冪等上書き) は index `## ドメイン知識` を参照。本フェーズ固有の差分: 要件定義段階では checklist C1〜C11 それぞれがどの component に帰着するかの初期対応 (RTM) を index「受入確認」章の対応表として仮固定する。出力設計は **単一恒久 report DB の既存確認 + 冪等上書き (Design D)** であり、C06 sink が指定ブロック/見出し周辺の既存 DB を `in-block` → `under-heading` → `page` の順で探し、存在すれば更新、無ければ指定ページ『請求書発行チェック』(report_parent_page) 直下へ新規 report DB を作成する。Notion API は database 作成の親に block_id を指定できないため新規作成はページ直下だが、UI でトグル内または見出し直下に置かれた既存 DB の更新は可能とする。レポート列は取引先名/対象月/漏れチェック/商品名/先月の金額/今月の金額/先月と今月の比較/コメントの 8 列とし、先月の金額と今月の金額を並置して比較可能にする (C1 更新)。特に C7 (同月内の日々追加=行キー {対象月×取引先×商品} で重複行 0) と C10 (既存 DB 優先更新・未存在時のみ新規作成) は C06 sink が所有する要件であることをここで明示する。

## 成果物
- `goal-spec.json` (purpose/background/goal/checklist C1〜C11/constraints/handoff_targets) の確定。
- target_plugin_slug=`mf-kessai-invoice-check` と plan_dir の確定値。
- C1〜C11 各要件のどの component が担うかの初期対応表 (index 受入確認章と対応・C7/C10→C06)。

## スコープ外
- component 分解の確定・build_target/依存 DAG の設計 (P02 へ委譲)。
- ヒアリング機構の再実装 (`run-goal-elicit` を引用するのみ・再発明しない)。
- 実装・build (P05 と後段 builder の責務)。

## 完了チェックリスト
- [ ] `goal-spec.json` の checklist C1〜C11 (C10=既存 report DB 優先更新・未存在時のみ新規作成) が全て非空で purpose「前月↔今月比較レポートの冪等生成」から導出されている。
- [ ] target_plugin_slug が ASCII kebab (`mf-kessai-invoice-check`) で確定し以降のフェーズがそれを参照できる。
- [ ] `check-plugin-goal-spec.py` が exit0 (R1 goal-spec + plugin 固有アンカー充足)。

## 参照情報
- `references/purpose-driven-requirements.md` (目的ドリブン要件化の正本)。
- `schemas/plugin-goal-spec.schema.json` / `scripts/check-plugin-goal-spec.py`。
- 対象 component C01〜C06 (`component-inventory.json`)。後続 P02 (この goal-spec を component 分解の入力とする)。
