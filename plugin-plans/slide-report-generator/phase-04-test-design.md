---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02, C03]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計)

## 目的
skill loop 系 component(C01 generate / C02 modify / C03 cross-deck-review)の受入基準を test-first に導出し、`feedback_contract` の inner/outer criteria として固定する。実装前は criteria が未達(Red)であることを確認する tdd-red gate。

## 背景
TDD の Red を先に立てることで、実装が「何を満たせば完了か」を purpose 由来で先に固定できる。汎用ゲートの言い換え(lint exit0 / 4 条件 PASS)に退化した criteria は purpose を一度も受入検証しないため、各 skill の goal/checklist 語彙由来であることを設計時に担保する(`criteria_purpose_traceability` が機械検出する退化を未然に防ぐ)。とりわけ output_mode 分岐の受入(slide=1メッセージ/report=読み物)を criteria に焼く。

## 前提条件
- P03 の design-gate を通過している。
- skill loop 系 component C01/C02/C03 の goal/checklist が inventory に確定済み。
- `feedback_contract.criteria` の SSOT 制約(inner/outer 各 1 件以上・id/verify_by enum)を参照できる。

## ドメイン知識
- inner/outer criteria: inner=生成時の自己検証観点(validate-output-mode / cross-deck-consistency 等)、outer=build 後の受入観点(mode 別成果物品質)。各 1 件以上が契約。
- Red = 実装前に criteria が未達であること(実装後に緑になることで criteria が実効だったと証明される)。
- purpose-traceability = criteria が各 skill の goal/checklist の語彙(output_mode / 視覚崩れ / 横断整合 等)を参照していること(汎用ゲート言い換え退化を `check-spec-frontmatter.py` が機械検出)。

## 成果物
- C01/C02/C03 の `feedback_contract.criteria`(inner+outer 各 1 件以上)が inventory に確定した状態。
- report 構造化 (C9-C14) の受入テストが Red で設計された状態 (下記)。

### report 構造化のテスト設計 (C10/C11/C12/C13・Red)

改善が「羅列でも破綻ゼロなら PASS」を塞げるよう、実装前に Red の受入観点を固定する。機械層 (C25) と意味層 (C24) を二層で設計する:

- **C25 validate-report-visual.py (機械・決定論)**: (i) markdown 表を含む fixture が `<table>` へ変換され `<br>` で潰れていない、(ii) フェンスドコードブロックが `<pre><code>` へ、番号リストが `<ol>` へ変換される、(iii) `section.narrative`(essence/approach/leverage) が非空、(iv) highlight/key-point 表現が render 出力に現れる、(v) placement.grid 指定時に図が段落末尾全幅でなく該当ゾーンへ配置される —— を検証する回帰を tests/test_validate_report_visual.py に Red で追加する。
- **C24 report-quality-reviewer (意味・RQ21-)**: 節内論理展開 (本質課題→解決→活用) の成立/block 構造多様性/要点強調の効き/図解の意味的配置/見出しごとの整形 を積極評価する rubric 次元を、羅列サンプル (現状出力相当) で FAIL・構造化サンプルで PASS になるよう設計する。
- **render-report.js (C19 tests_min≥80)**: 各 block レンダラの単体テスト (表/コード/番号リスト/小見出し/key-point/stat-tile/highlight/placement) を Red で用意する。

## スコープ外
- criteria を満たす実装(P05)。
- harness カバレッジの設計・実行(P06・kind 別観点はそちらで扱う)。
- 非 skill component(sub-agent/hook/command/script)の受入(output_contract ベースで P07 が判定)。

## 完了チェックリスト
- [ ] 3 skill の criteria が purpose 由来で inner/outer を各 1 件以上持つ(汎用ゲート言い換えに退化していない)。
- [ ] C01 は「slide=1メッセージ/report=1項目1ビジュアルで視覚崩れ0の生成後評価 PASS」、C02 は「指定箇所のみ修正で非対象不変・再評価崩れ0」、C03 は「既知の不整合を全件検出」を outer criterion に持つ。
- [ ] 実装前は criteria が未達(Red)であることが確認できる。
- [ ] report 構造化の受入テスト (C25 機械チェック / C24 積極評価 RQ21- / render-report.js block 単体) が Red で設計され、羅列サンプルで FAIL・構造化サンプルで PASS になる観点が固定されている。

## 参照情報
- `prompts/R3-emit-specs.md` §2.2(criteria の purpose-traceability・test-first 導出)。
- report 構造化テストの要件正本 = P01「改善要件」節、設計正本 = P02「report 構造化設計」節。
- 対象 component C01(生成)/ C02(修正)/ C03(横断レビュー) + report 構造化は C19/C24/C25。
- 後続 P05(implementation)。
