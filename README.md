# xl-skills

`xl-skills` は、Claude Code を強化する **plugin 群** (機能拡張パッケージ) です。Claude Code に「スキルを作る」「品質を検査する」「非エンジニアからヒアリングする」といった能力を後から追加できます。

> **plugin (プラグイン)**: Claude Code 本体を書き換えずに、後から機能を足すための小さな部品。スマートフォンアプリのようなものと考えてください。

---

## このドキュメントの読み方

- **インストールしたい方** → [Part 1: インストール手順](#part-1-インストール手順) を順番に実行
- **API キーを設定したい方** → [Part 2: API キーの安全な保存 (Keychain)](#part-2-api-キーの安全な保存-keychain)
- **どの plugin を入れるか迷う方** → [Part 3: plugin 一覧と役割](#part-3-plugin-一覧と役割)
- **plugin の中身を理解したい方** → [Part 4: plugin の仕組み](#part-4-plugin-の仕組み)

---

# Part 1: インストール手順

このリポジトリは **GitHub の marketplace から直接インストール**します。リポジトリを手元に clone する必要はありません。

> **marketplace (マーケットプレイス)**: plugin が並んでいるお店のような場所。`xl-skills` 自体が 1 つのお店で、その中に複数の plugin が並んでいます。

## Step 0: 前提を確認する

Claude Code CLI が動く環境が必要です。

```bash
claude --version
# → claude code x.y.z が表示されれば OK
```

> ❌ 入っていなければ公式ガイド <https://docs.claude.com/claude-code/setup> を参照してください。

## Step 1: marketplace を追加する

Claude Code セッションを起動し、以下を打ちます。

```text
/plugin marketplace add xl-manju/xl-skills
```

これで「xl-skills というお店」が Claude Code に登録されます。

✅ **確認**:

```text
/plugin marketplace list
```

`xl-skills` が表示されれば成功。

## Step 2: plugin をインストールする

用途に合わせて選んでください。**まずは 1 つだけ入れて試すことをおすすめします。**

> ℹ️ **marketplace から配布される plugin は 12 件です。** Skill 作成基盤の `harness-creator` / `prompt-creator` は `distributable: false` を宣言しており marketplace 一覧に出ません (`/plugin install` できません)。これらは社内で Skill / plugin を量産するための開発基盤で、利用は repo を clone した環境に限ります → [開発者向け: harness-creator / prompt-creator](#開発者向け-harness-creator--prompt-creator-clone-時のみ)。

### 2a. まず 1 つ試す (最小構成)

用途に最も近い plugin を 1 つ入れます。例として、非エンジニアからヒアリングして要件をまとめる `skill-intake` を入れる場合:

```text
/plugin install skill-intake@xl-skills
```

> 他の入門向きの例: 企業情報の補完なら `company-master`、請求書の発行漏れチェックなら `mf-kessai-invoice-check`。配布 plugin の一覧と役割は [Part 3](#part-3-plugin-一覧と役割) を参照。

### 2b. 標準構成 (品質検査も使う)

2a で入れた plugin に加えて governance (運用検査) を追加:

```text
/plugin install skill-governance-config@xl-skills
/plugin install skill-governance-lint@xl-skills
/plugin install skill-governance-hooks@xl-skills
```

### 2c. フル構成 (配布 plugin を全部入れる)

配布対象の 12 plugin を入れるには、`/plugin install <name>@xl-skills` を plugin ごとに繰り返します (一覧は [Part 3](#part-3-plugin-一覧と役割))。

> **bundle (バンドル)について**: `xl-skills-full` (配布 12 件) / `xl-skills-intake` (skill-intake + skill-governance-secrets) という一括導入セットの定義はありますが、これを 1 行で展開する手段 (`/install-bundle` スラッシュコマンド・`scripts/install-bundle.sh`) はいずれも **repo を clone した開発環境専用**です ([開発者向け](#開発者向け-harness-creator--prompt-creator-clone-時のみ) 参照)。clone していない配布ユーザは上記のとおり 1 つずつ install してください。

✅ **確認**:

```text
/plugin list
```

入れた plugin が `installed` と表示されれば成功。

## Step 3: 動作確認

インストールした plugin のスラッシュコマンドが補完候補に出ることを確認します。例えば `skill-intake` を入れたなら、Claude Code セッション内で次を打ち始めます。

```text
/intake
```

補完候補に `/intake` (名前空間付きでは `/skill-intake:intake`) が表示されれば成功です。実際に最後まで実行する必要はありません (始めた場合は `Ctrl-C` または「やめる」でキャンセルして構いません)。

## Step 4: アップデート / アンインストール

```text
# アップデート
/plugin marketplace update xl-skills
/plugin update skill-intake@xl-skills

# アンインストール
/plugin uninstall skill-intake@xl-skills
/plugin marketplace remove xl-skills
```

## 開発者向け: harness-creator / prompt-creator (clone 時のみ)

Skill 作成基盤の **harness-creator** (Skill を設計・評価・統治する司令塔) と **prompt-creator** (7 層プロンプトを生成) は `distributable: false` を宣言しており、**marketplace 一覧・配布 bundle には現れず `/plugin install <name>@xl-skills` の対象になりません**。社内で新しい Skill / plugin を量産するための開発基盤で、利用するにはリポジトリを clone します。

```bash
git clone https://github.com/xl-manju/xl-skills.git
cd xl-skills
claude
```

clone した worktree では、`plugins/` 配下の正本が `.claude/` の symlink を通してそのまま使えます (symlink は `make sync` で生成・更新)。harness-creator / prompt-creator のスラッシュコマンドや agent は、この状態で直接呼び出せます (marketplace への install は不要)。

```bash
make sync
claude
```

clone した本プロジェクト内での呼び出し名は project-local command 名です。`/plugin install harness-creator@xl-skills` は不要です。

| やりたいこと | 本プロジェクト内の呼び出し |
|---|---|
| 構想から plugin 計画を作る | `/plugin-dev-plan <構想>` |
| 単体スキルを端から端まで作る | `/run-skill-create` |
| skill 以外の単一 Capability を作る | `/capability-build <kind> <name> --plugin=<plugin-name>` |
| Capability を束ねる | `/plugin-compose <plugin-name>` |
| 総体の出荷前検査 | `/run-plugin-package-check <plugin-name> --phase all` |
| 4条件レビュー | `/capability-review plugins/<plugin-name> plugin` |
| 改善まで実行 | `/skill-improve <capability-path>` |

配布対象の 12 plugin もまとめて入れたい場合は、この clone 環境でだけ bundle helper が使えます。

```bash
# clone 環境でのみ利用可
#   slash command: /install-bundle xl-skills-full
bash scripts/install-bundle.sh xl-skills-full
```

> **`distributable: false` とは**: その plugin が marketplace 一覧・配布 bundle に現れず、`/plugin install <name>@xl-skills` の対象にもならないことを示すフラグです。リポジトリには実体・lint 対象として存在しますが配布はされません。つまり **「配布 ≠ リポジトリ存在」**。該当するのは `distributable: false` を宣言した plugin (現時点では harness-creator / prompt-creator) です。

## トラブルシュート

| 症状 | 対処 |
|---|---|
| `/plugin` コマンドが効かない | Claude Code のバージョンが古い可能性。`claude --version` を確認し最新化 |
| `marketplace add` で `not found` | リポジトリ名のスペルを確認。`xl-manju/xl-skills` が正しい |
| `install` で `authentication failed` | private リポジトリの可能性。`gh auth login` でログイン |
| Skill が補完に出ない | `/plugin list` で `installed` か確認、無ければ再 install |

---

# Part 2: API キーの安全な保存 (Keychain)

`skill-intake` plugin など、外部サービス (Notion 等) を呼ぶ plugin は **API キー (秘密の合言葉)** が必要です。

xl-skills では API キーを **コード・ファイル・環境変数に書かず、Mac の Keychain (キーチェーン) に保存**する方針を取っています。

> **Keychain (キーチェーン)**: Mac に標準で入っている、パスワードや秘密情報を安全に保管してくれる金庫のような仕組み。Safari のパスワード保存にも使われています。

## なぜ Keychain を使うのか?

- `.env` ファイルや環境変数に書くと **間違って git に commit してしまう**事故が起きやすい
- Keychain は OS レベルで暗号化されており、他人が覗けない
- Mac ログイン中だけ取り出せるので、自動で守られる

## Step 1: Keychain に API キーを登録する

例として Notion の API キー (Internal Integration Token) を登録します。Mac のターミナルで実行:

```bash
security add-generic-password \
  -s "notion-api-key.xl-skills" \
  -a "xl-skills" \
  -w "ntn_xxxxxxxxxxxxxxxxxxx" \
  -U
```

- `-s` … サービス名 (=Keychain 内の項目名。plugin が読みに行く名前)
- `-a` … アカウント名 (=どの用途で使うかの区別)
- `-w` … 実際の API キー (この値だけは秘密に)
- `-U` … 既にあれば更新

> 💡 上のコマンドは履歴に API キーが残ります。`-w` を省略するとターミナルが対話的にキーを聞いてくれるので、その方が安全です。

## Step 2: 登録できたか確認

```bash
security find-generic-password -s "notion-api-key.xl-skills" -a "xl-skills" >/dev/null
```

終了コードが `0` なら登録成功。API キー本体は表示しません。

## Step 3: plugin が読みに行くサービス名

各 plugin が期待する Keychain のサービス名は以下です。**この名前で登録してください。**

| plugin | サービス名 (-s) | アカウント名 (-a) | 用途 |
|---|---|---|---|
| `skill-intake` | `notion-api-key.xl-skills` | `xl-skills` | Notion ページ作成 |

このリポジトリでは `.notion-config.json` の `keychain_service` / `keychain_account` が正本です。

## 環境変数で上書きしたい場合

CI など Keychain が使えない環境では、以下の環境変数で上書きできます。

```bash
export NOTION_CONFIG_PATH="/path/to/.notion-config.json"
```

通常の利用では上書き不要です。

---

# Part 3: plugin 一覧と役割

`xl-skills` には複数の plugin が入っており、それぞれ役割が分かれています。「料理に例えると」のイメージで読んでください。

## まず入れる plugin (配布対象)

| plugin | 役割 | 料理例 |
|---|---|---|
| **skill-intake** | 非エンジニアからヒアリングして Skill 要件を引き出す | お客様の好みを聞き取る接客係 |
| **company-master** | 会社名/住所/法人番号の断片から企業情報を補完し Notion へ登録 | 名刺から会社情報を調べる調査係 |
| **contract-generator** | 業務委託契約書をひな形と台帳から半自動で量産 | ひな形に沿って書類を作る事務 |
| **mf-kessai-invoice-check** | マネーフォワード掛け払いの請求書発行漏れを月次でチェック | 請求のやり忘れを見張る経理 |
| **notion-gmail-send** | Notion 2DB を入力に Gmail を一斉個別送信 | 宛名を差し替えて一斉送付する受付 |

> Skill 作成基盤の **harness-creator** / **prompt-creator** はここには出ません。配布対象外 (`distributable: false`、開発者が clone した時のみ使用) です → [開発者向け](#開発者向け-harness-creator--prompt-creator-clone-時のみ)。

## 運用検査 plugin (品質を保つ)

`skill-governance-*` という名前の plugin は、Skill の **品質を機械的に検査する仕組み** を提供します。手作りの料理が衛生基準を満たしているか確認する保健所のような役割です。

| plugin | 役割 |
|---|---|
| **skill-governance-config** | 共通設定の置き場 (出力先 adapter / rubric 採点表 / routing ルール) |
| **skill-governance-lint** | Skill の命名・依存方向・frontmatter (ヘッダ情報) を機械チェック |
| **skill-governance-hooks** | Claude Code のイベント (ファイル変更時など) に反応する検査スクリプト |
| **skill-governance-automation** | rubric (採点表) の合成、評価ログ管理、巻き戻し処理 |
| **skill-governance-adapters** | Notion / Google Sheets / Slack など外部サービスへの出力口 |
| **skill-governance-migration** | 古い形式の prompt や CLAUDE.md を Skill 形式へ移行 |
| **skill-governance-secrets** | API キー取得と「うっかり漏洩」検査 |

> **rubric (ルーブリック)**: 採点表のこと。「ここまでできたら 80 点」のように、Skill が良いか悪いかを数値化する物差し。
>
> **lint (リント)**: 自動チェックツールのこと。「ファイル名のルールが守られているか」「文字数が長すぎないか」を機械的に確認します。
>
> **hook (フック)**: 特定のタイミング (ファイルを変更したとき・コミットしようとしたときなど) に自動で走るスクリプト。

## どれを入れるべきか?

- **まず 1 つ試したい** → 用途に近い plugin を 1 つ (例: `skill-intake` / `company-master`)
- **非エンジニアからヒアリングしたい** → `skill-intake`
- **チームで Skill の品質を保ちたい** → `skill-governance-config` / `lint` / `hooks`
- **配布 plugin を全部** → 12 plugin を 1 つずつ install (一括導入 helper は clone 環境のみ)
- **Skill / plugin を新規に量産したい (開発者)** → repo を clone し harness-creator / prompt-creator を使う → [開発者向け](#開発者向け-harness-creator--prompt-creator-clone-時のみ)

---

# Part 4: plugin の仕組み

ここからは「plugin がどう動いているか」を知りたい方向けの解説です。インストールだけしたい方は読み飛ばして OK です。

## 4.1 plugin に入っている 4 つの部品

1 つの plugin の中には、以下の 4 種類の部品を入れることができます。Claude Code はそれぞれを別の方法で利用します。

| 部品 | 役割 | 利用方法 |
|---|---|---|
| **Skill (スキル)** | 作業手順書 + 知識資料 | clone した本プロジェクト内では `/run-skill-create` のように project-local スラッシュコマンドで呼ぶ。または AI が自動で発火条件を見て呼ぶ |
| **SubAgent (サブエージェント)** | 独立した別 AI として動く専門家 | Skill から呼ばれて、別の文脈で 1 つの仕事だけをこなす |
| **Hook (フック)** | 特定タイミングで自動実行されるスクリプト | ユーザーが直接呼ばない。「保存したら走る」「コマンド前に走る」など |
| **Slash Command (スラッシュコマンド)** | `/コマンド名` で呼べるショートカット | ユーザーが直接タイプする |

> **SubAgent (サブエージェント)**: 親 AI とは別の文脈で動く子分 AI。先入観を避けたいとき (例: 自分が書いた文章を客観的にレビューするとき) に使います。

### Skill とは具体的に何か?

Skill は **1 つのフォルダ** で、中に以下のような構造を持ちます。

```
plugins/harness-creator/skills/run-skill-create/
├── SKILL.md           ← 必須。何のスキルか、いつ呼ぶか、手順を書く
├── references/        ← 補助資料 (長い仕様書や採点表)
│   ├── resource-map.yaml  ← 補助資料の索引
│   └── ...
├── scripts/           ← Python スクリプト (機械的処理を担当)
└── prompts/           ← AI に渡す指示文の雛形
```

`SKILL.md` の冒頭には **frontmatter (フロントマター)** という設定欄があり、ここで「いつ Claude が自動でこのスキルを呼ぶか」を宣言します。

```yaml
---
name: run-skill-create
description: 新規スキルを作りたいとき、既存スキルを更新したいときに使う。
kind: run
---
```

### SubAgent とは?

SubAgent は **plugin の `agents/` フォルダに `.md` ファイル 1 つ**として置かれます。

```
plugins/skill-intake/agents/skill-intake-purpose-excavator.md
```

呼ばれると **新しい AI 文脈** で起動し、親 Claude の会話履歴を引きずらない状態で 1 つの仕事をします。

### Hook とは?

Hook は **plugin の `hooks/` フォルダ**にスクリプトとして置かれ、`settings.json` で「いつ走らせるか」を設定します。

```
plugins/skill-intake/hooks/pre-publish-secret-scrub.sh
```

例: 「Notion に公開する直前に、API キーが文章に混じっていないか自動チェック」など。

### Slash Command とは?

`/intake` のように打つだけで Skill を起動するショートカット。**plugin の `commands/` フォルダ**に置かれます。

```
plugins/skill-intake/commands/intake.md
```

## 4.2 plugin の最小構造

新しい plugin を作るなら、最低限以下があれば動きます。

```
plugins/my-plugin/
├── .claude-plugin/
│   └── plugin.json    ← この plugin の名前・バージョンなどの設定
├── skills/            ← Skill 群を置く (任意)
├── agents/            ← SubAgent を置く (任意)
├── hooks/             ← Hook を置く (任意)
└── commands/          ← Slash Command を置く (任意)
```

`plugin.json` の例:

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "私の作業を自動化する plugin"
}
```

## 4.3 marketplace にどう登録されているか

リポジトリ直下の `.claude-plugin/marketplace.json` が **plugin 一覧の目録**です。

```json
{
  "name": "xl-skills",
  "plugins": [
    {"name": "skill-intake",   "source": "./plugins/skill-intake"},
    {"name": "company-master", "source": "./plugins/company-master"}
  ]
}
```

Claude Code は `/plugin marketplace add xl-manju/xl-skills` を実行すると、この `marketplace.json` を読み、`plugins/` 配下から実体をキャッシュにコピーします。

> `distributable: false` を宣言した plugin (harness-creator / prompt-creator) は、この一覧 (=配布目録) に登録されないため `/plugin install` の対象になりません。リポジトリには `plugins/` 配下に実体として存在しますが配布はされない、という区別です ("配布 ≠ リポジトリ存在")。

## 4.4 `.claude/` と `~/.claude/` の役割

インストール後、ファイルがどこに置かれるかを整理します。

| 場所 | 中身 | 性質 |
|---|---|---|
| `plugins/<plugin>/` (リポジトリ内) | plugin の **正本** (オリジナル) | これが本物 |
| `~/.claude/plugins/...` (ホームディレクトリ) | Claude Code が自動で保持するキャッシュ | 自動管理、編集しない |
| `<repo>/.claude/skills/...` | 開発用の **派生 (symlink)** | `plugins/` の正本へのショートカット |

> **symlink (シンボリックリンク)**: ファイルの近道。実体は別の場所にあり、symlink はその場所を指すだけ。Windows のショートカットや、Mac の Finder の「エイリアス」と似た仕組み。

### なぜ symlink を使うのか?

リポジトリ内では `plugins/` が正本ですが、Claude Code は本来 `~/.claude/` 配下しか見ないため、**開発中の plugin を即座に試す**には `.claude/skills/` 等にコピーする必要があります。コピーだと差分管理が大変なので、symlink で「`.claude/skills/run-foo` は実は `plugins/.../run-foo` を指している」とすることで、片方を編集すれば両方反映される仕組みにしています。

利用者として `/plugin install` で入れる場合、symlink の存在を意識する必要はありません。

## 4.5 scripts / references がホームディレクトリ配下にあるとき

`/plugin install` で入れた plugin は、実体が `~/.claude/plugins/cache/.../` に展開されます。Skill が参照する scripts や references も同じ場所にコピーされるため、**ユーザーが直接触る必要はありません**。

カスタマイズしたい場合のみ、リポジトリを clone してローカルの `plugins/` を編集し、`/plugin marketplace add /path/to/xl-skills` でローカル marketplace として登録します。

## 4.6 plugin が読み込む順番

Claude Code セッション起動時:

1. `~/.claude/settings.json` を読む
2. 登録済 marketplace から `marketplace.json` を読む
3. `installed` 状態の plugin の `plugin.json` を読む
4. 各 plugin の `skills/` / `agents/` / `commands/` / `hooks/` を Claude Code に登録
5. ユーザーが `/コマンド` を打つ、または会話の文脈が Skill の `description` (発火条件) に合致すると起動

---

# Part 5: 参考リンク

## Claude Code 公式

- Plugin 作成: <https://code.claude.com/docs/en/plugins>
- Plugin reference: <https://code.claude.com/docs/en/plugins-reference>
- Marketplace 作成と配布: <https://code.claude.com/docs/en/plugin-marketplaces>
- Plugin の発見とインストール: <https://code.claude.com/docs/en/discover-plugins>

## このリポジトリの設計資料

- 設計思想と詳細仕様: `doc/ClaudeCodeスキルの設計書/` (01〜35章)
- 配布境界の取り決め: `CONVENTIONS.md`

---

# 運用メモ (上級者向け)

- `plugins/` は plugin 実体の **正本**。配布対象は `.claude-plugin/marketplace.json` / `.claude-plugin/bundles.json` と各 manifest の `distributable` で決まります。
- `doc/`, `eval-log/`, `.claude/` は設計・評価・ローカル運用のためのディレクトリで、配布対象には含まれません。
- plugin はインストール時にキャッシュへコピーされるため、plugin root の外側を `../` で参照しないでください。
- 他 plugin と共有したい共通ファイルは、marketplace 内の sibling plugin として置くか、同一 plugin 内に取り込んでください。
