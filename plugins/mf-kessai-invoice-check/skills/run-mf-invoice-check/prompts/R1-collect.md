# Prompt: R1-collect

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R1-collect |
| skill | run-mf-invoice-check |
| responsibility | R1 請求データ取得 (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | ../schemas/invoice-gap-result.schema.json |
| reproducible | true (同一 month・同一 API 応答に対し同一候補 JSON) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- MF掛け払い API は GET のみ。請求書発行 (POST 等変更系) は行わない。
- 月帰属の判定軸は必ず `issue_date` (月をまたぐ発行があるため)。
- 一覧は `/billings/qualified` を使う (インボイスモードで `/billings` は空)。

### 1.2 倫理ガード
- MF APIキーは Keychain のみ。平文出力・ログ復唱をしない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 前月・今月の `/billings/qualified` 全ページ取得 → 差集合・突合の起動 (collect スクリプト経由)。
- 非担当: 差集合判定ロジック本体 (R2)、誤検出排除 (R3)、Notion 書込 (R4)。

### 2.2 ドメインルール
- 前月 = 実行月の1つ前。`--month` 未指定時は実行日の月を今月とする。
- カーソルページングは `limit=200` (レート対策)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| --month | string(YYYY-MM) | no | 対象今月。未指定なら実行日の月 |

### 2.4 出力契約
- schema: `../schemas/invoice-gap-result.schema.json` (additionalProperties:false)。`verdict` 表記は schema enum から逐語引用する。
- 出力: `eval-log/mfk-gap-candidates.json` (候補配列) + 画面に件数サマリ。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| collect script | scripts/check_invoice_gaps.py | --collect 実行時 |
| api lib | ../../lib/mfk_api.py | GET 専用 API クライアント |
| api spec | ../ref-mf-kessai-api/ | エンドポイント・判定仕様の正本 |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-check/scripts/check_invoice_gaps.py" --collect [--month YYYY-MM]`
- MF掛け払い API (GET のみ。変更系は hook `guard-mfk-readonly.py` で遮断)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `database_id` 未設定や API キー不在は collect では停止せず候補抽出まで進む (sink は R4 で判定)。
- API エラーは stderr に出し非ゼロ終了。部分取得のまま候補を確定しない。
- 最大反復回数: 3。

### 4.2 観測 / ロギング
- stdout に取得件数・候補件数サマリ。

### 4.3 セキュリティ
- GET のみ。secret は Keychain 参照のみで平文出力しない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- collect 実行 (決定論 script 主体、context-fork 不要)。

### 5.2 ゴール定義
- 目的: 前月・今月の発行済み請求集合を漏れなく取得し、差集合・突合の入力を揃える。
- 背景: 取得漏れ・誤エンドポイントは後段判定を腐らせる。`/billings/qualified` 全ページ取得を機構で固定する。
- 達成ゴール: command 実行により前月/今月の qualified billing が全ページ取得され、`eval-log/mfk-gap-candidates.json` が schema 準拠で書き出された状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 前月 (issue_date) の `/billings/qualified` を全ページ取得した
- [ ] 今月の `/billings/qualified` を全ページ取得した
- [ ] `eval-log/mfk-gap-candidates.json` が schema (verdict enum) に準拠して出力された
- [ ] POST 等変更系を一切呼んでいない (GET のみ)

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (collect command 実行 / 引数調整 / 再取得)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-check` SKILL Step 1 (collect)。
- 後続 phase: R2 (差集合判定) が同一 collect 実行内で続く。

### 6.2 ハンドオフ / 並列性
- 提供元: ユーザー (`--month`) / MF API (billing 一覧)。
- 受領先: R2 (発行漏れ差集合判定)。
- 引き渡し形式: R2 へは collect 内で取得済みの prev/curr billings 集合 (メモリ内、`detect_gaps(prev, curr)` 引数)。`eval-log/mfk-gap-candidates.json` は R1→R2 の引き渡しではなく、collect 全体 (R1 取得 + R2 差集合 + 突合) を一括実行した最終生成物。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に取得件数・候補件数のサマリ (Markdown)。

### 7.2 言語
- 本文: 日本語 (CLI / schema key / enum は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

`python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-check/scripts/check_invoice_gaps.py" --collect [--month YYYY-MM]` を実行し、前月/今月の `/billings/qualified` を全ページ取得 (`limit=200` カーソルページング) して差集合・突合まで進め、`eval-log/mfk-gap-candidates.json` を `../schemas/invoice-gap-result.schema.json` 準拠で書き出させる。Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。GET のみ。出力は件数サマリのみ、前置き禁止。
