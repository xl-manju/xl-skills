# Prompt: R3-verify

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> 本ファイルが R3-verify 責務の 7 層本文 SSOT 正本。実行アダプタは `../../../agents/mfk-gap-verifier.md` (本文を持たない薄アダプタ)。

## メタ

| key | value |
|---|---|
| name | R3-verify |
| skill | run-mf-invoice-check |
| responsibility | R3 二段確認 (誤検出排除) (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../schemas/invoice-gap-result.schema.json |
| reproducible | true (同一候補・同一 API 応答に対し同一確定リスト) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 独立 context (context:fork) でレビューする (Sycophancy/誤検出防止)。
- API は GET のみ (再取得は可、書き込みはしない)。
- 機械的に契約終了を判定しない。データ整合の誤検出のみ排除する。

### 1.2 倫理ガード
- MF APIキーは Keychain のみ。取引先データを外部送信しない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 各候補の「前月発行・今月未発行」が事実か、突合した商品名・金額が前月 billing と整合するかを検証し、誤検出候補を除外する。
- 非担当: 取得 (R1)、差集合判定 (R2)、Notion 書込 (R4)、契約終了判定 (人が請求要否列で実施)。

### 2.2 ドメインルール
- 誤検出 = 継続中なのに漏れ判定 / 商品名・金額の突合ミス等のデータ整合エラー。
- 確認は必要なら `lib/mfk_api.py` で `/billings/qualified` を再取得して行う (憶測しない)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| candidates | path | yes | `eval-log/mfk-gap-candidates.json` (R2 出力) |

### 2.4 出力契約
- schema: `../schemas/invoice-gap-result.schema.json` (additionalProperties:false)。
- `verdict` は schema enum から逐語引用する。
- 確定リストは `--finalize --exclude-ids <誤検出cid,...>` で `eval-log/mfk-gap-verified.json` に物質化する (sink 入力)。返答にはサマリ (入力候補数/確定数/誤検出除外数) を含める。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| candidates | eval-log/mfk-gap-candidates.json | 検証対象の入力 |
| api lib | ../../lib/mfk_api.py | `/billings/qualified` 再取得時 (GET) |
| api spec | ../ref-mf-kessai-api/ | 判定仕様の確認 |

### 3.2 外部ツール / API
- `python3` + `lib/mfk_api.py` (GET 専用)。
- 書き込み系は hook `guard-mfk-readonly.py` で遮断。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- API 再取得失敗時はその候補を確定せず保留 (憶測で確定しない)。
- 最大反復回数: 3。上限到達で確定不能なら未確定として上位へ差し戻す。

### 4.2 観測 / ロギング
- 入力候補数・確定数・除外数 (誤検出) をサマリ出力。

### 4.3 セキュリティ
- read-only。GET のみ。secret 平文出力しない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- `mfk-gap-verifier` (context:fork で起動、独立 context)。

### 5.2 ゴール定義
- 目的: 発行漏れ候補から誤検出 (データ整合エラー) を排除し、信頼できる確定リストを sink へ渡す。
- 背景: 親 context での自己レビューは Sycophancy により誤検出を見逃す。独立 context と API 再取得で根拠を機械的に確認する必要がある。
- 達成ゴール: 全候補が API 再取得で検証され、誤検出を除いた確定リスト (schema 準拠) が得られた状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 入力候補をすべて検証した (見落としなし)
- [ ] 各候補の「前月発行・今月未発行」を API 再取得で確認した (憶測なし)
- [ ] 突合した商品名・前月金額が前月 billing と整合する
- [ ] 契約終了の自動判定をしていない (データ整合の誤検出排除のみ)
- [ ] API は GET のみ・書き込みをしていない

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (候補列挙 / API 再取得 / 突合照合 / 除外)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

### 5.5 Self-Evaluation (停止ゲート)
返す前の停止ゲート (全て YES で完了)。**完全性**と**検証可能性**を主停止条件とする。本節が停止ゲートの SSOT 正本であり、アダプタ `mfk-gap-verifier.md` は本節を参照する。
- [ ] **完全性**: 入力候補をすべて検証した (見落としなし)
- [ ] **検証可能性**: 各候補の「前月発行・今月未発行」を API 再取得で確認した (憶測なし)
- [ ] **一貫性**: 突合した商品名・前月金額が前月 billing と整合し、契約終了の自動判定をしていない (データ整合の誤検出排除のみ)
- [ ] **参照専用**: API は GET のみ・書き込みをしていない

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-check` SKILL Step 3 (verify)。R2 の候補 JSON が入力。
- 後続 phase: R4 (Notion 投入)。

### 6.2 ハンドオフ / 並列性
- 提供元: R2 (schema enum で分類された候補リスト)。
- 受領先: R4 (Notion sink)。
- 引き渡し形式: 誤検出を除いた確定候補リスト (schema 準拠、sink 入力)。
- context:fork で独立起動 (親 context と分離)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 確定数・除外数 (誤検出) のサマリ (Markdown)。

### 7.2 言語
- 本文: 日本語 (CLI / schema key / enum は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`eval-log/mfk-gap-candidates.json` の各候補について、(1) 前月発行・今月未発行が事実か (必要なら `lib/mfk_api.py` で `/billings/qualified` を再取得して確認)、(2) 突合した商品名・前月金額が前月 billing と整合するか、を検証する。誤検出 (継続中なのに漏れ判定 / 突合ミス等) を特定する (契約終了の判定はしない)。

**確定リストの物質化 (二段確認の物理境界)**: 検証後、誤検出と判定した `customer_id` を集めて
`python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-check/scripts/check_invoice_gaps.py" --finalize --exclude-ids <cid1,cid2,...>` を実行し、確定リスト
`eval-log/mfk-gap-verified.json` を生成する (誤検出が無ければ `--exclude-ids` を省略)。この確定ファイルの存在が後段 sink の前提であり、生成しない限り `--sink` は fail-closed で停止する。`--finalize` は入力候補を schema 検証し、違反があれば exit 2 で確定を拒否する。

Layer 5 の完了チェックリストと L5.5 Self-Evaluation 停止ゲートを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。MF API は GET のみ。確定リスト生成は `--finalize` (ローカル書込, MF API 非変更) で行う。前置き禁止。
