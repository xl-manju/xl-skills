---
id: P07
phase_number: 7
phase_name: acceptance-criteria
category: 判定
prev_phase: 6
next_phase: 8
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13]
applicability:
  applicable: true
  reason: ""
---

# P07 — acceptance-criteria (受入基準判定)

## 目的
各 component の二値の受入基準 (AC) を build 後の受け入れとして判定する。purpose「システム構築に必要な仕様情報をヒアリングで漏れなく収集し1つの仕様書へまとめる」が組み上がったプラグインで実際に満たされているかを確認する見方を固定する。

## 背景
品質ゲート (lint/coverage) を通ることと、purpose を実際に満たすことは別の保証である。本フェーズは「組み上がったプラグインが仕様収集の網羅性という purpose を満たすか」を purpose 由来の受入観点で二値判定する成果物評価であり、index の「受入確認」章と対応する。

## 前提条件
- P06 で harness テストが緑。
- 各 component の output_contract と skill loop の criteria が確定している。
- purpose「システム構築仕様をヒアリングで漏れなく収集し仕様書へまとめる」を受入観点の正本 (`goal-spec.purpose`) として参照できる。

## ドメイン知識
- AC (受入基準) と品質ゲートの区別: lint/coverage は「壊れていない」保証、AC は「purpose を満たす」保証 (両方必要・相互代替不可)。
- 網羅性の観測方法: カテゴリ×プラットフォームのマトリクスに未収集セルが残っていないことを observe する (C01/C12 の outer criterion)。
- fail-closed: 判定不能・異常時に安全側 (拒否/上書き阻止) へ倒す性質 (C11 hook の受入観点)。

## 成果物
- 全 component の AC 判定結果 (PASS/FAIL の二値)。

## スコープ外
- 不合格時の修正実装 (P05 へ差し戻し)。
- 機械品質ゲートの実行 (P09)・全域最終審査 (P10)。
- 受入観点の新規発明 (正本は `goal-spec.purpose`・ここでは判定のみ)。

## 完了チェックリスト
- [ ] C01: 往復ヒアリング後にカテゴリ×プラットフォームマトリクスの全セルが確定/対象外理由付きで埋まっていると判定できる。
- [ ] C02: 対象ツール/インフラ/フレームワークの最新公式ドキュメントに取得日時と参照元が記録されていると判定できる。
- [ ] C03/C05: 生成された仕様書ドキュメントセットが章立て複数 Markdown+index の形式でマトリクス確定状態・設計知識反映・出典を含み、独立評価が合格と判定できる。
- [ ] C11: 確定済み章の上書きが hook で fail-closed に阻まれると判定できる。
- [ ] C11: 非対象パス (仕様章以外) への Write|Edit は exit0 で即通過し誤爆しない。
- [ ] C05 評価は /spec-compile (C10) 完了後に自動連鎖して起動する。
- [ ] 残り component の output_contract が満たされ受入テストが二値で PASS している。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: サンプルヒアリング応答セット (C01 所有 fixture) 投入後、マトリクスの未収集セル 0 + 対象外理由付与を validate-coverage-matrix.py の exit0 で判定できる。
- 満たさない例: lint/coverage が緑であることを根拠に AC を PASS 扱いする (品質ゲートと受入の混同) / 判定にスコアの中間値を許し二値にならない。

### 事前解決済み判断
- 分岐点: AC FAIL 時の戻し先 → 判断: P05 へ差し戻す (受入観点の再定義はしない・正本は goal-spec.purpose)。

## 参照情報
- `goal-spec.purpose` / index「受入確認 (build 後の見方)」章。
- 対象 component C01-C13。
- 後続 P08 (refactoring)。
