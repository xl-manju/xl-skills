# 7層プロンプト Markdown テンプレ (正規形)

prompts/*.md の唯一の正規骨格。各 skill は本テンプレを写経し、内容を domain に置換する。
YAML 版は legacy フォールバック扱い (新規作成禁止)。

---

```markdown
# Prompt: <responsibility-id> (例: R1-republish-precheck)

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | <prompt 名 / kebab-case> |
| skill | <親 SKILL 名> |
| responsibility | <R1 / R2 …> (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, ...] |
| output_schema | schemas/<...>.schema.json |
| reproducible | true (同入力→同出力を保証) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- <ルール 1>
- <ルール 2>

### 1.2 倫理ガード
- <禁止事項 / 取扱注意データ>

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: <この prompt が果たす単一責務>
- 非担当: <他 prompt に委譲する責務>

### 2.2 ドメインルール
- <ドメイン制約 / 不変条件>

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| <name> | <type> | yes/no | <意味> |

### 2.4 出力契約
- schema: `schemas/<...>.schema.json` (additionalProperties:false)
- 必須フィールド: <列挙>

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| <id> | <path> | <タイミング> |

### 3.2 外部ツール / API
- <CLI / MCP / script>

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- <exit code 規約 / fallback>

### 4.2 観測 / ロギング
- <出力先 / 形式>

### 4.3 セキュリティ
- <secret 取扱 / PII 制約>

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- <agent 名 / context-fork 要否>

### 5.2 推論手順 (再現可能)
1. <step 1>
2. <step 2>
3. <step 3>

### 5.3 自己検証 checklist
- [ ] <観点 1>
- [ ] <観点 2>

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: <skill / manifest phase>
- 後続 phase: <次の prompt or hook>

### 6.2 並列性
- <並列可否 / 排他条件>

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- <Markdown / JSON / 図>

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

<具体的なタスク文。入力 placeholder は `{{...}}`。
出力は Layer 2.4 で宣言した schema に準拠した JSON / Markdown のみとする。
余計な前置き・後書き・思考過程出力は禁止。>
```

---

## 命名規則

- `prompts/<R-id>-<slug>.md` (例: `prompts/R1-precheck.md`)
- 1 ファイル = 1 責務 = 1 agent。複数責務を 1 ファイルにまとめない。
- 旧 `main.yaml` は責務分割後に削除 (legacy として残す場合は `prompts/_legacy/`)。

## 既定フォーマット方針

| 形式 | 用途 | 状態 |
|---|---|---|
| Markdown (`.md`) | 全新規 prompt | **既定** |
| YAML (`.yaml`) | 既存資産 / 機械生成 pipeline | 許容 (新規禁止) |
| JSON (`.json`) | tool args として埋め込む場合のみ | 限定 |

## skill-creator 連携

- `run-build-skill` の scaffold は本テンプレを写経して `.md` を生成する。
- `run-skill-create` の P0 lint は `prompts/*.md` を優先検出し、`.yaml` のみ存在する場合は warn を出す (block しない)。
- 詳細は `doc/ClaudeCodeスキルの設計書/23a-prefix-driven-internal-structure.md` の prompt 形式節を参照。
