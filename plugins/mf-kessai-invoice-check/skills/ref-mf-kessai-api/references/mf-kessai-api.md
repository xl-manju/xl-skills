# MF KESSAI API v2 — 発行漏れチェック用リファレンス

> 一次ソース: https://developer.mfkessai.co.jp/docs/v2/ (swagger 2.14.0)
> 本ドキュメントは `run-mf-invoice-check` / `run-mf-invoice-db-setup` が参照する実装知識。実レスポンス例は 2026-06 時点の本番疎通で確認した構造（企業名・口座等の機微値はマスク）。

## 1. 認証 / ベースURL

| 項目 | 値 |
|---|---|
| 認証ヘッダ | `apikey: <APIキー>`（Bearer ではない） |
| 本番 | `https://api.mfkessai.co.jp/v2` |
| サンドボックス | `https://sandbox-api.mfkessai.co.jp/v2` |
| Accept | `application/json` |
| キー保管 | macOS Keychain `mfkessai-api-key.xl-skills` / `xl-skills`（`lib/mfk_keychain.py`） |

## 2. エンドポイント実レスポンス例（マスク済み）

### 2.1 GET /customers?limit=1
```json
{"items":[{"id":"XXXX-XXXX","name":"<企業名>","number":"<法人番号>","payment_method":{...口座情報(本チェックでは不要)...},"object":"customer"}],
 "pagination":{"end":"XXXX-XXXX","has_next":true,"total":121}}
```
→ `id`(顧客ID) と `name`(企業名) のみ使用。口座情報は使わない。

### 2.2 GET /billings/qualified?issue_date_from=...&issue_date_to=...&status=invoice_issued
```json
{"items":[
  {"id":"9PVV-GMYR","customer_id":"N4V9-R3E7","amount":110000,"issue_date":"2026-06-19",
   "due_date":"2026-07-31","status":"invoice_issued","invoice_ids":["XXXX-XXXX"],"object":"billing"}
 ],
 "pagination":{"end":"...","has_next":true,"total":89}}
```
→ 発行漏れ判定の母集合。`customer_id` を集合化し差集合を取る。`amount` は金額（前月/今月比較）。

### 2.3 GET /transactions?billing_id=9PVV-GMYR
```json
{"items":[
  {"id":"EW3E-PAWW","customer_id":"N4V9-R3E7","billing_id":"9PVV-GMYR","amount":110000,
   "date":"2026-05-31","issue_date":"2026-06-19","due_date":"2026-07-31","status":"passed",
   "created_at":"2026-06-19T15:47:39+09:00",
   "transaction_details":[
     {"description":"<商品名>（2026年4月分）","amount":50000,"unit_price":50000,"quantity":1},
     {"description":"<商品名>（2026年5月分）","amount":50000,"unit_price":50000,"quantity":1}
   ]}]}
```
→ 商品名(`description`)・金額(`amount`/`unit_price`×`quantity`)・更新日(`created_at`)を突合。

## 3. 発行漏れ判定 擬似コード

```python
def detect_gaps(prev_billings, curr_billings):
    P = {b["customer_id"] for b in prev_billings if b["status"] == "invoice_issued"}
    C = {b["customer_id"] for b in curr_billings if b["status"] == "invoice_issued"}
    return {
        "gap_candidates": P - C,   # 前月発行・今月未発行 = 発行漏れ候補 ★本丸
        "continuing":     P & C,   # 継続発行 (金額変動を amount で検出)
        "new_this_month": C - P,   # 今月新規
    }
```

- 月帰属は `issue_date` 基準。
- `gap_candidates` の各 customer は `/customers?ids=` で企業名、`/transactions?billing_id=`(前月billing) で商品名・前月金額を解決。
- 「契約終了で今月不要」は API で判別不能 → 候補として出し、除外は Notion `請求要否` 列で人が判断。

## 4. フィールド定義（使用分）

| フィールド | 型 | エンドポイント | 用途 |
|---|---|---|---|
| `customer_id` | string | billings/transactions | 差集合キー・名寄せキー |
| `name` | string | customers | 取引先企業名 |
| `amount` | int | billings/transactions | 金額(税込) |
| `issue_date` | date | billings | 発行月の判定軸 |
| `status` | enum | billings | `invoice_issued`/`scheduled`/`account_transfer_notified`/`stopped` |
| `invoice_ids` | string[] | billings | 発行済み請求書の実体(発行確証) |
| `transaction_details[].description` | string | transactions | 商品名 |
| `unit_price`/`quantity` | int | transactions | 単価×数量(継続/期間明細) |
| `created_at` | datetime | transactions | 更新日の代替(updated_at は無い) |

## 5. ページネーション

カーソル型。`limit`(≤200, 既定20)。応答 `pagination.end` を次回 `after=<end>` に渡し `has_next=false` まで反復。`pagination.total` で全件数。

```python
def iter_all(get, path, params):
    params = dict(params, limit=200)
    while True:
        page = get(path, params)
        yield from page["items"]
        if not page["pagination"]["has_next"]:
            break
        params["after"] = page["pagination"]["end"]
```

## 6. 注意点

1. `GET /billings`(区分記載) はインボイスモードで **0件**。必ず `GET /billings/qualified`。
2. `updated_at` は存在しない。更新日は `created_at`/`accepted_at`/`billing_accepted_at`。
3. レート制限は spec 未記載 → `limit=200` カーソル + バックオフを保守的に。
4. 定期請求/自動延長の概念は API に無い。「20万×3」等のスケジュールは人が管理。
5. 全て GET（参照専用）。POST/PATCH/DELETE は `run-mf-invoice-check` の PreToolUse hook で遮断。
