# パイプライン境界契約 (E1/E2/E3)

> skill-intake → plugin-dev-planner → harness-creator build → 改善 という量産パイプラインの
> 3 つの段境界における producer/consumer の機械契約・検証ゲート・provenance を単一箇所に集約する
> 参照正本。各段の**実行は分離**したまま (自動連鎖 orchestrator は設けない)、境界の *契約* だけを固める。

## 用語

- **E1 (intake→goal-spec)**: skill-intake の `intake.json` を plugin-dev-planner が消費し goal-spec へ源泉反映する境界。
- **E2 (plan→build)**: plugin-dev-planner の `handoff-run-plugin-dev-plan.json` の `routes[]` を harness-creator の build 実行入口が消費する境界。
- **E3 (改善→plan)**: 改善成果物 (run-elegant-review 等) を `improvement-handoff.json` に正規化し、`run-plugin-dev-plan --mode update` が受理して plan へ還流する境界。
- **provenance chain**: `intake.json → goal-spec(source_intake) → plan → build handoff → 改善成果物(source_improvement) → 次サイクル goal-spec` の 5 ノード追跡可能性。

## 境界ごとの producer / consumer / gate

| 境界 | producer | consumer | 検証ゲート | provenance |
|---|---|---|---|---|
| E1 | skill-intake `intake.json` (v2.0.0) | `run-plugin-dev-plan` R1 (C01)・`/plugin-dev-plan --intake-json` (C02) | `check-intake-consumption.py` (C04・情報漏れ検出) | goal-spec `source_intake: {ref, schema_version}` |
| E2 | `handoff-run-plugin-dev-plan.json` の `routes[]` + `render-skill-brief.py` | `run-skill-create` R1 `brief_path`/`handoff` (C06)・`/capability-build --handoff --route-id` (C07) | `check-route-component-parity.py` (C08・routes↔inventory 1:1) | route ↔ inventory の 1:1 対応 |
| E3 | 改善成果物 → `emit-improvement-handoff.py` (C09) → `improvement-handoff.json` | `run-plugin-dev-plan --mode update` `improvement_handoff` (C01) | `check-provenance-chain.py` (C05)・`enforce-provenance-chain` hook (C11) | goal-spec `source_improvement: {ref, schema_version}` |

## 契約スキーマ

- `improvement-handoff.json`: `plugins/plugin-dev-planner/skills/run-plugin-dev-plan/schemas/improvement-handoff.schema.json` (schema_version / source{kind,ref} / target_plugin_slug / plan_dir / findings[] / provenance)。
- goal-spec provenance フィールド: `plugin-goal-spec.schema.json` の `source_intake` / `source_improvement` (任意・欠落は後方互換で WARN 受理)。

## 新規作成フロー一巡 (E1→E2)

1. `intake.json` を用意し `/plugin-dev-plan "<構想>" --intake-json <intake.json>` を起動 (C02→C01)。
2. R1 が §0/§3/split_candidates を反映し `source_intake` を記録、`check-intake-consumption.py` で未反映 0 を確認 (C04)。
3. plan 生成後、`handoff-run-plugin-dev-plan.json` を得る。
4. `/capability-build --handoff <handoff> --route-id <Cxx>` で route を消費 (C07)。build 前に `check-route-component-parity.py` を preflight (C08)。
5. skill route は `run-skill-create` が `brief_path` 経由で再ヒアリングなしに build (C06)。

## 改善フロー一巡 (E3)

1. 改善成果物 (例 `run-elegant-review` の findings) を `emit-improvement-handoff.py` で `improvement-handoff.json` へ正規化 (C09)。
2. 現 goal-spec に対し `check-intake-consumption.py` / `check-provenance-chain.py` を `--marker-dir <PLAN_DIR>` 付きで PASS させ、C04/C05 の pass marker (goal-spec digest pin) を作る。
3. `/plugin-dev-plan "<構想>" --mode update --improvement-handoff <handoff>` を起動 → `enforce-provenance-chain` hook (C11) が PreToolUse で marker の存在と digest 一致を確認 (欠落/stale なら exit2 block)。
4. C01 が `findings[]` を反映し `source_improvement` を記録、`check-provenance-chain.py` で断裂なしを確認 (C05)。
5. `plugin-dev-plan-improvement-reviewer` (C10) が改善成果物と再生成 plan の意味的整合を独立レビューし verdict を返す。

## 二層分離 (機械層 / 意味層)

- 機械層: C04 (反映 signal 重複)・C05 (provenance 構造連続性)・C08 (routes↔inventory parity)・C11 (marker digest pin) が exit code で fail-closed 判定する。
- 意味層: C10 (改善反映の意味的忠実性) が独立 context で verdict を返す。「機械緑」を反映の十分条件にせず、意味の正否は fork reviewer に委ねる。
