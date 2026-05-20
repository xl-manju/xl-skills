# reproducibility-trace-schema

`eval-log/skill-build-trace.json` に保存する再現性トレースの schema。
run-build-skill Step 3.5 はこの schema に従って各キーを埋めること。
`references/build-steps.md#reproducibility-trace` も参照する。

## 必須キー

- `design_model`: 01章5要素（Intent / Contract / Boundary / Execution / Feedback）
- `context_map_decision`: resource-map が選んだ task category / selected_docs / 理由
- `build_flow_coverage`: 01a Step 1〜9 の PASS/FAIL と証跡パス
- `doc_coverage`: 02 / 03 / 04 / 05 / 06 / 07 / 08 / 09 / 10 / 11 / 13 / 14 / 15 / 16 / 26 / 27 / 28 / 29 / 30 / 31 / 32 / 33 / 34 / 35 章の設計判断をどこへ反映したかの PASS/FAIL と証跡パス
- `layer_decisions`: Skill / Subagent / Hook / MCP / CLI / script の採否理由、deterministic判定、fallback、依存方向、macOS stdlib 適合
- `variant_support`: run/ref/assign/wrap/delegate と role-suffix の適用可否
- `pattern_decisions`: `pattern_refs` の採否、量産対象パターン、再利用先、negative cases
- `script_execution_model`: 28章に基づく script 種別、実行コンテキスト A-E、優先順位、権限境界、frontmatter 状態
- `governance_model`: 27章に基づく rubric version/hash、提案要否、影響評価、役割分離、猶予条件
- `dogfooding_model`: 26章に基づく artifact 化、fork evaluator、再帰チェック、eval-log 出力先
- `reproducibility_gates`: lint / evaluator / elegant-review / governance の結果
- `rubric_composition_model`: 設計書29に基づく L0/L1/L2 `rubric_refs`、合成順序、merge_strategy、conflict_policy、hash 証跡
- `paradigm_analogy_model`: 設計書30に基づく既存パラダイム類推、適用限界、最終配置判断
- `output_routing_model`: 設計書31に基づく task_kind、payload schema、route、adapter registry、fallback、secret境界
- `implementation_ledger_model`: 設計書32に基づく manifest登録、正本/派生、残課題、C1-C4判定の証跡
- `change_governance_model`: 設計書33に基づく P0-P3分類、approval、cooldown、blast radius、changelog の証跡
- `plugin_boundary_model`: 設計書34に基づく plugin境界、外部参照棚卸し、Phase gate、移行禁止条件の証跡
- `meta_harness_model`: 設計書35に基づく observables、ログスキーマ、hook opt-in、再現性しきい値の証跡
- `variable_contract`: 具体値からテンプレート変数への写像、既定値、必須性、不適用条件、source_trace

## バリデーション

`scripts/validate-build-trace.py` が上記キーの存在と PASS/FAIL/N/A 理由を検証する。
N/A の場合は理由を必ず添えること（空欄禁止）。
