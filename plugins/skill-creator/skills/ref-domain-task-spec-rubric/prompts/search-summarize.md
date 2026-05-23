# Prompt: R1-search-summarize (ref-domain-task-spec-rubric)

> 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の seven-layer-format.md を正本とする。
> Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | ref-domain-task-spec-rubric |
| responsibility | R1-search-summarize (task-spec rubric の検索/要約) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | inline (object: summary / matches / phase_coverage) |
| reproducible | true (同 query + 同 rubric.json → 同 matches[]) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **CONST_001 (version 明記)**: rubric.json の `version` を応答に明記する。
  - 目的: caller が後から rubric 改訂による結果差分を再現できるようにする。
- **CONST_002 (重み合計)**: matches[] の axis weight 合計が 1.0 ±0.01 を破らない。
  - 目的: 部分集合返却時に重みが歪んで採点が偏るのを防ぐ。
  - 背景: 過去に scope=weights_only で抜粋した結果、合計 0.6 のまま採点される事故があった。
- **CONST_003 (thresholds 3 段)**: thresholds は `pass / warn / fail` 3 段で揃える。
  - 目的: caller の判定ロジックを共通化する。

### 1.2 倫理ガード
- 存在しない axis / threshold を捏造しない。
- 未知 phase 番号は推定で補完せず `suggestions` に返す。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: references/rubric.json から task-spec を採点する axes / weights / pass-thresholds を query / task_phase に応じて抽出する。
- 非担当: rubric の改訂、採点本体、rubric_hash 再計算。

### 2.2 ドメインルール
- `task_phase` でフィルタ (該当 phase の axes のみ)。
- scope: `axes_only | weights_only | thresholds_only | full`。
- summary は 50-800 字、800 字超過時は truncate + 省略マーカー。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| query | string | yes | 探したい axis 名 / phase / 重み / 閾値 |
| task_phase | enum | no | phase1 ... phase13 / all (既定 all) |
| scope | enum | no | axes_only / weights_only / thresholds_only / full (既定 full) |

### 2.4 出力契約
- inline schema (object, required: [summary, matches, phase_coverage])
  - `summary`: string (50-800 字)
  - `matches`: array<{path: string, value: any}>
  - `phase_coverage`: array<string> (返却した axes が網羅する phase 名)

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| rubric | references/rubric.json | パース時 (version / axes 取得) |

### 3.2 外部ツール / API
- Read のみ。ネットワーク不使用。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- rubric.json 欠損 → exit 1 + stderr に欠損 path。
  - 目的: caller が rubric 配置不備を即座に検知できるようにする。

### 4.2 観測 / ロギング
- 標準出力に JSON。stderr は診断情報のみ。

### 4.3 セキュリティ
- 読み取り専用、外部送信なし。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- ref-domain-task-spec-rubric 配下の R1 SubAgent (context fork 推奨)。

### 5.2 推論手順 (再現可能)
1. references/rubric.json をパースし version を取得する。
2. `task_phase` でフィルタ (該当 phase の axes のみ)。
3. query に該当する keys を抽出する。
4. scope に応じて返却を絞る。
5. 200-400 字で要約 + JSON path を併記する。
6. 採点時の注意 (axis 間独立性 / 重み合計 = 1.0) を 1-3 件添える。

### 5.3 自己検証 checklist
- [ ] rubric.json の version が応答に明記されているか
- [ ] matches[] の weight 合計が 1.0 ±0.01 に収まるか
- [ ] task_phase フィルタが守られているか
- [ ] thresholds が pass/warn/fail 3 段で揃っているか
- [ ] summary が 50-800 字に収まっているか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: assign-skill-design-evaluator 等。
- 後続 phase: caller が matches[] を取り採点ロジックに利用。

### 6.2 並列性
- 副作用なし。並列実行可。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- JSON (summary / matches / phase_coverage)。

### 7.2 言語
- 本文: 日本語 (parameter / schema key は英語のまま)。

---

## 正規化方針 (auto-applied)

- phase 表記: `phase\s*\d+` / `P\d+` / `フェーズ\d+` を NFKC 後正規表現で `phase<N>` に統一。
- 代表 query 抽出は rubric.json の axes[].phase / axes[].keywords を動的に走査し上位 5 件 (固定列挙しない)。
- 未知 phase 番号は `suggestions` に返し、推定で補完しない。

## 出力指示 (LLM 実行時に読む箇所)

LLM は references/rubric.json を `{{task_phase}}` + `{{query}}` で検索し、scope に従って
`summary` / `matches` / `phase_coverage` を JSON で返す。
余計な前置き・後書き・思考過程出力は禁止。
