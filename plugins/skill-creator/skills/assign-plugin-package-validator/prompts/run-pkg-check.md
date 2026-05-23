# Prompt: R1-run-pkg-check

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | run-pkg-check |
| skill | assign-plugin-package-validator |
| responsibility | R1 (PKG-002〜008/014 worker 実行) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/findings.schema.json |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール

- **CONST_001 (PKG ID 一次情報)**: 本 prompt 内で PKG ID 表を再定義しない。`ref-pkg-contract` を一次情報として参照
  - **目的**: 契約 drift を防ぐため
  - **背景**: validator 側で独自定義すると契約改廃 governance を回避してしまう
- **CONST_002 (eval-log path 規約)**: 27章 §3.1 規約を厳守
  - **目的**: 集約 script の走査整合性を保つため
  - **背景**: 自由パスは aggregate-pkg-findings.py を壊す
- **CONST_003 (受理 ID 限定)**: 静的検査の中核 7 件 (PKG-002/003/004/005/006/007/008) + PKG-014 のみ受理。それ以外は `unsupported_pkg_id` エラー
  - **目的**: 責務外 ID の誤実行を防ぐため
  - **背景**: PKG-001/009〜013/015 は別 worker / 別 script の管轄

### 1.2 倫理ガード

- proposer ≠ approver（23章）: 本 worker は判定者であり改善実行はしない
- context: fork 強制（呼出元 context を継承しない）

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)

- 担当: 指定 PKG ID 群に対し `scripts/validate-plugin-package.py` を順次実行し findings JSON を集約
- 非担当: PKG-001（claude CLI validate, run-plugin-package-check 直接）、PKG-009/015（外部 lint）、PKG-010〜013（smoke / permission scripts）

### 2.2 ドメインルール

- `package_mode=skill-only` の場合、PKG-003/005/006/007/008 を即 `not_applicable` 確定（exec しない）
- `fail_fast=true` でも全 PKG ID の status を確定する。未実行は `status: skip` + `skip_reason: "fail_fast_triggered"`
- 入力 `pkg_ids` 省略時は中核 7 件 + PKG-014 を全件実行

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| `target_plugin` | string | yes | kebab-case plugin 名 |
| `pkg_ids` | string[] | no | 省略時は中核 7 件 + PKG-014 |
| `options.fail_fast` | bool | no | default false |
| `options.output_path` | path | no | eval-log 保存先（指定なしなら stdout のみ） |

### 2.4 出力契約

- schema: `schemas/findings.schema.json`（additionalProperties: false）
- 必須フィールド: `plugin`, `aggregated_at`, `pkg_results[]`, `verdict`
- 各 `pkg_results[i]` は `pkg_id`, `status` (`pass|fail|skip|not_applicable`), `findings[]`, `script_exit_code` を含む

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| validator-script | `scripts/validate-plugin-package.py` | 全 PKG 実行で必須 |
| renderer | `scripts/render-pkg-findings.py` | options.render=markdown 時 |
| pkg-catalog | `../ref-pkg-contract/references/pkg-id-catalog.yaml` | PKG ID メタ参照 |
| pkg-schema | `../ref-pkg-contract/schemas/package-contract.schema.json` | input pkg_ids バリデーション |
| chap27 | `doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook.md` §3.1 | eval-log path 規約 |

### 3.2 外部ツール / API

- `python3 scripts/validate-plugin-package.py --check <pkg-id> --plugin <name>` を sub-process 起動
- plugin.json 読込: `plugins/<target_plugin>/.claude-plugin/plugin.json`

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動

- exit 0: 全 pass / not_applicable
- exit 1: 1 件以上 fail（findings には fail PKG ID を全て含む）
- exit 2: 入力 schema 違反 / unsupported_pkg_id / target_plugin 不在
- sub-process 異常（segfault 等）: 当該 PKG を `status: skip` + `skip_reason: "executor_error: <detail>"` で続行

### 4.2 観測 / ロギング

- stdout: findings JSON（§2.4 schema 準拠）
- stderr: 進捗ログ（`PKG-NNN start/end <duration>`）
- `options.output_path` 指定時は eval-log に保存（27章 §3.1 規約: `eval-log/<plugin>/pkg-batch/<YYYY-MM-DD>-<run>.json`）
- 35章 observable は呼出元（run-plugin-package-check の aggregate-pkg-findings.py）が emit

### 4.3 セキュリティ

- secret 取扱なし
- `target_plugin` 値の path traversal 防止（`../` 含む値は exit 2）

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent

- assign-plugin-package-validator skill（kind=assign, **context: fork 強制**）

### 5.2 推論手順 (再現可能)

1. 入力検証: `target_plugin` 値の正規表現マッチ + `pkg_ids` の中核 7 件 + PKG-014 限定確認
2. `plugins/<target_plugin>/.claude-plugin/plugin.json` を Read し `package_mode` 抽出（欠落 → `skill-only` 推定）
3. `package_mode=skill-only` なら PKG-003/005/006/007/008 を `not_applicable` 確定（script 実行スキップ）
4. 残る PKG ID を順次 `python3 scripts/validate-plugin-package.py --check <pkg-id> --plugin <name>` で実行
5. 各 sub-process 結果（exit code + JSON stdout）を `pkg_results[i]` に集約
6. `fail_fast=true` かつ 1 件目 fail で残 PKG を `status: skip` で確定し break
7. `verdict.{pass,fail,skip,not_applicable}` を集計
8. `options.output_path` 指定時は eval-log に保存
9. stdout に findings JSON 出力、exit code 設定

### 5.3 自己検証 checklist

- [ ] 全 PKG ID が `pkg_results[]` に存在（実行 or skip or not_applicable）
- [ ] schema validation pass（`schemas/findings.schema.json`）
- [ ] eval-log 保存先が 27章 §3.1 規約準拠
- [ ] unsupported_pkg_id を受理していない

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続

- 呼び出し元: `run-plugin-package-check` (PKG-002〜008 phase で `Skill(assign-plugin-package-validator, context=fork)`)
- 後続 phase: `aggregate-pkg-findings.py` が本 worker findings + 他 script findings を結合

### 6.2 並列性

- 同一 target_plugin に対し 1 invocation のみ（plugin.json read 競合回避）
- 異なる target_plugin への並列呼出は可

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式

- 機械可読 JSON（findings.schema.json）が主出力
- `options.render=markdown` 指定時のみ `render-pkg-findings.py` 経由で markdown サマリも出力

### 7.2 言語

- 本文: 日本語、findings の `message` フィールドは日本語、key / status enum は英語

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `{{target_plugin}}` / `{{pkg_ids}}` / `{{options}}` を受け、Layer 5.2 の手順を逐次実行し、Layer 2.4 の findings JSON のみを stdout に出力する。前置き・後書き・思考過程出力は禁止。exit code は §4.1 に従う。
