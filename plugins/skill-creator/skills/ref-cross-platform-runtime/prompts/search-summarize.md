# Prompt: R1-search-summarize (ref-cross-platform-runtime)

> 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の seven-layer-format.md を正本とする。
> Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | search-summarize |
| skill | ref-cross-platform-runtime |
| responsibility | R1-search-summarize (OS 別挙動 / 禁止 CLI の検索/要約) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | schemas/query-result.schema.json (任意配置) |
| reproducible | true (同 query + 同 references → 同 matches[]) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **CONST_001 (禁止 CLI 整合)**: 抽出した CLI は forbidden-clis.md の最新行と一致させる。
  - 目的: 古い行を誤って許容と表示し host OS で壊れる事故を防ぐ。
  - 背景: forbidden 表は変動するため、抽出時に正本との一致をチェックしないと drift が発生する。
- **CONST_002 (OS 表記正規化)**: mac / macOS / darwin 等の表記揺れを正規化する。
  - 目的: caller 側のマッチ判定を 1 表現に統一して誤判定を防ぐ。
- **CONST_003 (代替コマンド欠落禁止)**: 禁止行を返す際は alternative 列を欠落させない。
  - 目的: caller が即時に置換できるようにする。

### 1.2 倫理ガード
- 禁止 CLI を「許容」と誤表示しない (warn フラグを必ず付与)。
- 推定で alternative を生成しない (forbidden-clis.md 記載分のみ)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: references/ (os-matrix.md, forbidden-clis.md) から query (例 "macOS で使えない CLI") に該当する記述を抽出・要約する。
- 非担当: 禁止リストの追加・改訂、CLI の実行。

### 2.2 ドメインルール
- 出力は per-OS テーブル形式に正規化 (mac / linux / windows カラムを保持)。
- ヒット行と前後 ±5 行、および同表の alternative 列を併せて抽出する。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| query | string | yes | 知りたい OS 別挙動 / 禁止 CLI 名 / 代替コマンド名 |
| scope | array | no | [os-matrix, forbidden-clis]。未指定なら両方走査 |

### 2.4 出力契約
- schema: `schemas/query-result.schema.json` (任意)。
- 必須フィールド: `matches[]` (per-OS テーブル)、該当ゼロ時 `suggestions[]`。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| resource_map | references/resource-map.yaml | scope 解決時 |
| os_matrix | references/os-matrix.md | OS 別挙動抽出時 |
| forbidden | references/forbidden-clis.md | 禁止 CLI 確認時 |

### 3.2 外部ツール / API
- Read / Grep のみ。ネットワーク不使用。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- references 欠損 → exit 1 + stderr に欠損 path。
  - 目的: silent fallback で「禁止 CLI が無い」と誤報するのを防ぐ。
- 該当ゼロは exit 0 で `matches: []` + 近傍 topic の `suggestions`。

### 4.2 観測 / ロギング
- 標準出力に query-result JSON。stderr は診断情報のみ。

### 4.3 セキュリティ
- 読み取り専用、外部送信なし。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- ref-cross-platform-runtime 配下の R1 SubAgent (context fork 推奨)。

### 5.2 推論手順 (再現可能)
1. resource-map.yaml で対象 references を絞り込む。
2. query を CLI 名 / OS 名 / 機能名で keyword マッチする。
3. 該当行と前後 ±5 行、および同表の alternative 列を併せて抽出する。
4. 出力を per-OS テーブル形式に正規化 (mac / linux / windows カラムを保持)。
5. 該当ゼロなら `matches: []` + 近傍 topic の `suggestions`。

### 5.3 自己検証 checklist
- [ ] 抽出した CLI が forbidden-clis.md の最新行と一致しているか
- [ ] OS 表記揺れ (mac / macOS / darwin) を正規化したか
- [ ] alternative 列を欠落させていないか
- [ ] 禁止行に warn フラグを付与したか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: 任意 (cross-platform 確認が必要な skill)。
- 後続 phase: caller が CLI 選定 / 代替コマンドへの置換に利用。

### 6.2 並列性
- 副作用なし。並列実行可。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- query-result JSON (per-OS テーブル形式)。

### 7.2 言語
- 本文: 日本語 (parameter / schema key は英語のまま)。

---

## 正規化方針 (auto-applied)

- OS 名: NFKC + lowercase 後、`{mac, macos, darwin, osx} → darwin` / `{win, windows, win32} → windows` / `{linux, ubuntu, debian, alpine} → linux` を内蔵 alias で集約。
- 上記以外の値は `suggestions` に元 keyword を返し、勝手に補完しない。
- 表記揺れ吸収は references 明示分のみ。未定義 alias の自動拡張禁止。

## 出力指示 (LLM 実行時に読む箇所)

LLM は references/ (os-matrix, forbidden-clis) を `{{query}}` で検索し、
per-OS テーブル形式で JSON を返す。該当ゼロは `matches: []` + `suggestions`。
余計な前置き・後書き・思考過程出力は禁止。
