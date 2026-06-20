# マネーフォワード掛け払い 請求書発行チェック

請求データをマネーフォワード掛け払い (MF KESSAI) API で確認し、**前月の発行状況**と**今月の発行漏れ**を月次でチェックして Notion で管理するためのプラグイン。

このドキュメントは「**API キーを macOS Keychain に登録し、月次チェックを回せる状態にする**」までのセットアップ手順です。判定ロジック・Notion 出力・参照専用ガード・二段確認 subagent は実装済みです (下記「構成」参照)。

---

## できること

- API キーを Keychain から安全に取得 (`lib/mfk_keychain.py`)
- MF 掛け払い API v2 への読み取り (GET) 呼び出し (`lib/mfk_api.py`)
- 疎通確認 (`--smoke`) と任意エンドポイントの取得
- 前月発行−今月発行の差集合で**発行漏れ候補**を検出 (`lib/mfk_invoice_diff.py`)
- 結果を Notion DB『請求書チェック_DB』へ**冪等 upsert** (`lib/notion_invoice_sink.py`)
- 候補0件の月も `月次サマリ` 行で**確認済み月**を残し、各ページ本文へ実行履歴を追記

秘匿情報 (API キー本体) は **Keychain にのみ保存**し、git にもチャット履歴にも残しません。
**Notion DB は配布既定に焼き込み済み**で、導入者は ID 設定不要です (下記 Step 2)。

---

## Claude Code への頼み方（かんたん実行）

コマンドや引数を覚える必要はありません。**Claude Code にふだんの言葉で頼むだけ**で、内部で適切なスラッシュコマンド／スクリプトが実行されます。下の「一言」をそのままチャット欄に打てば動きます。

| やりたいこと | Claude Code への一言（例・コピペ可） | 内部で動くもの |
|---|---|---|
| **初回: 出力先の Notion DB を準備** | `請求書チェック用の Notion DB を準備して` | `/run-mf-invoice-db-setup` |
| **今月の発行漏れをチェック** | `先月と今月の請求書発行漏れをチェックして` | `/run-mf-invoice-check` |
| **月を指定してチェック** | `2026-05 の請求書発行漏れをチェックして` | `/run-mf-invoice-check --month 2026-05` |
| **過去にチェックした月を遡ってチェック** | `2026-03 から今月まで毎月の発行漏れをチェックして` | `/run-mf-invoice-check` を月ごとに実行 |
| **過去月の確認状況を Notion で見たい** | `過去にチェックした月の状況を Notion でどう見ればいい？` | 下記「過去月の状態を確認する」を案内 |

- **スラッシュコマンドを直接打ってもOK**: チャット欄に `/run-mf-invoice-check` と入力すれば、同じ正規フロー（collect → verify → finalize → sink）が自動で走ります。コマンド名がうろ覚えなら「請求書の発行漏れチェックして」と日本語で言えば Claude Code が該当コマンドを選びます。
- **月の指定は任意**: 何も言わなければ実行日の当月（前月は自動算出）が対象です。「2026-05 を」のように月を添えればその月になります。
- **安全**: チェックは MF 掛け払い API を**読み取り専用**で叩くだけで、請求データを書き換えることはありません（参照専用ガードで機構的に保証）。Notion への書き込みも、人が記入する管理列（請求要否／対応状況／チェック済／備考）には一切触れません。

> はじめての場合は **①「請求書チェック用の Notion DB を準備して」→ ②「先月と今月の請求書発行漏れをチェックして」** の2ステップだけで回り始めます。

---

## 前提

- macOS (Keychain を利用)
- Python 3.11+
- MF 掛け払いの **本番 API キー** を取得済み (管理画面で発行)

> **パス表記について**: 以下のコマンド例はこのリポジトリ直下を CWD とした相対パス (`plugins/mf-kessai-invoice-check/…`) です。マーケットプレースで**任意のディレクトリ構成に install** した場合、プラグインの実体は `~/.claude/plugins/<marketplace>/mf-kessai-invoice-check/` 等になります。その場合は **スラッシュコマンド** (`/run-mf-invoice-check`・`/run-mf-invoice-db-setup`) を使うか、コマンド中のパスを **`$CLAUDE_PLUGIN_ROOT`** 基準に読み替えてください (例: `python3 "$CLAUDE_PLUGIN_ROOT/lib/mfk_api.py" --smoke`)。スクリプト内部のモジュール解決と設定ファイル探索は `__file__` 相対なので install 位置に依存しません。

---

## Step 1. API キーを Keychain に登録

> **安全原則**: API キーを `-w 'xxxx'` のように引数で渡すと、シェル履歴や AI アシスタントの会話に残ります。必ず **対話入力モード** (`-w` を値なしで末尾に置く) で、**自分のローカルターミナル**で実行してください。

```bash
# 既存登録の確認 (任意)
security find-generic-password -s mfkessai-api-key.xl-skills -a xl-skills 2>/dev/null \
  && echo "既存あり (更新になります)" || echo "未登録"

# 登録 (対話入力モード)。実行後 "password data:" が出たら本番キーを貼り付けて Enter
security add-generic-password \
  -s mfkessai-api-key.xl-skills \
  -a xl-skills \
  -U \
  -w
```

| オプション | 意味 |
|---|---|
| `-s` | service 名 = `mfkessai-api-key.xl-skills` (`MFK_KEYCHAIN_SERVICE` で上書き可) |
| `-a` | account 名 = `xl-skills` (`MFK_KEYCHAIN_ACCOUNT` で上書き可) |
| `-w` | パスワード本体 (**省略すると対話入力**。シェル履歴に残らない) |
| `-U` | 既存があれば更新 |

> 命名は既存の `notion-api-key.xl-skills` / account `xl-skills` と同じ規約に揃えています。

---

## Step 2. 設定 (ほぼゼロ設定)

設定は **2 層**です。**通常は何もしなくても動きます**。

| ファイル | git | 役割 |
|---|---|---|
| `mf-kessai-config.default.json` | 追跡 (コミット) | **配布既定**。`environment`/`base_url`/Keychain 名/**Notion `database_id`** が入っており、導入者はこのまま使える |
| `.mf-kessai-config.json` | 無視 (gitignore) | **任意の上書き**のみ。書いた**非空値だけ**が既定を上書きする (空欄は既定を温存) |
| `.mf-kessai-config.example.json` | 追跡 | 上書きの書式サンプル |

```bash
# 別環境・別 DB を使う場合のみ (通常は不要)。install パス非依存に $CLAUDE_PLUGIN_ROOT で解決:
cp "$CLAUDE_PLUGIN_ROOT/.mf-kessai-config.example.json" "$CLAUDE_PLUGIN_ROOT/.mf-kessai-config.json"
# 例: サンドボックスで試す → environment を "sandbox" に / 別の Notion DB → notion.database_id を上書き
```

> Notion 出力先は既定で DB『請求書チェック_DB』(`database_id` 焼き込み済み) です。利用には Keychain の Notion トークン (`notion-api-key.xl-skills`) と、**その DB への integration 接続**が必要です (下記「Notion セットアップ」)。

---

## Step 3. 取得確認 (キー本体は表示しない)

```bash
# Keychain からキーを取得できるか (マスク表示)
python3 "$CLAUDE_PLUGIN_ROOT/lib/mfk_keychain.py" --check
# → OK service=mfkessai-api-key.xl-skills account=xl-skills 1a2b...zz (len=NN)
```

---

## Step 4. API 疎通確認

```bash
python3 "$CLAUDE_PLUGIN_ROOT/lib/mfk_api.py" --smoke
# → base_url = https://api.mfkessai.co.jp/v2
#   OK: /customers 到達 (HTTP 200)。顧客総数 total=121
#   → APIキーは Keychain から取得し、ヘッダ apikey に載りました (本体は非表示)
```

`HTTP 200` と顧客総数が出れば、本番 URL・キーともに正常です。

---

## 使い方 — 任意エンドポイントの取得

`--path` と `--param key=value` (複数可) で任意の GET を叩けます。`status` のような配列も `--param` を複数並べれば展開されます。

```bash
# 前月(2026-05)の発行済み請求書
python3 "$CLAUDE_PLUGIN_ROOT/lib/mfk_api.py" \
  --path /billings/qualified \
  --param issue_date_from=2026-05-01 \
  --param issue_date_to=2026-05-31 \
  --param status=invoice_issued \
  --param limit=5

# 取引(商品名 description・金額)
python3 "$CLAUDE_PLUGIN_ROOT/lib/mfk_api.py" --path /transactions --param limit=5
```

### Python から呼ぶ

```python
import os, sys; sys.path.insert(0, os.path.join(os.environ["CLAUDE_PLUGIN_ROOT"], "lib"))
from mfk_api import get

# 今月発行済みの請求一覧 (発行漏れ判定の母集合)
data = get("/billings/qualified", {
    "issue_date_from": "2026-06-01",
    "issue_date_to": "2026-06-30",
    "status": "invoice_issued",
    "limit": 200,
})
for b in data["items"]:
    print(b["customer_id"], b["amount"], b["issue_date"])
```

---

## エンドポイント早見表 (発行漏れチェックで使うもの)

| 用途 | パス | 主なパラメータ |
|---|---|---|
| 顧客一覧 (企業名 name の名寄せ) | `/customers` | `ids`, `limit`, `after` |
| 発行済み請求一覧 (インボイスモード) | `/billings/qualified` | `issue_date_from/to`, `status`, `limit`, `after` |
| 請求単体 (status・amount・invoice_ids) | `/billings/{id}` | — |
| 取引・明細 (商品名 description・金額) | `/transactions` | `billing_id`, `limit`, `after` |

> 注: この事業者はインボイス制度モードのため、一覧は `/billings`(区分記載用) ではなく **`/billings/qualified`** を使います (`/billings` は空を返す)。

---

## 環境変数による上書き

| 変数 | 用途 |
|---|---|
| `MFK_KEYCHAIN_SERVICE` / `MFK_KEYCHAIN_ACCOUNT` | 別の Keychain entry (staging 等) を使う |
| `MFK_API_KEY` | Keychain が無い CI / 非macOS のフォールバック (キーが環境に載る点に注意) |
| `MFK_BASE_URL` | base_url を一時的に上書き |

---

## Notion セットアップ (出力先)

出力先 DB『請求書チェック_DB』(`database_id` は配布既定に焼き込み済み) を使うための準備:

1. **Notion トークンを Keychain に登録** (未登録なら): service `notion-api-key.xl-skills` / account `xl-skills`。
2. **DB に integration を接続**: Notion でその DB を開き `···` → `+ 接続` (Connections) から、上記トークンの integration を接続。**未接続だと `HTTP 404 object_not_found`** になります。
3. **スキーマを適用** (冪等。既存 DB に不足プロパティを追加・タイトル列を `取引先企業名` にリネーム):

```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-db-setup/scripts/build_notion_db.py"
python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-db-setup/scripts/verify_db_schema.py"
# → PASS 全 19 プロパティが存在します。
```

> 別の DB を使いたい場合は `.mf-kessai-config.json` に `{"notion": {"database_id": "<id>"}}` を書けば上書きできます。`database_id` を空にして `parent_page_id` を指定すると、その親ページ配下に**新規 DB を作成**するモードになります。

---

## 過去月の状態を確認する (運用者向け)

> **過去月の確認結果は失われません。** 毎月の upsert キーは `顧客ID × 対象年月` なので月ごとに別行で残り上書きされません。候補0件の月も `月次サマリ` 行で「確認済み」を記録し、各ページ本文には実行履歴を毎回追記 (append-only) します。管理列 (請求要否/対応状況/チェック済/備考) は自動実行が一切触れないため、人の運用判断もそのまま保持されます。

経理担当が「いつ・何を確認したか」を Notion 上で振り返るための見方を Q&A 形式でまとめます。多くは**既存プロパティへのフィルタ/ソートで足り、列の追加は不要**です。

| 知りたいこと | Notion ビューの作り方 |
|---|---|
| **ある月を確認したか?** | DB を `対象年月` で**降順ソート**し、`レコード種別 = 月次サマリ` で**フィルタ**。各月1行=その月のチェック完了証跡。 |
| **その月の発行漏れは何件?** | 月次サマリ行の **「発行漏れ件数」「金額変動件数」「チェック件数合計」** プロパティ列で一覧確認。内訳 (どの取引先か) は同行の**ページ本文**の実行履歴。 |
| **今月の要対応は?** | `レコード種別 = 明細` × `対応状況 ≠ 対応済` でフィルタした「要対応」ビュー。既存の管理列「対応状況」を使うだけで列追加は不要。 |
| **過去にやり残しは?** | 同じく `レコード種別 = 明細` × `対応状況 = 未確認 / 確認中` を**全期間**で。期間フィルタを外せば積み残しを横断確認できる。 |

> **注意 — 月次サマリ行は削除しないこと。** `顧客ID = __monthly_summary__` の行は「その月のチェックを完了した」という内部記録です。**消すとその月の確認済み証跡が失われます** (候補0件で確認した月も含む)。

**役割分担** (上記「構成」L198 と整合):

- **DB プロパティ** = 絞り込み・並び替え・件数の一覧表示用 (`対象年月` / `レコード種別` / `対応状況` / `発行漏れ件数` 等)。
- **ページ本文** = 詳細な実行履歴 (監査ログ)。`確認済み日時` / `チェック実行ID (run_id)` / 件数の明細を毎回追記する **append-only**。ただし**同一実行 (run_id) の重複追記はしない** (冪等)。

---

## トラブルシュート

| 症状 | 原因 | 対処 |
|---|---|---|
| `Keychain lookup failed` | 未登録 / service・account 名違い | Step 1 をやり直す |
| `HTTP 401` | キー不正 / 本番・サンドボックス取り違え | Keychain の値・環境を確認 |
| `HTTP 404` / 接続失敗 (MF) | base_url 誤り | `environment` / `base_url` を確認 |
| `/billings` が 0 件 | インボイスモード事業者 | `/billings/qualified` を使う |
| Notion `404 object_not_found` | DB に integration 未接続 | 上記「Notion セットアップ」2 を実施 |
| 企業名が全て空欄 | `/customers?ids=` が解決失敗 | stderr 警告を確認 (形式は doseq `ids=A&ids=B` で検証済み) |

---

## 構成 (実装済み)

1. **発行漏れ判定** (`lib/mfk_invoice_diff.py`): 前月発行の `customer_id` 集合 − 今月発行の `customer_id` 集合 = 発行漏れ候補。純関数・pytest 済み。
2. **Notion DB 出力** (`lib/notion_invoice_sink.py`): 取引先企業名・商品名・前月/今月金額・発行日・更新日を `customer_id × 対象年月` キーで冪等 upsert。管理列 (請求要否/対応状況/チェック済/備考) は人の運用領域で自動実行は触れない。
3. **月次完了履歴**: 毎回 `顧客ID=__monthly_summary__ × 対象年月` の `月次サマリ` 行を作成/更新し、候補0件でも「その月を確認済み」として残す。月次サマリ行には件数を **DBプロパティ「発行漏れ件数」「金額変動件数」「チェック件数合計」** として持たせ、`対象年月` ソート＋`レコード種別` フィルタのビューで**過去月の確認済み状態と件数を一覧表示**できる。各明細ページ・月次サマリページ本文には `確認済み日時` / `チェック実行ID (run_id)` / 件数明細を追記し過去の実行証跡を消さない (append-only)。ただし**同一 run_id の重複追記はしない (冪等)**。DBプロパティは絞り込み・並び替え・件数一覧用、ページ本文は詳細な監査ログ用。過去月の見方は上記「過去月の状態を確認する」節を参照。
4. **スキル化** (3スキル): `ref-mf-kessai-api` (API仕様参照) / `run-mf-invoice-db-setup` (Notion DB スキーマ適用/新規構築) / `run-mf-invoice-check` (月次チェック→Notion投入)。
5. **参照専用ガード** (`hooks/guard-mfk-readonly.py`): MF API への POST/PUT/PATCH/DELETE を PreToolUse hook で遮断 (指示でなく仕組みで保証)。
6. **二段確認** (`agents/mfk-gap-verifier.md`): 発行漏れ候補を独立 context の subagent で誤検出排除してから Notion 投入。

### 使い方 (月次)

**推奨はスラッシュコマンド経由** (install パス非依存・二段確認 subagent を含む正規フローを自動実行):

```
/run-mf-invoice-db-setup   # 初回のみ: 既定DB『請求書チェック_DB』にスキーマ適用 (冪等)
/run-mf-invoice-check      # 毎月: collect → verify(subagent) → finalize → sink を統括実行
```

スクリプトを直接叩く場合 (デバッグ用)。`$CLAUDE_PLUGIN_ROOT` でこのプラグインの install 位置を解決するので、リポジトリ/マーケットプレースのどちらでも動きます:

```bash
SK="$CLAUDE_PLUGIN_ROOT/skills"

# 初回のみ: 既定DBにスキーマ適用 (冪等)
python3 "$SK/run-mf-invoice-db-setup/scripts/build_notion_db.py"

# 毎月の正規フロー (collect → verify → finalize → sink)
python3 "$SK/run-mf-invoice-check/scripts/check_invoice_gaps.py" --collect [--month YYYY-MM]
#  → 未検証候補を eval-log/mfk-gap-candidates.json に出力
#  → subagent mfk-gap-verifier が誤検出を排除し、確定リストを finalize:
python3 "$SK/run-mf-invoice-check/scripts/check_invoice_gaps.py" --finalize [--exclude-ids <cid,...>]
#  → 確定リスト eval-log/mfk-gap-verified.json を生成 (= 二段確認の証跡)
python3 "$SK/run-mf-invoice-check/scripts/check_invoice_gaps.py" --sink
#  → 確定リストを Notion へ冪等 upsert。月次サマリ行とページ本文の実行履歴も追記。
#     確定リスト不在なら fail-closed (exit 2)
```

> **出力先 (eval-log) の解決**: 成果物 (候補/確定 JSON) の置き場は install パスに依存させず、
> `MFK_OUTPUT_DIR` (env) > `CLAUDE_PROJECT_DIR` > 実行 CWD の優先順で `<base>/eval-log/` に解決します。
> collect・finalize・sink は同じ CWD (または同じ `MFK_OUTPUT_DIR`) で実行してください。
> **二段確認をスキップして未検証候補を直接投入する場合のみ** `--sink --force-unverified` を明示します (非推奨)。
