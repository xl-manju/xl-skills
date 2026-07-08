# Prompt: R1-collect

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | R1-collect |
| skill | run-mf-invoice-report |
| responsibility | R1 対象月決定 + 前月/今月 MF実績取得 + per-月verdict収集 (1 prompt = 1 責務 = 1 agent) |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| output_schema | (schema なし・C05 mfk_period_report.py の入力 I/O 契約が正本) |
| reproducible | true (同一 target・同一 API 応答に対し同一 per-月 verdict 入力) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- MF掛け払い API は GET のみ。変更系 (POST/PATCH/DELETE) は一切行わない (hook `guard-mfk-readonly.py` でも遮断)。
- 月帰属の判定軸は必ず `transaction.date` (取引日・月末締め)。「6月分の請求書」は取引日 `2026-06-30` の請求で、発行日が翌月月初でも 6月分として扱う。
- **今月 = 直近締め済みの請求対象月** (実行日カレンダー月の前月)。例: 2026-07-02 実行 → 今月=`2606` (2026-06分)・先月=`2605` (2026-05分)。対象月決定は `mfk_period_report.resolve_target_months` の規約に一致させる (自作の月計算を発明しない)。
- **per-月 verdict は既存 `lib/mfk_reconcile.py` の出力を消費するのみ** (SUPPRESS_ENDED / SUPPRESS_ANNUAL / MATCH_ANNUAL / REVIEW_ENDED_NO_BASIS 等)。C05 が消費する verdict を R1 で再照合・再パースしない (終了根拠判定 SSOT=mfk_reconcile)。
- 取引先の突合キーは既存 `mfk_reconcile.normalize`/`extract_names` で正規化して表記揺れを吸収する (自作正規化を発明しない)。

### 1.2 倫理ガード
- MF APIキー / Notion トークンは Keychain のみ (別 entry)。平文出力・ログ復唱をしない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: 対象月 (今月/先月) を決定し、前月・今月の全取引先 MF発行実績を参照専用 GET で取得、既存 reconcile engine で per-月 verdict を収集し、取引先×商品で状態遷移 (今月あり×前月あり / 今月あり×前月なし / 今月なし×前月なし / 今月なし×前月あり) を抽出する。差分に現れた**該当取引先のみ** 12 ヶ月分の発行履歴を追加取得し、請求確認シート由来の契約終了月も収集する。最終的に C05 (`mfk_period_report.py`) が読む入力 JSON (`curr-verdicts` / `prev-verdicts` / `lookback-12mo` / `contract-end`) を組む。
- 非担当: 前月↔今月の状態遷移分類・事情コメント生成 (R2=C05)、二段確認 (R3 sub-agent)、Notion 書込 (R4=C06)。

### 2.2 ドメインルール
- 候補取得は**取引先単位**で絞り、分類照合とコメント根拠は**取引先×商品単位**で行う。同一取引先・同一商品に複数契約があるときのみ契約ID (`contract_id`) を disambiguator に足す (C05 の `_needs_disambiguation` と同じ規約)。
- 12 ヶ月遡りは**差分該当取引先のみ**に限定する (全件遡らない=API 負荷最小化)。`--lookback-12mo` には差分該当分だけを渡す前提。
- **12 ヶ月遡りのデータ源は MF掛け払い API の発行実績 (`transaction.date` 履歴) であり、請求確認シートではない**。シートは `--contract-end` (契約終了月=二次情報) の源にすぎず、シートの開始月 (例: 2605 開始) は 12 ヶ月遡りの可否と無関係。前月なし今月あり (新規/年→月切替) は「12ヶ月前の年契約一括→月額自動切替」の可能性が高い (C3) ため、**シートの開始月を理由に 12 ヶ月遡りを省略しない**。MF 実績自体が 12 ヶ月前まで存在しない場合 (口座開設が新しい等) のみ遡り不可で、そのときは省略理由を「MF実績が YYMM 開始のため」と源を正しく特定して明示する (シートと取り違えない)。省略した場合、C05 は前月なし今月あり行のコメントへ『12ヶ月ルックバック未実行→年→月切替か真の新規か未確認』を焼き、stderr に警告を出す (silent skip の禁止)。
- per-月 verdict 行の各要素は C05 が消費するキーを保持する: `verdict` / `customer` (または `取引先`) / `product` (または `商品`) / `contract_id` / `evidence`(desc/amount) / `現行単価` 等の金額 / トライアル信号のための canon 前の生商品名 (`商品生名`/`product_raw`) や `確認内容`。
- 契約終了月 (`--contract-end`) は二次情報。C05 は `has_end_basis` 由来の既存 verdict を一次源にし、構造化列『契約終了月』は cross-check に使う (根拠なき終了月を抑制に使わない)。
- **【既知の限界・未実装 (GAP-R1-COLLECT-CURR-PRESENT)】curr の非請求月 suppress 行の curr-present 化**: reconcile は非請求月にも `SUPPRESS_OFFMONTH`/`SUPPRESS_ONESHOT`/`SUPPRESS_ANNUAL` を算出するが、`--curr-verdicts` が DB2 スナップショット由来だとこの抑制行が persist されず落ち、C05 で `curr=None` になる。C05 は③年契約(prev=MATCH_ANNUAL 識別的)と①MATCH_ENDED_FINAL(終端識別的)を prev.verdict で症状救済済みだが、⑤隔月/単発 (prev=MATCH_MONTHLY 非識別的) の curr=None は『対象外月(正常)』と『真の月次漏れ(要対応)』が原理的に分離不能ゆえ、現状は安全側で⑥要対応へ落ちる (過剰報告)。**根治は本 R1 収集層で「reconcile が返す全 rec (SUPPRESS_* 含む) を `--curr-verdicts` に persist して curr-present 化する」ことだが未実装**。実装時の副契約: suppress 行に正金額 evidence を載せない (C05 `_is_issued` が True 化し継続発行に誤分類されるのを防ぐ)。追跡=handoff `GAP-R1-COLLECT-CURR-PRESENT`。
- `status=canceled` かつ商品名が残る 0円明細は取消証跡として保持する (単純 0円除外にしない・`build_mf_index` が inactive へ残す)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| --target | string(YYMM) | no | 今月=対象月 (例 `2606`)。省略時は実行日から直近締め済み月を導出。YYMM 不正は fail-closed |

### 2.4 出力契約
- R1 単体の成果物: C05 が読む入力 JSON ファイル群 (`curr-verdicts`/`prev-verdicts`/任意 `lookback-12mo`/`contract-end`)。各 JSON は per-月 verdict 行の list もしくは `{"rows":[...]}` 形 (C05 の `_rows_of` が受ける形)。
- 画面には対象月 (今月/先月) と収集件数サマリ (`[collect] 今月=YYMM 先月=YYMM / MF顧客 N社 / 差分該当 N社 12ヶ月遡り`) を出す。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| api lib | `$CLAUDE_PLUGIN_ROOT/lib/mfk_api.py` | GET 専用 API クライアント (`iter_all` / `get`) |
| reconcile engine | `$CLAUDE_PLUGIN_ROOT/lib/mfk_reconcile.py` | per-月 verdict 供給 (`build_mf_index` / `reconcile`) + 突合キー正規化 (`normalize` / `extract_names`) |
| classify engine | `$CLAUDE_PLUGIN_ROOT/scripts/mfk_period_report.py` | 対象月決定規約 (`resolve_target_months`) と入力キー契約の確認 |
| api spec | `$CLAUDE_PLUGIN_ROOT/skills/ref-mf-kessai-api/` | エンドポイント・判定仕様の正本 |

### 3.2 外部ツール / API
- MF掛け払い API (GET のみ。変更系は hook `guard-mfk-readonly.py` で遮断)。
- Notion REST (請求確認シート read = 契約終了月収集。GET のみ)。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `--target` が YYMM 不正なら exit 2 (fail-closed)。
- API エラー (HTTP / 接続 / ページング異常) は stderr に出し、部分取得のまま入力 JSON を確定しない。
- 最大反復回数: 3。

### 4.2 観測 / ロギング
- stdout に対象月 (今月/先月) と MF顧客数・差分該当取引先数・12ヶ月遡り対象数のサマリ。

### 4.3 セキュリティ
- GET のみ。secret は Keychain 参照のみで平文出力しない。取引先データを外部送信しない。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- collect 実行 (決定論 lib / GET 主体、context-fork 不要)。

### 5.2 ゴール定義
- 目的: 対象月を正しく決定し、前月/今月の MF発行実績と per-月 verdict、差分該当取引先の 12 ヶ月履歴、契約終了月を漏れなく集め、C05 が消費する入力 JSON を揃える。
- 背景: 対象月の取り違え (実行日カレンダー月を今月にする等) や 12 ヶ月全件遡りは、分類の腐敗・API 過負荷を招く。対象月決定は C05 規約に、遡りは差分該当のみに機構で固定する。
- 達成ゴール: `curr-verdicts`/`prev-verdicts`/(必要時)`lookback-12mo`/`contract-end` の JSON が用意され、per-月 verdict が既存 engine の出力そのままで、突合キーが `normalize`/`extract_names` で正規化された状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] 対象月 (今月=直近締め済み請求対象月・先月=その1ヶ月前) を `resolve_target_months` 規約で決定した
- [ ] 前月・今月の全取引先 MF発行実績を全ページ GET し per-月 verdict を既存 `mfk_reconcile` engine で収集した (再照合・再パースなし)
- [ ] 取引先×商品で状態遷移を抽出し、差分に現れた**該当取引先のみ** 12 ヶ月分の発行履歴を **MF API (transaction.date 履歴) から** 追加取得した (全件遡らない・請求確認シートの開始月を理由に省略しない。MF実績自体が無いときのみ源を明示して省略)
- [ ] 請求確認シート由来の契約終了月を収集した (二次情報・`contract-end` JSON)
- [ ] 突合キーを `mfk_reconcile.normalize`/`extract_names` で正規化した (自作正規化なし)
- [ ] C05 が読む入力 JSON (`curr-verdicts`/`prev-verdicts`/任意 lookback/contract-end) を組んだ
- [ ] POST 等変更系を一切呼んでいない (GET のみ)

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案 (対象月決定 / GET / verdict 収集 / 遡り絞り込み / JSON 組み立て)→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: `run-mf-invoice-report` SKILL Step 1 (collect)。
- 後続 phase: R2 (classify=C05) が同一実行内で続く。

### 6.2 ハンドオフ / 並列性
- 提供元: ユーザー (`--target`) / MF API / 請求確認シート / 既存 reconcile engine (per-月 verdict)。
- 受領先: R2 classify (`mfk_period_report.py` の `--curr-verdicts`/`--prev-verdicts`/`--lookback-12mo`/`--contract-end`)。
- 引き渡し形式: JSON ファイル群。per-月 verdict 行の list か `{"rows":[...]}`。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 画面に対象月 (今月/先月) と収集件数サマリ (Markdown)。

### 7.2 言語
- 本文: 日本語 (CLI / schema key / enum / path は原文)。

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

まず対象月を決定する。`--target YYMM` があればそれを今月とし、無ければ `mfk_period_report.resolve_target_months` の規約 (今月=実行日カレンダー月の前月=直近締め済み請求対象月・先月=その1ヶ月前) で導出する。例: 2026-07-02 実行 → 今月=`2606`・先月=`2605`。

前月・今月の全取引先 MF発行実績を `$CLAUDE_PLUGIN_ROOT/lib/mfk_api.py` で参照専用 GET し、既存 `$CLAUDE_PLUGIN_ROOT/lib/mfk_reconcile.py` (`build_mf_index`/`reconcile`) で per-月 verdict を収集する (既存 verdict をそのまま消費・再照合や自由文の終了根拠再パースをしない)。取引先×商品で状態遷移 (今月あり×前月あり / 今月あり×前月なし / 今月なし×前月なし / 今月なし×前月あり) を抽出し、差分に現れた**該当取引先のみ** 12 ヶ月分の発行履歴を追加 GET する (全件遡らない=API 負荷最小化)。請求確認シートを read-only GET して契約終了月を収集する (二次情報)。突合キーは `mfk_reconcile.normalize`/`extract_names` で正規化する。

これらを C05 が読む入力 JSON へ整形し `Write` で保存する: `curr-verdicts` (今月=target の per-月 verdict 行)・`prev-verdicts` (先月)・任意 `lookback-12mo` (差分該当取引先のみの 12 ヶ月履歴)・任意 `contract-end` (契約終了月)。各行は C05 が消費するキー (`verdict`/`customer`/`product`/`contract_id`/`evidence`/金額/canon 前の生商品名) を保持する。

Layer 5 の完了チェックリストを唯一の停止条件とし、未充足項目を特定→解消手順を都度立案→実行→自己評価→全項目充足まで反復する (固定手順なし、上限: Layer 4 最大反復回数)。GET のみ (変更系を一切呼ばない)。出力は対象月と収集件数サマリのみ、前置き禁止。
