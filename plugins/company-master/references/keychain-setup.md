# Keychain 鍵セットアップ (チームメンバー向けオンボーディング)

> このプラグインが使う秘密情報・設定は **env ファイルではなく macOS Keychain** に置く。本書は「自分の
> マシンでどの鍵を登録すればよいか」を**ロール別**にまとめた、チーム配布用の手順正本。背景や API キーの
> 取得方法は `japanpost-api-setup.md` (BYO / 日本郵便鍵取得) と `postal-proxy-deploy.md` (中央プロキシ) を参照。

## まず自分のロールを確認する

| ロール | 何をする人か | 実施する節 |
|---|---|---|
| **チームメンバー** | 各自のローカル Claude Code でこのプラグインを使う人 | **A** だけ |
| **プロキシ運用者 (管理者)** | 固定IPサーバで中央プロキシ (`postal_proxy.py`) を立て鍵を集約する人 | **B**（+ デプロイは `postal-proxy-deploy.md`） |

> 当チームの配布モデルは **中央プロキシが既定**（フルリモート・送信元IPがバラつくため）。
> そのため **チームメンバーは日本郵便の `client_id`/`secret_key` も送信元IP登録も不要**（プロキシが肩代わり）。

---

## A. チームメンバーが自分の Keychain に登録する鍵 (4つ)

郵便番号は**中央プロキシ経由**で取得するので、各メンバーは次の4つだけ登録する。`-w` を**値なし**で実行すると
対話入力になり、トークンがコマンド履歴/ログに残らない（secret は必ずこの方式で貼り付ける）。

```bash
# 1. Notion 連携トークン (企業マスタDBへの書き込み用)
security add-generic-password -U -s notion-api-key.xl-skills -a xl-skills -w
#    ↑ 実行後プロンプトに Notion インテグレーショントークンを貼り付けて Enter

# 2. gBizINFO トークン (会社名/法人番号 → 正式名称・住所の取得用)
security add-generic-password -U -s gbizinfo-api-token.xl-skills -a xl-skills -w

# 3. 中央プロキシ URL (管理者から共有される。秘密でないので値を直接書いてよい)
security add-generic-password -U -s japanpost-da-api -a proxy_url -w 'https://<チームのプロキシ>/addresszip'

# 4. プロキシ通行トークン (管理者から共有される)
security add-generic-password -U -s japanpost-da-api -a proxy_token -w
```

### 登録できたか確認 (中身は表示しない)

```bash
security find-generic-password -s notion-api-key.xl-skills   -a xl-skills  >/dev/null 2>&1 && echo "Notion: OK"      || echo "Notion: 未登録"
security find-generic-password -s gbizinfo-api-token.xl-skills -a xl-skills >/dev/null 2>&1 && echo "gBizINFO: OK"    || echo "gBizINFO: 未登録"
security find-generic-password -s japanpost-da-api -a proxy_url             >/dev/null 2>&1 && echo "proxy_url: OK"   || echo "proxy_url: 未登録"
security find-generic-password -s japanpost-da-api -a proxy_token           >/dev/null 2>&1 && echo "proxy_token: OK" || echo "proxy_token: 未登録"
```

登録後、Claude Code のチャットで「**doctor を実行して**」と言えば総合診断が走る（`company_master.py doctor`）。
「**郵便番号取得モード: 中央プロキシ経由**」と表示され FAIL が無ければ完了。あとは「〇〇社の郵便番号を取得して」で使える。

---

## B. プロキシ運用者がプロキシサーバ側に登録する鍵

固定IPサーバ上で実施（デプロイ全体は `postal-proxy-deploy.md` が正本）。**日本郵便の本物の鍵はここだけに置く**。

```bash
# 日本郵便 for Biz で取得した本番システムの鍵
security add-generic-password -U -s japanpost-da-api -a client_id  -w 'for Biz の client_id'
security add-generic-password -U -s japanpost-da-api -a secret_key -w          # 対話入力 (初回のみ表示)
# チームに配る通行トークン (同じ値を各メンバーの A-4 proxy_token に入れてもらう)
security add-generic-password -U -s japanpost-da-api -a proxy_token -w
```

- このサーバの**固定送信元IP**を for Biz に登録する（`doctor` の「送信元IP」行に表示される IP）。
- Keychain の無い Linux/コンテナでは env で供給する（`postal-proxy-deploy.md`）:
  `COMPANY_MASTER_JAPANPOST_CLIENT_ID` / `COMPANY_MASTER_JAPANPOST_SECRET_KEY` / `COMPANY_MASTER_POSTAL_PROXY_TOKEN`。

---

## (参考) 単独 / 少数拠点で BYO 直叩きする場合

中央プロキシを立てず1台で完結させるなら、A の `proxy_url`/`proxy_token` の代わりに、自分の Keychain へ
日本郵便の `client_id`/`secret_key` を入れ、送信元IPを for Biz に登録する（手順は `japanpost-api-setup.md`）。
送信元IPは既定で自動検出され、`doctor` が「登録すべき IP」を表示する。固定したいときのみ `egress_ip` を pin。

---

## (補助) Mac で自分の送信元(グローバル)IP を調べる

for Biz に登録する／プロキシに設定するのは「**外から見える出口(グローバル)IP**」。Mac での調べ方:

```bash
# ① 送信元グローバルIP (for Biz 登録・proxy 用はこれ)
curl -s https://api.ipify.org; echo
#   別サービスでも可:  curl -s https://ifconfig.me; echo  /  curl -s https://checkip.amazonaws.com

# ② プラグインの自動検出値を表示 (doctor の「送信元IP」行に同じ IP が出る)
python3 plugins/company-master/scripts/company_master.py doctor
```

注意:
- **LAN内の私的IP は使えない**。`ipconfig getifaddr en0`(Wi-Fi) / `ipconfig getifaddr en1` や「システム設定 > ネットワーク」に出る `192.168.x.x` / `10.x.x.x` は**ルータ内部の私的IP**で、日本郵便ゲートウェイには届かない。登録すべきは上記①の**グローバルIP**。
- **家庭/オフィス回線は動的のことが多い**（ISP が定期的に変える）。① を時間をおいて2回実行して変われば動的。変動したら for Biz で再登録するか、固定IP環境／中央プロキシ（出口IPを1つに固定）を使う。
- プラグインは既定で①を**自動検出**して `x-forwarded-for` に使うので、BYO でも「自分のIPを毎回調べて env に入れる」必要はない（doctor が表示した IP を for Biz に登録するだけ）。

## セキュリティ (重要)

- **日本郵便の `secret_key` はチームに配らない**（プロキシ運用者の1台のみ）。`proxy_token` は身内チーム内で共有可（漏れたら作り直す）。
- これらの鍵の**平文出力**（`security find-generic-password ... -w`）・**削除**（`delete-generic-password`）は、`hooks/hook-guard-secret.py`（動的層）と `references/settings-hardening.json`（静的層）の二段防御が `notion-api-key.xl-skills` / `gbizinfo-api-token.xl-skills` / `japanpost-da-api` の3サービスについて機械的に block する。**登録 (`add`) は許容**。
- 値をコマンド引数に直書きすると履歴に残るため、secret は `-w` を空にした**対話入力**を使う。
