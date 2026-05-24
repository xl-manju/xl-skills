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
  - 目的: 同一骨格を多 skill で再利用可能にする
  - 背景: 固有名詞の直書きは保守不能と複製事故を生む
- kind→template 対応表を本文に再掲しない (schemas 参照のみ)
  - 目的: 単一情報源 (SSOT) を schemas/ に集約する
  - 背景: 表の二重管理は drift と矛盾を招く

### 1.2 倫理ガード
- secret / 個人識別子を骨格に埋め込まない
  - 目的: 流出リスクを構造的に排除する
  - 背景: SKILL.md は公開 plugin に同梱され得る

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: SKILL.md の骨格 (frontmatter + Purpose & Output Contract + Key Rules 参照 + Steps 見出し) を生成
- 非担当: R-id 別 prompt 生成 (R2)、template 選択 (R3)、trace 記入 (R4)

### 2.2 ドメインルール
- SKILL.md は 170 行以下
- frontmatter に `responsibility_refs` と `manifest` を含める
- kind→template 対応は `schemas/template-selection.schema.json#/selection_rules` を参照

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| skill_brief | path | yes | eval-log/skill-brief.json |
| template_selection_schema | path | yes | schemas/template-selection.schema.json |
| resource_map | path | yes | references/resource-map.yaml |

### 2.4 出力契約
- schema: `schemas/skill-build-trace.schema.json#/properties/build_flow_coverage`
- 必須フィールド: build_flow_coverage の scaffold セクション
- 形式: SKILL.md (Markdown) + build_flow_coverage[scaffold] (JSON)

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| brief | eval-log/skill-brief.json | 骨格生成開始時 |
| template_schema | schemas/template-selection.schema.json | kind→template 確認時 |
| resource_map | references/resource-map.yaml | 参照ファイル解決時 |

### 3.2 外部ツール / API
- Read / Write のみ (CLI / MCP 不使用)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- variable_contract に source_trace が残らない場合は exit 1
  - 目的: 再現性ゲート C2 を満たすため
  - 背景: trace 欠落は同入力→同出力保証を破壊する

### 4.2 観測 / ロギング
- 出力先: `eval-log/skill-build-trace.json#/build_flow_coverage`
- 形式: JSON Patch 部分集合

### 4.3 セキュリティ
- 固定 URL / owner / token を骨格に直書き禁止
  - 目的: secret 漏洩と環境固定化を防ぐ
  - 背景: 公開 plugin に同梱される前提

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- run-build-skill 配下の R1 SubAgent (context-fork 不要)

### 5.2 ゴール定義
- **目的**: brief から再利用可能な SKILL.md 骨格を機械再現性付きで吐く
- **背景**: 直書きと固定手順は drift / 複製事故を生むため変数化+ゴールシーク化が必須
- **達成ゴール**: brief を入力に schema 準拠の骨格 Markdown + scaffold trace が成立し、再実行で sha256 一致する状態

### 5.3 完了チェックリスト (停止条件)
- [ ] SKILL.md が 170 行以下で frontmatter に responsibility_refs / manifest を含む
- [ ] kind→template 対応は schemas 参照 1 行のみで本文に表が無い
- [ ] 実行系 kind は `## ゴールシーク実行` を持ち固定 `### Step N:` を羅列していない (`ref-*` 除く)
- [ ] `{{goal}}` / `{{purpose_background}}` / `{{generated_checklist}}` が brief 由来で埋まりリテラル未残存
- [ ] 具体値は全て変数化され variable_contract.source_trace に brief フィールド由来が記録されている
- [ ] 依存方向 L7→L1 単方向 (逆参照 0)
- [ ] 同 brief 再実行で出力 sha256 一致 (validate-build-trace.py exit 0)

### 5.4 実行方式 (動的手順生成ループ)
1. 未充足チェックリスト項目を特定
2. 解消手順をその場で立案 (brief 読み / schema 参照 / 骨格生成 / source_trace 記録 のいずれか)
3. 立案手順を実行し成果物を更新
4. チェックリストで自己評価し全項目充足まで反復 (上限: Layer 4 最大反復回数)
5. 上限到達時は exit 1 + Layer 4 エスカレーション

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-build-skill (R1 phase)
- 後続 phase: responsibility-emit (R2)

### 6.2 並列性
- 単発実行 (R2 の前段として直列)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- SKILL.md (Markdown) + build_flow_coverage[scaffold] (JSON 部分集合)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

Layer 5.2 のゴール+5.3 完了チェックリストを唯一の停止条件とし、5.4 ループで
動的に手順を生成・実行・自己評価する。入力 `{{skill_brief}}` を Read し、SKILL.md
骨格を変数化形式で生成、kind→template は `{{template_selection_schema}}` の
selection_rules を参照する。出力は次の 2 つのみとする:

1. `SKILL.md` 本文 (Markdown / 170 行以下 / frontmatter 含む)
2. `build_flow_coverage[scaffold]` エントリ (JSON / source_trace を含む)

余計な前置き・後書き・思考過程出力は禁止。
