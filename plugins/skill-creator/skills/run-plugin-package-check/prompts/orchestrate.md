# Prompt: R1-orchestrate

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | orchestrate |
| skill | run-plugin-package-check |
| responsibility | R1 (PKG-001〜015 phase 別 orchestration) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/run-report.schema.json |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール

- **CONST_001 (PKG ID 一次情報)**: PKG ID 表の再定義禁止。`ref-pkg-contract` を一次情報として参照
  - **目的**: 契約 drift を物理的に不可能にするため
  - **背景**: 複数定義は 36章本文との齟齬を生む
- **CONST_002 (eval-log path 規約)**: 27章 §3.1 規約厳守 `eval-log/<plugin>/pkg-<id>/<YYYY-MM-DD>-<run>.{json,log}`
  - **目的**: 集約 script が単一規約で走査できるようにするため
  - **背景**: 自由パスは aggregate スクリプトを壊す
- **CONST_003 (dry_run 副作用ゼロ)**: `dry_run=true` のとき副作用なし (実行予定 PKG ID 列挙のみ)
- **CONST_004 (observable 単一 emitter)**: 35章 observable `pkg_check_failed` は本 prompt 配下 `aggregate-pkg-findings.py` のみが emit
  - **目的**: 二重発火による誤集計を防ぐため
  - **背景**: 35章 meta-harness feedback loop の一意性要求

### 1.2 倫理ガード

- proposer ≠ approver（23章）: orchestrator は実行のみ、改善実行は別 skill（run-skill-create / run-skill-rubric-governance）
- `failure_action: abort` の Step 失敗時は force-continue 禁止

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)

- 担当: phase 0/1/2 別に PKG-001〜015 を順次/並列実行し findings を集約、verdict を出力
- 非担当: 個別 PKG 実装（assign-plugin-package-evaluator）、完了判定 phase ロジック（R2 gate-decide）、契約 schema 改廃（governance）

### 2.2 ドメインルール

- `package_mode=skill-only` は適用 PKG ID を PKG-002/PKG-004 のみに限定
- PKG-001 が exit 2（claude CLI 不在）でも全体停止しない（skip 扱い）
- PKG-013 sub-check は `all_must_pass`: a/b/c/d 全 pass で PKG-013 全体 pass、1 件 fail で全体 fail
- `failure_action: abort` の Step（PKG-010）が fail したら以降の Step スキップ
- `failure_action: record_and_continue` の Step は fail でも次に進む

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| `plugin` | string | yes | kebab-case plugin 名 |
| `phase` | enum | no | `0` / `1` / `2` / `all`、default `all` |
| `pkg` | string[] | no | 個別 PKG ID 絞込（カンマ区切り入力を配列化） |
| `dry_run` | bool | no | default false |
| `output_dir` | path | no | default `eval-log/<plugin>/` |

### 2.4 出力契約

- schema: `schemas/run-report.schema.json`（additionalProperties: false）
- 必須フィールド: `plugin`, `aggregated_at`, `pkg_checks{}`, `verdict{pass,fail,skip,not_applicable,total}`
- 副次出力: stdout に markdown サマリ（§4.2）、eval-log に JSON

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| manifest | `workflow-manifest.json` | phase ordering, failure_action, completion_signals |
| catalog | `../ref-pkg-contract/references/pkg-id-catalog.yaml` | PKG ID メタ参照 |
| resource-map | `references/resource-map.yaml` | Progressive Disclosure 起点 |
| chap27 | `doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook.md` §3.1 | eval-log path 規約 |
| chap34 | `doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md` Phase 0/1/2 | phase 完了判定 |
| chap36 | `doc/ClaudeCodeスキルの設計書/36-plugin-package-harness-contract.md` | PKG-001〜017 一覧 |

### 3.2 外部ツール / API

- `scripts/run-plugin-validate-strict.sh` (PKG-001)
- `scripts/smoke-plugin-install.sh` (PKG-010)、`smoke-plugin-uninstall.sh` (PKG-011)、`smoke-plugin-upgrade.sh` (PKG-012)
- `scripts/validate-plugin-permissions.py` (PKG-013a〜d)
- `scripts/aggregate-pkg-findings.py` (Step 9 集約 + observable emit)
- 外部 lint: `../../scripts/lint-external-refs.py` (PKG-009)、`../../scripts/lint-rubric-violation.py` (PKG-015)
- delegate: `Skill(assign-plugin-package-evaluator, context=fork)` (PKG-002〜008/014)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動

- exit 0: 全 pass / not_applicable / skip
- exit 1: 1 件以上 fail
- PKG-001 claude CLI 不在 → exit 2 → 当該 PKG `status: skip`、全体は続行
- aggregate-pkg-findings.py 失敗 → exit 3（structural error）
- `dry_run=true` → 副作用なし、`{planned_pkg_ids: [...]}` を返す

### 4.2 観測 / ロギング

- eval-log: 各 PKG 結果は `eval-log/<plugin>/pkg-<id>/<YYYY-MM-DD>-<run>.json`、集約は `eval-log/<plugin>/pkg-summary/<YYYY-MM-DD>-<run>.json`
- 35章 observable: `verdict.fail > 0` で `aggregate-pkg-findings.py` が `pkg_check_failed` event を `.claude/logs/meta-harness.jsonl` に append
- stdout markdown サマリ:
  ```markdown
  # PKG Check Report: <plugin>
  - phase: <phase>
  - verdict: pass=<n> fail=<n> skip=<n> not_applicable=<n>
  - failed_pkg_ids: [...]
  ```

### 4.3 セキュリティ

- `plugin` 値の path traversal 防止（`../` 含む値は exit 2）
- sub-process 起動時の shell injection 防止（argv 直渡し、shell=False）

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent

- run-plugin-package-check skill 本体（context-fork 不要、orchestrator は親 context 継承）
- 個別 PKG check は `Skill(assign-plugin-package-evaluator, context=fork)` で delegate

### 5.2 推論手順 (再現可能)

1. **Step 0 入力検証**: `plugins/<plugin>/.claude-plugin/plugin.json` 存在確認、`package_mode` 抽出（欠落→skill-only 推定）、`pkg` 引数で対象 ID 絞込
2. **Step 1 PKG-001**: `scripts/run-plugin-validate-strict.sh` 実行
3. **Step 2 PKG-002〜008**: `Skill(assign-plugin-package-evaluator, context=fork, pkg_ids=[002..008])`
4. **Step 3 PKG-009**: `../../scripts/lint-external-refs.py`
5. **Step 4 PKG-010**: `scripts/smoke-plugin-install.sh`（`failure_action: abort`、fail で以降 skip）
6. **Step 5 PKG-011/012**: `smoke-plugin-uninstall.sh` / `smoke-plugin-upgrade.sh`
7. **Step 6 PKG-013a〜d**: `validate-plugin-permissions.py` 各 sub-check
8. **Step 7 PKG-014**: `Skill(assign-plugin-package-evaluator, context=fork, pkg_ids=[PKG-014])`
9. **Step 8 PKG-015**: `../../scripts/lint-rubric-violation.py`
10. **Step 9 集約**: `aggregate-pkg-findings.py --plugin <name> --out eval-log/<plugin>/pkg-summary/<date>-<run>.json`
11. **Step 10 verdict 出力**: stdout に markdown サマリ + exit code 設定

### 5.3 自己検証 checklist

- [ ] 全 PKG ID が `pkg_checks{}` に存在（実行 / skip / not_applicable のいずれか）
- [ ] `failure_action: abort` Step fail 時に以降 Step が skip されている
- [ ] `package_mode=skill-only` で PKG-001/003/005/006/007/008/009/010〜015 が `not_applicable`
- [ ] eval-log path が 27章 §3.1 規約準拠
- [ ] `dry_run=true` 時に副作用ゼロ

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続

- 呼び出し元: `run-skill-create` (Step 5 PKG completeness check)、CI/CD pipeline、開発者 manual invocation
- 後続 phase: R2 `gate-decide`（phase 完了判定）、`run-elegant-review` (Step 5.5)、`assign-skill-design-evaluator` (Step 6)

### 6.2 並列性

- 同一 plugin への並列実行は eval-log 競合のため禁止（run-id で識別）
- 異なる plugin への並列実行は可
- 内部 Step は `phases[].parallel` フラグで個別制御（workflow-manifest.json 参照）

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式

- 機械可読 JSON（`schemas/run-report.schema.json`）を eval-log に保存
- stdout に markdown サマリ（§4.2 フォーマット）

### 7.2 言語

- 本文: 日本語、PKG ID / status enum / key は英語

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `{{plugin}}` / `{{phase}}` / `{{pkg}}` / `{{dry_run}}` / `{{output_dir}}` を受け、Layer 5.2 の Step 0〜10 を逐次実行する。各 Step 完了時に `failure_action` を判定し、Step 10 で Layer 2.4 の run-report JSON を eval-log に保存し、§4.2 の markdown サマリを stdout に出力する。前置き・後書き・思考過程出力は禁止。exit code は §4.1 に従う。
