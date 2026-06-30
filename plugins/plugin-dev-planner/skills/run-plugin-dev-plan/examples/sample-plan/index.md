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

> プラグイン構想「タスク台帳を Notion DB へ冪等同期する」を 5 構成要素へ単一責務分解した計画。
> 本数 N=5 は構成要素数から導出 (13 固定ではない)。各仕様書は skill-creator 評価基準を frontmatter で携帯。

## 仕様書一覧 (依存 top-sort 順)

1. C05 — validate-sync-payload.py (script) / depends_on: なし / status: planned
2. C04 — guard-destructive-sync (hook) / depends_on: なし / status: planned
3. C01 — run-notion-task-sync (skill/run) / depends_on: C05 / status: planned
4. C02 — notion-sync-verifier (sub-agent) / depends_on: C01 / status: planned
5. C03 — sync-tasks (slash-command) / depends_on: C01 / status: planned

## 本数根拠

- `requested_count`: null (ユーザーは本数を指定していない)
- `derived_count`: 5

capability(同期実行/独立検証/手動起動/破壊防止/形式検査) を SRP 分割し 5 構成要素へ写像。
skill 偏重を避け 5 種の component_kind を網羅。機能開発 13 Phase の読み替えではなく実ライフサイクルから derived_count=5 を導出。
ユーザーが本数 (例 13) を要求した場合は requested_count に記録し、derived_count と並記して差の理由を明示する (`--force-13` は component spec 13 本固定の逃げ道であり、Phase1-13 文書ビューそのものではない)。

## Plugin-level surfaces

| surface | 判定 | 記録先 |
|---|---|---|
| manifest | required | `plugin_meta.manifest` |
| plugin-composition | required | `plugin-composition.yaml` |
| harness/eval | required | `EVALS.json` + `plugin_meta.harness_eval` |
| references/config/assets | required | `plugin_meta.ssot_dedup` |
| MCP/app connector | omitted | component inventory の omitted_reason |

## 全体完了条件
- 全 buildable spec が core 規律 (quality_gates + harness_coverage block) を携帯し同梱 core 5 scripts / 6 invocations + surface inventory gate + build handoff gate が exit0
- index が依存 top-sort 順で全 5 仕様書を列挙 (unassigned 0 件) し plugin_meta を携帯
- 各仕様書を component_kind 別ルーティング (skill→run-skill-create / 非 skill→親 skill build の kind dispatch) で後段へ投入

## 受入確認 (build 後の見方)

> 計画 (上記) が満たすのは「各 spec が評価基準を携帯し決定論ゲートを通る」こと。**組み上がった実プラグインが当初 purpose を満たすか**は build 後に下記で確認する。plan は受入基準を**契約として焼く**だけで、実行は後段 build (run-skill-create の harness criteria-test)。purpose の正本 = `goal-spec.purpose`「タスク台帳を Notion DB へ冪等同期する」。

| 受入観点 (purpose 由来) | 確認の見方 (build 後) | 焼き先 |
|---|---|---|
| 差分が正しく同期される | 同期実行後に同期レポートの追加/更新件数が台帳差分と一致 | 同期 skill の OUT criterion + harness criteria-test |
| 二重発行/重複しない (冪等) | 同一台帳を二回同期し二周目の追加/更新が 0 件 | 同期 skill の inner/outer criterion |
| 破壊的操作で消えない | guard hook が物理削除を fail-closed で阻む | guard hook |

build 後、各 component の `feedback_contract.criteria` が criteria-test として実行され、上表の受入が PASS して初めて「purpose を満たすプラグインが出来た」と確定する。`EVALS.json` の `llm_eval` はこの受入が評価系に配線されていることを宣言する。
