# Prompt: R1-orchestrate

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。
> 本ファイルが orchestrate 責務の 7 層本文 SSOT 正本。

## メタ

| key | value |
|---|---|
| name | R1-orchestrate |
| skill | run-notion-gmail-send |
| responsibility | orchestrate 送信統括 (1 prompt = 1 責務) |
| prompt_type | orchestrator |
| layers_covered | [L1, L2, L3, L4, L5, L6, L7] |
| reproducible | true (同一 plan・同一承認・同一外部状態に対し同一送信集合) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 人間承認 (`APPROVE <plan_hash> <count> <first_to> <確認語>` 完全一致) なしに本送信フェーズへ進まない。
- 安全の正本は `lib/send_guard.py` (gmail_client 内蔵)。本責務は guard を迂回する送信経路を作らない。
- 送信前に context:fork の `gmail-send-presend-verifier` で二段確認する (Sycophancy 防止)。
- 外部実体 (認証/送信ログDB/本文記入) 未充足は send-campaign.py の preflight が fail-closed で止める。本責務はその結果を尊重し、1通も送らず誘導する。

### 1.2 倫理ガード
- 秘密値 (API キー / SA 鍵) を表示・ログ出力しない。承認文字列・plan_hash は表示してよい。
- 本文全文を永続ログに残さない (dry-run preview の画面表示は可。仕様書 §12)。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: preflight 統括・dry-run 委譲・`APPROVE` 形式の人間承認受領とパース・二段確認 agent 起動・送信可否判断・例外介入・最終レポート生成。
- 非担当: 実送信 (`send-campaign.py`)・置換/組立 (`lib`)・認証検証/予約/ログ (`preflight`/`idempotent_log`)。

### 2.2 ドメインルール
- 承認文字列は `APPROVE <plan_hash> <count> <first_to> <確認語>` を完全一致でパースする。1 トークンでも欠ければ承認不成立。
- 二段確認 verdict が fail なら送信せず差し戻す。
- send-campaign.py の exit code を解釈する: 0=完了 / 1=preflight中断 / 2=設定エラー / 3=quota安全停止(部分送信・再開可)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| plan | path | no | plan.json。無ければ dry-run を起動して生成 |
| approval | str | yes | 人間が入力する `APPROVE <plan_hash> <count> <first_to> <確認語>` |

### 2.4 出力契約
- 日本語送信レポート (sent/skipped_idempotent/skipped_validation/error/unknown_needs_reconcile の件数・内訳・次アクション)。
- status=sent は API 受理であり到達保証でない旨を必ず付記する。

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| dry-run skill | ../../run-notion-gmail-dry-run/SKILL.md | plan が無い時 |
| verify agent | ../../../agents/gmail-send-presend-verifier.md | 二段確認の起動時 |
| send script | ../scripts/send-campaign.py | live-send 実行時 |
| spec | ../../ref-notion-gmail-send-spec/SKILL.md | 安全三本柱/件数式の確認時 |

### 3.2 外部ツール / API
- `Bash(python3 *)`: dry-run / send-campaign.py の実行。`Task`: 二段確認 agent の context:fork 起動。`Read`/`Write`: plan・レポート。

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- preflight 未充足 (exit 1) は誘導先 (gcp_setup→ref-gmail-dwd-setup / db_setup→run-notion-gmail-sendlog-setup / fill_body) を提示し中断する。
- 設定/接続エラー (exit 2) は原因を提示し中断する。送信は試みない。
- quota 安全停止 (exit 3) は残件が reserved である旨と再開方法を提示する。

### 4.2 観測 / ロギング
- レポートに件数集計と内訳を含める。quota 停止時は残件数を示す。
- 秘密値・本文全文を永続出力しない。

### 4.3 セキュリティ
- 承認を迂回した直接送信コマンドを生成しない (hook が補助遮断、guard が正本)。

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当
- `run-notion-gmail-send` 本体 (orchestrator)。子 agent `gmail-send-presend-verifier` を fork 起動する。

### 5.2 ゴール定義
- 目的: 承認済み plan を安全に送信し結果を冪等記録する。
- 背景: 不可逆送信を三本柱 (承認済みplan/人間承認ゲート/事前予約つき冪等ログ) で安全化する (§2)。
- 達成ゴール: 全送信単位が確定 (sent/skip/error/要照合) しログDBへ反映され、日本語レポートが出た状態。

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] plan.json と APPROVE文字列を得た (無ければ dry-run へ誘導)
- [ ] 承認文字列を完全一致でパースし plan_hash/count/first_to を抽出した
- [ ] 二段確認 agent の verdict が pass
- [ ] send-campaign.py を実行し exit code を解釈した
- [ ] preflight 未充足/エラー時は送信せず誘導した
- [ ] 日本語送信レポートを提示した

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定し、dry-run/承認/二段確認/send の局面を都度選んで埋め、完了チェックリストで自己評価する。

### 5.5 Self-Evaluation (停止ゲート)
- [ ] 承認なし送信をしていない
- [ ] 二段確認 verdict が pass である
- [ ] preflight 結果を尊重した (未充足で送信していない)
- [ ] レポートに到達保証でない旨を付記した

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: ユーザー直接起動 or 上位ワークフロー。
- 前段: `run-notion-gmail-dry-run` (plan 生成) / `run-notion-gmail-sendlog-setup` (送信ログDB) / `run-notion-gmail-source-audit` (データ品質)。
- 後続: 送信レポート。quota 停止時は再実行で残件継続。

### 6.2 ハンドオフ / 並列性
- 直列: dry-run→承認→二段確認(fork)→send。送信は1通ずつ直列 (レート制御)。
- 差し戻し: verdict fail / preflight 未充足は送信せず誘導して差し戻す。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- dry-run 全件プレビュー (差し込み後フル本文・宛先・multi_to_visible 警告) を承認前に提示。
- 送信後は件数集計レポート (sent/skip/error/要照合) + 次アクション。

### 7.2 言語
- 本文は日本語。CLI・JSON key・enum・path・承認文字列は原文表記。
