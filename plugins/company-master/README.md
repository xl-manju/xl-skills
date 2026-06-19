# company-master 導入・使い方ガイド(Claude Desktop 版)

> **このドキュメントについて**
>
> このプラグインを使い始めるために **あなたが行う作業を、上から順にこなすだけ** で完了するようまとめています。
> 専門知識は不要です。**作業はすべて Claude Desktop アプリの中だけで完結**します(ターミナル.app を別途開く必要はありません)。
> API キー(トークン)は macOS の Keychain(キーチェーン)に保管し、ファイルには平文で残しません。
>
> 各ステップには「**こう表示されれば成功**」の確認方法を添えています。違うときは「[9. うまくいかないとき](#9-うまくいかないとき)」を見てください。

> **どこに書き込まれるか(対象読者)**
>
> 記録先は **XLOCAL 社内の共有 Notion 一覧表(設定済み)** です。社内で使う方は、このまま読み進めれば設定不要でその表に書き込まれます。
> **自分の別の Notion で使いたい方**は、同じ8列の一覧表を自分で用意し(列の作り方: [`company-master-columns.md`](references/company-master-columns.md))、書き込み先を切り替えられます(Claude に「出力先の Notion データベースを ○○ に変えて」と頼むか、設定値 `COMPANY_MASTER_NOTION_DATABASE_ID` / `.notion-config.json` で指定。詳細: [`README-setup.md`](references/README-setup.md))。

---

## 1. このプラグインでできること(概要)

**会社名・住所・法人番号のどれか一部だけ** を伝えると、足りない企業情報を自動で調べて **Notion の一覧表(企業マスタ)** に整えて記録します。

調べてくれる情報と取得元:

| Notion の列 | 内容 | どこから取るか |
|---|---|---|
| 会社名 | あなたが入力した通称 | 入力そのまま |
| 正式名称 | 登記上の正式な社名 | gBizINFO(経済産業省) |
| 住所 | 都道府県から始まる住所 | gBizINFO |
| 郵便番号 | `123-4567` の8文字 | 日本郵便データ |
| 法人番号 | 13桁の番号 | gBizINFO |
| 電話番号 | ハイフン区切り | ネット検索 |
| 情報の確かさ | その行がどれくらい信頼できるか(下記4種) | 自動判定 |
| 備考 | 取れなかった項目の理由(定型文) | 自動記録 |

(上記の8列に加えて、ネット検索した値の**根拠ページURL**は各企業の **Notion ページ本文**に「確認用URL（手動検証用）」として固定の見出し付きで自動記録されます。DB の列は8列のままに保ちます。)

「情報の確かさ」は次の4つのいずれかが入ります(専門用語は使いません):

- **公的データで確認済み** … 一番信頼できる
- **公的データ取得** … 公的データから取得
- **ネット検索(要確認)** … ネット検索由来。念のためページ本文の確認用URLで確認を
- **未確定(要確認)** … 確実に分からなかった(空欄)。間違った値は入れません

> このプラグインは **間違った値を入れるくらいなら空欄にする** 方針です。一度で取得できなかった項目も、**複数の手段 (公的データの別の引き方 → ネット検索) を自動で順に試し**、それでも分からなかった項目だけを空欄 + 「備考」(どの手段を試したか付き) で人間に引き継ぎます。空欄の理由は「備考」に、ネット検索した値の確認先は**ページ本文の「確認用URL」**に残るので、後から人の目で確認できます。

### 2つの使い方
- **(A) チャットで聞く** … Claude Desktop の Code タブに「この会社を調べて」と話しかける
- **(B) Notion の空欄をまとめて補完** … すでに会社名や住所が入っている行の、空いている項目だけ埋める

---

## 2. 全体の流れ(やることは4つ)

```
[ステップ0] Claude Desktop を用意   … アプリを入れて Code タブでこのフォルダを開く (一度だけ)
        ↓
[ステップA] 事前準備               … トークンを登録し、Notion とつなぐ (一度だけ・約10分)
        ↓
[ステップB] インストール           … プラグインを入れる (一度だけ・約2分)
        ↓
[ステップC] 使う                  … Code タブで会社情報を集める (毎回)
```

> **大事な前提**: このプラグインのような独自プラグインは、Claude Desktop の「設定(Settings)→ Extensions」画面からは追加できません(あの画面は公式ストアのプラグイン専用です)。
> 代わりに **Code タブのチャット欄にコマンドを打ち込んで** 追加します。本ガイドはその方法を案内します。

---

## 3. 事前に準備するもの(チェックリスト)

- [ ] **Mac**(macOS)
- [ ] **Claude Desktop アプリ**と、**Pro / Max / Team / Enterprise いずれかのプラン**(Code 機能に必要)
- [ ] **Notion のアカウント**と、情報を貯める **データベース(一覧表)**
  - 出力先のデータベースは **このプラグインに既定で設定済み**です(ID 入力は不要)
- [ ] **Notion の API トークン**(`ntn_` で始まる文字列。[My integrations](https://www.notion.so/my-integrations) で「New integration」を作ると発行)
- [ ] **gBizINFO の API トークン**([gBizINFO 利用申請](https://info.gbiz.go.jp/hojin/APIManual)。無料・数時間〜即日でメール)

> トークン2つ(Notion・gBizINFO)が手元にそろってから次へ進んでください。

---

## 4. ステップ0: Claude Desktop を用意する

1. ブラウザで **https://claude.com/download** を開き、**Claude Desktop(Mac 版)** をダウンロードして、アプリを **アプリケーション** フォルダに入れる
2. アプリを起動し、**自分の Anthropic アカウントでサインイン**する
3. 画面上部の **「Code」タブ** をクリックする(ここが、設定や操作を打ち込む場所です)
4. **「Select folder(フォルダを選択)」** をクリックし、**このプラグインが入ったプロジェクトフォルダ** を選ぶ
5. 「このフォルダを信頼しますか?」と聞かれたら **信頼(Trust)** を選ぶ

> これ以降の「Code タブのチャット欄に〜と入力」という指示は、この画面下部の入力欄に文字を打って Enter する操作を指します。

---

## 5. ステップA: 事前準備(すべて Code タブで実行)

> **チームで配布する場合**: 「どの鍵を Keychain に入れるか」をロール別(チームメンバー / 中央プロキシ運用者)に
> まとめた配布用の正本が [`references/keychain-setup.md`](references/keychain-setup.md) にあります。
> 多拠点・フルリモートのチームは**中央プロキシが既定**で、メンバーは日本郵便の鍵を持たず `proxy_url`/`proxy_token` だけ登録します。
> Mac で自分の送信元(グローバル)IP を調べる方法も同書に記載。以下 5-1〜5-2.5 は単独/少数拠点(BYO)向けの個別手順です。

### 5-1. Notion のトークンを登録

Code タブのチャット欄に、**トークンを書かずに** 次のように頼みます(Enter):

```
Notion のトークンを Keychain に登録して。サービス名は notion-api-key.xl-skills、アカウントは xl-skills
```

Claude が「トークンを教えてください」と聞いてきたら、そのときだけトークン(`ntn_` で始まる文字列)を貼り付けて渡してください。

> こうすると、指示メッセージにトークン平文を含めずに登録できます。
> エラーが出ずに「登録しました」と返れば成功です。
>
> **(代替・上級者向け)** 1行で済ませたい場合は、次を貼り付けても登録できます(**トークン平文がチャット履歴に残る**点に注意。`<...>` を自分のトークンに置き換え):
> `! security add-generic-password -s notion-api-key.xl-skills -a xl-skills -w '<NOTION_INTEGRATION_TOKEN>' -T '' -U`
> (行頭の `!` は「このコマンドをそのまま実行して」という意味です)

### 5-2. gBizINFO のトークンを登録

同じように、トークンを書かずに頼みます:

```
gBizINFO のトークンを Keychain に登録して。サービス名は gbizinfo-api-token.xl-skills、アカウントは xl-skills
```

聞かれたら、申請して届いた gBizINFO トークンを貼り付けて渡してください。

> **(代替・上級者向け)** `! security add-generic-password -s gbizinfo-api-token.xl-skills -a xl-skills -w '<GBIZINFO_API_TOKEN>' -T '' -U`(平文がチャット履歴に残る点に注意)

### 5-2.5. 日本郵便 郵便番号API のキーを登録(郵便番号を自動取得する場合)

住所→郵便番号の自動取得には日本郵便「郵便番号・デジタルアドレスAPI」の鍵が要ります。取得〜登録の詳しい手順は [`references/japanpost-api-setup.md`](references/japanpost-api-setup.md) を参照してください。要点だけ:

1. `client_id` と `secret_key` を取得(**secret_key は初回のみ表示**)。
2. Keychain に登録(env ファイルは使わず Keychain に保存。secret_key は `-w` を空にして対話入力 → 履歴に残さない):

```
! security add-generic-password -U -s japanpost-da-api -a client_id -w '<あなたのclient_id>'
! security add-generic-password -U -s japanpost-da-api -a secret_key -w
```

3. `! python3 plugins/company-master/scripts/company_master.py doctor` を実行 → 「送信元IP」行に**自分の送信元IP**が表示される。その IP を日本郵便 for Biz のシステム登録で**送信元IP**として登録(最大10件)。
   - 送信元IPは**自動検出**されるので env も保存も基本不要。プロキシ等で固定したいときだけ Keychain に pin: `! security add-generic-password -U -s japanpost-da-api -a egress_ip -w '<IP>'`

> 鍵が未設定でも他の機能は動きます。その場合は郵便番号だけ空欄+備考になります。`! ... doctor --probe` で実疎通(登録IPとのズレ)を確認できます。

### 5-3. 登録できたか確認(トークンの中身は表示しません)

Code タブのチャット欄に次を貼り付けて Enter:

```
! security find-generic-password -s notion-api-key.xl-skills -a xl-skills >/dev/null 2>&1 && echo "Notion: 登録OK" || echo "Notion: 未登録"; security find-generic-password -s gbizinfo-api-token.xl-skills -a xl-skills >/dev/null 2>&1 && echo "gBizINFO: 登録OK" || echo "gBizINFO: 未登録"; security find-generic-password -s japanpost-da-api -a client_id >/dev/null 2>&1 && echo "日本郵便: 登録OK" || echo "日本郵便: 未登録(郵便番号は空欄になります)"
```

> **すべて「登録OK」** と出れば成功です(日本郵便は郵便番号取得を使う場合のみ必須)。
> 途中で Mac の許可ポップアップが出たら **「常に許可」** を選ぶと、次回から出ません。

### 5-4. Notion のデータベースに連携を「接続」する(ブラウザでクリック操作)

トークン登録だけでは Notion 側が書き込みを許可していません。下記をクリックで接続します。

1. ブラウザで、情報を貯める **Notion のデータベース(一覧表)のページ** を開く
2. 右上の **「…」(三点メニュー)** をクリック
3. **「コネクト(Connections)」→「接続を追加」** を選ぶ
4. 手順 3 で作った **自分の Integration(連携)** を選んで追加

> これを忘れると、後で「権限がありません(401/403)」エラーになります。

### 5-5. (任意・推奨)安全設定を有効にする

トークンが誤って画面に出たり削除されたりするのを防ぐ追加設定です。詳しい手順は
[`references/README-setup.md`](references/README-setup.md) の「settings-hardening」を参照(任意)。

---

## 6. ステップB: プラグインのインストール(Code タブで実行)

> Claude Desktop の **設定画面ではなく、Code タブのチャット欄** で行います(独自プラグインは設定画面から追加できないため)。

### 6-1. このプロジェクトを「マーケットプレイス」として登録

Code タブのチャット欄に次を入力して Enter:

```
/plugin marketplace add .
```

> `.` は「いま開いているフォルダ」を指します。`エラーが出る場合`はフォルダのフルパスを指定してください(例: `/plugin marketplace add /Users/あなた/プロジェクト`)。

### 6-2. プラグインをインストール

```
/plugin install company-master@xl-skills
```

> 画面の指示に従って許可すればインストールされます。
> メニューから選びたい場合は、`/plugin` だけ入力すると一覧メニューが開きます。

### 6-3. 入ったか確認

```
/plugin list
```

> 一覧に **`company-master`** が表示されれば成功です。
> (関連プラグインをまとめて入れたい場合は `/skill-creator:install-bundle xl-skills-full` も使えます)

---

## 7. ステップC: 使い方(毎回・Code タブで)

### 7-1. いちばん簡単: チャットで話しかける

Code タブの入力欄に、ふつうの言葉で伝えるだけです。

| やりたいこと | 話しかけ例 |
|---|---|
| 会社を調べて Notion に登録 | 「株式会社サンプルを調べて企業マスタに登録して」 |
| 住所だけ分かっている | 「東京都千代田区丸の内1-1 の会社を調べて」 |
| 法人番号から調べる | 「法人番号 1234567890123 の会社情報を埋めて」 |

> 同じ名前の会社が複数見つかった場合や住所だけで1社に絞れない場合は、Claude が **候補一覧を出して「どれですか?」と聞きます**。選ぶだけでOKです。確実に決められないものは無理に登録せず「未確定(要確認)」で保留します。

### 7-2. コマンドで実行する

Code タブの入力欄に:

```
/company-master --name "株式会社サンプル" --address "東京都千代田区..." --upsert
```

- `--name`(会社名) / `--address`(住所) / `--hojin-bango`(法人番号)のいずれかを指定
- **`--upsert` を付けたときだけ Notion に書き込みます**。付けないと「調べるだけ(書き込まない)」
- まず `--upsert` なしで確認 → 良ければ `--upsert` 付きで本登録、が安全です

### 7-3. Notion の空欄をまとめて補完する(backfill)

```
/company-master-backfill --dry-run
```

- `--dry-run` は **書き込まず、対象行だけ確認** するお試しモード
- 想定どおりなら `--dry-run` を外して本実行
- すでに値が入っているセルは **上書きしません**(空欄だけ埋めます)

### 7-4. 結果の見方

- **「情報の確かさ」** が「ネット検索(要確認)」「未確定(要確認)」の行は、人の目で確認すると安心
- **ページ本文の「確認用URL（手動検証用）」** … ネット検索で調べた値の根拠ページ。企業ページを開くと本文に出ます。クリックして正誤を確認できます
- **「備考」** … 取れなかった項目の理由が定型文で入ります(例:「【取得失敗】電話番号: …」)

---

## 8. 最初の動作確認(おすすめ)

いきなり本登録せず、まず1社で「書き込みなし」で試すと安心です。

1. Code タブで「`株式会社サンプル` を調べて。まだ Notion には書き込まないで」と伝える
2. 出てきた結果(正式名称・住所・郵便番号など)が正しそうか目で確認する
3. 問題なければ「では Notion に登録して」と伝える(または `--upsert` 付きで実行)
4. Notion のデータベースに行が追加され、各列が埋まっていることを確認する

---

## 9. うまくいかないとき

まずは **一括診断 (doctor)** を実行すると、どこでつまずいているかを 1 回でまとめて確認できます。Code タブのチャット欄に:

```
company-master の doctor(セットアップ診断)を実行して
```

(コマンドで直接実行する場合: `! python3 plugins/company-master/scripts/company_master.py doctor`)

> doctor は「トークン2つの登録 / 書き込み先データベースの設定 / Notion への接続と列構成の一致 / 安全設定の適用」を順に点検し、各項目を **OK / WARN / FAIL / SKIP** と「次に何をすべきか」付きで日本語表示します(トークンの中身は表示しません)。FAIL の項目だけ、表示された次アクションを実施してください。

| 症状 | 原因と対処 |
|---|---|
| 設定(Settings)画面にプラグインが見つからない | 独自プラグインは設定画面からは追加できません。**Code タブで** 手順 6 のコマンドを使ってください |
| `/plugin marketplace add .` でエラー | `.` の代わりにフォルダのフルパスを指定。Code タブで開いているフォルダがこのプロジェクトか確認 |
| `gBizINFO トークン不在` で止まる | 手順 5-2 が未実施、または綴り違い。手順 5-3 の確認で「登録OK」になるか確認 |
| Notion で「権限がありません(401/403)」 | 手順 5-4 の「接続」が未実施。データベースに Integration を接続したか確認 |
| トークンを入れ直したい | 手順 5-1 / 5-2 と同じ手順をもう一度行えば上書き登録されます |
| `BLOCKED: ... find-generic-password -w` と出る | 安全装置が「トークンの中身の表示」を止めた正常動作です。中身を画面に出す必要はありません |
| 実行中に Mac の許可ポップアップが出る | キーチェーンへのアクセス確認です。「常に許可」を選ぶと次回から出ません |
| 同名の会社が多すぎる/住所だけで絞れない | 仕様どおりです。候補から選ぶか、保留(未確定)のまま後で確認してください |
| 郵便番号がいつも空欄で、備考に「日本郵便APIの認証に失敗」と出る | 日本郵便 addresszip API の鍵未登録か、送信元IPが for Biz 登録値とズレています。[`references/japanpost-api-setup.md`](references/japanpost-api-setup.md) の手順で client_id/secret_key を Keychain `japanpost-da-api` に登録し、`! ... doctor` が表示する送信元IPを日本郵便 for Biz に登録してください(IPは自動検出。固定したいときだけ Keychain `egress_ip` に pin)。`! python3 plugins/company-master/scripts/company_master.py doctor --probe` で実疎通と登録IPとのズレを確認できます |
| 郵便番号が空欄で、備考に「日本郵便APIへの通信に失敗」と出る | ネットワーク不達か日本郵便側の一時障害です。時間をおいて再実行してください。誤った郵便番号は入れず空欄+備考で保留する設計です |
| 送信元IPがバラつく / 多拠点(社内チーム・フルリモート)で使う | 日本郵便のIP許可リストは1鍵最大10件のため、各自が直接叩く方式は成立しません。**鍵と固定IPを1台に集約する中央プロキシ**を立て、各クライアントは `proxy_url` だけ設定します(既定の本番配布モデル)。手順: [`references/postal-proxy-deploy.md`](references/postal-proxy-deploy.md) |

---

## 10. 技術的な詳細(エンジニア向け)

- セットアップのコマンド詳細・トラブルシュート: [`references/README-setup.md`](references/README-setup.md)
- 仕様(何を・どう処理するか)の正本: [`skills/run-company-master-build/SKILL.md`](skills/run-company-master-build/SKILL.md)
- Notion の列定義: [`references/company-master-columns.md`](references/company-master-columns.md)
- 取得元(gBizINFO / 日本郵便 / ネット検索)と確かさの基準: [`references/data-sources.md`](references/data-sources.md)

> 改善要望は Code タブで「`company-master` の○○を直してほしい」と伝えるか、`/run-skill-feedback company-master` で投入できます。

---

## 出典(Claude Desktop / プラグインの最新仕様)

- [Claude Code Docs — Desktop application](https://code.claude.com/docs/en/desktop)
- [Claude Code Docs — Get started with the desktop app](https://code.claude.com/docs/en/desktop-quickstart)
- [Claude Code Docs — Discover and install prebuilt plugins through marketplaces](https://code.claude.com/docs/en/discover-plugins)
- [Claude Code Docs — Create and distribute a plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces)
- [Claude Code Docs — Plugins reference](https://code.claude.com/docs/en/plugins-reference)
