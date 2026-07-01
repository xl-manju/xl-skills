---
id: IDX0
title: notion-task-sync 開発計画 index (main)
plugin_meta:
  manifest:
    required: true
    path: .claude-plugin/plugin.json
    name_matches_folder: true
    no_todo_placeholders: true
    validate_plugin: true
  marketplace:
    default_personal: true
    policy:
      installation: AVAILABLE
      authentication: ON_INSTALL
      category: Productivity
    cachebuster_for_update: true
  distribution:
    distributable: true
    bundles: [xl-skills-full]
    marketplace: true
  pkg_contract:
    pkg: 002-008
  governance:
    runbook: required
  ci:
    workflow: governance-check
  ssot_dedup:
    lint: ssot-duplication
    references_config_assets: tracked
  feedback_deploy:
    deploy: run-skill-feedback
  harness_eval:
    evals_json: EVALS.json
    mechanical: required
    llm_eval: required
---

# notion-task-sync 開発計画 index (main)

> プラグイン構想「タスク台帳を Notion DB へ冪等同期する」を、人間可読な 13 フェーズのライフサイクル (本 index + phase-01..13.md) と、機械可読な buildable component 目録 (`component-inventory.json`) の 2 軸直交で計画したもの。
> ライフサイクル軸 (フェーズ) は上から順に読める実行可能タスク仕様で primary deliverable。成果物実体軸 (component) は build routing・依存 DAG・品質機構を保持する唯一の SSOT。フェーズは component id を `entities_covered` で参照するだけで build_target を再記述しない (正規化)。

## フェーズ一覧

1. P01 — requirements (要件定義) / 未実施
2. P02 — design (設計) / 未実施
3. P03 — design-review (設計レビューゲート) / 未実施
4. P04 — test-design (テスト設計) / 未実施
5. P05 — implementation (実装) / 未実施
6. P06 — test-run (テスト実行) / 未実施
7. P07 — acceptance-criteria (受入基準判定) / 未実施
8. P08 — refactoring (リファクタリング) / 未実施
9. P09 — quality-assurance (品質保証) / 未実施
10. P10 — final-review (最終レビューゲート) / 未実施
11. P11 — evidence (手動テスト検証) / 未実施
12. P12 — documentation (ドキュメント) / 未実施
13. P13 — release (完了/PR・リリース) / 未実施

## コンポーネント目録の所在

buildable な実体 (skill×3 / sub-agent×3 / slash-command×2 / hook×1 / script×2 = 計 11) は `component-inventory.json` が唯一の SSOT。各 component は Phase02 (設計) と Phase05 (実装) の `entities_covered` で参照され、build_target・依存 DAG・quality_gates・harness_coverage・feedback_contract を目録側が保持する。フェーズファイルは build_target を再記述せず component id 参照のみで紐づく。

## Plugin-level surfaces

| surface | 判定 | 記録先 |
|---|---|---|
| manifest | required | `plugin_meta.manifest` |
| plugin-composition | required | `plugin-composition.yaml` |
| harness/eval | required | `EVALS.json` + `plugin_meta.harness_eval` |
| references/config/assets | required | `plugin_meta.ssot_dedup` |
| MCP/app connector | omitted | component inventory の omitted_reason |

## 全体完了条件
- 13 フェーズ (P01..P13) が phase_number 昇順で全存在し、各 phase の本文 section 床 (目的/実行タスク/成果物/完了条件) を満たす。
- `component-inventory.json` の全 11 component が build_target 非空・builder/build_kind 整合・依存 DAG 非循環で、core 規律 (quality_gates + harness_coverage + skill loop の feedback_contract) を携帯する。
- 各 component が >=1 phase の `entities_covered` に出現する (orphan 0 件)。
- 同梱 core scripts (index top-sort / detect-unassigned / spec-frontmatter / spec-gates / matrix-coverage / surface-inventory / build-handoff) が exit0。
- `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で、各 component を後段 builder (skill→run-skill-create / 非 skill→run-build-skill or parent-skill-build) へルーティングする。

## 受入確認 (build 後の見方)

> 計画 (上記) が満たすのは「各 component が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった実プラグインが当初 purpose を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test)。purpose の正本 = `goal-spec.purpose`「タスク台帳を Notion DB へ冪等同期する」。

| 受入観点 (purpose 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| 差分が正しく同期される | 同期実行後に同期レポートの追加/更新件数が台帳差分と一致 | 同期 skill (C01) の OUT criterion + harness criteria-test |
| 二重発行/重複しない (冪等) | 同一台帳を二回同期し二周目の追加/更新が 0 件 | 同期 skill (C01) の inner/outer criterion |
| 過去分が取りこぼしなく移行される | 初期一括投入後に台帳全件が Notion に存在 | backfill skill (C03) の OUT criterion |
| 発行漏れが網羅的に検出される | 既知の発行漏れを注入し reconcile が全件検出 | reconcile skill (C02) の OUT criterion |
| 破壊的操作で消えない | guard hook が物理削除を fail-closed で阻む | guard hook (C11) |

build 後、各 component の `feedback_contract.criteria` が criteria-test として実行され、上表の受入が PASS して初めて「purpose を満たすプラグインが出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。
