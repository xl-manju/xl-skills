# Prompt: R1-search-summarize (ref-claude-code-skill-spec)

> 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の seven-layer-format.md を正本とする。
> Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | ref-claude-code-skill-spec |
| responsibility | R1-search-summarize (Claude Code Skill 仕様の検索/要約) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/query-result.schema.json (任意配置) |
| reproducible | true (同 query + 同 references → 同 matches[]) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **CONST_001 (逐語抽出)**: 抽出は references 原文のまま改変しない。
  - 目的: 仕様の意味改変を防ぎ、呼び出し元が安全に判断できる根拠を保証する。
  - 背景: 要約で paraphrase すると frontmatter のキー名や制約値が暗黙に揺らぐ事故が頻発した。
- **CONST_002 (空ヒット時の suggestions 必須)**: 該当ゼロは `matches: []` + `suggestions` を返す。
  - 目的: 呼び出し元 LLM が即座に query 改善 or scope 拡大を判断できるようにする。
  - 背景: 黙って空配列を返すと caller が「該当無し」と「fetch 失敗」を区別できない。
- **CONST_003 (token budget)**: 出力は <= 2KB 目安。
  - 目的: progressive disclosure を維持し caller の context を圧迫しない。

### 1.2 倫理ガード
- false positive (query に擦っただけの周辺記述) を matches に混ぜない。
- 公式仕様と local 拡張を混同しない (frontmatter-fields.md の official/local 列を保持)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: references/ から query に該当する Claude Code Skill 仕様 (frontmatter / lifecycle / subagent / hook) を抽出して要約する。
- 非担当: 仕様の改訂、Claude Code 本体の挙動推論、SKILL.md 生成。

### 2.2 ドメインルール
- スコア降順に最大 5 件、重複は dedupe (path + 行範囲が同一なら 1 件に統合)。
- ヒット箇所は前後 ±10 行を抽出し、要約は別フィールド (`summary`) に分離する。
- frontmatter フィールドは official / local 区別を必ず保持する。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| query | string | yes | 知りたい仕様トピック (例 "disable-model-invocation の挙動") |
| scope | array | no | [frontmatter, lifecycle, subagent, hook]。未指定なら全 references 走査 |

### 2.4 出力契約
- schema: `schemas/query-result.schema.json` (任意。未配置なら markdown 可)。
- 必須フィールド: `matches[]` (path / excerpt / summary)、該当ゼロ時 `suggestions[]`。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| resource_map | references/resource-map.yaml | scope 解決時 (file 索引取得) |
| frontmatter | references/frontmatter-fields.md | frontmatter scope 時 |
| lifecycle | references/lifecycle.md | lifecycle scope 時 |
| subagent_hook | references/subagent-and-hook.md | subagent / hook scope 時 |

### 3.2 外部ツール / API
- Read / Grep のみ。ネットワーク不使用。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- references 欠損 → exit 1 + stderr に欠損ファイル path を出力。
  - 目的: caller が再 fetch / skill 配置不備を即座に検知できるようにする。
  - 背景: silent fallback で空 matches を返すと caller が誤った仕様を信じる事故になる。

### 4.2 観測 / ロギング
- 標準出力に query-result JSON または markdown。stderr は診断情報のみ。
  - 目的: stdout を機械パース可能に保ち、caller が JSON 抽出に困らないようにする。

### 4.3 セキュリティ
- 読み取り専用、外部送信なし。secret/PII を扱わない。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- ref-claude-code-skill-spec 配下の R1 SubAgent (context fork: 推奨。caller context を汚さない)。

### 5.2 推論手順 (再現可能)
1. resource-map.yaml を読み、scope に該当する file をフィルタする。
2. 各 file 内を query で keyword / 章番号マッチし、ヒット箇所の前後 ±10 行を抽出する。
3. ヒットが複数なら score 降順に最大 5 件まで残し、path + 行範囲が同一なら dedupe する。
4. 抽出は原文のまま改変せず、要約は別フィールド `summary` に分離する。
5. 1 件も無ければ `matches: []` + 近傍 topic の `suggestions` を返す。

### 5.3 自己検証 checklist
- [ ] query に対する false positive を含んでいないか
- [ ] 原文改変していないか (逐語抽出)
- [ ] official / local 区別を保持したか
- [ ] 該当ゼロ時に suggestions を返したか
- [ ] 出力が token budget (<= 2KB 目安) に収まるか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: 任意 (Claude Code Skill 仕様を確認したい skill / manifest phase)。
- 後続 phase: caller 側で matches[] を読み skill 設計判断に利用。

### 6.2 並列性
- 副作用なし。同一 references に対して並列実行可。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- query-result JSON (推奨) または markdown。

### 7.2 言語
- 本文: 日本語 (parameter / schema key は英語のまま)。

---

## 正規化方針 (auto-applied)

- 章番号: `^(\d{2,3})[a-z]?` を抽出し 3 桁 0 埋め (例 "03章" → `003`、"03a-foo" → `003a`)。NFKC + lowercase 後に照合。
- 同義語: frontmatter ⇄ メタデータ / spec ⇄ 仕様 など references 内に明示された alias のみ採用 (新規 alias 生成禁止)。
- 不一致は `suggestions` に NFKC 後 keyword を返し、推定で補完しない。

## 出力指示 (LLM 実行時に読む箇所)

LLM は references/ を `{{query}}` で検索し、ヒット箇所の前後 ±10 行を逐語抽出して
最大 5 件を JSON で返す。該当ゼロは `matches: []` + `suggestions`。
余計な前置き・後書き・思考過程出力は禁止。
