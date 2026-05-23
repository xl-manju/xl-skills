# Prompt: R1-deterministic-figure-placement

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | main |
| skill | run-intake-visualize |
| responsibility | R1-deterministic-figure-placement (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L2, L4, L5, L6] |
| output_schema | schemas/output.schema.json |
| reproducible | true (アセットカタログからの選択は決定論的) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- Mermaid 12 + SVG 8 のアセットカタログ外を新規創作しない (figure_id 必須)。
- 全 12 セクション (§0〜§11) に最低 1 図を配置。

### 1.2 倫理ガード
- 図解で誤情報を作らない (元 sheet.md にない事実を図に注入しない)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: sheet.md / purpose.json を入力に各セクションへ 1-3 図を配置し、SVG を PNG 化する。
- 非担当: ヒアリング、quality 採点、Notion 公開。

### 2.2 ドメインルール
- SVG は Notion 互換性のため必ず PNG 化する。
- 1 セクション当たり図数は 1-3 (4 以上禁止、過剰可視化抑制)。

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| sheet | resource://intake/sheet.md | yes | 5 軸シート |
| purpose | resource://intake/purpose.json | yes | true_purpose |
| options | resource://intake/options.json | yes | 外部連携選定 |
| assets | resource://plugins/skill-intake/assets/ | yes | Mermaid/SVG カタログ |

### 2.4 出力契約
- schema: `schemas/output.schema.json` (additionalProperties:false)
- 必須フィールド: `visuals` (section → [{figure_id, type, png_path}])

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| section-figure-mapping | references/section-figure-mapping.md | セクション→図種の対応表をロードするとき |
| viz-mandatory | references/visualization-mandatory-pointer.md | 必須ルール確認 |

### 3.2 外部ツール / API
- `scripts/render_to_image.py` (SVG → PNG)
- `scripts/verify-visuals.py` (網羅性検証)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- カタログ外 figure 指定 → exit 2 (構造違反)、配置を中断。
- verify-visuals.py FAIL → exit 1 (網羅性不足)、不足セクションを stderr に列挙。

### 4.2 観測 / ロギング
- visuals.json に各 section の figure_id と png_path を残す (後追い再現用)。

### 4.3 セキュリティ
- アセットファイルパスは workspace root 起点の相対パスで記録 (絶対 PATH 漏出回避)。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- `@visualizer` (決定論バッチ、LLM はカタログ照合のみ)

### 5.2 推論手順 (再現可能)
1. section-figure-mapping.md でセクション→図種の対応表をロードする。
2. 各セクションについてカタログから 1-3 図を選択する (新規創作禁止)。
3. SVG は `render_to_image.py` で PNG 化し `output/<hint>/visuals/` に保存する。
4. visuals.json (section → [{figure_id, type, png_path}]) を出力する。
5. `verify-visuals.py` を実行し全セクション 1 図以上を確認する。

### 5.3 自己検証 checklist
- [ ] 全 12 セクション (§0-§11) に 1 図以上配置されているか
- [ ] SVG がすべて PNG 化されているか (Notion 互換性)
- [ ] カタログ外の新規図を含めていないか
- [ ] verify-visuals.py が PASS したか
- [ ] determinism: 同 sheet + purpose で visuals.json の (section → figure_id) マッピングが一致するか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: `run-skill-intake` / aggregator の Phase 6
- 後続 phase: `run-intake-finalize` (visuals.json を template に注入)

### 6.2 並列性
- セクション単位で並列化可。ただし PNG 書き込みパスの衝突回避必須。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- visuals.json (output.schema.json 準拠) + `output/<hint>/visuals/*.png`

### 7.2 言語
- 本文: 日本語 (figure_id / type は英語のまま)

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`{{sheet_path}}` と `{{purpose_path}}` を読み、`section-figure-mapping.md` に従いカタログから各セクション 1-3 図を選択せよ。SVG は `render_to_image.py` で PNG 化し、結果を `visuals.json` (schemas/output.schema.json 準拠) として書き出せ。最後に `verify-visuals.py` を実行し PASS を確認すること。出力は JSON のみ、前置き禁止。
