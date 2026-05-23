# Prompt: R1-search-summarize (ref-task-context-map)

> 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の seven-layer-format.md を正本とする。
> Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | ref-task-context-map |
| responsibility | R1-search-summarize (task 文脈 → 章番号マップの検索/要約) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/query-result.schema.json |
| reproducible | true (同 query + 同 task-context-map.yaml → 同 matches[]) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **CONST_001 (実在チェック)**: `chapter_refs` のパスは `doc/ClaudeCodeスキルの設計書/` 配下で実在を確認する。
  - 目的: caller が動的ロード時に「ファイル無し」エラーで止まらないようにする。
  - 背景: yaml だけ更新して設計書側を rename すると参照崩れが起きやすい。
- **CONST_002 (安定 sort)**: 同 priority 内の順序は安定 sort で再現性確保する。
  - 目的: 同 query で順序がブレない (snapshot test に必要)。
- **CONST_003 (上限 5 件)**: 複数ヒットなら priority 降順、最大 5 件。
  - 目的: caller の context 圧迫を防ぐ。

### 1.2 倫理ガード
- 存在しない章番号を返さない。
- 未マッチ keyword を推定で類義語置換しない (`suggestions` に返す)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: references/task-context-map.yaml から task 文脈に対応する設計書章番号を抽出し、動的ロード対象として返す。
- 非担当: 設計書本体の改訂、動的ロード実行、章本文の取得。

### 2.2 ドメインルール
- query を `trigger_keywords / verbs / domains` にマッチする。
- `chapter_refs[]` (章番号 + パス) を抽出する。
- 上限 5 件、超過は切り捨て (priority 同値時は安定 sort)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| query | string | yes | タスク種別 / 動詞 / キーワード (例 "skill 命名", "lint 失敗") |
| scope | array | no | [task-context-map] 固定 |

### 2.4 出力契約
- schema: `schemas/query-result.schema.json` (推奨配置)。
- 必須フィールド: `matches[]` (chapter_refs 含む)、該当ゼロ時 `suggestions[]`。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| resource_map | references/resource-map.yaml | scope 解決時 |
| map | references/task-context-map.yaml | パース時 |

### 3.2 外部ツール / API
- Read のみ。ネットワーク不使用。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- map 欠損 → exit 1 + stderr に欠損 path。
  - 目的: caller が動的ロード判定不能のまま続行するのを防ぐ。
- 該当ゼロは exit 0 で `matches: []` + 近傍 trigger を `suggestions` に入れる。

### 4.2 観測 / ロギング
- 標準出力に JSON。stderr は診断情報のみ。

### 4.3 セキュリティ
- 読み取り専用、外部送信なし。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- ref-task-context-map 配下の R1 SubAgent (context fork 推奨)。

### 5.2 推論手順 (再現可能)
1. task-context-map.yaml を読み、context entries を走査する。
2. query を entry の `trigger_keywords / verbs / domains` にマッチする。
3. ヒット entry の `chapter_refs[]` (章番号 + パス) を抽出して返す。
4. 複数ヒットなら priority 降順、最大 5 件まで保持する (同 priority は安定 sort)。
5. 該当ゼロなら近傍 trigger を `suggestions` に入れる。

### 5.3 自己検証 checklist
- [ ] chapter_refs のパスが `doc/ClaudeCodeスキルの設計書/` 配下で実在しているか
- [ ] 同 priority 内の順序を安定 sort で再現性確保したか
- [ ] 上限 5 件を超えていないか
- [ ] 該当ゼロ時に suggestions を返したか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: 動的ロード対象章を判定したい skill (run-skill-create 等)。
- 後続 phase: caller が `chapter_refs[]` を取り設計書動的ロードに利用。

### 6.2 並列性
- 副作用なし。並列実行可。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- query-result JSON。

### 7.2 言語
- 本文: 日本語 (parameter / schema key は英語のまま)。

---

## 正規化方針 (auto-applied)

- 語幹化: NFKC + lowercase 後、英語は末尾 `-ing/-ed/-s` を剥がす、日本語は活用語尾 (する/した/しない) を剥がす。
- 日英 alias: references/task-context-map.yaml の `aliases:` ブロックのみ採用、新規対応は作らない。
- 未マッチ keyword は `suggestions` に NFKC 後の元語を返し、推定で類義語に置換しない。

## 出力指示 (LLM 実行時に読む箇所)

LLM は task-context-map.yaml を `{{query}}` で検索し、priority 降順最大 5 件の
`chapter_refs` を JSON で返す。該当ゼロは `matches: []` + `suggestions`。
余計な前置き・後書き・思考過程出力は禁止。
