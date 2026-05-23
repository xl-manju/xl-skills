# Prompt: R1-search-summarize (ref-yaml-spec-fetcher)

> 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の seven-layer-format.md を正本とする。
> Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | ref-yaml-spec-fetcher |
| responsibility | R1-search-summarize (YAML spec キャッシュの検索/要約) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/query-result.schema.json |
| reproducible | true (同 query + 同 cache → 同 matches[] + staleness) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **CONST_001 (鮮度判定)**: `yaml-spec-cache.md` の `last_fetched:` が 30 日超過なら `staleness=true` を付与する。
  - 目的: caller が古い仕様を最新と誤認するのを防ぐ。
  - 背景: Claude Code 公式 frontmatter は不定期に追加/変更される。
- **CONST_002 (safe-fail)**: キャッシュ未配置時は `matches: []` + `staleness=missing` を返し exit 0。
  - 目的: 週次 fetch 失敗時も caller の orchestration を止めない。
- **CONST_003 (キャッシュ更新は範囲外)**: 本 prompt はキャッシュを書き換えない。
  - 目的: 読み取り責務に閉じ込めて副作用を遮断する。

### 1.2 倫理ガード
- 古いキャッシュを最新と偽らない (staleness フラグ必須)。
- ネットワーク fetch を本 prompt 内で実行しない (別 skill 責務)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: references/yaml-spec-cache.md (公式 frontmatter 仕様のローカルキャッシュ) と spec-diff-history.md から query に該当する仕様 / 差分を返す。
- 非担当: キャッシュの更新 (別 skill)、仕様の改訂、公式 doc fetch。

### 2.2 ドメインルール
- query をフィールド名 / 日付でマッチし、定義行と例を抽出する。
- spec-diff-history.md に該当フィールドの変更履歴があれば併記する。
- `staleness` は `true / false / missing` の 3 値。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| query | string | yes | 確認したい frontmatter フィールド名 / 仕様キーワード / 取得日付 |
| scope | array | no | [yaml-spec-cache, spec-diff-history]。未指定なら両方走査 |

### 2.4 出力契約
- schema: `schemas/query-result.schema.json` (推奨配置)。
- 必須フィールド: `matches[]` / `staleness` (true / false / missing)。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| resource_map | references/resource-map.yaml | scope 解決時 |
| cache | references/yaml-spec-cache.md | 仕様抽出時 (last_fetched 取得) |
| diff | references/spec-diff-history.md | 履歴併記時 |

### 3.2 外部ツール / API
- Read / Grep のみ。ネットワーク不使用 (fetch は別 skill)。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- キャッシュ未配置 → `matches: []` + `staleness=missing` (exit 0)。
  - 目的: 週次 fetch 失敗時にも caller 側 orchestration を止めない。
  - 背景: 初回 fetch 前は cache 物理ファイルが存在しない設計のため exit 1 にはしない。

### 4.2 観測 / ロギング
- 標準出力に JSON。stderr は診断情報のみ (staleness 判定根拠など)。

### 4.3 セキュリティ
- 読み取り専用、外部送信なし。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- ref-yaml-spec-fetcher 配下の R1 SubAgent (context fork 推奨)。

### 5.2 推論手順 (再現可能)
1. resource-map.yaml で対象を解決する。
2. `yaml-spec-cache.md` の `last_fetched:` を確認し、30 日超過なら `staleness=true` を付与する。
3. query をフィールド名 / 日付でマッチし、定義行と例を抽出する。
4. spec-diff-history.md に該当フィールドの変更履歴があれば併記する。
5. キャッシュ未配置の場合は `matches: []` + `staleness=missing` を返す。

### 5.3 自己検証 checklist
- [ ] `last_fetched` の鮮度判定 (30 日閾値) を正しく行ったか
- [ ] キャッシュと現行 03 章の差分が history に整合しているか
- [ ] キャッシュ未配置時に safe-fail (`staleness=missing` + exit 0) したか
- [ ] 推奨再取得 URL を warn に添えたか (閾値超過時)

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: 任意 (frontmatter 仕様確認が必要な skill)。
- 後続 phase: caller が staleness=true 検出時は別 skill (週次 fetch) を起動。

### 6.2 並列性
- 副作用なし。並列実行可。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- query-result JSON (matches[] + staleness)。

### 7.2 言語
- 本文: 日本語 (parameter / schema key は英語のまま)。

---

## 正規化方針 (auto-applied)

- staleness 閾値: 既定 30 日 (`STALE_DAYS` env で上書き可)。`last_fetched` から `now - STALE_DAYS` を超えたら warn。
- 差分履歴: ISO8601 (YYYY-MM-DD) で正規化、ローカル時刻文字列は UTC に変換して比較。
- 閾値超過時は warn + 推奨再取得 URL を返し、勝手にキャッシュ更新を実行しない。

## 出力指示 (LLM 実行時に読む箇所)

LLM は `yaml-spec-cache.md` と `spec-diff-history.md` を `{{query}}` で検索し、
`matches[]` + `staleness` フラグ + 変更履歴を JSON で返す。
余計な前置き・後書き・思考過程出力は禁止。
