# spec-detail — run-notion-gmail-send 詳細参照

`SKILL.md` の知識索引を補完する詳細。実装 SSOT は `doc/run-notion-gmail-send-仕様と検証メモ.md`。本書はその抜粋・図示であり、矛盾時は SSOT を正とする。

---

## 1. Notion 2DB 列マッピング（全表・§3）

### DB1「メール本文_DB」(`38807a0cd18c80f1ae82f01a90ff5aa2`)

| プロパティ | 型 | 役割 | メール組立での写像 |
|---|---|---|---|
| 件名 | title | メール件名（`{{}}` 置換対象） | Subject |
| メールの送り主 | email | From（impersonate 対象） | **From** |
| CC | email（カンマ区切りで複数可） | CC | **CC**（カンマ分割し1通に並列） |
| メッセージ対象 | checkbox | ✅ かつ本文非空の行だけ送信 | 送信フィルタ |
| （ページ本文） | コードブロック | メール本文テンプレ（`{{}}` 置換対象） | Body |

### DB2「メール送信先_DB」(`38807a0cd18c80e9b47cd9ceb81463db`)

| プロパティ(厳密名) | 型 | 役割 | メール組立での写像 |
|---|---|---|---|
| `担当者様名` | title | 差し込み＋宛名 | `{{担当者様名}}` |
| `会社名` | rich_text | 差し込み | `{{会社名}}` |
| `メール（プロ人材）` | email（カンマ区切り可） | 送信先(プロ人材) | **To**（カンマ分割し1通に並列） |
| `メール（cc秘書）` | email（カンマ区切り可） | CC(秘書) | **CC**（本文DB CC と結合・To除外・重複排除） |
| `メールを送らない` | checkbox | ✅ なら送信対象より優先で抑制 | 抑制フィルタ（最優先） |
| `送信対象` | checkbox | ✅ かつ 送らない☐ かつ プロ人材メール非空の人だけ宛先 | 宛先フィルタ |

> `部署名` は廃止（D1・2026-06-25）。同一プロ人材メール重複は最新 `created_time` の1件のみ送信し、同時刻の場合は `page_id` 降順で決定する（dedup 一次キー=`created_time` 降順・口語の「上位ID＝新しいもの」は作成時刻の意で page_id の大小ではない）。
>
> - **`メール（cc秘書）` が空**: CC無しでプロ人材（To）のみへ送信。秘書必須ではない（F2/F5）。
> - **秘書 addr == プロ人材 To**: To 優先で CC 除外（同一人物の二重可視回避）。除外は dry-run の `cc_suppressed_due_to_to_overlap` 警告で可視化（F1/F8・挙動は不変）。
> - **`送信対象=false`**: dry-run では母集団外で無記録。承認後に `送信対象=☐`/`メールを送らない=✅` へ変えられた場合のみ live-send が `send_suppressed` で記録（F8・C-1）。

### 取得時の確定事項

- From は `@shonai.inc`（Workspace ドメイン）。固有値は config へ退避し、承認状況は実行時に動的検証する（G1）。
- 現状 `メッセージ対象=✅` の2件は本文コードブロックが未記入（空）。空本文は送信対象外。送信には `{{}}` トークン入り本文の記入が必要（preflight で0通なら送信せず案内）。

---

## 2. ページ本文コードブロック抽出規則（§3末）

- DB1 ページ本文は Notion blocks API で子ブロックを **pagination しながら取得**する。
- 本文テンプレートは **最初の非空 `code` block** を採用する。
- 非空 `code` block が複数あるときは `skipped_validation(reason=multiple_body_code_blocks)` とし、**暗黙連結しない**。
- 空白のみの `code` block は空本文として扱う。`code` block 以外の paragraph 等は本文に使わない。
- ページ本文取得失敗・子ブロック未取得・pagination 未完了は fail-closed（`error` または `skipped_validation(reason=body_fetch_failed)`）。

---

## 3. 件数式 2段の詳細（§4）

### フィルタ定義

- **本文 true** ≡ `メッセージ対象=true` **かつ** 本文コードブロックが非空
- **宛先 true** ≡ `送信対象=true` **かつ** `メールを送らない=false` **かつ** `メール（プロ人材）`(To) が非空。`メールを送らない=true` は最優先で抑制し、同一プロ人材メール重複は最新 `created_time` の1件のみ残す（同時刻は `page_id` 降順）
- 満たさない行は送信せず `skipped_validation` として計上・報告する。

### 直積と hash

- 送信単位 = （本文 true の全行）×（宛先 true の全行）。各単位を1通として送信する。
- `campaign_id`: 実行ごとの識別子（例: `YYYYMMDD-HHMMSS-<shortuuid>`）。同一キャンペーン内の全送信単位に付与。
- `content_hash`: 置換後の Subject / Body / From / To / CC / 本文page_id / 宛先page_id を正規化し SHA-256。「recipient list」は独立フィールドではなく To(sorted)/CC(sorted)/宛先page_id の総称（実装 `lib/plan_build._normalize` の固定7キー。観測メタは hash 非対象）。
- `plan_hash`: dry-run で生成した全送信単位（順序安定・正規化済み）の SHA-256。live-send は `--approved-plan-hash` が dry-run の `plan_hash` と一致しない限り Gmail API を呼ばない。
- 冪等キー: `{本文page_id}:{宛先page_id}:{content_hash}`。`campaign_id` は含めないため、別実行でも同一内容の二重送信を止める。宛先行のメール列に複数アドレスがあっても、その宛先行に対する1送信単位として扱う。意図的再送時だけ `--allow-resend` が campaign suffix を付ける。
- `plan.json` は本文全文を含むがローカル作業領域のみ（git 管理外推奨）。Notion ログには本文全文を保存せず `content_hash` と件名を保存する。

### 件数式

| 段 | 式 | 依存 |
|---|---|---|
| 第1段: 計画送信単位 | `本文true件数 × 宛先true件数` | **DB不要**（dry-run はここまで常に算出可） |
| 第2段: 正味送信予定 | `計画送信単位 − sent済み件数` | **送信ログDB ID 確定が前提**（preflight G2 通過時のみ評価） |

dry-run は送信ログDB が未確定でも第1段まで提示する。第2段（冪等差し引き）は preflight G2 通過後にのみ算出する。

---

## 4. 状態遷移図（§9）

```
                       ┌──────────────────────────────────────────────┐
 dry-run               │            live-send                         │
                       │                                              │
 [planned] ──approve──▶│ [reserved] ──guard pass──▶ [sending] ──API ok──▶ [sent]
                       │     │                          │
                       │     │ (already sent in log)    │ Notion 更新失敗 / 中断
                       │     ▼                          ▼
                       │ [skipped_idempotent]   [unknown_needs_reconcile]
                       └──────────────────────────────────────────────┘

 送信前に弾かれる経路:
   本文空 / 宛先欠落 / 未置換トークン / 不正アドレス  ──▶ [skipped_validation]
   Gmail API 失敗（未送信と判断可）                  ──▶ [error]
```

- `reserved` は自動再送禁止のロック。`sent` と `unknown_needs_reconcile` は自動再送しない。
- 部分再開は冪等ログを起点に、`reserved` の未送信分のみを再実行で継続する。
- 送信成功後ログ失敗時はローカル journal に冪等キー・messageId・時刻・plan_hash を保存し、次回 `unknown_needs_reconcile` として手動照合を要求する。

---

## 5. 依存実体トレーサビリティ表（§13）

契約条項が消費する未確定実体を、確定方法と未確定時の fail-closed gate に1対1で連結する。これらが build 時点で未確定でも、preflight gate と `send_guard()` が fail-closed で吸収するため build は完遂可能。実値が揃い plan が承認され reserved ログ行が作られるまで1通も送信しない。

| 契約条項 | 依存実体 | 確定方法 | 未確定時のゲート |
|---|---|---|---|
| 承認済み plan（§4,§8） | `plan.json` / `plan_hash` | dry-run で生成し live-send で hash 照合 | G3: 不一致なら送信中断 |
| 冪等記録（§9） | 送信ログDB ID | `.notion-config.json` の `databases.gmail-send-log.db_id` に焼き込み（db-setup で先行確定） | G2: 不在なら db-setup へ差し戻し |
| 事前予約（§9,§11） | reserved ログ行ID | Gmail API 呼び出し前に Notion create/search | G3: reserved なしなら送信中断 |
| impersonate 送信（§6 From） | Keychain SA鍵 svce/acct | preflight で `security` 列挙確認 | G1: 取得不可なら中断 |
| Gmail 送信（§8-9） | shonai.inc の DWD + gmail.send 承認 + From sendAs alias | 実 API で動的検証 | G1: 未承認なら GCP 手順へ誘導 |
| 送信単位生成（§4） | 本文 true ≥ 1（✅2件の本文記入） | 本文コードブロック記入 | G2: 0通なら記入を促し終了 |

---

## 6. 責務一覧（§7・二層分離）

決定論的に確定できる処理は script、LLM 判断・人間承認・例外介入は run-skill が担う。

| id | 担当層 | prompt_required |
|---|---|---|
| orchestrate | run-skill | true |
| presend-verify | run-skill | true |
| notion-fetch | script | false |
| render-substitute | script（本文＋件名の `{{}}` 置換、未置換 fail-closed） | false |
| message-assemble | script（From/To/CC 写像・カンマ分割・RFC822/MIME 組立） | false |
| plan-build | script（正規化・campaign_id/content_hash/plan_hash・dry-run preview・plan.json） | false |
| gmail-send | script（`send_guard()` 通過後だけ1通ずつ送信、quota/レート制御） | false |
| idempotent-log | script（reserved→sending→sent/unknown・既送照合・部分再開起点） | false |

---

## 7. 耐障害・セキュリティ（§11,§12）

- **quota/レート**: 1通ごと最低1秒待機。429/403 rateLimit/quota は指数バックオフ（最大3回、初期2秒、上限60秒）。3回失敗または quota 枯渇判定で安全停止し、残件は `reserved` のまま次回再開対象。
- **重複検知**: 同一プロ人材メールアドレスが複数 page に存在する場合は最新 `created_time` の1件だけを送信対象に残し、他は `duplicate_dropped` として報告する（会社名違いでも同一人物への重複送信を防ぐ）。
- **認証**: macOS Keychain の Google SA鍵のみ。鍵の平文化・ログ出力を禁止。DWD は任意ユーザー impersonate 可能なため対象を運用で固定。
- **PII**: dry-run preview は本文全文・アドレスを表示してよい。永続ログ（Notion 送信ログ / eval-log / journal）には本文全文を保存しない。エラーログでは secret/key を必ず redaction する。

---

## 8. 用語対応表（ユーザー語彙 ↔ 実装語彙）

要件ヒアリングの口語と実装・本仕様の語を1対1で対応させ、読み手の取り違えを防ぐ（F2）。

| ユーザー語彙（口語） | 実装・仕様語彙 | 補足 |
|---|---|---|
| プロ人材（に送る） | `メール（プロ人材）` → **To** | DB2 列。カンマ区切りで複数可 |
| 秘書（にCC） | `メール（cc秘書）` → **CC** | 空なら CC無しで送信（必須でない・F2/F5） |
| 送り主 | `メールの送り主` → **From** | DB1 列。impersonate 対象 |
| 「上位ID＝新しいもの」 | dedup 一次キー=`created_time` 降順 | 作成時刻であり page_id の大小ではない（F4） |
| 同じ人を1回だけ | プロ人材メールで dedup（最新1件） | tie-break のみ `page_id` 降順 |
| 送らない | `メールを送らない=✅` → `suppressed` | `送信対象` より最優先 |
| この人には送る | `送信対象=✅` → 宛先 true | false は dry-run 母集団外（無記録・F8） |
| 重複で消えたCC | `cc_suppressed_due_to_to_overlap` | 秘書==To で CC 除外された可視化警告（F1） |
| 送った/送信済み | `status=sent`（Gmail API 受理） | 到達保証ではない |
| 内容のハッシュ | `content_hash`（固定7キー） | 「recipient list」は To/CC/宛先page_id の総称（F2） |
| 計画 | `plan` / `plan_hash` | dry-run 出力。承認の照合キー |
| 確認語 | `nonce`（`approval_nonce`） | プレビュー目視強制の短コード |

---

## 9. 参照元

| ファイル | 役割 |
|---|---|
| `doc/run-notion-gmail-send-仕様と検証メモ.md` | 実装 SSOT |
| `doc/GCP-Gmail送信設定手順.md` | 認証基盤（Gmail API 有効化 + DWD スコープ）設定手順 |
| `plugins/notion-gmail-send/lib/` | 決定論的実行コード |
