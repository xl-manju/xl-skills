---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装)

## 目的
全 buildable component を後段 builder へ委譲して実体化し、P04 で設計した criteria を満たす (Green) 状態にする。build routing は `component-inventory.json` の依存 top-sort 順に実行する (phase 順 ≠ build 順)。

## 背景
build は phase 順ではなく component の依存 top-sort 順に走る。phase 軸 (人間可読) と build 軸 (機械 routing) を分離しているため、実装は inventory の DAG を正本にする。C01はC04 taxonomy、C02はC01 spec-state、C05はC06-C08監査Agent、C10はC05自動評価に依存する。手続き的な build 順は `handoff-run-plugin-dev-plan.json` の routes が SSOT であり、本フェーズはその実行結果 (到達状態) を宣言する。

## 前提条件
- P04 で C01/C02/C03 の criteria が Red で確定している。
- `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で用意されている (C12/C13/C04 → C01 → C11/C02/C06/C07/C09 → C03/C08 → C05 → C10 を満たす top-sort。独立nodeは同wave並列可)。
- P05 preflight で GAP-ENVELOPE-001 / GAP-PLUGIN-SURFACE-BUILDER / GAP-GOVERNANCE-SURFACE-BUILDER の blocking owner・実行手段が解決し、GAP-SCRIPT-BUILDER の `build-script-route.py` 実在が確認済み。
- 後段 builder (run-skill-create / run-build-skill / plugin-scaffold) が利用可能。

## ドメイン知識
- build 順の不変条件: inventory DAG の top-sort 順 (依存先が常に先。phase 番号順ではない)。
- builder 4 種の実行実体差: `builder_status` が executor-backed (実行 skill 実在) / contract-only (routing 語彙のみ・`gap_ref` 必須) を区別する (解決表は io-contract §9)。
- Green 判定の主体は P04 で固定した criteria (実装が判定基準を都合よく再定義しない)。
- C11 の scoping 不変条件: hookのfail-closed範囲は確定章へのWrite/Editとprotected path/spec-stateを参照するBash (曖昧な動的書換を含む)。明らかな非対象操作は即 exit0 通過する。全書換経路はC01/C03の単一writer/transition gateが正本防御を担う。
- C01のR0 bootstrapはmatrix population前にfoundation containerを作り、R1再初期化でfoundationを消さない。R5はdecision lifecycleの単一writerを使い、AI推奨とユーザー確定を別stateにする。
- C04 referenceはseed examplesとしてdeep knowledge contractを満たし、未知領域はproject candidateで発見可能にする。全promptはprompt-creator C1-C4/L5 gateを通す。

## 成果物
- 全 13 component の実体 (skills/agents/commands/hooks/scripts) が build_target に生成された状態。
- `envelope-draft/plugin.json` を基にした plugin manifest (後段 scaffold owner)。
- required plugin-level surfaces (`plugin-composition.yaml` / `EVALS.json` / C04 references) と plugin_meta required surface (`RUNBOOK.md` / governance-check CI wiring) が handoff envelope の owner/build_targetどおり生成された状態。

## スコープ外
- カバレッジ拡充・テスト網羅 (P06)。
- purpose 受入判定 (P07)・SSOT 重複整理 (P08)。
- builder 自体の改修 (harness-creator 側の責務・gap は `open_issues` へ起票)。

## 完了チェックリスト
- [ ] 依存 top-sort 順に全 component が build され、3 run skill (C01/C02/C03) の criteria が Green (受入テスト PASS) になる。
- [ ] build 実体パスが inventory の build_target と一致する。
- [ ] 共有 script C12/C13 が plugin-root へ実体化されている (単一 skill 配下に退化していない)。
- [ ] required surface の owner/build_target が解決され、`plugin-composition.yaml` / `EVALS.json` / C04 references / `RUNBOOK.md` / governance-check CI wiring が存在する。
- [ ] U1-U9確定、decision guidance、deep/open-world knowledge、prompt-creator gateの実体・tests・現SHA証跡が揃う。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: build が C12/C13/C04 → C01 → C11/C02/C06/C07/C09 → C03/C08 → C05 → C10 を満たす top-sortで実行され、C05をbuildする時点でfork対象C06-C08が全て実体化されている。
- 満たさない例: phase 番号順・id 昇順に build され、C01 が参照する validate-coverage-matrix.py が未実体のまま criteria 検証が走る / C11 が確定章以外のパスもブロックする (scoping 不変条件違反)。

### 事前解決済み判断
- 分岐点: script route (C12/C13) の builder に実行 skill が無い → 判断: contract-only builder として `gap_ref: GAP-SCRIPT-BUILDER` を明示し、harness-creator の build-script-route.py が消費する (本 plan では builder を発明しない)。
- 分岐点: C11 hook の書込許可条件 → 判断: Write/Edit/Bashの補助防御とし、protected path/spec-state参照または曖昧な動的Bash書換を安全側で拒否する。全経路の正本はC01/C03の単一writer/transition gate。再オープン状態の場合のみ許可する。

## 参照情報
- `handoff-run-plugin-dev-plan.json` (build routing) / `component-inventory.json` (依存 DAG)。
- 対象 component C01-C13。
- 後続 P06 (test-run)。
