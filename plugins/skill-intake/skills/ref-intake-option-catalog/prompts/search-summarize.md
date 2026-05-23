# Prompt: R1-catalog-lookup-and-options-emit

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | ref-intake-option-catalog |
| responsibility | R1-catalog-lookup-and-options-emit (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L2, L5, L6] |
| output_schema | schemas/options.schema.json |
| reproducible | true (カタログ照合は決定論的) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- カタログを Read-only で参照、新規連携は追加しない。
- tier=required の連携が selected から欠けてはならない。

### 1.2 倫理ガード
- ユーザー却下時は `reason` を必ず記録 (恣意的除外の防止)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: purpose.json の true_purpose.verb_object を入力に、integration カタログから候補連携を引き tier 付きで options.json を生成。
- 非担当: 連携の実装、認証情報取得、Notion 公開。

### 2.2 ドメインルール
- tier は `required | optional` の 2 値。required は欠けたら exit 非 0。
- options.json は `selected_integrations[]` と `rejected[{integration_id, reason}]` を必ず含む。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| purpose | resource://intake/purpose.json | yes | true_purpose.verb_object を含む |
| integration-catalog | resource://ref-intake-option-catalog/references/integration-catalog-pointer.md | yes | カタログ実体への pointer |
| tier-criteria | resource://ref-intake-option-catalog/references/tier-criteria.md | yes | tier 判定基準 |

### 2.4 出力契約
- schema: `schemas/options.schema.json`
- 必須フィールド: `selected_integrations[]`, `rejected[{integration_id, reason}]`

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| catalog-pointer | references/integration-catalog-pointer.md | カタログ参照前 |
| tier-criteria | references/tier-criteria.md | tier 付与時 |

### 3.2 外部ツール / API
- AskUserQuestion (候補提示と選択取得)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 必須連携がユーザーに却下された → exit 1 (warn)、stderr で再考を促す。
- カタログ不在 → exit 3。

### 4.2 観測 / ロギング
- rejected[].reason をすべて options.json に残す (監査用)。

### 4.3 セキュリティ
- 連携の API キー / トークンはこの責務では扱わない。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- `@option-presenter` (対話あり、AskUserQuestion 経由)

### 5.2 推論手順 (再現可能)
1. purpose.json から `verb_object` / `time_freed_intent` を抽出する。
2. integration-catalog-pointer.md 経由でカタログを Read-only で参照する。
3. tier-criteria.md に従い候補に `tier=required|optional` を付与する。
4. ユーザーに提示し選択を取得、rejected には `reason` を必須記録する。
5. options.json を出力する。

### 5.3 自己検証 checklist
- [ ] 必須 (tier=required) 連携が全て selected_integrations に含まれているか
- [ ] rejected 各項目に reason が記録されているか
- [ ] カタログ未掲載の連携を追加していないか (Read-only 遵守)
- [ ] 出力が options.schema.json に適合するか
- [ ] determinism: 同 purpose.json と同ユーザー選択履歴で options.json (selected_integrations + rejected) が一致するか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: `run-skill-intake` の Phase 6 (options 選定)
- 後続 phase: `run-intake-visualize` / `run-intake-next-action`

### 6.2 並列性
- AskUserQuestion は 1 問ずつ (並列禁止)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- options.json (options.schema.json 準拠)

### 7.2 言語
- 本文: 日本語 (integration_id / tier 値は英語)

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`{{purpose_json_path}}` を読み、integration カタログから候補連携を抽出、tier-criteria に従い tier を付与せよ。ユーザー提示と選択取得後、rejected には reason を必須で記録し、options.json (schemas/options.schema.json 準拠) を出力すること。前置き禁止。
