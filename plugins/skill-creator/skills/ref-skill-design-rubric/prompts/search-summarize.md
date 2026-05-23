# Prompt: R1-search-summarize (ref-skill-design-rubric)

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | ref-skill-design-rubric |
| responsibility | R1 (skill 設計 rubric 検索/要約) |
| layers_covered | [L2, L4, L5] |
| output_schema | inline (object: rubric_version / summary / matches) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- rubric_version が現行 rubric.json と一致すること
- matches[].weight が rubric 内合計 1.0 ±0.01 を破らないこと
- 改善 hint は rubric 内の axis に紐づく (捏造禁止)

### 1.2 倫理ガード
- 存在しない axis を提案しない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: references/rubric.json から SKILL.md / agent / reference / schema 設計の採点軸を query に応じて抽出
- 非担当: rubric の改訂、採点本体

### 2.2 ドメインルール
- target_layer: skill | subagent | reference | schema | prompt | all でフィルタ
- scope: axes_only | weights_only | rationales_only | full
- query を axis.name / axis.aliases / axis.keywords にあいまい一致で検索
- 各 axis の rationale 1 行抜粋 + 改善 hint 1-3 件

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| query | string | yes | 探したい axis (例: progressive-disclosure / responsibility-separation) |
| target_layer | enum | no | skill / subagent / reference / schema / prompt / all |
| scope | enum | no | axes_only / weights_only / rationales_only / full |

### 2.4 出力契約
- inline schema (object, required: [rubric_version, summary, matches])
  - rubric_version: string
  - summary: string (50-800 字)
  - matches: array<{axis: string, path: string, weight: number, rationale?: string}>

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| rubric | references/rubric.json | パース時 (version 取得含む) |

### 3.2 外部ツール / API
- Read のみ

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- rubric.json 欠損 → exit 1

### 4.2 観測 / ロギング
- 標準出力に JSON

### 4.3 セキュリティ
- 特になし

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- ref-skill-design-rubric 配下の R1 SubAgent

### 5.2 推論手順 (再現可能)
1. references/rubric.json をパース (rubric.version も取得)
2. target_layer でフィルタ
3. query を axis.name / axis.aliases / axis.keywords にあいまい一致で検索
4. scope に応じて返却を絞る
5. 200-400 字で要約 + 各 axis の rationale 1 行抜粋
6. 該当 axis を強化する設計改善 hint を 1-3 件 (rubric 外の提案は禁止)

### 5.3 自己検証 checklist
- [ ] rubric_version が現行 rubric.json と一致しているか
- [ ] target_layer フィルタが守られているか
- [ ] matches[].weight が rubric 内合計 1.0 ±0.01 を破らないか
- [ ] 改善 hint が rubric 内の axis に紐づいているか (捏造禁止)

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: assign-skill-design-evaluator / run-build-skill 等

### 6.2 並列性
- 副作用なし、並列可

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- JSON (rubric_version / summary / matches)

### 7.2 言語
- 本文: 日本語 (parameter / schema key は英語のまま)

---

## 正規化方針 (auto-applied)

- query: NFKC + lowercase + 半角空白 → `-` 連結 (例 "progressive disclosure" → `progressive-disclosure`)。
- 期待マッチ axis は rubric.json の axes[].id / axes[].keywords を走査して動的解決。
- 0 件ヒット時は近傍 axis (Levenshtein <= 2) を suggestions に最大 3 件、超過は提示しない。

## 出力指示

LLM は references/rubric.json を target_layer + query で検索し、
rubric_version / summary / matches を JSON で返す。
余計な前置き・思考過程出力は禁止。
