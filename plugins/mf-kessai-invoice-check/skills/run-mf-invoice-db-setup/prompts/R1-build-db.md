# Prompt: R1-build-db

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R1-build-db |
| skill | run-mf-invoice-db-setup |
| responsibility | R1 Notion DB構築 (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../schemas/notion-db-schema.json |
| reproducible | true (既存 database_id があれば冪等スキップ) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- DB プロパティ定義は `../schemas/notion-db-schema.json` (事実列 / 管理列 / upsert_key) を唯一の正本とする。
- 冪等: `.mf-kessai-config.json` に `database_id` が既にあれば新規作成せず既存を利用する (重複 DB 防止)。
- 再構築時も既存データ・人が記入した管理列を破壊しない。

### 1.2 倫理ガード
- Notion トークン (Keychain `notion-api-key.xl-skills` / `xl-skills`) を出力・ログに残さない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: Notion DB の初回作成と `database_id` の config 記録。
- 非担当: スキーマ検証 (R2 責務)、発行漏れチェック本体 (`run-mf-invoice-check` 責務)。

### 2.2 ドメインルール

| 用語 | 定義 |
|---|---|
| 事実列 | API 由来の列 (取引先企業名/顧客ID/対象年月/判定/商品名/前月金額/今月金額/発行日/更新日)。 |
| 管理列 | 人が運用する列 (請求要否/対応状況/チェック済/備考)。初回に作成するが以後 `run-mf-invoice-check` は触らない。 |
| status 型不可 | Notion API は status 型を新規作成できないため「対応状況」は select で表現する。 |

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| parent_page_id | string | yes | `.mf-kessai-config.json` の `notion.parent_page_id`。インテグレーション共有済みの親ページ。 |

### 2.4 出力契約
- schema: `../schemas/notion-db-schema.json` (properties / fact_columns / managed_columns / upsert_key が正本)
- 成果: `.mf-kessai-config.json` の `notion.database_id` に作成済み DB の id が記録される。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| schema | ../schemas/notion-db-schema.json | プロパティ物質化時 |
| config | .mf-kessai-config.json | parent_page_id 取得 / database_id 記録時 |
| token | Keychain notion-api-key.xl-skills / xl-skills | Notion API 認証時 |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-db-setup/scripts/build_notion_db.py"` (Notion API で DB 作成 + database_id 記録)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `notion.parent_page_id` が空 → **停止**し、ユーザーに「親ページをインテグレーションに共有し page_id を設定」するよう依頼する (達成ゴールの前提)。
- 再実行・再構築時も既存データ・管理列の記入を破壊しない (冪等動作で保護)。

### 4.2 観測 / ロギング
- 作成成功時は記録した `database_id` を 1 行で報告する。既存利用時はその旨を明示する。

### 4.3 セキュリティ
- Notion トークンは Keychain からのみ取得し、標準出力・config に書き戻さない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- DB 構築 executor (非対話バッチ)。実体: `scripts/build_notion_db.py`。

### 5.2 ゴール定義
- 目的: 発行漏れチェック結果を投入できる Notion DB を初回に用意する。
- 背景: API 由来の事実列と人が運用する管理列を分離した設計を確立し、後段の冪等 upsert が安定して書き込める土台を作る。
- 達成ゴール: 設計通りの DB が作成され `database_id` が config に記録され、後続 R2 の検証が全プロパティ PASS を返す状態 (前提: parent_page_id 設定済み)。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] `notion.parent_page_id` が設定されている (空なら停止しユーザーへ共有依頼)
- [ ] 事実列・管理列が schema 通りに DB に存在する (status 型は使わず select で表現)
- [ ] `database_id` が `.mf-kessai-config.json` に記録される (既存があれば冪等スキップ)
- [ ] 再実行で既存データ・管理列の記入が破壊されていない
- [ ] R2 の検証が全プロパティ PASS を返す

### 5.4 実行方式
- 固定手順を持たない。未充足チェック項目を特定→解消手順を都度立案 (config 読込 / DB 作成 / database_id 記録 など)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。
- 逸脱時: parent_page_id 未設定なら Layer 4.1 に従い停止しユーザーへ差し戻す。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-db-setup` SKILL.md ゴールシークループ。
- 後続 phase: R2 (DBスキーマ検証) が本責務の `database_id` を検証対象に取る。

### 6.2 ハンドオフ / 並列性
- 直列: 本責務が `notion.database_id` (提供元) を config に記録し、R2 (受領先) がそれを検証対象として読む。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- stdout に作成/既存利用の結果と `database_id` を 1 行報告。parent_page_id 未設定時は共有依頼メッセージ。

### 7.2 言語
- 本文: 日本語 (schema key / プロパティ名 / CLI は原文のまま)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`.mf-kessai-config.json` の `notion.parent_page_id` を確認せよ。空なら Layer 4.1 に従い停止し、親ページのインテグレーション共有と page_id 設定を依頼する。設定済みなら `database_id` の有無を確認し、無ければ `python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-db-setup/scripts/build_notion_db.py"` を実行して DB を作成し `database_id` を config に記録、既存があれば冪等スキップする。`../schemas/notion-db-schema.json` を正本とし status 型は使わず select で表現する。前置き禁止。
