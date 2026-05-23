# Prompt: R1-scaffold

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | scaffold |
| skill | run-build-skill |
| responsibility | R1 (SKILL.md 骨格生成) |
| layers_covered | [L2, L4, L5, L6] |
| output_schema | schemas/skill-build-trace.schema.json#/properties/build_flow_coverage |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 本文に具体値を直書きしない (全て `{{...}}` で変数化する)
- kind→template 対応表を本文に再掲しない (schemas 参照のみ)

### 1.2 倫理ガード
- secret / 個人識別子を骨格に埋め込まない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: SKILL.md の骨格 (frontmatter + Purpose & Output Contract + Key Rules 参照 + Steps 見出し) を生成する
- 非担当: R-id 別 prompt 生成 (R2)、template 選択 (R3)、trace 記入 (R4)

### 2.2 ドメインルール
- SKILL.md は 170 行以下
- frontmatter に `responsibility_refs` と `manifest` を含める
- kind→template 対応は schemas/template-selection.schema.json の selection_rules を参照する

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| skill_brief | path | yes | eval-log/skill-brief.json |
| template_selection_schema | path | yes | schemas/template-selection.schema.json |
| resource_map | path | yes | references/resource-map.yaml |

### 2.4 出力契約
- schema: `schemas/skill-build-trace.schema.json#/properties/build_flow_coverage`
- 必須フィールド: build_flow_coverage の scaffold セクション

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| brief | eval-log/skill-brief.json | 骨格生成開始時 |
| template_schema | schemas/template-selection.schema.json | kind→template 確認時 |
| resource_map | references/resource-map.yaml | 参照ファイル解決時 |

### 3.2 外部ツール / API
- なし (Read / Write のみ)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- variable_contract に source_trace が残らない場合は exit 1

### 4.2 観測 / ロギング
- eval-log/skill-build-trace.json#/build_flow_coverage に記録

### 4.3 セキュリティ
- 具体値 (固定 URL / owner) を骨格に直書きしない

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- run-build-skill 配下の R1 SubAgent

### 5.2 推論手順 (再現可能)
1. eval-log/skill-brief.json を Read し {{SKILL_NAME}} / {{KIND}} / {{OUT_BASE}} を抽出する
2. schemas/template-selection.schema.json の selection_rules から該当 template の骨格を取得する
3. SKILL.md frontmatter (responsibility_refs / manifest) と本文見出し (Purpose & Output Contract / Key Rules / Steps) を変数化した形で生成する
4. variable_contract に source_trace (どの brief フィールドから派生したか) を記録する

### 5.3 自己検証 checklist
- [ ] SKILL.md 行数が 170 行以下か
- [ ] frontmatter に responsibility_refs と manifest が含まれるか
- [ ] kind→template 対応表が schemas/ へ外出しされているか (本文は 1 行参照のみ)
- [ ] 具体値が変数化されているか (variable_contract に source_trace が残るか)
- [ ] 依存方向: 生成 SKILL.md が L7→L1 単方向参照を保持し逆参照を含まないか
- [ ] 決定論性: 同 brief 再実行で出力 sha256 が一致するか (validate-build-trace.py で検証)

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-build-skill (R1 phase)
- 後続 phase: responsibility-emit (R2)

### 6.2 並列性
- 単発実行 (R2 の前段として直列)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- SKILL.md (Markdown) と build_flow_coverage (JSON 部分集合)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM は以下のタスクのみ実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `{{skill_brief}}` を読み、SKILL.md 骨格を変数化形式で生成する。
出力は SKILL.md 本文 (Markdown) と build_flow_coverage[scaffold] エントリ (JSON) のみ。
余計な前置き・思考過程出力は禁止。
