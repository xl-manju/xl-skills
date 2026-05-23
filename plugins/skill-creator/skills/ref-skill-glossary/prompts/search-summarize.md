# Prompt: R1-search-summarize (ref-skill-glossary)

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | ref-skill-glossary |
| responsibility | R1 (用語集 検索/要約) |
| layers_covered | [L2, L4, L5] |
| output_schema | schemas/query-result.schema.json (任意) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 正式表記は見出しから取得する (本文の表記揺れに引きずられない)
- 該当ゼロは Levenshtein 距離 <= 2 の近傍語を suggestions に入れる

### 1.2 倫理ガード
- 用語定義を捏造しない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: references/terms.md から query (用語) の定義行を抽出し、正式表記・同義語・参照章番号を返す
- 非担当: 用語の追加・改訂

### 2.2 ドメインルール
- 完全一致 → 部分一致の順でマッチ
- 同義語/別表記は aliases[] に分離
- 定義段落 (見出し直下〜次見出しまで) を全文抽出

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| query | string | yes | 確認したい用語 (日本語/英語どちらも可) |
| scope | array | no | [terms] 固定 (将来拡張用) |

### 2.4 出力契約
- schema: `schemas/query-result.schema.json` (任意。未配置時は markdown 可)
- 必須: matches[] (term / definition / aliases / chapter_refs) + (該当ゼロ時) suggestions[]

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| terms | references/terms.md | 全件パース時 |

### 3.2 外部ツール / API
- Read / Grep のみ

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- terms.md 欠損 → exit 1

### 4.2 観測 / ロギング
- 標準出力に JSON or markdown

### 4.3 セキュリティ
- 特になし

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- ref-skill-glossary 配下の R1 SubAgent

### 5.2 推論手順 (再現可能)
1. terms.md を読み、見出し行に対し query を完全一致 → 部分一致の順でマッチ
2. ヒット用語の定義段落 (見出し直下〜次見出しまで) を全文抽出
3. 同義語/別表記は aliases[] に分離
4. 該当ゼロなら Levenshtein 距離 <= 2 の近傍語を suggestions に入れる

### 5.3 自己検証 checklist
- [ ] 用語の正式表記を見出しから取得しているか (本文の表記揺れに引きずられないか)
- [ ] aliases を本文から漏れなく拾ったか
- [ ] 該当ゼロ時に suggestions を返したか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: 任意 (用語確認したい skill)

### 6.2 並列性
- 副作用なし、並列可

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- query-result JSON or markdown

### 7.2 言語
- 本文: 日本語 (parameter / schema key は英語のまま)

---

## 正規化方針 (auto-applied)

- alias: references/terms.md の `aliases:` 行 (日英対) に明示されたペアのみ採用。
- 章番号: `^(\d{2,3})[a-z]?` を抽出して 3 桁 0 埋めで照合 (例 "01章" / "01-overview" → `001`)。
- 未収録 term は suggestions に NFKC 後の元語を返し、推定訳を生成しない。

## 出力指示

LLM は references/terms.md を query で検索し、term / definition / aliases /
chapter_refs を JSON で返す。該当ゼロは matches: [] + Levenshtein 近傍 suggestions。
余計な前置き・思考過程出力は禁止。
