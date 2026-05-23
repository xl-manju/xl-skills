# Prompt: R2-gate-review

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | gate-review |
| skill | run-skill-create |
| responsibility | R2 (Gate 1-4 共通 AskUserQuestion テンプレ) |
| layers_covered | [L4, L5, L6] |
| output_schema | schemas/handoff.schema.json |
| reproducible | true (承認結果が handoff に確定保存) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- ユーザー承認なしに次フェーズへ進まない (Key Rule 1)
- 明示確認時に「次へ」と書かれていなければ進めない
- 承認時は schemas/handoff.schema.json に従い handoff JSON を保存
- 否認時は dependsOn の前段に戻る (最大 3 周)

### 1.2 倫理ガード
- ユーザー応答を改変・推測しない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: Gate 1-4 で AskUserQuestion を発行し、承認結果を handoff に確定保存する
- 非担当: ヒアリング (R1)、Governance 判定 (R3)

### 2.2 ドメインルール
- Gate 1: brief 確認 (skill-brief.json + open_questions)
- Gate 2: diff 確認 (git diff + build-trace)
- Gate 2.5: 横展開確認 (build-manifest-registration-plan.py 出力)
- Gate 3: 評価結果確認 (findings.json + C1-C4 + severity)
- Gate 4: 最終承認 (完了レポート全体)

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| gate_id | enum | yes | 1 / 2 / 2.5 / 3 / 4 |
| phase | string | yes | any |
| manifest | path | yes | workflow-manifest.json |
| handoff_schema | path | yes | schemas/handoff.schema.json |
| artifacts | array | yes | 該当ゲートの成果物パス |

### 2.4 出力契約
- schema: `schemas/handoff.schema.json`
- 必須: approver / next_phase / artifacts / (否認時) required_fixes[]

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| brief | eval-log/skill-brief.json | Gate 1 |
| trace | eval-log/skill-build-trace.json | Gate 2 |
| docs | eval-log/docs/<NN>-<timestamp>.json | Gate 3 |
| findings | eval-log/findings.json | Gate 3 |

### 3.2 外部ツール / API
- AskUserQuestion

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 否認 3 周超過は exit 1

### 4.2 観測 / ロギング
- 各 Gate ごとに handoff-after_<gate>.json を保存

### 4.3 セキュリティ
- ユーザー応答原文を改変せず保存

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- run-skill-create 配下の R2 SubAgent

### 5.2 推論手順 (再現可能)
1. gate_id に対応する artifacts を集約し、AskUserQuestion を発行する
2. 「次へ」を含む応答 → approver=user, next_phase 更新
3. solo_operator_mode 等の自動承認条件を満たす → approver=solo_operator_auto / system_auto
4. 否認 → required_fixes[] を埋め、dependsOn 前段へ戻る (最大 3 周)
5. schemas/handoff.schema.json に従い JSON を Write

### 5.3 自己検証 checklist
- [ ] approver フィールドが user / solo_operator_auto / system_auto のいずれかか
- [ ] artifacts[] が当該ゲートの対象成果物を網羅しているか
- [ ] next_phase が workflow-manifest.json phases[].id と一致するか
- [ ] 否認時は required_fixes[] に修正項目を残したか
- [ ] gate_id が manifest の gate 値と一致するか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-skill-create の各 Gate 直前
- 後続 phase: handoff.next_phase に従う

### 6.2 並列性
- 単発実行 (各 Gate ごと)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- AskUserQuestion (Markdown 要約 + 承認/否認選択肢)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM は gate_id に対応する artifacts を集約し AskUserQuestion を発行、応答を解釈して
handoff.schema.json 準拠の JSON を出力する (handoff-after_<gate>.json へ保存)。
余計な前置き・思考過程出力は禁止。
