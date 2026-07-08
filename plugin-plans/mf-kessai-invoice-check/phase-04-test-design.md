---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C04, C05, C06]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
skill loop の C01 (`run-mf-invoice-report`) の受入基準を test-first に導出して `feedback_contract` の inner/outer criteria として固定し、C05 (`mfk_period_report.py` 分類エンジン) のテスト観点、C06 (`notion_report_sink.py` 月次 DB 積層 sink) の「月次新規 DB 作成 + newest-on-top 配置 + 月内冪等」テスト観点、C02 (sub-agent 二段確認) の検証観点、C04 (hook 拡張) の遮断/非遮断テスト観点を実装前に設計する。実装前は criteria が未達 (Red) であることを確認する tdd-red gate。

## 背景
TDD の Red を先に立てることで、実装が「何を満たせば完了か」を purpose 由来で先に固定できる。goal-spec checklist C2〜C5 (12 ヶ月遡り/年契約/トライアル/契約終了) は分類エンジン C05 の `verify_by:test` 対象、C7 (同月内の日々追加=upsert 主キーで重複行 0) と C10 (月次 DB 積層・newest-on-top・履歴保持) は sink C06 の `verify_by:test` 対象であり、両者の単体テスト設計が本フェーズの中心になる (skill へ畳むと C7/C10 の test 対象が消える=幻テスト化を防ぐ)。

## 前提条件
- P03 の design-gate を通過している。
- C01/C05/C06 の goal/checklist が inventory に確定済み。
- `feedback_contract.criteria` の SSOT 制約 (inner/outer 各 1 件以上・id/verify_by enum) を参照できる。

## ドメイン知識
inner/outer criteria の定義 (index参照)。本 plan 固有の差分: C05 のテスト設計は「対象月決定(例: 2026-07-02 実行なら今月=2026-06分・先月=2026-05分)→前月+今月の取引先×商品集合突合→差分該当取引先のみ 12 ヶ月遡り」の 3 段階処理を固定する。状態遷移は、今月あり×前月あり=正常:継続発行、今月あり×前月なし=12ヶ月前の年契約から月額自動切替の可能性確認、今月なし×前月なし=対象外(元々請求なし)、今月なし×前月あり=年契約期間内/商品名トライアル完了/契約完了(請求ナシ(YYMM 終了)等)/該当なしなら発行漏れ候補(要対応)の全分岐をカバーする。候補取得は取引先単位、分類照合は取引先×商品単位、必要時のみ契約IDで disambiguate することも固定テストに含める。加えて (a) 契約完了は既存 mfk_reconcile.has_end_basis/_END_BASIS_PAT(確認内容の『請求ナシ』『(YYMM終了)』注記検出)→ verdict SUPPRESS_ENDED を入力に取り自由文を再パースしないこと(根拠なき終了月は REVIEW_ENDED_NO_BASIS で抑制しない安全弁の保全)、(b) 年契約正常化は既存 SUPPRESS_ANNUAL/MATCH_ANNUAL を一次源とし 12 ヶ月ルックバックは既存判定を上書きせずコメント根拠補強に限定すること(precedence)、(c) トライアル判定は canon 前の生商品名/MF 明細 desc を見ること(canon 4 値後は信号消失)、(d) 前月↔今月集合の突合キーは既存 mfk_reconcile.normalize/extract_names で表記揺れを吸収し継続契約が偽の前月あり今月なしへ誤分裂しないこと、(e) 継続発行(今月あり×前月あり)行も全 emit し非 emit は今月なし×前月なしのみであること、をテスト観点に含める。C06 のテスト設計は (1) **月次新規 DB 作成**: 対象月の DB が無ければ指定ページ『請求書発行チェック』の指定トグル見出し2ブロック配下の先頭 (newest-on-top) へ新規 DB を find-or-create すること、(2) **月次 DB 再利用**: 同一 target_month + logical_parent + title の再実行では同じ month_db_id を再利用し二重 DB を作らないこと、(3) **newest-on-top 順序**: 月が進むたびに新しい DB がトグル配下の最上部に積まれ過去月 DB がその下に残ること、(4) **月内冪等**: 同月内で同一主キー {取引先×契約ID×商品} を 2 回投入しても当月 DB へ 1 行に収束し重複行が出ないこと (日々追加・件数 created/updated/skipped の内訳)、(5) **先月の金額/今月の金額列充足**: 当月 DB の全行で先月の金額列・今月の金額列(税抜)が埋まること、(6) **列順・title 固定**: 生成後 DB のプロパティ位置順が [取引先名, 漏れチェック, 商品名, 先月の金額, 今月の金額, 先月と今月の比較, コメント] と一致し title(=ページ作成/ページ名)プロパティ=取引先名であること(build_notion_db.build_property 踏襲)、(7) **非破壊マージ**: run-1={A,B}→run-2={A,C} の順に投入後、当月 DB が {A,B,C} を保持し以前 run の行が削除されないこと(clear-then-insert と区別可能・deleted=0)、の 7 観点をカバーする。C02 は sub-agent ゆえコード単体テストでなく「真の漏れを問題ないと誤って隠していないか」の二段確認観点を設計する。C04 は既存 hook への拡張ゆえ、新規 classify/compare/period_diff の Write/Edit を exit2 で遮断しつつ既存 R1-R3/allowlist の挙動を壊していないことを両方テストする。

## 成果物
- C01 の `feedback_contract.criteria` (inner+outer 各 1 件以上) が inventory に確定した状態。
- C05 のテスト設計 (`test_mfk_period_report` が満たすべきケース一覧・据置)。
- C06 のテスト設計 (`test_notion_report_sink` の月次新規 DB 作成/月次 DB 再利用/newest-on-top 配置/月内冪等 upsert 主キー/先月の金額/今月の金額列充足のケース一覧)。
- C02/C04 の検証観点確定。実装前は全て未達 (Red)。

## スコープ外
- criteria を満たす実装 (P05)。
- harness カバレッジの実行 (P06・kind 別観点はそちらで扱う)。
- C03 (slash-command) の受入 (output_contract ベースで P07 が判定)。

## 完了チェックリスト
- [ ] C01 の criteria が purpose 由来で inner「7 列 (漏れチェック/取引先名/商品名/先月の金額/今月の金額/先月と今月の比較/コメント) が『この左→右の順で』全行で埋まる(title=取引先名・列6=テキスト説明・金額税抜)。C05 producer キー(gap_check/amount/period_diff 等)→C06 7列写像は ROW_CONTRACT SSOT で固定し、C05 実出力→C06 を実 pipe で貫通する seam 統合テストで 7列全充足を機械検証する(各 unit 緑では捕捉不能)」・outer「同月内 2 回連続実行で重複行 0・非破壊マージで以前 run の行が消えない (日々追加・C06 sink が所有)・月跨ぎで新規 DB が指定トグル配下へ append 作成され newest-on-top の意図位置が intended_index で開示される」を持つ。
- [ ] C05 のテスト設計が対象月決定(7月2日実行なら今月=6月分・先月=5月分)、取引先×商品集合の4状態(継続発行/前月なし今月あり/元々請求なし/前月あり今月なし)、差分該当取引先限定の 12 ヶ月遡り、年契約周期/年→月切替/トライアル完了/契約終了/発行漏れ候補(要対応)の全分岐をカバーし、契約完了=既存 has_end_basis→SUPPRESS_ENDED 消費(自由文非再パース)・年契約=既存 SUPPRESS_ANNUAL 一次源(遡りは補強のみ)・トライアル=canon 前の生商品名・突合キー=既存 normalize 再利用を含む。
- [ ] C06 のテスト設計が月次新規 DB 作成・同一対象月の month_db_id 再利用(二重 DB 0)・append 配置+newest-on-top intended_index 開示・月内冪等 (入力同定 {取引先×契約ID×商品}・stored key (取引先名,商品名) で 2 回投入 1 行収束。7列固定に契約ID列なし=契約ID非永続ゆえ契約ID違いは要対応優先で collapse し collapsed_multi_contract に計上=漏れ隠蔽防止)・--apply は --verified 必須(未指定 exit2)・先月の金額/今月の金額列充足・列順とtitle固定(取引先名=title・build_property 踏襲)・非破壊マージ(run-1={A,B}→run-2={A,C}で{A,B,C}保持=以前行が消えない)の観点をカバーする。
- [ ] C02 (誤って漏れを問題ないと隠していないかの二段確認) と C04 (新規 classify/compare/period_diff 遮断・既存 R1-R3 非破壊) の検証観点が確定し、実装前は criteria が未達 (Red) であることが確認できる。

## 参照情報
- `prompts/R3-emit-specs.md` §2.2 (criteria の purpose-traceability・test-first 導出)。
- 対象 component C01 (report skill) / C02 (verifier) / C04 (guard hook 拡張) / C05 (分類エンジン) / C06 (冪等 sink)。
- 後続 P05 (implementation)。
