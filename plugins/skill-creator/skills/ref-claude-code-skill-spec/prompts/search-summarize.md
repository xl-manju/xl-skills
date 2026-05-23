# Prompt: R1-search-summarize (ref-claude-code-skill-spec)

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | ref-claude-code-skill-spec |
| responsibility | R1 (Claude Code Skill 仕様 検索/要約) |
| layers_covered | [L2, L4, L5] |
| output_schema | schemas/query-result.schema.json (任意) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 抽出は原文のまま改変しない (引用は逐語)
- 該当ゼロ時は matches: [] + suggestions を返す
- 出力 token budget は <= 2KB 推奨

### 1.2 倫理ガード
- false positive を含めない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: references/ から呼び出し元 query に該当する Claude Code Skill 仕様 (frontmatter / lifecycle / subagent / hook) を抽出
- 非担当: 仕様変更、Claude Code 本体の動作

### 2.2 ドメインルール
- score 降順に最大 5 件、重複は dedupe
- ヒット箇所の前後 ±10 行を抽出
- 要約は別フィールドに付ける (原文と分離)

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| query | string | yes | 知りたい仕様トピック (例 "disable-model-invocation の挙動") |
| scope | array | no | [frontmatter, lifecycle, subagent, hook]。未指定なら全 references 走査 |

### 2.4 出力契約
- schema: `schemas/query-result.schema.json` (任意。未配置なら text/markdown 可)
- 必須: matches[] + (該当ゼロ時) suggestions[]

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| resource_map | references/resource-map.yaml | scope 解決時 |

### 3.2 外部ツール / API
- Read / Grep のみ

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- references 欠損 → exit 1

### 4.2 観測 / ロギング
- 標準出力に JSON or markdown

### 4.3 セキュリティ
- 特になし

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- ref-claude-code-skill-spec 配下の R1 SubAgent

### 5.2 推論手順 (再現可能)
1. resource-map.yaml を読み、scope に該当する file をフィルタする
2. 各 file 内を query で keyword/章番号マッチし、ヒット箇所の前後 ±10 行を抽出
3. ヒットが複数なら score 降順に最大 5 件まで残し、重複は dedupe
4. 抽出は原文のまま改変しない (要約は別フィールド)
5. 1 件も無ければ matches: [] + suggestions (近傍 topic) を返す

### 5.3 自己検証 checklist
- [ ] query に対する false positive を含んでいないか
- [ ] 原文改変していないか (引用は逐語)
- [ ] 該当ゼロ時に suggestions を返したか
- [ ] 出力が呼び出し元の token budget (<= 2KB 推奨) に収まるか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: 任意 (Claude Code Skill 仕様を確認したい skill)

### 6.2 並列性
- 副作用なし、並列可

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- query-result JSON or markdown

### 7.2 言語
- 本文: 日本語 (parameter / schema key は英語のまま)

---

## 正規化方針 (auto-applied)

- 章番号: `^(\d{2,3})[a-z]?` を抽出し 3 桁 0 埋め (例 "03章" → "003"、"03a-foo" → "003a")。NFKC + lowercase 後に照合。
- 同義語: frontmatter ⇄ メタデータ / spec ⇄ 仕様 など references 内に明示された alias のみ採用 (新規 alias は生成しない)。
- 不一致は suggestions に NFKC 後 keyword を返し、勝手に補完しない。

## 出力指示

LLM は references/ を query で検索し、ヒット箇所の前後 ±10 行を逐語抽出して
最大 5 件を JSON で返す。該当ゼロは matches: [] + suggestions。
余計な前置き・思考過程出力は禁止。
