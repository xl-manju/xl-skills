---
name: run-intake-finalize
description: intake 全 JSON を統合したいとき、intake.md と intake.json を Jinja2 で render して quality_gate と cross_check を通したいときに使う。
allowed-tools:
  - Read
  - Write
  - Bash
kind: run
user-invocable: true
effect: local-artifact
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-24
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
role_suffix: null
owner: team-platform
since: 2026-05-22
responsibility_refs:
  - prompts/R1-main.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
---

# run-intake-finalize

## Purpose & Output Contract

Phase 9 担当。Phase 1-8 で生成された全 JSON / sheet.md / visuals.json を統合し、最終成果物 `intake.md` (人間向け) と `intake.json` (skill-creator 入力) を **決定論的に**生成する。`render-intake-final.py` (Jinja2) と `quality_gate.py` / `cross_check.py` を順に exec する。skill-creator 引き渡し用の `next-action.json` は Notion 公開後の Phase 11 で生成する。

**入力**: Phase 1-8 の全成果物 + `intake-final-template.md.tmpl` + `intake-final-schema.json`
**出力**:
- `output/<hint>/intake.md`
- `output/<hint>/intake.json` (`schemas/output.schema.json` 準拠、`validation` field 必須)

**完了条件**: render PASS + quality_gate PASS + cross_check PASS。FAIL 時は `validation.failures[].retry_phase` を埋めて orchestrator へ返却。

## Key Rules

1. **LLM は呼ばない**: render は Jinja2、検証は決定論 script のみ。
2. **schema/template の正本**: 旧 aggregator references を参照。Phase C で物理移管予定。
3. **失敗時の戻り先明示**: render fail → 該当 Phase へ、quality_gate fail → 該当軸の Phase へ、cross_check fail → 不整合元 Phase へ。
4. **検証順序固定**: render → quality_gate → cross_check の直列 (順序入替・並列起動禁止、atomic write 保証)。
5. **日本語成果物**: 本文・validation reason は日本語、schema key / CLI 引数 / path は英語。

## ゴールシーク実行

### Goal
Phase 1-8 の全成果物を決定論的に統合し、`schemas/output.schema.json` 準拠の `intake.md` / `intake.json` を bit-identical な再現性で生成、`validation.render` / `validation.quality_gate` / `validation.cross_check` が全 PASS、または FAIL 時に `failures[].retry_phase` が必ず埋まり intake.json に validation サマリが書き戻されている状態。

### Why
LLM 推論を混入させると同入力で差分が出て、後段 (`run-notion-intake-publish` 公開・diff 監査) が破綻する。検証 2 段 (quality_gate → cross_check) は順序固定でなければ偽陽性/偽陰性が混入する。固定手順を辿るのではなく、**チェックリスト未充足を起点に必要 script をその都度起動して反復**することで、入力欠落や中間生成物破損にも頑健になる。

### 完了チェックリスト (停止条件)
- [ ] Phase 1-8 全成果物 (JSON / sheet.md / visuals.json) の存在と schema 適合を確認した
- [ ] LLM 推論を呼ばずに Jinja2 / script のみで完了している
- [ ] `intake.json` が `schemas/output.schema.json` に適合している
- [ ] `quality_gate.py` と `cross_check.py` を順序通り (順序入替禁止) 実行した
- [ ] FAIL 時に `validation.failures[]` の各項目に `where` / `reason` / `retry_phase` が明示されている
- [ ] 同一 Phase 1-8 入力で `intake.md` / `intake.json` が bit-identical (determinism)
- [ ] 不足成果物を推測補完していない (欠落は FAIL として返している)
- [ ] `intake.json.validation` サマリ書き戻し済み (render / quality_gate / cross_check 各 enum)

未充足項目を特定 → 必要 script (`build-intake-final-context.py` / `render-intake-final.py` / `quality_gate.py` / `cross_check.py`) を該当ステップから起動 → validation 更新 → 再度チェックリストで自己評価、を反復する。固定手順は持たない。

### 参考: 主要 script 起動例

```bash
# context 集約
python3 plugins/skill-intake/scripts/build-intake-final-context.py \
  --out-dir output/<hint>/ \
  --context-out output/<hint>/intake-final-context.json

# render
python3 plugins/skill-intake/scripts/render-intake-final.py \
  --context output/<hint>/intake-final-context.json \
  --template plugins/skill-intake/skills/run-skill-intake-aggregator/references/intake-final-template.md.tmpl \
  --schema   plugins/skill-intake/skills/run-skill-intake-aggregator/references/intake-final-schema.json \
  --md-out   output/<hint>/intake.md \
  --json-out output/<hint>/intake.json

# 検証 2 段 (順序固定)
python3 plugins/skill-intake/scripts/quality_gate.py output/<hint>/intake.json
python3 plugins/skill-intake/scripts/cross_check.py  output/<hint>/intake.json output/<hint>/intake.md
```

Step/Gate の機械可読定義は `workflow-manifest.json` (P1-collect / P2-render / P3-quality-gate / P4-cross-check) を参照。

## Gotchas

1. **template / schema は移管前**: 旧 aggregator references パスを直書きしている。Phase C で本 references 配下へ移管後にパス書き換える。
2. **render と quality_gate は単一発火点**: 重複呼び出し禁止。orchestrator は本 Skill を 1 回だけ呼ぶ。単一発火点の SSOT 定義は `../run-skill-intake-aggregator/SKILL.md` 「単一発火点」項を参照。
3. **並列起動禁止**: 検証順序維持と atomic write 保証のため、本 Skill は直列・単発のみ。
4. **欠落の推測補完禁止**: Phase 1-9 成果物に欠けがある場合は FAIL として `retry_phase` を埋めて返す (補完しない)。

## Additional Resources

- `workflow-manifest.json` — Phase (P1-P4) / Gate (C1-C4) / resource の機械可読定義
- `schemas/output.schema.json` — intake.json 出力契約 (validation field 必須)
- `prompts/R1-main.md` — R1 責務プロンプト (7 層 Markdown、決定論実行指示)
- `references/template-pointer.md` — Jinja2 テンプレ / schema の正本パス案内
- `references/validation-flow.md` — render → quality_gate → cross_check の順序と失敗戻り先表
- `references/resource-map.yaml` — リソース一覧 (machine-readable)
