---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
C01 (`run-mf-invoice-report` skill) の二値の受入基準 (AC) を build 後の受け入れとして判定する。purpose「前月↔今月の発行状況を比較して真の発行漏れだけを残した冪等レポートを生成する」が組み上がったプラグインで実際に満たされているかを確認する見方を固定する。

## 背景
品質ゲート (lint/coverage) を通ることと、purpose を実際に満たすことは別の保証である。本フェーズは goal-spec checklist C1〜C11 (index「受入確認」章対応表) を purpose 由来の受入観点で二値判定する成果物評価であり、実行 (criteria-test の実走) は build フェーズが担う。

## 前提条件
- P06 で harness テストが緑。
- C01 の output_contract と `feedback_contract.criteria` が確定している。
- purpose「前月↔今月比較レポートの冪等生成」を受入観点の正本 (`goal-spec.purpose`) として参照できる。

## ドメイン知識
AC (受入基準) と品質ゲートの区別 (index参照)。本 plan 固有の差分: 冪等の観測は 2 軸で行う。(1) 月内冪等 (C7): 同一対象月で 2 営業日目・3 営業日目相当のデータを連続投入し、当月 DB が入力同定 {取引先×契約ID×商品}・stored key (取引先名,商品名) で重複行 0 に収束し日々追加されることを観測する(7列固定に契約ID列なし=契約ID非永続ゆえ契約ID違いは要対応優先で collapse し collapsed_multi_contract に計上=漏れ隠蔽防止)。(2) 月次 DB 積層 (C10): 月が進むと新しい月の DB が指定ページ『請求書発行チェック』のトグル見出し2ブロック配下へ append 作成され (newest-on-top の意図位置は intended_index で開示=Notion API は任意位置 insert 不可)、過去月の DB が記録として保持されることを観測する。両方とも実体は C06 sink が所有する。加えて (3) 非破壊マージ (C11): 以前 run で書いた行が今回入力に無くても当月 DB から削除されず全情報が保持されること (clear-then-insert でないこと) を観測する。

## 成果物
- C01 の AC 判定結果 (PASS/FAIL の二値、C1〜C11 対応)。

## スコープ外
- 不合格時の修正実装 (P05 へ差し戻し)。
- 機械品質ゲートの実行 (P09)・全域最終審査 (P10)。
- 受入観点の新規発明 (正本は `goal-spec.purpose`・ここでは判定のみ)。

## 完了チェックリスト
- [ ] C1: レポートが漏れチェック/取引先名/商品名/先月の金額/今月の金額/先月と今月の比較/コメントの 7 列を『この左→右の順で』全行で持ち、title(=ページ作成/ページ名)プロパティ=取引先名・列6=テキスト説明・金額は税抜と判定できる (先月・今月の金額が並置され比較可能)。
- [ ] C2〜C5: 7月2日実行時に今月=6月分・先月=5月分として扱い、取引先×商品集合の4状態(継続発行/前月なし今月あり/元々請求なし/前月あり今月なし)と年契約周期(既存 SUPPRESS_ANNUAL 一次源)/年→月自動切替/トライアル完了(canon 前の生商品名)/契約終了(既存 has_end_basis→SUPPRESS_ENDED)の各イレギュラーが根拠コメント付きで正しく分類されると判定できる。
- [ ] C6〜C8: 分類不能な差分のみが真の発行漏れとして漏れチェックに残り、C02 (sub-agent) が誤隠蔽を検出し、C7 (同月内の日々追加=入力同定 {取引先×契約ID×商品}・stored key (取引先名,商品名) で重複行 0・契約ID非永続ゆえ契約ID違いは要対応優先 collapse で漏れを隠さない・C06 sink 所有) が満たされると判定できる。
- [ ] C9: MF API 参照専用維持と新規 classify/compare 再実装遮断が判定できる。
- [ ] C10: 月次で新しい DB がトグル見出し2ブロック配下へ append 作成され newest-on-top の意図位置が intended_index で開示され、過去月の DB が記録として保持されると判定できる (Notion API は任意位置 insert 不可・C06 sink 所有)。
- [ ] C11: 当月 DB への上書きが非破壊マージで、以前 run で書いた行が今回入力に無くても削除されず全情報が保持されると判定できる (run-1={A,B}→run-2={A,C}→{A,B,C}・clear-then-insert でない・C06 sink 所有)。

## 参照情報
- `goal-spec.purpose` / index「受入確認 (build 後の見方)」章。
- 対象 component C01。後続 P08 (refactoring)。
