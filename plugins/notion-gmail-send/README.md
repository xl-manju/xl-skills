# notion-gmail-send

Notion の2つのDB（メール本文_DB / メール送信先_DB）を入力に、`メッセージ対象=✅ かつ 本文非空` の本文を `送信対象=✅ かつ メールを送らない☐ かつ プロ人材メール非空` の宛先へ `{{}}` 差し込み置換して **Gmail で一斉個別送信**する plugin。宛先は **プロ人材（To）と秘書（CC）の両方**へ送る。

不可逆なメール送信を **承認済み plan + 人間承認ゲート + 事前予約つき冪等ログ** の三本柱で安全化する（実装 SSOT: `doc/run-notion-gmail-send-仕様と検証メモ.md`）。

### 宛先DB（メール送信先_DB）の主なルール
- `メール（プロ人材）` → **To**、`メール（cc秘書）` → **CC**（本文DBの CC と結合）。両方へ送る。
  - 秘書欄が**空なら CC無しでプロ人材だけに送る**（秘書は必須ではない）。秘書がプロ人材と同じアドレスのときは、二重に届かないよう CC から外す（dry-run で `cc_suppressed_due_to_to_overlap` と表示。To で届くので問題なし）。
- `メールを送らない=✅` は **`送信対象` より優先**で送信しない（最優先の抑制）。
- `送信対象=☐`（OFF）の人は **dry-run の計画に最初から入らない**（記録もしない）。承認後に OFF へ変えた人だけ、本送信時に `send_suppressed` として「送らなかった」記録が残る。
- 同一の `メール（プロ人材）` が複数行にあると（会社名違いでも）**最新の1件だけ**送信する（`created_time` 降順、同時刻は `page_id` 降順。重複送信しない）。「上位ID＝新しいもの」は作成時刻の新しさのこと。
- `部署名` は廃止。本文に `{{部署名}}` を書かないこと（残すと未置換でその通は送られない）。`/run-notion-gmail-source-audit` を実行すると、DB2 に `部署名` 列が残っていれば `deprecated_property` として削除を促す。
- 送ったメールは**送信者の「送信済み」に残る**（Gmail の仕様）。

> 用語（プロ人材＝To / 秘書＝CC など）の対応表は `skills/ref-notion-gmail-send-spec/references/spec-detail.md` §8 を参照。

---

## TL;DR: 5ステップで送信（非エンジニア向け）

0→送信までの最短手順。各ステップの詳細は本 README 内の該当節（**太字**の見出し）を参照。

1. **Notion を3つのDBで用意し ID を登録** — メール本文_DB（本文テンプレ）・メール送信先_DB（送信先）・送信ログDB の3つを作り、それぞれの id を**作業フォルダ**（Claude を開いているフォルダ＝`$CLAUDE_PROJECT_DIR`。clone 開発者は repo-root）直下の `.notion-config.json` に記入する。（→ **セットアップ** の「2. 設定ファイル」「4. 送信ログDB の構築」）
2. **認証鍵を macOS Keychain に設定** — Notion API token（`notion-api-key.xl-skills`）と Google サービスアカウント鍵（`gmail-sa.xl-skills`）を登録し、Gmail 側の DWD / gmail.send scope / sendAs を設定する。**秘密値はチャットや issue に貼らない**。設定できたら Claude に「**doctor で確認して**」と頼めば、本送信せずに認証/設定の成否を一括点検でき、live-send まで進む前に不備を見つけられる。（→ **セットアップ** の「3. 認証鍵」/ `ref-gmail-dwd-setup`）
3. **dry-run で件数と plan_hash を確認** — `/run-notion-gmail-dry-run` を実行すると、送信件数・`plan_hash`・全件プレビュー・`APPROVE` 文字列・`<確認語>` が出力される。少数検品は `--canary N`。**この段階では1通も送信しない**。（→ **使い方（推奨フロー）**）
4. **全件プレビューを目視** — 誰に・どの本文が送られるかを必ず目視する。送信元データの品質点検は `/run-notion-gmail-source-audit`。（→ **使い方（推奨フロー）**）
5. **承認して本送信** — `/run-notion-gmail-send` に `APPROVE <plan_hash> <count> <first_to> <確認語>` を**完全一致**で入力する。二段確認 → preflight（認証/送信ログDB/整合）の自動検証 → Gmail 送信 → 送信ログ記録 → 日本語レポート、の順に進む。（→ **使い方（推奨フロー）** / **安全設計（三本柱）**）

> 初回や大量に送る前に、**想定送信規模と大量送信（canary 運用）** 節も必ず確認してください。

---

## 構成（責務分離）

| 種別 | 名前 | 役割 |
|---|---|---|
| ref skill | `ref-notion-gmail-send-spec` | データ契約・安全設計の参照正本（2DB schema / 送信ログDB schema / 冪等キー / preflight / status enum） |
| ref skill | `ref-gmail-dwd-setup` | Gmail API / DWD / SA鍵 / sendAs alias 認証設定ガイド |
| run skill | `run-notion-gmail-sendlog-setup` | 送信ログDB のプロパティを §9 schema に冪等構築 |
| run skill | `run-notion-gmail-source-audit` | 送信元2DB のデータ品質を送信前に監査（空本文/未知トークン/不正アドレス/未置換リスク） |
| run skill | `run-notion-gmail-dry-run` | 送信計画を生成・全件プレビュー（**送信しない**） |
| run skill | `run-notion-gmail-send` | 承認済み plan を live-send（preflight→reserve→send_guard→Gmail→log→report） |
| agent | `gmail-send-presend-verifier` | context:fork で送信前二段確認（Sycophancy 防止） |
| hook | `guard-gmail-send` | PreToolUse 補助防御（承認迂回の Gmail 直接送信を遮断） |
| lib | `lib/*.py` | 決定論モジュール（notion/gmail クライアント・置換・組立・plan・send_guard・冪等ログ・preflight） |

---

## セットアップ

### 1. install

```bash
# marketplace 経由
/plugin marketplace add xl-manju/xl-skills
/plugin install notion-gmail-send

# または CLI (リポジトリ clone 済みの場合)
claude plugin install ./plugins/notion-gmail-send
```

### 2. 設定ファイル `.notion-config.json`

下記のテンプレを**作業フォルダ**（Claude を開いているフォルダ＝`$CLAUDE_PROJECT_DIR`。clone 開発者は repo-root）直下に `.notion-config.json` として作成し、実値を埋める（gitignore 対象・git に載らない。clone 済みなら `plugins/notion-gmail-send/.notion-config.json.example` を雛形に使える）。設定ファイルの探索順は `env(NOTION_GMAIL_CONFIG) > $CLAUDE_PROJECT_DIR > 上位ディレクトリ走査 > カレント`（`lib/notion_config.py`）。

```json
{
  "databases": { "gmail-send-log": { "db_id": "<送信ログDBのid>" } },
  "notion_gmail_send": {
    "source": { "body_db": "<メール本文DBのid>", "recipient_db": "<メール送信先_DBのid>" },
    "sender": {
      "impersonate": "<送信元アドレス @your-domain>",
      "sa_keychain": { "service": "gmail-sa.xl-skills", "account": "xl-skills" }
    }
  }
}
```

### 3. 認証鍵（macOS Keychain）

| 用途 | service | account | 取得方法 |
|---|---|---|---|
| Notion API | `notion-api-key.xl-skills` | `xl-skills` | Notion integration の internal token |
| Google SA鍵 | `gmail-sa.xl-skills`（config と一致） | `xl-skills` | GCP サービスアカウント鍵JSON。ローカル端末で下の対話式登録を使う |

秘密値を shell history や AI 会話に残さないため、SA JSON はファイルパスだけを入力し、内容はローカル端末内で Keychain へ渡す。

```bash
python3 - <<'PY'
import pathlib, subprocess
path = pathlib.Path(input("SA JSON file path: ").strip()).expanduser()
subprocess.run([
    "security", "add-generic-password", "-U",
    "-s", "gmail-sa.xl-skills", "-a", "xl-skills",
    "-w", path.read_text(encoding="utf-8"),
], check=True)
PY
```

Gmail API / DWD（ドメイン全体の委任）/ gmail.send scope / sendAs の設定は **`ref-gmail-dwd-setup`** と `doc/GCP-Gmail送信設定手順.md` を参照。Python 依存 `google-auth` が必要（`pip install google-auth`）。

セットアップ状態だけを確認したい場合は **doctor**（config / Keychain / 送信ログDB ID / Gmail 認証を横断診断。本送信はしない）を使う。

- **推奨（install 形態を問わず動く）**: チャットで Claude に「セットアップを doctor で確認して。`--probe` も」と頼む。Claude が plugin 同梱の `setup_doctor.py` を `$CLAUDE_PLUGIN_ROOT` 経由で解決して実行する（ユーザーがパスを手で打つ必要はない）。
- **リポジトリを clone した開発者が自分のターミナルで直接打つ場合**:

```bash
python3 plugins/notion-gmail-send/lib/setup_doctor.py --config .notion-config.json
python3 plugins/notion-gmail-send/lib/setup_doctor.py --config .notion-config.json --probe --from <送信元アドレス>
```

> 注: 上記 `python3 plugins/notion-gmail-send/…` は **repo を clone した場合のみ有効**な相対パス。`/plugin marketplace add`（README 冒頭の install）で入れたユーザーの作業フォルダには `plugins/` が無いため、上の「Claude に頼む」を使う（`$CLAUDE_PLUGIN_ROOT` は Claude の実行環境でのみ解決され、素のターミナルでは未定義）。

`--probe` は Gmail 実 API で DWD / sendAs まで確認する。本送信はしない。

### 4. 送信ログDB の構築

```
/run-notion-gmail-sendlog-setup --db-id <送信ログDBのid>          # 差分確認 (dry-run)
/run-notion-gmail-sendlog-setup --db-id <送信ログDBのid> --apply  # プロパティを実適用
```

---

## 使い方（推奨フロー）

```
[0 整備] /run-notion-gmail-source-audit         # 送信元2DB の品質を点検し、空本文/不正アドレス/未置換リスクを直す
[1 計画] /run-notion-gmail-dry-run         # plan.json + APPROVE文字列 + 全件プレビュー (送信しない)
# 少数検品: /run-notion-gmail-dry-run --canary 3
[2 目視] 全件プレビューを確認              # 誰に・どんな本文が送られるか目視
[3 送信] /run-notion-gmail-send            # APPROVE <plan_hash> <count> <first_to> <確認語> を入力 → 二段確認 → 送信
```

送信は dry-run が出した `APPROVE <plan_hash> <count> <first_to> <確認語>` を**完全一致**で入力しないと進みません。`<確認語>` は dry-run が特定の送信単位のプレビュー行末にのみ表示する短コードで、その単位を目視で探さないと得られません（blind approve 防止の読解強制）。承認後も context:fork のエージェントが plan を独立再検査し、`send_campaign` が **units から plan_hash/件数/content_hash を再計算して fail-closed 照合**（fork や人間の自己申告に依存しない）した上で、preflight（認証/送信ログDB/整合）を通過した送信単位だけが送られます。

---

## 想定送信規模と大量送信（canary 運用）

- **想定規模**: 本 plugin は個別差し込みの一斉送信を **〜数百件** 程度まで安全に扱う設計。dry-run が `本文true × 宛先true` の直積を全件 plan 化し、`send_campaign.py` が承認済み plan の全単位を1通ずつ順に送る。
- **これを超える規模では分割（canary）送信を推奨**: まず少数だけ送って検品し、問題なければ残りを送る。`/run-notion-gmail-dry-run --canary 3`（または `--limit 3`）は送信可能 unit の安定順先頭だけを plan 化し、その限定後の件数・`plan_hash`・確認語に承認を束縛する。より厳密に対象者を選ぶ場合は **送信元DBの ✅ フラグで対象を絞る**:
  1. メール送信先_DBで、まず少数の宛先だけ `送信対象=✅` にする。
  2. `/run-notion-gmail-dry-run --canary 3` → 全件プレビュー目視 → `/run-notion-gmail-send` で承認・送信し、到達・本文・From・CC を検品する。
  3. 問題なければ残りの宛先を `送信対象=✅` にして、再度 dry-run → 承認 → 送信する。
  - 冪等ログは **content ベース dedup（`{本文page_id}:{宛先page_id}:{content_hash}`・campaign_id 非依存）** なので、2回目以降に対象を広げて再実行しても**既に送った単位は機構で skip** され二重送信にならない（同一内容を意図して再送する場合のみ `--allow-resend`）。
- **Gmail API の日次送信 quota に注意**: 大量送信は1ユーザー/日あたりの送信上限に達することがある。`send_campaign.py` は quota 到達を検知すると **安全停止（exit 3）し、未送信の単位を `reserved` に戻して次回実行で自動再開**する。上限に達しないよう、上記の ✅ フラグ分割で **日をまたいで小分け**に送るのが安全。

---

## 安全設計（三本柱）

| 安全装置 | 守る対象 | 守らないもの（正直な明示） |
|---|---|---|
| **承認済み plan**（plan_hash・units から決定論再計算で束縛） | dry-run と live-send の内容ずれ・plan.json 改竄／件数偽装 | — |
| **人間承認ゲート**（APPROVE 完全一致 + 確認語 + 二段確認） | 誤った本文・宛先の**送信を止める停止点**。確認語で blind approve のコストを上げる | 人間が内容を理解したことの保証（機構では強制不能。最終的な内容妥当性は承認者の目視に依存） |
| **事前予約つき冪等ログ**（content ベース dedup・reserved→sent/unknown） | 再実行・**別実行（別 campaign）**の二重送信、送信成功後ログ失敗 | 意図的再送（`--allow-resend` で明示） |

- 安全の正本は `lib/send_guard.py`（`lib/gmail_client.py` が内部で必ず呼ぶ）＋ `send_campaign` の決定論セルフチェック（units→plan_hash/件数/content_hash を再計算照合）。PreToolUse hook は補助防御。
- 冪等キーは `{本文page_id}:{宛先page_id}:{content_hash}` で **campaign_id を含めない**ため、別実行でも同一内容の再送は既 sent 行にヒットして機構で止まる。意図的再送は `--allow-resend`。
- 送信成否が不明な失敗（接続/timeout、2xx 受理後の解析失敗）は **自動再送せず** `unknown_needs_reconcile` とし手動照合へ回す（at-least-once を避ける）。
- `status=sent` は Gmail API が受理したことを意味し、**受信者への到達を保証しない**。
- 本文全文を含む `plan.json` はローカル作業領域のみ（git・Notion ログに残さない）。

---

## トラブルシュート

| 症状 | 原因 / 対処 |
|---|---|
| G1 で停止（認証） | SA鍵/DWD/sendAs 未設定。`ref-gmail-dwd-setup` と `doc/GCP-Gmail送信設定手順.md` 参照。`pip install google-auth` |
| G2 で停止（送信ログDB） | `run-notion-gmail-sendlog-setup` で構築。config `databases.gmail-send-log.db_id` を確認 |
| 本文0通 | メッセージ対象=✅ かつ `{{}}` 入り本文をDB1に記入 |
| 宛先0（抑制/重複で残らない） | dry-run の「送信抑制 / 重複除外」内訳を確認。`メールを送らない=✅` や プロ人材重複で全滅していないか点検 |
| 送るはずの人に届かない | `メールを送らない=✅` になっていないか、同一プロ人材メールの**より新しい行**が抑制されていないかを確認 |
| skip が多い | `run-notion-gmail-source-audit` で未置換/不正アドレス/未知・廃止トークン（`{{部署名}}`）を事前に直す |
| quota 停止（exit 3） | 再実行で reserved 残件を継続（停止単位は reserved へ戻り自動再開対象）。dedup は content ベースなので campaign_id 維持は不要 |
| 同一内容を意図的に再送したい | 既定はクロス実行の二重送信を機構で防止。再送は `run-notion-gmail-send --allow-resend` |

---

## テスト

```bash
cd plugins/notion-gmail-send && python3 -m pytest tests/ -q
```

コア安全装置（send_guard 全違反検出・冪等 reserve 状態遷移・データ品質監査）をカバー。
