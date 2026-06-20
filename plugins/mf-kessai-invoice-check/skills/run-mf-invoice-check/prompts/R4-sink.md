# Prompt: R4-sink

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R4-sink |
| skill | run-mf-invoice-check |
| responsibility | R4 Notion 投入 (冪等 upsert) (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../schemas/invoice-gap-result.schema.json |
| reproducible | true (同一確定リストの再投入は重複行を作らず冪等) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- upsert キーは `customer_id × 対象年月`。既存あれば更新、なければ作成 (重複行を作らない)。
- `database_id` 未設定なら停止し `run-mf-invoice-db-setup` を案内する。

### 1.2 倫理ガード
- Notion トークンは Keychain のみ (MF APIキーとは別 entry)。平文出力しない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 確定候補リストを Notion DB に `customer_id × 対象年月` キーで冪等 upsert する。
- 非担当: 取得 (R1)、差集合判定 (R2)、誤検出排除 (R3)、DB 構築 (run-mf-invoice-db-setup)。

### 2.2 ドメインルール
- 事実列 (fact_columns) = API 由来の値 + 実行監査メタ (取引先企業名/レコード種別/顧客ID/対象年月/判定/商品名/前月金額/今月金額/発行日/更新日/確認済み日時/チェック実行ID/発行漏れ件数/金額変動件数/チェック件数合計)。月次サマリ行は件数3列を持ち、明細行は空欄。
- 管理列 (managed_columns) = 人の運用列 (請求要否/対応状況/チェック済/備考)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| --input | path | no | 確定 JSON。未指定時は既定の確定リスト `eval-log/mfk-gap-verified.json` (R3 の `--finalize` 出力)。不在なら fail-closed (exit 2)。 |
| --force-unverified | flag | no | 二段確認を経ない未検証候補を直接投入 (非推奨。明示時のみ許可) |

### 2.4 出力契約
- schema: `../schemas/invoice-gap-result.schema.json` (additionalProperties:false)。`verdict` は schema enum から逐語引用する。
- 出力: Notion DB に候補反映 + 月次サマリ行 + ページ本文の実行履歴追記 + 画面に created/updated 件数。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| sink script | scripts/check_invoice_gaps.py | --sink 実行時 |
| sink lib | ../../lib/notion_invoice_sink.py | Notion upsert の実体 |
| config | .mf-kessai-config.json | `database_id` 読込 |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-check/scripts/check_invoice_gaps.py" --sink [--input <確定JSON>]`
- Notion API (DB query / page create / page update)。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `database_id` 未設定なら停止し db-setup を案内 (書き込まない)。
- 最大反復回数: 3。

### 4.2 観測 / ロギング
- created / updated 件数、対象年月、チェック実行IDを画面に表示。

### 4.3 セキュリティ
- Notion トークンは Keychain のみ。平文出力しない。

### 4.4 管理列不可侵 (CONST)
- 本体: Notion へは事実列と実行監査メタ (fact_columns) のみ書き込み、管理列 (managed_columns = 請求要否/対応状況/チェック済/備考) には一切触れない。
- 目的: 人が記入した運用判断を機械が上書きしないことを保証する。
- 背景: 契約終了等の請求不要判断は API で判別できず人が請求要否列で管理するため、再投入で管理列を消すと運用が破壊される。
- 月次完了履歴: `顧客ID=__monthly_summary__ × 対象年月` の `月次サマリ` 行を毎回 upsert し、件数3列 (発行漏れ件数/金額変動件数/チェック件数合計) を埋め、各ページ本文へ `確認済み日時` / `チェック実行ID` / 件数を追記する。候補0件でも確認済み月を残す。同一 `チェック実行ID` の履歴ブロックは既存なら追記せず冪等スキップする (過去証跡は保持)。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- sink 実行 (決定論 script 主体、context-fork 不要)。

### 5.2 ゴール定義
- 目的: 確定候補を Notion DB に冪等 upsert し、要確認リストの SSOT を更新する。
- 背景: 再実行での重複行や管理列上書きは運用を壊す。upsert キーと事実列限定書込を機構で固定する。
- 達成ゴール: command 実行により確定候補と月次サマリが `customer_id × 対象年月` キーで冪等 upsert され、管理列が不可侵のまま事実列/監査メタのみ更新され、ページ本文に実行履歴が追記された状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `database_id` が config に設定されている (未設定なら停止し db-setup 案内)
- [ ] 確定候補が `customer_id × 対象年月` キーで upsert された (重複行なし)
- [ ] 月次サマリ行 (`__monthly_summary__ × 対象年月`) が upsert された
- [ ] 各ページ本文に `確認済み日時` / `チェック実行ID` / 件数の履歴が追記された
- [ ] 事実列/監査メタ (fact_columns) のみ書き込み、管理列 (managed_columns) に触れていない
- [ ] created / updated 件数、対象年月、チェック実行IDが画面に表示された

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (config 確認 / sink command 実行 / 件数確認)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-check` SKILL Step 4 (sink)。R3 の確定リストが入力。
- 後続 phase: なし (ユーザー提示で終端)。

### 6.2 ハンドオフ / 並列性
- 提供元: R3 (誤検出を除いた確定候補リスト)。
- 受領先: ユーザー (画面の要確認リスト) + Notion DB (冪等 upsert)。
- 引き渡し形式: Notion DB 行 (事実列/監査メタのみ更新) + ページ本文の実行履歴 + 画面の created/updated サマリ。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に要確認リスト + created/updated 件数 + 対象年月 + チェック実行ID (Markdown)。

### 7.2 言語
- 本文: 日本語 (列名 / CLI / schema key / enum は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-check/scripts/check_invoice_gaps.py" --sink [--input <確定候補JSONのpath>]` を実行し、確定候補を `customer_id × 対象年月` キーで Notion DB に冪等 upsert させる (既存は更新、なければ作成、重複行を作らない)。同時に `顧客ID=__monthly_summary__ × 対象年月` の月次サマリ行を upsert し、各ページ本文に `確認済み日時` / `チェック実行ID` / 件数の履歴を追記する。`--input` 未指定時は既定で確定リスト `eval-log/mfk-gap-verified.json` (R3 の `--finalize` 出力) を読む。**確定リストが不在なら exit 2 で fail-closed** し、二段確認 (verify→finalize) を先に実施するよう促す (未検証候補を直接投入するのは `--force-unverified` 明示時のみ)。sink 入口で入力 JSON を schema 検証し、違反 (period_ym 形式不正等) があれば exit 2 で停止する。事実列/監査メタ (fact_columns) のみ書き込み、管理列 (managed_columns = 請求要否/対応状況/チェック済/備考) には一切触れない (L4.4 CONST)。`database_id` 未設定なら停止し `run-mf-invoice-db-setup` を案内する。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。出力は created/updated 件数、対象年月、チェック実行ID、要確認リストのみ、前置き禁止。
