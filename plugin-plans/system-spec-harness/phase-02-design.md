---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06, C07, C08, C09, C10, C11, C12, C13]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
capability を 5 種の component_kind (skill/sub-agent/slash-command/hook/script) へ写像し、N=13 実体を `component-inventory.json` へ分解する。各 component の build_target・依存 DAG・品質機構を確定し、plugin envelope (`.claude-plugin/plugin.json`) の draft を設計する owner フェーズ。あわせて 4 件の設計判断 (ヒアリング機構の独立実装/出力形式/最新ドキュメント取得手段/command 採否) を根拠付きで確定する。

## 背景
P01 で確定した goal-spec を、実際に build 可能な実体へ落とす最初の設計フェーズ。skill 偏重を避けるため 5 種の component_kind を必ず検討した上で N=13 実体へ分解し、ライフサイクル軸 (13 phase) と成果物実体軸 (inventory) を二重に持たない正規化を敷く。build_target/depends_on は inventory のみが保持し、phase は id 参照だけで紐づく。

## 前提条件
- P01 の `goal-spec.json` が確定している。
- 5 種の component_kind の写像規約 (`references/component-domain.md`) と envelope 物理契約 (`references/plugin-creator-contract.md`) を参照できる。
- 既存の skill-intake plugin (ヒアリング機構を持つ既存資産) の設計を参照可能な状態にある。

## ドメイン知識
- 正規化原則: build_target/depends_on は `component-inventory.json` のみが保持し、phase ファイルは `entities_covered` の id 参照だけで紐づく (二重保持は drift 源)。
- kind 写像の判定核: `needs_independent_context`→sub-agent、`needs_lifecycle_enforcement`→hook、決定論検査→script (5 種の定義は index `## ドメイン知識` 参照)。
- `placement_scope`: script のみ持つ配置属性。C12 (validate-coverage-matrix.py) は C01/C03 の 2 skill から共有され、C13 (validate-source-citation.py) は C02/C03 の 2 skill から共有されるため、いずれも plugin-root へ hoist する (単一 skill 配下への固定は install 携帯性を損なう)。
- 意味依存のDAG規則: taxonomy consumer C01→C04、spec-state consumer C02→C01、fork owner C05→C06/C07/C08、自動評価command C10→C05を `depends_on` に明示し、部分buildの依存閉包だけで参照先が揃うようにする。
- required plugin-level surface は component route外でも owner/build_target/status を handoff envelope に持つ。`plugin-composition.yaml`=run-build-skill、`EVALS.json`=plugin-scaffold、references=config/assets=C04 owner。
- **設計判断1 (skill-intake との関係)**: system-spec-harness は skill-intake plugin のヒアリング機構を再利用せず**独立実装**とする。両者はドメイン (システム開発仕様網羅 vs. 汎用インテーク) が異なり、往復ヒアリング+段階ゲート/承認という**設計流儀のみ**を着想として借用する。コード・skill の直接依存や symlink 共有は行わない (cross-plugin 依存を持ち込むと携帯性/独立配布性が損なわれるため)。
- **設計判断2 (出力形式)**: 最終成果物は**章立ての複数 Markdown ファイル + index** (`system-spec/` 配下) を既定形式とする。単一 Markdown への集約はカテゴリ×プラットフォームの広さに対し可読性/差分レビュー性で劣るため採らない。C03 (compile skill) の `output_contract` がこの形式を確定する。
- **設計判断3 (最新ドキュメント取得手段)**: 取得手段は **WebSearch/WebFetch** を既定とする。C02はtarget_id、公式publisher/host、versionまたはlast_updated、retrieved_at/latest_checked_atを記録し、C13が形式/host/全件差分、C08が公式サイト上の現行版との意味照合を担う。MCP連携や特定API統合は将来拡張として `open_issues` (GAP-MCP-DOCFETCH) へ保留する。
- **設計判断4 (command 採否)**: command は主動線 2 本 (spec-hearing-start=C09 / spec-compile=C10) のみ。doc-fetch (C02) と completeness evaluator (C05) は skill trigger 連鎖 (C02=C10 実行前の未取得参照検出または C01 R2/R5 中の裏取り要求、C05=C10 コンパイル完了後の自動連鎖) で起動し独立 command を持たない (入口の重複を避け起動経路を契約化する)。
- **設計判断5 (意思決定支援)**: 新しい入口componentは増やさず、C01 R5が`needs_guidance`を所有し、C02の最新公式証拠とC04のdeep knowledge seedを入力に比較・推奨する。推奨は`recommended_pending_confirmation`、ユーザー選択だけが`confirmed`へ遷移する。
- **設計判断6 (知識境界)**: C04はread-only curated seed/contractを所有する。未知知識の発見はC01/C02がproject candidateとして行い、一次資料・深度・鮮度・重複統合を満たすものだけをcurated promotion候補にする。
- **設計判断7 (prompt品質)**: prompt-creatorの`verify-completeness.py`/`validate-prompt.py`と独立C1-C4 evaluatorを全responsibility promptへ適用し、route successの証跡にする。

## 成果物
- `component-inventory.json` (build 軸の唯一 SSOT・全 13 component)。
- `envelope-draft/plugin.json` (manifest draft)。
- 上記 4 件の設計判断とその根拠 (本セクションが記録の正本)。

## スコープ外
- 設計の合否判定 (P03 design-gate へ委譲・自己承認しない)。
- 受入 criteria の導出 (P04 へ委譲)。
- 実体の生成 (P05・実 `plugins/` へは書かない)。

## 完了チェックリスト
- [ ] 全 13 component が build_target 非空・builder/build_kind 整合・depends_on 非循環で inventory に載っている。
- [ ] considered_component_kinds が 5 種全列挙され、plugin_level_surfaces の採否が明示されている。
- [ ] `envelope-draft/plugin.json` に manifest draft (entry_points / hooks 配線 / distribution) が設計されている。
- [ ] C01→C04、C02→C01、C05→C06/C07/C08、C10→C05の意味依存とrequired plugin-level surfaceのowner/build_target/statusがinventory/handoffに反映されている。
- [ ] skill-intake 非再利用/出力形式(章立て複数 Markdown+index)/最新ドキュメント取得手段(WebSearch/WebFetch)/command 採否(主動線 2 本のみ)の 4 設計判断が根拠付きで記録されている。
- [ ] 意思決定支援/C04 open-world境界/prompt-creator品質の設計判断が、既存C01/C02/C04責務と循環しない形で記録されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: C12/C13 が placement_scope=plugin-root で inventory に載り、C01/C03 の deterministic_checks から共有参照されている (単一 skill 配下への固定なし)。
- 満たさない例: 網羅マトリクス検証が C01 skill 内の prompt 記述だけで済まされ、独立 script (C12) として component 化されていない / build_target が phase ファイル側にも重複記載されている。

### 事前解決済み判断
- 分岐点: ヒアリング機構を skill-intake plugin から再利用するか → 判断: 独立実装 (設計判断1・cross-plugin 依存は携帯性を損なう)。
- 分岐点: command を何本立てるか → 判断: 主動線 2 本 (C09/C10) のみ (設計判断4・C02/C05 は skill trigger 連鎖で起動)。

## 参照情報
- `references/component-domain.md` / `references/phase-lifecycle.md` / `references/plugin-creator-contract.md`。
- 対象 component C01-C13 (`component-inventory.json`)。
- 後続 P03 (この設計を design-gate で審査する)。
