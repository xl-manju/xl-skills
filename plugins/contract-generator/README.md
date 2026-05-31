# contract-generator セットアップ手順書

> このプラグインを動かすために**あなたが一度だけ行う設定**を、上から順にこなすだけで完了するようまとめています。
> 機密(API鍵・トークン)は全て macOS Keychain に保管します(平文ファイルに残しません)。

## このプラグインができること(概要)

管理台帳(Google Sheets)のチェックが入っていない行を読み、Drive上の.docxひな形(個人/法人)に値を差込んで業務委託契約書を生成し、Slackに通知 → あなたがSlackで承認(✅/OK)し **Claude Code で確定を指示したとき** にPDF化して共有 → 台帳に完了チェック、までを半自動化します。承認はあくまで *記録* で、PDF確定は明示指示で発火します(pull型・誤確定防止)。**常駐サーバーのデプロイは不要**で、Claude Code単体で動きます。

---

## 使い方(セットアップ後・毎回)

**通常は Claude Code に話しかけるだけです。** 下記のように頼むと、対応するスキルが自動で起動し、設定(`~/.config/contract-generator/google-config.json`)や差込定義を**正しい場所から自動で読み込んで**実行します。ターミナルで `cd` したりコマンドを打つ必要はありません。

| やりたいこと | Claude Code への話しかけ例 | 起動するスキル |
|---|---|---|
| 契約書の下書きを作る | 「契約書の下書きを作って」 | `run-contract-generate` |
| 承認後に PDF を確定する | 「契約書のPDFを確定して」 | `run-contract-finalize` |
| ひな形が変わったので追従 | 「契約書のひな形が変わりました」 | `run-template-sync` |
| 使ってみた改善要望を送る | 「このスキルの○○が分かりにくい/直してほしい」 | `run-skill-feedback`(skill-creator 共通スキル) |

> 💡 仕組み: 各スキルは内部で `$CLAUDE_PLUGIN_ROOT`(Claude Code がプラグインの実体位置を指す変数)経由でコマンドを実行するため、**あなたの作業ディレクトリがどこでも動きます**。設定ファイルはホーム配下(`~/.config/contract-generator/`)の絶対パスで読まれるので、プラグインを更新しても消えません。

> 🛠 以下に出てくる手動の `python3 lib/...` コマンドは **初回セットアップ・疎通確認・cron 自動化のとき限定**の補助手段です。日常運用では不要です(ターミナルで直接動かしたい場合のみ使用。その際は下記「作業ディレクトリの固定」に従って plugin フォルダで実行してください)。

---

## Quickstart (設定済みの方向け・5 step / 設定済みなら5分)

**この5 stepは「2回目以降・既にセットアップを終えた方」向けの最短手順**です(Task 1-9 の SA 作成・Keychain 登録・Slack App 設定が完了済みであることが前提)。
**初回の方は、この Quickstart を飛ばして下の [Detailed Setup](#detailed-setup) (Task 0-14・初回所要 約30〜40分) から進めてください。**

| step | 操作 | 完了確認 |
|---|---|---|
| 1 | **SA 鍵を Keychain 登録**: Detailed Setup の [Task 4](#task-4-sa鍵を-keychain-に登録する平文ファイルは即削除) を実行。Task 4 内でインストール済み plugin の場所を `~/.claude` 配下から自動検出します。⚠️ SA鍵は登録後すぐ削除(平文ファイルを残さない) | `python3 lib/keychain_get_secret.py --service xl-skills-gdrive --account "contract-generate/service-account-json" --check` が `OK` |
| 2 | **`google-config.json` を設定フォルダに配置**: `mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/contract-generator" && cp skills/run-contract-generate/references/google-config.sample.json "${XDG_CONFIG_HOME:-$HOME/.config}/contract-generator/google-config.json"` して `slack_channel` を自分の channel ID に編集 | `~/.config/contract-generator/google-config.json` があり値を編集済 |
| 3 | **draft 実行 (台帳の◯行を契約書化 → Slack通知)**: `python3 lib/engine.py --phase draft --type all` | 個人/法人フォルダに黄色維持版 Docs が作成され Slack に通知が届く |
| 4 | **Docs(黄色版)の内容を確認**(Slack通知のリンクから。✅/OK は任意・発火条件ではない) | 下書き内容に問題がないことを目視確認 |
| 5 | **finalize 実行 (Claude Code で確定を指示 → draft 行を直接 PDF 化)**: `python3 lib/engine.py --phase finalize --type all`(自動化したい場合のみ純Pythonを cron。`/loop` はトークン費用が嵩むため非推奨) | PDF が同フォルダに保存され台帳ステータスが `completed` |

### 事前条件 (Quickstart 開始前に必須)

- **Task 4-2 の手順で `contract-generator` フォルダに移動済**。インストール済み plugin は通常 `~/.claude` 配下にあります。
- macOS / Python 3.11+ / gcloud CLI 導入済 (Detailed Setup Task 1-2)
- Google Cloud で SA 作成済・Drive/Sheets API 有効化済 (Task 3-5)
- Slack App 作成済・Bot Token を Keychain (`xl-skills-slack`) に登録済 (Task 6-9)
- **甲 (発注者) の固定値**は `lib/config_auth.load_party_a()` を SSOT とする (ハードコード禁止)。優先順位: `$XL_PARTY_A_JSON_PATH` > `~/.config/contract-generator/party_a.json` > `~/.config/xlocal/party_a.json`(後方互換) > `references/party_a.default.json`。デフォルトは株式会社XLOCAL。上書きは `references/party_a-readme.md` 参照。

> 上記が揃っているか不安なときは `python3 lib/setup_doctor.py` を実行すると、未完了の Task を名指しで教えてくれます。

---

## Detailed Setup

以下は初回セットアップの完全版。各タスクは「①コマンド/操作 → ②✅完了確認 → ③次のタスクへ」の形。**上から順に、飛ばさず**進めてください。

> ✅ **`pip install` は一切不要**：.docx編集・Google Drive/Sheets・Slack は全て **Python 標準ライブラリ**(`zipfile`/`xml.etree`/`urllib`)で実装しています。外部Pythonライブラリの導入で詰まる心配はありません。認証トークンの取得だけ gcloud CLI(コマンドラインツール)を使います(Task 2)。

---

## 事前に用意するもの(チェックリスト)

- [ ] macOS(Keychainを使うため)
- [ ] Googleアカウント(Drive/Sheetsの管理者)
- [ ] Google Cloud のプロジェクトを作れる権限
- [ ] Slackワークスペースの管理者(またはApp作成権限)
- [ ] ひな形フォルダ・出力フォルダ・管理台帳のURL(=ID)

> 所要時間の目安: 全タスクで約30〜40分。

---

> ⚠️ **作業ディレクトリの固定(重要)**
> 以降の `python3 lib/...` コマンドは全て **`contract-generator` フォルダ**で実行します。
> `/plugin install` 済みの場合、実体は通常 `~/.claude` 配下にあります。Task 4-2 の手順で自動検出して移動してください。
> 開発中のリポジトリから実行する場合のみ、`plugins/contract-generator` フォルダに移動します。

---

## Task 0. プラグインを有効化する(フックを効かせる前提)

このプラグインの **PreToolUse フック(機密ガード `hook-guard-secret.py`)は、プラグインを有効化して初めて発火**します。`.claude-plugin/marketplace.json` に登録済みなので、以下で有効化します。

```bash
# Claude Code でこの marketplace を追加し、contract-generator を有効化
/plugin marketplace add <このリポジトリのパス or URL>
/plugin install contract-generator@xl-skills
```

✅ 完了確認: `/plugin` 一覧に `contract-generator` が enabled で表示される。SA鍵を `--print-unsafe` で出そうとするとブロックされる(`hook-guard-secret.py` が動作)。
- 有効化しない場合のフォールバック: `skills/run-contract-generate/references/settings-hardening.json` の `permissions.deny` を `.claude/settings.json` に手動マージ(Task 11)。
→ できたら Task 1 へ。

---

## Task 1. Python が動くか確認する（pip install は不要）

このプラグインは **Python 標準ライブラリだけで動作**します（`pip install` 一切不要）。
.docx編集・Google REST・Slack は全て標準ライブラリ(`zipfile`/`xml.etree`/`urllib`)で実装済みです。

```bash
python3 --version    # 3.11 以上であればOK
```

✅ 完了確認: `Python 3.11.x` 以上が表示される。外部ライブラリのインストールは行いません。
→ 表示されたら Task 2 へ。

> 💡 認証(Service Accountの署名)だけは標準ライブラリで完結できないため、次の Task 2 で導入する **gcloud CLI**(コマンドラインツール。pipパッケージではない)を使ってトークンを取得します。

---

## Task 2. Google Cloud で API を有効化する

```bash
# gcloud 未導入なら: https://cloud.google.com/sdk/docs/install
gcloud auth login                      # ブラウザでGoogleログイン
gcloud config set project <あなたのPROJECT_ID>
gcloud services enable drive.googleapis.com sheets.googleapis.com
gcloud services list --enabled | grep -E "drive|sheets"
```

✅ 完了確認: 最後に `drive.googleapis.com` と `sheets.googleapis.com` の2行が表示される。
→ 表示されたら Task 3 へ。

---

## Task 3. Service Account(SA) を作り、鍵を発行する

```bash
gcloud iam service-accounts create xl-contract-sa --display-name "XL Contract Generator"

gcloud iam service-accounts keys create /tmp/xl-contract-sa.json \
  --iam-account "xl-contract-sa@<あなたのPROJECT_ID>.iam.gserviceaccount.com"

# SAのメールアドレスを控える(Task 5で使う)。表示された値をコピーしておく。
echo "SAメール: xl-contract-sa@<あなたのPROJECT_ID>.iam.gserviceaccount.com"
```

✅ 完了確認: `/tmp/xl-contract-sa.json` が作られ、`ls -la /tmp/xl-contract-sa.json` でファイルが見える。SAメールをメモした。
→ できたら Task 4 へ。

---

## Task 4. SA鍵を Keychain に登録する(平文ファイルは即削除)

用意済みの SA鍵 JSON ファイルを macOS Keychain に保存し、元の JSON ファイルはすぐ削除します。

> ⚠️ SA鍵 JSON の中身(`private_key` など)は、チャット・Slack・メール・ドキュメントに貼らないでください。
> この手順では **JSON の中身ではなく、ファイルの場所(ファイルパス)** だけを Terminal に入力します。
> 中身を貼ってしまった場合は、その鍵を Google Cloud で削除し、新しい鍵を作り直してください。

### 4-1. SA鍵 JSON のファイルパスを指定する

まず Finder で、手元にある SA鍵 JSON ファイルのパスを確認します。

1. Finder で SA鍵 JSON ファイルを表示します。
2. そのファイルを右クリックします。
3. `option` キーを押したままにします。
4. メニュー内の **"xxxx.json"のパス名をコピー** をクリックします。
5. コピーした値を、下の `<SA鍵JSONのパス>` の代わりに貼り付けます。

たとえば、コピーしたパスが `/Users/taro/Downloads/xl-contract-sa.json` の場合は、次のようにします。

```bash
SA_KEY_JSON="/Users/taro/Downloads/xl-contract-sa.json"
```

自分の環境では、`/Users/taro/Downloads/xl-contract-sa.json` の部分を、Finder でコピーしたパスに置き換えてください。

ファイルが存在することを確認します:

```bash
ls -la "$SA_KEY_JSON"
```

✅ ファイル名が表示されればOKです。`No such file or directory` と出た場合は、パスが違うので 4-1 をやり直してください。

### 4-2. contract-generator のフォルダへ移動する

通常、インストール済み plugin は `~/.claude` 配下にあります。
Finder で探す必要はありません。次のコマンドをそのまま実行して、`keychain_get_secret.py` の場所を自動で探します。

```bash
KEYCHAIN_HELPER="$(find "$HOME/.claude" -type f -path '*/contract-generator/lib/keychain_get_secret.py' -print -quit 2>/dev/null)"
if [ -z "$KEYCHAIN_HELPER" ]; then
  echo "contract-generator が ~/.claude 配下に見つかりません。/plugin install が完了しているか確認してください。"
else
  echo "$KEYCHAIN_HELPER"
fi
```

✅ `.../contract-generator/lib/keychain_get_secret.py` のようなパスが表示されればOKです。
見つからないメッセージが出た場合は、先に `/plugin install contract-generator@xl-skills` が完了しているか確認してください。

続けて、スクリプトを実行できる `contract-generator` フォルダへ移動します。

```bash
CONTRACT_GENERATOR_DIR="$(dirname "$(dirname "$KEYCHAIN_HELPER")")"
cd "$CONTRACT_GENERATOR_DIR"
```

移動できたか確認します:

```bash
pwd
ls -la lib/keychain_get_secret.py
```

✅ `pwd` の最後が `contract-generator` になり、`lib/keychain_get_secret.py` が表示されればOKです。

> 開発中のリポジトリから実行していて `KEYCHAIN_HELPER` が空になる場合のみ、`CONTRACT_GENERATOR_DIR` に開発中の `plugins/contract-generator` フォルダのパスを指定してから `cd "$CONTRACT_GENERATOR_DIR"` してください。

### 4-3. Keychain に登録して、元ファイルを削除する

```bash
security add-generic-password \
  -s xl-skills-gdrive \
  -a "contract-generate/service-account-json" \
  -w "$(< "$SA_KEY_JSON")" \
  -U

# ⚠️ SA鍵 JSON は登録後すぐ削除(平文を残さない)
shred -u "$SA_KEY_JSON" 2>/dev/null || rm -P "$SA_KEY_JSON"

# 確認(鍵はマスク表示される。hook 経由必須: CLAUDE_HOOK_INVOKED=1)
CLAUDE_HOOK_INVOKED=1 python3 lib/keychain_get_secret.py \
  --service xl-skills-gdrive --account "contract-generate/service-account-json" --check

# 元ファイルが削除されていることを確認
test ! -e "$SA_KEY_JSON" && echo "SA鍵 JSON は削除済みです"
```

✅ 完了確認: 最後に `OK {...マスク...}` と表示され、`SA鍵 JSON は削除済みです` と表示される。

> `--check` は「Keychain から値を取り出せるか」だけを確認します。
> SA鍵 JSON として正しいかは Task 12 の `python3 lib/setup_doctor.py` で確認します。
> `setup_doctor.py` で `Could not read json file ... Extra data` が出た場合は、JSON 全体ではなく `private_key_id` など一部の文字列が Keychain に入っている可能性があります。
> `Could not read json file ... Expecting value` が出た場合は、JSON の中身ではなく `/Users/...` のようなファイルパスを Keychain に登録している可能性があります。
> どちらの場合も 4-1 からやり直し、正しい SA鍵 JSON ファイルのパスを指定して 4-3 を再実行してください。`security add-generic-password ... -U` により同じ service/account の値は上書きされます。
→ 表示されたら Task 5 へ。

---

## Task 5. Drive のフォルダと台帳を 万壽本 に共有する

Drive をブラウザで開き、以下を **Task 3で控えた SAメール** に共有します(右クリック→共有→メール貼り付け→権限を選択)。

| 対象 | ID | 権限 |
|---|---|---|
| ひな形フォルダ | `1kgD_H1aVOKWZTg-cgkQACzGb9M73N0Bu` | 閲覧者 |
| 出力フォルダ(親) | `1X31oVxf_X_weJfJJxOUZNAjkRA3orXBm` | 編集者 |
| └ 個人フォルダ | `1uVsw6_jyIKcDBMYaW4btHWC9jOu4EJ9w` | 編集者 |
| └ 法人フォルダ | `1I2xWORsX-8IbDQEG6iMCRvoIlKV1sDqG` | 編集者 |
| 管理台帳 | `1_24Bh1vRx4d9nMgS9InWIt1TlYwNyJh4Eu8j5SYfLms` | 編集者 |

✅ 完了確認: 5つ全てに「編集者(ひな形は閲覧者でも可)」でSAメールが追加されている。
→ できたら Task 6 へ。

> ⚠️ **共有範囲のガード(重要)**: 共有ダイアログの「**全般アクセス**」は「**制限付き**」のままにし、**特定ユーザー(上記 SAメール)だけ**を追加してください。**「リンクを知っている全員」にはしない**こと — 乙の住所・代表者・口座などの機微情報が外部に漏れます。
> 💡 同じ理由で、共有相手(人間)も最小限にしてください。
> 💡 `storageQuotaExceeded` が出る場合、出力先が My Drive 配下で、Service Account がファイル所有者になれずアップロードできていません。出力先の個人/法人フォルダを **共有ドライブ** 配下に作り、SAメールをコンテンツ管理者または編集者として追加し、`google-config.json`(`~/.config/contract-generator/`)の `individual_folder_id` / `corporate_folder_id` を共有ドライブ上のフォルダIDに差し替えてください。

---

## Task 6. Slack App を作る

1. https://api.slack.com/apps をブラウザで開く → **Create New App** → **From scratch**。
2. App Name: `XL Contract Notifier`、ワークスペースを選択 → **Create App**。

✅ 完了確認: Appの管理画面(Basic Information)が開いている。
→ できたら Task 7 へ。

---

## Task 7. Slack Bot Token の権限(scope)を設定する

1. 左メニュー **OAuth & Permissions** を開く。
2. **Scopes → Bot Token Scopes** に以下を **Add an OAuth Scope** で追加:

| scope | 区分 | 用途 |
|---|---|---|
| `chat:write` | **必須** | 契約書通知の送信 |
| `channels:read` | **必須** | 通知先 public チャンネルへBotが到達できるか確認 |
| `channels:history` | **必須** | 通知メッセージへの「OK」返信を読む(publicチャンネル) |
| `reactions:read` | **必須** | 「✅」リアクションでの承認を読む |
| `groups:read` | 条件付き | privateチャンネルを通知先に使う場合のみ |
| `groups:history` | 条件付き | privateチャンネルを通知先に使う場合のみ |
| `files:write` | 任意 | PDFをSlackに添付する場合のみ |

> 最小権限原則: public チャンネル運用なら **必須4つ(`chat:write`/`channels:read`/`channels:history`/`reactions:read`)だけで動きます**。private チャンネルを使う場合は `groups:read` と `groups:history` も追加してください。`files:write` は PDF 添付時だけ追加してください。
> scope を追加・変更したら、必ずページ上部の **Reinstall to Workspace** を実行してください。再インストール後に表示された Bot User OAuth Token を Task 8 で Keychain に登録します。

3. ページ上部 **Install to Workspace** → 許可 → **Bot User OAuth Token**(`xoxb-` で始まる)が表示される。これをコピー。

✅ 完了確認: `xoxb-` で始まるトークンをコピーした。
→ コピーしたら Task 8 へ。

---

## Task 8. Slack Bot Token を Keychain に登録する

`<ここにxoxb-トークン>` を Task 7 でコピーした値に置き換えて実行:

```bash
security add-generic-password \
  -s xl-skills-slack \
  -a "contract-generate/bot-token" \
  -w "<ここにxoxb-トークン>" \
  -U

# 確認(マスク表示。hook 経由必須: CLAUDE_HOOK_INVOKED=1)
CLAUDE_HOOK_INVOKED=1 python3 lib/keychain_get_secret.py \
  --service xl-skills-slack --account "contract-generate/bot-token" --check
```

✅ 完了確認: `OK {xoxb...マスク...}` と表示される。
→ 表示されたら Task 9 へ。

---

## Task 9. 通知用チャンネルを用意し、Bot を招待して channel ID を取得

1. Slackで通知用チャンネル(例 `#契約書通知`)を作る(既存でも可)。
2. そのチャンネルで `/invite @XL Contract Notifier` を実行し Bot を招待。
3. **channel ID の取得**: チャンネル名をクリック→一番下に `チャンネルID: C0XXXXXXXXX` が表示される。これをコピー。

> 💡 必要なのは `#契約書通知` のような **チャンネル名ではなく、`C` で始まる ID** です。チャンネルの「リンクをコピー」した URL 末尾(`/archives/C0XXXXXXXXX` の `C...` 部分)からも取得できます。
> `channel_not_found` が出る場合は、`google-config.json` の `slack_channel` が、今の Bot Token の workspace から見えていません。channel ID が正しい場合は、Slack App をインストールした workspace と、チャンネルIDをコピーした workspace が違う可能性が高いです。対象 workspace で **Reinstall to Workspace** し、表示された新しい token を Task 8 で Keychain に再登録してください。

✅ 完了確認: Botがチャンネルメンバーに居る／`C` で始まる channel ID をコピーした。
→ できたら Task 10 へ。

---

## Task 10. `google-config.json` を作る(環境IDの設定ファイル)

設定は **ホームの設定フォルダ `~/.config/contract-generator/`** に置きます。ここはあなた専用の場所で、**このプラグインを更新・再インストールしても消えません**(プラグイン本体の中には置きません)。サンプルをこのフォルダにコピーして、自分の値に編集します(cwd=`plugins/contract-generator/`):

```bash
# 設定フォルダを用意(無ければ作成)。${XDG_CONFIG_HOME:-$HOME/.config} は通常 ~/.config を指します
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/contract-generator"
mkdir -p "$CONFIG_DIR"
cp skills/run-contract-generate/references/google-config.sample.json "$CONFIG_DIR/google-config.json"
echo "作成しました: $CONFIG_DIR/google-config.json"
```

> 💡 `~/.config/contract-generator/` はホーム配下なので、もともと git の管理対象外です(誤コミットの心配がありません)。Finder で開くには `open ~/.config/contract-generator` を実行してください。
> 🔁 **後方互換**: すでに開発リポジトリのルートに `.google-config.json` を置いて運用している場合も、引き続きそのまま動きます(新しい `~/.config/contract-generator/google-config.json` があればそちらを優先します)。

`$CONFIG_DIR/google-config.json` を開き、`slack_channel` に Task 9 の channel ID を追記:
```json
{
  "spreadsheet_id": "1_24Bh1vRx4d9nMgS9InWIt1TlYwNyJh4Eu8j5SYfLms",
  "templates_folder_id": "1kgD_H1aVOKWZTg-cgkQACzGb9M73N0Bu",
  "individual_folder_id": "1uVsw6_jyIKcDBMYaW4btHWC9jOu4EJ9w",
  "corporate_folder_id": "1I2xWORsX-8IbDQEG6iMCRvoIlKV1sDqG",
  "keychain_service": "xl-skills-gdrive",
  "keychain_account": "contract-generate/service-account-json",
  "slack_channel": "C0XXXXXXXXX",
  "slack_keychain_service": "xl-skills-slack",
  "slack_keychain_account": "contract-generate/bot-token"
}
```

✅ 完了確認: `~/.config/contract-generator/google-config.json` が存在し、`slack_channel` に自分のIDが入っている(`cat "${XDG_CONFIG_HOME:-$HOME/.config}/contract-generator/google-config.json"` で確認できます)。
→ できたら Task 11 へ。

---

## Task 11. セキュリティ強化設定をマージする(任意だが推奨)

鍵の平文出力・誤削除をブロックする静的ルールを Claude Code 設定に取り込みます。

```bash
cat skills/run-contract-generate/references/settings-hardening.json
```

表示された `permissions.deny` の配列を、`.claude/settings.json`(無ければ作成)の `permissions.deny` に追記してください。

✅ 完了確認: `.claude/settings.json` に鍵ガードの deny ルールが入っている。
→ できたら Task 12 へ。

---

## Task 12. 疎通確認(設定が全部通っているかテスト)

セットアップ全体を一括診断します。cwd / Python / gcloud / 環境変数 / Keychain(SA鍵・Slack) / `google-config.json` / Drive / Sheets / Slack を横断点検し、未完了があれば**戻るべき Task 番号を名指し**します(正本は `~/.config/contract-generator/google-config.json`):

```bash
python3 lib/setup_doctor.py
```

✅ 完了確認: 最後に `✅ セットアップは整っています(draft 実行可能)。` と表示されれば成功です。
- `要対応: Task N` と出たら、その Task に戻って実施し、再度 `setup_doctor.py` を実行してください(全項目クリアまで繰り返す)。
- `Could not read json file ... Extra data` と出たら、Keychain に入っている SA鍵が JSON 全体ではなく壊れた内容です。Task 4 に戻り、正しい SA鍵 JSON ファイルのパスを指定して Keychain 登録を上書きしてください。
- `Could not read json file ... Expecting value` と出たら、Keychain に SA鍵 JSON の中身ではなくファイルパスを登録しています。Task 4 に戻り、`-w "$(< "$SA_KEY_JSON")"` のコマンドをそのまま実行して上書きしてください。
- `Drive ...: SAから見えません` と出たら、Task 5 に戻り、表示された `id=...` のフォルダ/台帳を SAメールに共有してください。
- `CERTIFICATE_VERIFY_FAILED` と出たら、macOS の Python 証明書が未設定です。`/Applications/Python 3.11/Install Certificates.command` を実行してから、再度 `setup_doctor.py` を実行してください。
- Google/Slack の疎通だけを個別に確認したいときは `python3 lib/config_auth.py --check`(先頭が `OK config=<google-config.json のパス>`、続けて gcloud トークン取得・Sheets台帳/個人/法人フォルダ到達OK(REST)と `Slack: <状態>` を含む行が出れば成功)。
→ 成功したら Task 13 へ。

---

## Task 13. 実行する

実行前に、ひな形の黄色箇所・台帳列・差込マッピングの整合を確認できます。個人/法人とも `OK` なら、黄色で変わる箇所に対して入力列または条件分岐が対応しています。

```bash
python3 lib/scan_template.py --type individual
python3 lib/scan_template.py --type corporate
```

確認できること:
- `MISSING anchor`: mapping にはあるが、ひな形側に差込位置が見つからない
- `UNMAPPED marker`: 黄色/未入力マーカーらしき箇所があるが、mapping 管理対象ではない
- `LEDGER missing column`: mapping に必要な列が、台帳ヘッダに存在しない

たとえば `[する／し、その詳細は別紙１に定める]` は `業務内容方式`、`［金XXXX円（消費税抜）／別紙２に定める金額］` は `料金方式` と `金額`、`XX年XX月XX日からXX年XX月XX日までのX年間` は `契約開始日` / `契約終了日` / `契約期間_年数` で管理されます。

```bash
# まず安全に(Drive保存・台帳書込なしで結果だけ確認)
python3 lib/engine.py --phase draft --type all --dry-run
```

初回実行で `個人` / `法人` シートがまだ無い場合、dry-run では次のように表示されます。これは正常です。dry-run ではシート作成も行わないため、読取をスキップします。

```text
[schema] {'個人': 'would-create', '法人': 'would-create'}
[個人][phase=draft] シート未作成(dry-runのため読取スキップ)
[法人][phase=draft] シート未作成(dry-runのため読取スキップ)
```

```bash
# 本番: 台帳の作成指示◯・未完了行を契約書化し、Slack通知まで
# 初回は `個人` / `法人` シートとヘッダも自動作成します
python3 lib/engine.py --phase draft --type all
```

✅ 完了確認: 下書き(Docs黄色版)が個人/法人フォルダに作られ、Slackに通知が届く。台帳のステータスが進む。

---

## Task 14. 承認後にPDFを確定する(既定=明示指示 / 任意=cron)

通知スレッドで**承認の意思表示**を付けたうえで、**Claude Code 上で確定を指示したとき**にPDFが生成・共有されます(pull型。承認だけでは自動生成しません)。承認と判定される入力は次のとおり(コード `lib/slack_poll.py` の実装):

- **リアクション**: `:white_check_mark:`(✅)/ `:heavy_check_mark:`(✔️)/ `:+1:`(👍)/ `:ok:` のいずれか。
- **返信本文**: 大小文字を無視した**部分一致**で `ok` / `おk` / `承認` / `approve` / `了解` のいずれかを含む。
- 上記以外のカスタム絵文字・任意の文言は承認と見なされません。

```bash
# 既定: 承認を確認したら Claude Code で確定を指示 → 1 回だけ実行(費用¥0)
# エントリは lib/engine.py に一本化(--phase finalize)。run-contract-finalize skill の
# scripts/finalize.py は同じ engine を呼ぶ薄い shim で等価。
python3 lib/engine.py --phase finalize --type all
python3 lib/engine.py --phase finalize --type all --dry-run   # 副作用なしで承認状態を確認

# 任意の自動化: 純Pythonを cron で定期実行(LLMを回さないためトークン費用ゼロ)
# 導入後の plugin 実体パスは固定文字列で書かず、下記で自動検出した絶対パスを使う:
#   CG=$(find "$HOME/.claude" -type f -path '*/contract-generator/lib/engine.py' -print -quit | xargs dirname | xargs dirname)
#   crontab 例: */10 * * * * cd "$CG" && python3 lib/engine.py --phase finalize --type all
#   (開発リポジトリから動かす場合のみ cd <repo>/plugins/contract-generator)
#
# 注: `/loop 10m /run-contract-finalize` でもポーリング可能だが、毎周回 LLM を起動するため
#     トークン費用が嵩む。自動化が必要なら上記 cron(純Python)を推奨。
```

---

## 環境変数(任意・上書き用)

通常は設定不要です。**他プロジェクトの設定と分けたい・既定の場所を変えたい場合のみ**、以下を `export` で上書きできます(`lib/config_auth.py` / `lib/keychain_get_secret.py` / `lib/docx_fill.py` が参照)。

| 変数 | 役割 | 未設定時の既定 |
|---|---|---|
| `GOOGLE_CONFIG_PATH` | `google-config.json` の場所を明示指定 | `~/.config/contract-generator/google-config.json` →(後方互換)cwd 直下・cwd から最大6階層上の `.google-config.json` を順に自動探索 |
| `XDG_CONFIG_HOME` | 設定フォルダの基準(正本 `<ここ>/contract-generator/`) | `~/.config`(= `~/.config/contract-generator/`) |
| `GDRIVE_KEYCHAIN_SERVICE` | SA鍵 Keychain の service を上書き | `xl-skills-gdrive` |
| `GDRIVE_KEYCHAIN_ACCOUNT` | SA鍵 Keychain の account を上書き | `contract-generate/service-account-json` |
| `XL_PARTY_A_JSON_PATH` | 甲(発注者)固定値 JSON の場所 | `~/.config/contract-generator/party_a.json` → `~/.config/xlocal/party_a.json`(後方互換) → 同梱 `references/party_a.default.json` の順 |
| `CONTRACT_TEMPLATE_MAPPING` | 差込マッピング JSON(`template-mapping.json`)の場所を上書き | `skills/run-contract-generate/references/template-mapping.json` |

> ⚠️ **沈黙故障に注意**: これらが**他プロジェクトで export 済み**だと、本 README どおりに設定しても参照先がズレ、エラーにならないまま誤ったファイル/Keychain を読みます。詰まったら次で残存を確認してください:
> ```bash
> env | grep -E 'GOOGLE_CONFIG|GDRIVE_KEYCHAIN|XL_PARTY|CONTRACT_TEMPLATE'
> ```
> 何も表示されなければ既定どおりで問題ありません。

---

## ひな形が変わったとき

ひな形(.docx)を**自社のひな形フォルダに置き換えた後**、Claude Code に自然言語で:
> 「契約書のひな形が変わりました」

と伝えると `run-template-sync` が発火し、差分を検知して差込マッピング・台帳列を追従させ、影響する契約書を作り直し対象にします。
(手動なら `python3 lib/scan_template.py --type individual` / `--type corporate`)

再現性のため、ひな形更新後は必ず以下の順に確認してください。

```bash
python3 lib/scan_template.py --type individual
python3 lib/scan_template.py --type corporate
python3 lib/engine.py --phase draft --type all --dry-run
```

`scan_template.py` は、黄色runの実体、mappingの差込位置、台帳ヘッダ列の3点を機械的に照合します。目視だけで「黄色になっている/なっていない」を判断しないでください。

---

## トラブルシュート

> 💡 まず `python3 lib/setup_doctor.py` を実行してください。どの Task が未完了か(Keychain / config / 疎通 など)を名指しで示します。下表は個別症状の対処です。

| 症状 | 原因 / 対処 |
|---|---|
| `Keychain lookup failed` | Task 4 / Task 8 未実施、または service/account 名の打ち間違い |
| `Could not read json file ... Extra data` | Keychain に登録した SA鍵が JSON 全体ではなく、`private_key_id` など一部の文字列になっている可能性が高い。Task 4 の 4-1 で正しい SA鍵 JSON ファイルのパスを指定し、4-3 を再実行して上書き登録する |
| `Could not read json file ... Expecting value` | Keychain に SA鍵 JSON の中身ではなく `/Users/...` のようなファイルパスを登録している可能性が高い。Task 4 の 4-3 をそのまま再実行し、`-w "$(< "$SA_KEY_JSON")"` で JSON の中身を登録する |
| `Drive ...: SAから見えません` | Task 5 の共有漏れ。表示された `id=...` のフォルダ/台帳を、setup-doctor に表示された SAメールに共有 |
| `Drive ...: SAは閲覧できますがファイル追加できません` | 出力先フォルダが閲覧者権限になっている。Task 5 に戻り、個人/法人フォルダを SAメールに **編集者** で共有 |
| `storageQuotaExceeded` / `Drive storage quota exceeded` | Service Account が My Drive 配下に新規ファイルを所有作成しようとして容量エラー。出力先の個人/法人フォルダを共有ドライブ配下に移し、SAメールをコンテンツ管理者または編集者にして `google-config.json` のフォルダIDを更新 |
| `CERTIFICATE_VERIFY_FAILED` | macOS Python の証明書未設定。`/Applications/Python 3.11/Install Certificates.command` を実行してから再試行 |
| `Slack 疎通: channel 到達不可: missing_scope` | Slack App の scope 不足。Task 7 で public チャンネルなら `channels:read`、private チャンネルなら `groups:read` を追加し、**Reinstall to Workspace** 後に Task 8 で新しい token を Keychain 登録。`provided=` に追加した scope が出ていない場合は、scope 追加後の再インストールか token 再登録が未完了 |
| `Slack 疎通: channel 到達不可: channel_not_found` | `slack_channel` が今の Bot Token の workspace から見えていない。channel ID が正しい場合は、Bot Token が別 workspace のもの。対象 workspace で **Reinstall to Workspace** し、表示された新しい token を Task 8 で Keychain に再登録。private チャンネルの場合はBot招待も確認 |
| `403 insufficient permissions` | Task 5 のSA共有漏れ。対象ID(フォルダ/台帳)をSAメールに共有 |
| `API has not been used` | Task 2 のAPI有効化漏れ |
| Slackに通知が来ない | Task 9 のBot招待漏れ、Task 8 のtoken誤り、`slack_channel` のID誤り |
| 承認しても PDF が出ない | 既定は pull 型 = 承認だけでは生成されない。**Claude Code で確定を指示**(または `python3 lib/engine.py --phase finalize --type all` を実行)したか確認。承認入力が対象スレッドか、承認判定はリアクション ✅`white_check_mark`・✔️`heavy_check_mark`・👍`+1`・`ok`、または返信本文に `ok`/`おk`/`承認`/`approve`/`了解` を含む(大小文字無視・部分一致)。これ以外の絵文字・文言は無効。自動化していて出ない場合は cron(純Python)が動いているか確認 |
| 生成Docに `●`/`XXXX` が残る | 台帳の対応列が空。`validate.py` の必須チェックを確認 |
| ひな形が変わって差込位置がズレた | 「ひな形が変わりました」で `run-template-sync` を実行し追従 |

---

## Keychain に保存する機密の一覧(命名規約)

| 用途 | service | account | 登録Task |
|---|---|---|---|
| Google Drive/Sheets SA鍵 | `xl-skills-gdrive` | `contract-generate/service-account-json` | Task 4 |
| Slack Bot Token | `xl-skills-slack` | `contract-generate/bot-token` | Task 8 |

> 将来Google Drive/Slackの別連携を足すときも、同じ `xl-skills-*` service の下に `用途/種別` の account で追加すれば衝突しません。
