# 日本郵便「郵便番号・デジタルアドレスAPI」セットアップ手順 (正本)

> company-master の郵便番号取得 (住所→NNN-NNNN 逆引き) は日本郵便 addresszip API (V2) に一本化している。
> 本ファイルが API キー取得〜送信元IP登録〜Keychain 保存の唯一の正本 (SSOT)。`run-company-master-build` /
> `run-company-master-backfill` のセットアップ節からここへリンクする。`company_master.py doctor` が未設定を診断する。
>
> **配布モデルの選択 (意思決定木)**: 日本郵便の送信元IP許可リストは 1鍵あたり最大10件のため、配布形態で正本を分岐する。
> - **多拠点 / 送信元IPがバラつく (>10)** → **中央プロキシが既定 (本番配布モデル)**。鍵と固定送信元IPをプロキシ1台に集約し、各クライアントは `proxy_url` (+任意 `proxy_token`) だけ設定する。正本手順は `references/postal-proxy-deploy.md`。社内チーム・フルリモート運用はこちら。
> - **単独 / 少数拠点・固定IP** → **BYO (Bring Your Own credentials)**。各ユーザが**それぞれ自分の** for Biz アカウント・client_id/secret_key・送信元IP を用意する (鍵は共有しない)。**本手順 (本書) は BYO のセットアップを案内する**。
>
> 以下の手順は **BYO (単独 / 少数拠点向け)** を対象とする。各ユーザが自分の環境で一度だけ実施する。送信元IP は既定で自動検出されるため、`doctor` が
> 表示する IP をそのまま for Biz に登録すればよい (「自分のグローバルIPが分からない」を解消)。秘密情報・設定は
> env ファイルではなく Keychain に置く方針 (鍵=`japanpost-da-api`/`client_id`,`secret_key`、固定IP=`/egress_ip`)。多拠点配布は本書でなく `references/postal-proxy-deploy.md` を正本とする。

## 必要な情報 (3 つ + ホストは固定)

| 情報 | 使う場面 | 保存先 |
|---|---|---|
| ホスト `https://api.da.pf.japanpost.jp` | token / addresszip 両方 | コードに固定 (`scripts/postal_api.py`)。入力不要 |
| `client_id` | token 発行 | Keychain `japanpost-da-api` / account `client_id` |
| `secret_key` | token 発行 | Keychain `japanpost-da-api` / account `secret_key` (**初回のみ表示**) |
| 送信元IP (`x-forwarded-for`) | token 発行ヘッダ (必須) | **既定は自動検出**。固定時のみ Keychain `japanpost-da-api`/`egress_ip` |

呼び出しフロー (実装は `postal_api.py`):

```
① token 発行  POST /api/v2/j/token
   header: x-forwarded-for: <登録IP>            ← 必須
   body:   {grant_type:"client_credentials", client_id, secret_key}
   返却:   {scope, token_type:"jwt", expires_in, token}
② 住所→郵便番号  POST /api/v2/addresszip
   header: Authorization: Bearer <①のtoken>
   body:   {pref_name, city_name, town_name} または {freeword}
   返却:   {addresses:[...], level(1=都道府県/2=市区町村/3=町域), count, page}
```

## ① for Biz 登録 → ② 送信元IP登録 → ③ 鍵取得

1. **for Biz アカウント作成**: 日本郵便「郵便番号・デジタルアドレスAPI」for Biz (https://biz.da.pf.japanpost.jp/) でゆうID→組織→システムを登録する。
2. **送信元IP登録**: システム情報で API を呼ぶ環境の**グローバル送信元IP**を登録する (最大10件)。ローカル実行ではこのマシンの egress IP。登録すべき IP は `python3 plugins/company-master/scripts/company_master.py doctor` を実行すると「送信元IP」行に表示される (プラグインが自動検出した、実際に外へ出ていく IP)。それをそのまま for Biz に登録するのが確実。**固定IP回線でないと変動する**点に注意 (変動したら再登録するか、doctor の WARN に従う)。
3. **client_id / secret_key 取得**: システム情報画面で `client_id` と `secret_key` を取得する。**`secret_key` は初回のみ表示**されるため、取得直後に Keychain へ保存する (取り逃すと再発行)。

> 本番とテスト用 API は別物。テスト用 API は固定の client_id/secret_key で東京都千代田区のみ検索可。本番は登録した自分の鍵を使い、ホストは `api.da.pf.japanpost.jp`。

## ④ Keychain 保存 (平文を履歴/ログに残さない)

```bash
# client_id (公開寄り。値を直接渡してよい)
security add-generic-password -U -s japanpost-da-api -a client_id -w 'あなたのclient_id'

# secret_key (-w を空にすると対話入力 → コマンド履歴/ログに平文が残らない)
security add-generic-password -U -s japanpost-da-api -a secret_key -w
#   ↑ 実行後にプロンプトが出るので secret_key を貼り付けて Enter

# 確認 (存在確認のみ・中身は出さない)
security find-generic-password -s japanpost-da-api -a client_id >/dev/null 2>&1 && echo "client_id: set"
security find-generic-password -s japanpost-da-api -a secret_key >/dev/null 2>&1 && echo "secret_key: set"
```

> 注意: 鍵をブラウザ等から貼り付ける際、不可視のハイフン (U+2011 等) や前後空白が混入すると認証に失敗する。ASCII ハイフン `-` と余分な空白なしを確認すること。

## ⑤ 送信元IP の供給 (既定は自動検出・固定は Keychain pin)

送信元IP は **既定で自動検出**される (公開エコー `https://api.ipify.org` で実際の egress IP を取得し `x-forwarded-for` に使う)。多くの BYO ユーザは **保存不要**で、④までの鍵登録 + for Biz への IP 登録だけで動く。

IP を固定したいとき (プロキシ/複数NIC で自動検出値が実際の送信元と異なる等) のみ、**env ファイルではなく Keychain に pin** する (鍵と同じ場所で一元管理):

```bash
security add-generic-password -U -s japanpost-da-api -a egress_ip -w '203.0.113.10'   # (任意) 固定IP
```

解決順は `postal_api.resolve_egress_ip()` = Keychain `japanpost-da-api`/`egress_ip` → env `COMPANY_MASTER_EGRESS_IP` (CI 用の低優先フォールバック) → 自動検出。バックグラウンド/cron 実行でも自動検出は働く。検出先を変えるときのみ env `COMPANY_MASTER_EGRESS_IP_DETECT_URL`。

## (任意) テスト環境(stub)で配線を先に検証する

本番システム登録の前に、for Biz の「テスト用API認証情報」で配線だけ確認できる(2026-06-18 に実 stub で疎通実証済み)。
テストAPIは**別ホスト**(`stub-....da.pf.japanpost.jp`)かつ**東京都千代田区のデータのみ**・負荷テスト禁止・データは予告なくクリーンアップ。

1. テスト用 client_id/secret_key を Keychain へ(本番と同じ account 名):
   ```bash
   security add-generic-password -U -s japanpost-da-api -a client_id  -w '<テスト client_id>'
   security add-generic-password -U -s japanpost-da-api -a secret_key -w
   ```
2. 接続先をテストホストへ上書き(Keychain。env でなく Keychain):
   ```bash
   security add-generic-password -U -s japanpost-da-api -a base_url -w 'https://stub-xxxxx.da.pf.japanpost.jp'
   ```
3. **テストデータにある住所**で確認(霞が関はテスト対象外。`飯田橋`/`一番町`/`岩本町`/`内幸町`/`大手町` が対象):
   ```bash
   python3 plugins/company-master/scripts/postal_api.py 東京都千代田区飯田橋   # → 102-0072
   python3 plugins/company-master/scripts/company_master.py doctor --probe       # 配線の総合確認
   ```
4. 本番移行時は base_url 上書きを削除(本番既定 `api.da.pf.japanpost.jp` に戻る):
   ```bash
   security delete-generic-password -s japanpost-da-api -a base_url
   ```

> テストAPIは検証専用。実在企業を全国規模で引く本番運用には**本番システム登録**(と送信元IP登録、または中央プロキシ)が必須。

## ⑥ 動作確認

> パスについて: 以下の `python3 plugins/company-master/scripts/...` は**リポジトリ直下から実行する場合**の例。
> Claude Code でインストール済みプラグインとして使う場合、スクリプトはインストール先 (`$CLAUDE_PLUGIN_ROOT` 配下) に
> 展開され、パスは全て `__file__` 起点で自己解決するため**どこに install しても動く**。コマンドを直に打つ必要はなく、
> チャットで「doctor を実行して」「〇〇社の郵便番号を取得して」と指示すれば Claude Code がスキル経由で正しいパスで実行する。

```bash
# 鍵/IP の有無診断 (ネット非依存)
python3 plugins/company-master/scripts/company_master.py doctor

# 実 API 疎通 (token 発行 + テスト検索。登録IPとのズレを検知)
python3 plugins/company-master/scripts/company_master.py doctor --probe
```

`doctor --probe` が `[FAIL] 日本郵便 API 実疎通: 認証失敗` を出す場合、送信元IPが登録IPと不一致か鍵が不正。
IP が変動していれば for Biz で再登録する。失敗時は郵便番号を空欄 + 備考 (`postal_api_unauthorized` /
`postal_api_unavailable`) で保留し、誤値は入れない (誤値を入れない非対称コスト原則)。
