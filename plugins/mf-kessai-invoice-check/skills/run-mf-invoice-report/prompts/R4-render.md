# Prompt: R4-render

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R4-render |
| skill | run-mf-invoice-report |
| responsibility | R4 月次レポートDBへ非破壊冪等upsert (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | (schema なし・notion_report_sink.py の stdout I/O 契約が正本) |
| reproducible | true (同一分類結果に対し同一 upsert) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- **DB 構築/配置/冪等 upsert は `scripts/notion_report_sink.py` (C06) が所有**。DB 生成・行 upsert を自作しない (DB 生成は build_notion_db 再利用・行 upsert は C06 が実体)。
- 月次レポート DB は**対象月ごとに find-or-create**。対象月 DB が実在すれば再利用し二重 DB を作らない (`month_db_reused=true`)。月跨ぎは新しい月 DB を指定トグル配下へ append 作成し、newest-on-top の意図位置 (`intended_index`) を `placement` で開示し、過去月 DB を保全する。
- **非破壊マージ**: 同月再実行は入力同定 {取引先 × 契約ID × 商品} と stored key (取引先名, 商品名) で同一行を 1 行へ収束 (重複行 0)。契約ID違いは要対応優先で collapse し `collapsed_multi_contract` に計上する。以前 run で書いた行は今回入力に無くても当月 DB から削除しない (`deleted` 常時 0・clear-then-insert でない)。
- **列順 SSOT (固定 7 列)**: [漏れチェック(select), 取引先名(title), 商品名(rich_text), 先月の金額(number/yen), 今月の金額(number/yen), 先月と今月の比較(rich_text), コメント(rich_text)]。金額は税抜。C06 の `COLUMN_ORDER` が正本。
- MF掛け払い API は GET のみ。Notion 書込 (POST/PATCH/PUT/DELETE) は `notion_transport._write_gap` がレート間隔を挟む。
- トグルブロック ID (`notion.report_toggle_block`) 未設定は `--apply` 時に fail-closed (exit 2)。dry-run はトグル未走査で完走する。

### 1.2 倫理ガード
- Notion トークンは Keychain のみ (MF APIキーとは別 entry)。平文出力・ログ復唱をしない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: R2 (C05) の分類済みレポート行を C06 (`notion_report_sink.py`) に渡し、対象月の月次レポート DB を find-or-create して 7 列行を**非破壊冪等 upsert** する。R3 で差し戻し (reinstate) があれば上流是正→再分類後の行を渡す。
- 非担当: MF実績・verdict 収集 (R1)、状態遷移分類 (R2=C05)、二段確認 (R3 sub-agent)。DB スキーマ定義・列型写像は C06/build_notion_db の責務。

### 2.2 ドメインルール (C06 が実装済み・ここで再実装しない)
- **find-or-create**: 対象月 DB を指定ページ『請求書発行チェック』(論理キー `report_parent_page`) 配下の指定トグル見出し2ブロック (論理キー `report_toggle_block`) の子として title『請求漏れ比較レポート YYYY-MM』で探索。実在すれば再利用・無ければ作成する。
- **配置**: newest-on-top の意図位置 (`intended_index`) を既存 child_database の YYYY-MM から算出し報告するが、Notion API は任意位置 insert 不可のため実配置は末尾 append (fallback=title の YYYY-MM で識別)。差は sink 出力の `placement` で開示。
- **入力同定と persist**: 入力行の同定は {取引先 × 契約ID × 商品}。ただし固定 7 列に契約ID 列は無く、当月 DB 内の 1 行は (取引先名, 商品名) で回収される (contract_id は persist しない=C06 の `_stored_key`)。同一対象月・同一取引先・同一商品は要対応優先で 1 行へ収束し、契約ID違いの collapse は stdout の `collapsed_multi_contract` で観測する。
- **非破壊 upsert**: 既存行あり→PATCH (title は送らない)・無し→POST。入力に無い nullable 事実列は明示クリアして stale を残さないが、行そのものは削除しない (非破壊マージ)。各行は try/except で隔離し個別失敗は skipped に計上して継続する。
- 取引先名 (title) が空の行は skip する (title 必須)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| --rows | path(JSON) | yes | C05 の分類済みレポート行 JSON list |
| --target | string(YYMM) | yes | 対象月 (例 2606)。月次 DB の title・一意キーになる |
| --apply | flag | no | 実書き込みを行う。未指定 (dry-run) は Notion を叩かず計画のみ返す |
| --config | path | no | 設定 JSON パス (省略時は既定 + ローカル上書き) |

### 2.4 出力契約
- 出力: stdout に upsert 結果 JSON `{created, updated, skipped, deleted(=0), collapsed_multi_contract, month_db_id, month_db_reused, placement}`。dry-run は `dry_run:true` + `planned_rows`。
- exit code: 0=OK / 1=部分失敗 (行 skip) / 2=fail-closed (target 不正・トグル未設定・rows 不正)。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| sink engine | `$CLAUDE_PLUGIN_ROOT/scripts/notion_report_sink.py` | find-or-create + 非破壊冪等 upsert の実体 (run / find_or_create_month_db / upsert_report_rows) |
| DB builder | `$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-db-setup/scripts/build_notion_db.py` | DB 生成・列型写像 (build_property) の再利用元 |
| transport | `$CLAUDE_PLUGIN_ROOT/lib/notion_transport.py` | HTTP 単一正本。書込レート間隔 _write_gap (MFK_NOTION_WRITE_GAP) |
| config | mf-kessai-config.default.json + .mf-kessai-config.json | notion.{report_parent_page, report_toggle_block} 読込 (配布既定 + ローカル上書き) |

### 3.2 外部ツール / API
- `python3 "$CLAUDE_PLUGIN_ROOT/scripts/notion_report_sink.py" --rows <ROWS> --target <YYMM> [--apply] [--config <PATH>]`
- Notion API (トグル子ブロック list / DB find-or-create / page create/update)。書込系は `_write_gap` のレート間隔付き。MF へは書かない。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- target 不正・トグルブロック ID 未設定・rows 不正なら C06 が exit 2 (fail-closed)。書き込まない。
- 各行は try/except で個別隔離。1 行の HTTP400/timeout を skipped に計上して残りを継続する (silent cap 禁止)。
- **skill 層のゲート**: 月次 DB 反映を含む `--apply` は dry-run と R3 二段確認が完了済みであることを示す `--verified` を skill が要求する (誤投入防止)。
- 最大反復回数: 3。

### 4.2 観測 / ロギング
- created/updated/skipped/deleted(=0) 件数 + collapsed_multi_contract + month_db_id + month_db_reused + placement (意図位置 vs 実配置 append)。dry-run は planned_rows。

### 4.3 セキュリティ
- Notion トークンは Keychain のみ。平文出力しない。MF API は GET のみ (本 sink から MF へ POST/PATCH/DELETE を発行しない)。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- render 実行 (決定論 script 主体、context-fork 不要)。

### 5.2 ゴール定義
- 目的: 分類済みレポート行を当月レポート DB へ非破壊冪等 upsert し、月次履歴を DB 単位で保全する (過去月 DB を残す)。
- 背景: 全消し再投入や過去月 DB の破壊は月次履歴を壊す。対象月ごとの find-or-create + 非破壊マージ (deleted 0) + stored key 収束 (重複行 0) + newest-on-top 意図位置開示を機構で固定する。
- 達成ゴール: command 実行により当月 DB が find-or-create され、7 列行が入力同定 {取引先×契約ID×商品} と stored key (取引先名,商品名) で 1 行へ収束して非破壊 upsert され、月跨ぎで新しい月 DB が append 作成され newest-on-top の意図位置が開示され過去月 DB が保全され、Notion 書込にレート間隔が挟まれた状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] R2 の分類済みレポート行 JSON を `--rows` に渡し `--target <YYMM>` を指定して C06 を実行した
- [ ] 対象月 DB を find-or-create した (実在すれば再利用・二重 DB を作らない=month_db_reused で確認)
- [ ] 7 列行を入力同定 {取引先×契約ID×商品} と stored key (取引先名,商品名) で 1 行へ収束させ非破壊冪等 upsert した (重複行 0・deleted 0・契約ID違いは `collapsed_multi_contract` に計上)
- [ ] 月跨ぎで新しい月 DB が指定トグル配下へ append 作成され、newest-on-top の意図位置が placement で開示され、過去月 DB が保全された
- [ ] 取引先名 (title) 空の行を skip した / 個別失敗を skipped に計上して継続した
- [ ] トグルブロック ID 未設定なら `--apply` 時に exit 2 で fail-closed した
- [ ] `--apply` は dry-run と R3 二段確認完了 (--verified 相当) の後にだけ実行した
- [ ] created/updated/skipped/deleted + month_db_id + placement を画面に表示した

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (config/トグル ID 確認 / dry-run で計画確認 / --apply 実行 / 件数確認)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-report` SKILL Step 4 (render)。R3 で二段確認した分類済みレポート行が入力。
- 後続 phase: なし (ユーザー提示で終端)。

### 6.2 ハンドオフ / 並列性
- 提供元: R2 (C05 分類済みレポート行) + R3 (二段確認・差し戻し反映済み)。config (report_parent_page/report_toggle_block 論理キー)。
- 受領先: 月次レポート DB (対象月 DB へ 7 列行を非破壊冪等 upsert) + ユーザー (画面の件数・placement サマリ)。
- 引き渡し形式: `notion_report_sink.py --rows <ROWS> --target <YYMM> [--apply]` → upsert 結果 JSON。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に created/updated/skipped/deleted(=0) 件数 + collapsed_multi_contract + month_db_id + month_db_reused + placement (意図位置 vs 実配置) + 対象月のサマリ (Markdown)。dry-run は planned_rows。

### 7.2 言語
- 本文: 日本語 (列名 / CLI / schema key / enum / path は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

R2 の分類済みレポート行 JSON をファイルに用意し、`python3 "$CLAUDE_PLUGIN_ROOT/scripts/notion_report_sink.py" --rows <ROWS> --target <YYMM> [--apply] [--config <PATH>]` を実行する。既定は dry-run (Notion を叩かず計画のみ)。月次レポート DB 反映を含む `--apply` は、dry-run と R3 二段確認が完了済みであることを skill が `--verified` で確認した後にだけ使う (誤投入防止)。

C06 は対象月 DB を指定ページ『請求書発行チェック』(論理キー `report_parent_page`) 配下の指定トグル見出し2ブロック (論理キー `report_toggle_block`) の子として title『請求漏れ比較レポート YYYY-MM』で find-or-create し (実在すれば再利用・二重 DB を作らない)、7 列行 (漏れチェック/取引先名=title/商品名/先月の金額/今月の金額/先月と今月の比較/コメント・金額税抜・列順固定) を入力同定 {取引先 × 契約ID × 商品} と stored key (取引先名,商品名) で **非破壊冪等 upsert** する。同月再実行は同一行を 1 行へ収束 (重複行 0)、契約ID違いは要対応優先で collapse し `collapsed_multi_contract` に計上する。以前 run の行は今回入力に無くても削除しない (deleted 常時 0=非破壊マージ)。月跨ぎは新しい月 DB を append 作成し、newest-on-top の意図位置を placement で開示し、過去月 DB を保全する。**DB 生成・行 upsert を自作せず C06 を呼び出すだけ**にする。

トグルブロック ID が未設定なら `--apply` 時に exit 2 で fail-closed する (dry-run は完走)。Notion 書込は `notion_transport._write_gap` が `MFK_NOTION_WRITE_GAP` のレート間隔を挟む。任意位置 insert は Notion API に無いため実配置は末尾 append となり、意図位置との差は sink 出力の `placement` で開示される。

Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を立案→実行→自己評価→全項目充足まで反復する。出力は created/updated/skipped/deleted 件数 + collapsed_multi_contract + month_db_id + placement + 対象月のサマリのみ、前置き禁止。
