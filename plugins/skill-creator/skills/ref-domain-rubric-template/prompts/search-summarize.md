# Prompt: R1-search-summarize (ref-domain-rubric-template)

> 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の seven-layer-format.md を正本とする。
> Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | ref-domain-rubric-template |
| responsibility | R1-search-summarize (rubric.json 部分集合の検索/要約) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | inline (object: summary / matches / references) |
| reproducible | true (同 query + 同 rubric.json → 同 matches[]) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **CONST_001 (version 明記)**: rubric.json の `version` を応答に必ず含める。
  - 目的: caller が後から rubric 改訂による結果差分を再現できるようにする。
  - 背景: version 無しの応答は採点結果の再現性を失わせる主因だった。
- **CONST_002 (捏造禁止)**: constraint 違反例は実 rubric から派生させる。
  - 目的: 存在しない axis / constraint で caller を誤誘導しない。
- **CONST_003 (summary 長制限)**: summary は 50-800 字に収める。
  - 目的: caller の token budget を保護する。

### 1.2 倫理ガード
- 存在しない axis / constraint を捏造しない。
- alias は rubric.json の `aliases:` ブロックに記載のものだけ採用。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: references/rubric.json から query に該当する部分集合 (axes / weights / constraints) を返す。
- 非担当: rubric の改変、ドメイン採点本体、rubric_hash の再計算。

### 2.2 ドメインルール
- scope: `rubric_full | axes_only | weights_only | constraints_only`。
- matches[].path は JSON Pointer 風 (`#/axes/0/name` 等) に正規化する。
- summary は 50-800 字、800 字超過時は truncate + 省略マーカー。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| query | string | yes | 探したい domain / axis / weight キー |
| scope | enum | no | rubric_full / axes_only / weights_only / constraints_only (既定 rubric_full) |
| locale | enum | no | ja / en (既定 ja) |

### 2.4 出力契約
- inline schema (object, required: [summary, matches, references])
  - `summary`: string (50-800 字)
  - `matches`: array<{path: string, value: any}>
  - `references`: array<string> (rubric.json 内の参照 path)

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| rubric | references/rubric.json | パース時 (version 取得含む) |

### 3.2 外部ツール / API
- Read のみ。ネットワーク不使用。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- rubric.json 欠損 → exit 1 + stderr に欠損 path。
  - 目的: caller が rubric 配置不備を即座に検知できるようにする。
  - 背景: 空 rubric を黙認すると採点結果が常に空 axes になり debug 困難。

### 4.2 観測 / ロギング
- 標準出力に JSON。stderr は診断情報のみ。

### 4.3 セキュリティ
- 読み取り専用、外部送信なし。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- ref-domain-rubric-template 配下の R1 SubAgent (context fork 推奨)。

### 5.2 推論手順 (再現可能)
1. references/rubric.json をパースし version を取得する。
2. query に該当する keys を deep search で抽出する (ネスト含む)。
3. scope に応じて返却部分集合を絞る。
4. 200-400 字で要約 + JSON 参照パス (`#/axes/0/name` 等) を併記する。
5. domain 適用時の注意点 (constraint 違反例) を実 rubric から 1-3 件添える。

### 5.3 自己検証 checklist
- [ ] rubric.json の version が応答に明記されているか
- [ ] matches[].path が JSON Pointer 風に正規化されているか
- [ ] scope (axes_only 等) の絞り込みが守られているか
- [ ] constraint 違反例が実 rubric から派生しているか (捏造禁止)
- [ ] summary が 50-800 字に収まっているか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: assign-* (rubric を domain 適用する skill)。
- 後続 phase: caller が matches[] を取り採点に利用。

### 6.2 並列性
- 副作用なし。並列実行可。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- JSON (summary / matches / references)。

### 7.2 言語
- 本文: 日本語 (parameter / schema key は英語のまま)。

---

## 正規化方針 (auto-applied)

- query は NFKC + lowercase 後、`domain:<name>` / `rubric:<axis>` の prefix を分離して照合。
- domain alias: references/rubric.json 内の `aliases:` ブロックのみ採用。
- 期待 matches.path は rubric.json の axes[].path から動的解決 (本文に列挙しない)。

## 出力指示 (LLM 実行時に読む箇所)

LLM は references/rubric.json を `{{query}}` で検索し、scope に従って絞り込んだ
`summary` / `matches` / `references` を JSON で返す。
余計な前置き・後書き・思考過程出力は禁止。
