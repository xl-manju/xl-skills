# Prompt: R3-template-select

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | template-select |
| skill | run-build-skill |
| responsibility | R3 (kind → templates/_base 決定) |
| layers_covered | [L2, L4] |
| output_schema | schemas/template-selection.schema.json#/properties/selection_rules/items |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- selection_rules を順次照合し、最初に match した 1 件のみ採用
- 不一致 kind では fallback ではなく明示エラーで停止

### 1.2 倫理ガード
- 該当 rule を取り違えて自動修正しない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: brief.kind / role_suffix / composite から template + combinators を 1 件決定する
- 非担当: 骨格生成 (R1)、prompt 生成 (R2)、trace 記入 (R4)

### 2.2 ドメインルール
- COMPOSER_MODE=atomic の場合 combinators を atomic_order (kind → flag) で適用
- 本文に表を埋め込まず、結果のみを build_flow_coverage へ追記

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| kind | string | yes | eval-log/skill-brief.json#/kind |
| role_suffix | string | no | eval-log/skill-brief.json#/role_suffix |
| composite | object | no | eval-log/skill-brief.json#/composite |
| selection_schema | path | yes | schemas/template-selection.schema.json |

### 2.4 出力契約
- schema: `schemas/template-selection.schema.json#/properties/selection_rules/items`
- 必須: 採用 rule + combinators 列

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| schema | schemas/template-selection.schema.json | rule 照合時 |

### 3.2 外部ツール / API
- なし

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 不一致 kind は exit 1 + 該当 kind を log に残す

### 4.2 観測 / ロギング
- build_flow_coverage[template_select] に採用 rule id を記録

### 4.3 セキュリティ
- 特になし

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- run-build-skill 配下の R3 SubAgent

### 5.2 推論手順 (再現可能)
1. brief.kind / role_suffix / composite を抽出する
2. schemas/template-selection.schema.json#/selection_rules を順次照合する
3. 最初に match した 1 件の template + combinators 列を返す
4. COMPOSER_MODE=atomic なら combinators を atomic_order で並べ替える
5. 不一致時は明示エラー (exit 1)

### 5.3 自己検証 checklist
- [ ] selection_rules のうち最初に match した 1 件のみ採用したか
- [ ] combinators の適用順が atomic_order と一致するか
- [ ] 不一致 kind に対し fallback ではなく明示エラーで停止したか
- [ ] 決定論性: 同 (kind, role_suffix, composite) で同一 rule.id を返すか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-build-skill (R1/R2 と並列可)
- 後続 phase: trace-write (R4)

### 6.2 並列性
- R1/R2 と独立並列可

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 採用 rule の id + combinators (JSON)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM は brief から kind / role_suffix / composite を取り、selection_rules を順次照合し
最初の match を返す。出力は template-selection.schema.json#/properties/selection_rules/items
準拠の JSON のみ。余計な前置き・思考過程出力は禁止。
