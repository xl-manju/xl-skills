# Prompt: R1-elicit

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | elicit |
| skill | run-skill-create |
| responsibility | R1 (Step 1 ヒアリング → skill-brief.json) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/skill-brief.schema.json |
| reproducible | true (open_questions は brief.open_questions[] に構造化保持、TODO(human) 化禁止) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール

- **CONST_001 (委譲固定)**: 委譲先は `run-skill-elicit` (Skill tool) のみ
  - **目的**: brief 構築ロジックの単一情報源を確保するため
  - **背景**: 複数 elicitor を許すと skill_name 規約が drift する
- **CONST_002 (出力先固定)**: 出力先は `eval-log/skill-brief.json`
  - **目的**: 後続 Step が固定パスから参照可能にするため
  - **背景**: 動的パスはオーケストレーション層の整合性を壊す
- **CONST_003 (引数なし→対話)**: 引数なし起動時は対話モードに自動遷移
  - **目的**: 利用者の認知コストを下げるため
  - **背景**: batch モード強制は新規利用者を阻害する

### 1.2 倫理ガード

- 個人特定情報 (PII) を brief に格納しない
- ヒアリング応答原文をそのまま保存しない (構造化変換必須)

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)

- 担当: ユーザー要望から skill-brief.json を構築する (Step 1 ヒアリング)
- 非担当: Gate 承認 (R2)、Governance 判定 (R3)、build 実行 (R4 以降)

### 2.2 ドメインルール

- **CONST_010 (skill_name 命名)**: prefix-kebab パターン (`^(run|assign|ref|wrap)-[a-z0-9-]+$`) を満たす
  - **目的**: prefix-driven 構造の機械検証を可能にするため
  - **背景**: 自由命名は P0 lint を破壊する
- **CONST_011 (prefix-kind 整合)**: prefix と kind が整合する
  - **目的**: orchestration 層が prefix のみで kind 推定できるようにするため
  - **背景**: 不整合は 23 章 prefix-driven 構造違反
- **CONST_012 (wrap/delegate 必須項目)**: prefix=wrap なら base_skill、delegate なら delegate_agent 必須
- **CONST_013 (言語既定)**: output_language=ja, parameter_language_exception=true

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| topic | string | no | 要望キーワード |
| mode | enum | no | `dialog` / `batch`、default `dialog` |
| manifest | path | yes | workflow-manifest.json |
| schema | path | yes | schemas/skill-brief.schema.json |

### 2.4 出力契約

- schema: `schemas/skill-brief.schema.json` (additionalProperties: false)
- 必須フィールド: skill_name / prefix / kind / hierarchy_level / trigger_conditions / boundary / responsibilities
- open_questions が残る場合は `brief.open_questions[]` に `{question, default_decision, rationale}` 形式で保持し、AI が default_decision を確定 (TODO(human) 化禁止)

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| manifest | workflow-manifest.json | phase=elicit context 取得時 |
| schema | schemas/skill-brief.schema.json | brief 構造検証時 |
| naming-rule | references/skill-naming-rule.md | skill_name 検証時 |

### 3.2 外部ツール / API

- `Skill(run-skill-elicit, args=topic)`
- `AskUserQuestion` (dialog モード時)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動

- schema 不一致時は brief を保存せず exit 1
- open_questions の default_decision 未確定は exit 1 (人間判断保留禁止)

### 4.2 観測 / ロギング

- `eval-log/skill-brief.json` に最終結果を保存
- stderr に進捗ログ (phase=elicit start/end)

### 4.3 セキュリティ

- 秘匿情報をヒアリング応答に書かない
- topic 引数の shell injection 防止 (argv 直渡し)

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent

- run-skill-create orchestrator が `run-skill-elicit` に委譲
- context-fork: 不要 (親 context 継承)

### 5.2 推論手順 (再現可能)

1. `workflow-manifest.json` から phase=elicit の context を取得
2. `Skill(run-skill-elicit, args=topic)` を起動 (引数なしなら対話モード)
3. 応答を `schemas/skill-brief.schema.json` に従って整形
4. open_questions が残れば AI が文脈から default_decision を決め `brief.open_questions[]` に `{question, default_decision, rationale}` で記録
5. `eval-log/skill-brief.json` に Write

### 5.3 自己検証 checklist

- [ ] skill_name が prefix-kebab パターンを満たす
- [ ] prefix と kind が整合する
- [ ] hierarchy_level=L2 なら rubric_refs が空でない
- [ ] prefix=wrap なら base_skill 必須、delegate なら delegate_agent 必須
- [ ] trigger_conditions が 2-3 件、各 80 文字以内
- [ ] boundary が 200 文字以内で「やらないこと」を 1 文で明示
- [ ] kind ∈ {run,assign} なら responsibilities に prompt_required=true が 1 件以上
- [ ] output_language=ja, parameter_language_exception=true

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続

- 呼び出し元: `run-skill-create` (Step 1)
- 後続 phase: `gate-review` (Gate 1)

### 6.2 並列性

- 単発実行 (対話 / batch どちらでも)
- 同一 topic への並列呼出は eval-log 競合のため禁止

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式

- 対話モード: `AskUserQuestion` 連鎖
- batch モード: JSON のみ

### 7.2 言語

- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM は `Skill(run-skill-elicit, args={{topic}})` を呼び出し、ユーザー要望から skill-brief.json を構築する。Layer 5.2 の手順を逐次実行し、出力は `schemas/skill-brief.schema.json` 準拠の JSON のみ (`eval-log/skill-brief.json` へ保存)。前置き・後書き・思考過程出力は禁止。
