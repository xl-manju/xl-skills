# xl-skills

`xl-skills` は、Claude Code Skill を **作る・評価する・量産する・共有する** ための plugin 群です。中核は `plugins/skill-creator/`、運用検査は `plugins/skill-governance-*` に分割されています。

---

## このドキュメントの読み方

**初めての方**: [Part 1: クイックスタート](#part-1-クイックスタート5分) を **上から順番に** 実行してください。各ステップに「✅ 確認」コマンドが付いており、結果が想定通りなら次に進めます。

**既に Claude Code を使っている方**: [Part 2: インストール (詳細)](#part-2-インストール詳細) から読んでください。

**Skill を作りたい方**: Part 1 → [Part 3: Skill を作る最短フロー](#part-3-skill-を作る最短フロー)。

**自分の plugin を配布したい方**: [Part 4: 自分の plugin を作って配布する](#part-4-自分の-plugin-を作って配布する)。

---

# Part 1: クイックスタート (5分)

このセクションは **完全にゼロからの手順** です。順番にコピペで実行してください。

## Step 0: 前提を確認する

以下の 3 つがインストールされていることを確認します。

```bash
# 1. git が入っているか
git --version
# → git version 2.x.x が出れば OK

# 2. Claude Code CLI が入っているか
claude --version
# → claude code x.y.z が出れば OK
# 入っていなければ: https://docs.claude.com/claude-code/setup

# 3. Python 3.10 以上が入っているか (lint scripts 用)
python3 --version
# → Python 3.10 以上なら OK
```

✅ **3 つすべてのバージョンが表示されたら Step 1 へ。**

> ❌ Claude Code が無い場合: 公式ガイド <https://docs.claude.com/claude-code/setup> に従ってインストール後、`claude login` を実行してください。

## Step 1: このリポジトリを取得する

選択肢が 2 つあります。**初めての方は方式 A を選んでください。**

### 方式 A: GitHub から clone する (推奨)

```bash
# 好きな場所に clone (例: ~/dev/ )
cd ~/dev
git clone https://github.com/xl-manju/xl-skills.git
cd xl-skills

# ✅ 確認
ls .claude-plugin/marketplace.json
# → ファイルパスが表示されれば OK
```

### 方式 B: GitHub から直接 marketplace 追加 (上級者向け)

Claude Code が GitHub URL から直接 marketplace を取得します。clone 不要ですが、ローカルでのカスタマイズができません。

```text
/plugin marketplace add xl-manju/xl-skills
```

→ Part 1 の残り Step は Step 3 にジャンプしてください。

## Step 2: marketplace として登録する

方式 A で clone した場合、Claude Code に「ここに plugin 群があるよ」と教えます。**Claude Code セッション内** で実行します。

```text
/plugin marketplace add /Users/<yourname>/dev/xl-skills
```

> 💡 パスは Step 1 で `cd` した絶対パスです。`pwd` で確認できます。

✅ **確認**: 以下を実行して `xl-skills` が出れば OK。

```text
/plugin marketplace list
```

## Step 3: plugin をインストールする

最低限 `skill-creator` 1 つで Skill 作成は動きます。フル機能を使うなら全部入れます。

### 3a. 最小構成 (まずはこれだけで OK)

```text
/plugin install skill-creator@xl-skills
/plugin install prompt-creator@xl-skills
```

### 3b. フル構成 (運用検査・governance も含める)

```text
/plugin install skill-creator@xl-skills
/plugin install prompt-creator@xl-skills
/plugin install skill-governance-config@xl-skills
/plugin install skill-governance-lint@xl-skills
/plugin install skill-governance-hooks@xl-skills
/plugin install skill-governance-automation@xl-skills
/plugin install skill-governance-adapters@xl-skills
/plugin install skill-governance-migration@xl-skills
/plugin install skill-governance-secrets@xl-skills
/plugin install skill-intake@xl-skills
```

✅ **確認**: `/plugin list` を実行し、上記が `installed` として表示されることを確認。

## Step 4: 動作確認 (Smoke Test)

Claude Code セッション内で以下を打ち、補完候補に出ることを確認します。

```text
/skill-creator:run-skill-create
```

実行すると対話が始まります。一旦キャンセル (`Ctrl-C` または「やめる」と返答) して構いません。

✅ **Skill が起動できた = インストール成功。**

## Step 5: 最初の Skill を作ってみる

本番の入口は **常に `run-skill-create`** です。これがオーケストレーターとなり、要件抽出 → 生成 → lint → 評価 → governance を順に呼びます。

```text
/skill-creator:run-skill-create
```

進行は次の順 (自動):

1. `run-skill-elicit`: 何を自動化したいかを brief にする
2. `run-build-skill`: `SKILL.md`, `references/`, `scripts/`, `prompts/` を生成
3. `run-prompt-creator-7layer`: 責務ごとの 7 層プロンプトを生成 (kind が run/assign の場合)
4. lint scripts: 命名/frontmatter/依存方向/責務 anchor を検査
5. `assign-skill-design-evaluator`: rubric に沿って独立評価
6. `run-elegant-review`: 大きめの変更は構造レビュー
7. governance: rubric や共通基盤変更なら承認フロー

✅ **brief が JSON で保存され、`plugins/<your-plugin>/skills/<your-skill>/SKILL.md` が生成されれば成功。**

---

## トラブルシュート (Part 1 で詰まったら)

| 症状 | 対処 |
|---|---|
| `/plugin` コマンドが効かない | Claude Code のバージョンが古い可能性。`claude --version` を確認し最新化 |
| `marketplace add` で「not found」 | パスが絶対パスでない可能性。`pwd` で取得した絶対パスを使う |
| `install` で「authentication failed」 | private repo の場合は GitHub に gh auth でログイン: `gh auth login` |
| Skill が補完に出ない | `/plugin list` で `installed` になっているか、無ければ再 install |
| Python script で ModuleNotFoundError | このリポジトリのスクリプトは標準ライブラリのみ。Python 3.10+ か再確認 |

---

# Part 2: インストール (詳細)

## 2.1 インストール scope の使い分け

`/plugin install` には 3 つの scope があり、`.claude/settings.json` のどこに記録するかが変わります。

| scope | 記録先 | 用途 |
|---|---|---|
| `--scope user` | `~/.claude/settings.json` | 個人用、全 project で有効 |
| `--scope project` | `<repo>/.claude/settings.json` | チームで共有 (git に commit) |
| `--scope local` | `<repo>/.claude/settings.local.json` | 特定 project の自分だけ (git 無視) |

チーム共有の例:

```text
/plugin marketplace add xl-manju/xl-skills --scope project
/plugin install skill-creator@xl-skills --scope project
```

これで同じ repo を clone したメンバーは `claude` 起動時に自動で marketplace 追加が走ります。

## 2.2 GitHub から直接インストール (リモート marketplace)

```text
/plugin marketplace add xl-manju/xl-skills
/plugin install skill-creator@xl-skills
```

clone 不要。Claude Code がキャッシュへコピーします。**ローカルで lint scripts などを編集したい場合は方式 A (clone) を選んでください。**

## 2.3 CLI からのインストール

セッション外から入れる場合:

```bash
claude plugin marketplace add xl-manju/xl-skills
claude plugin install skill-creator@xl-skills
```

## 2.4 アップデート

```text
/plugin marketplace update xl-skills
/plugin update skill-creator@xl-skills
```

## 2.5 アンインストール

```text
/plugin uninstall skill-creator@xl-skills
/plugin marketplace remove xl-skills
```

---

# Part 3: Skill を作る最短フロー

## 3.1 入口は常に `run-skill-create`

```text
/skill-creator:run-skill-create
```

手作業で `SKILL.md` を書かないでください。`run-skill-create` が brief → 生成 → 評価 → governance の pipeline を固定します。

## 3.2 `kind` を最初に決める

| kind | 用途 | プロンプト必須 |
|---|---|---|
| `run` | 手順を実行する workflow | ✅ 責務ごとに必須 |
| `ref` | 参照用の知識、仕様、rubric | optional |
| `assign` | 評価や採点を担当する独立 Skill | ✅ 責務ごとに必須 |
| `delegate` | 外部 agent / CLI に委譲 | skip |
| `wrap` | 既存 workflow の前後に安全策追加 | optional |

`run` / `assign` を選んだ場合、brief に `responsibilities[]` (R1, R2, ...) を 1 件以上書く必要があります (schema 強制)。

## 3.3 責務単位のプロンプト生成

`run-build-skill` は brief の `responsibilities[].id` ごとに `prompt-creator` を呼び、7 層 YAML を生成します。出力先:

```
plugins/<plugin>/skills/<skill>/prompts/R1.yaml
plugins/<plugin>/skills/<skill>/prompts/R2.yaml
```

SubAgent (`agents/<role>.md`) には `<!-- responsibility: R1 -->` という anchor が挿入され、prompt-creator がその直下に実発話例を充填します。

検証:

```bash
python3 plugins/skill-creator/skills/run-build-skill/scripts/validate-build-trace.py \
  eval-log/skill-build-trace.json

python3 plugins/skill-governance-lint/scripts/lint-agent-prompt-section.py \
  --strict-coverage --brief eval-log/skill-brief.json \
  plugins/<plugin>/agents/<role>.md
```

両方が `OK` を返せば再現性 PASS です。

## 3.4 Skill の最小形

```text
plugins/<your-plugin>/
├── .claude-plugin/plugin.json
├── skills/
│   └── run-your-workflow/
│       ├── SKILL.md           # 必須
│       ├── references/        # 長い仕様 (progressive disclosure)
│       ├── scripts/           # 決定論的処理
│       └── prompts/           # responsibility 別 7 層 YAML
└── agents/                    # SubAgent .md
```

SKILL.md 最小例:

```markdown
---
name: run-your-workflow
description: 何をしたいときに使うかを発火条件が分かるように書く。
kind: run
---

# run-your-workflow

## Purpose & Output Contract

入力、出力、完了条件を書く。

## Steps

手順を書く。決定論的処理は scripts/ に寄せる。
```

## 3.5 量産時の鉄則

1. **入口をひとつに** — 新規作成は `run-skill-create` だけ
2. **種別を最初に決める** — `run/ref/assign/delegate/wrap` を混ぜない
3. **Progressive disclosure** — SKILL.md は入口・契約・手順だけ。詳細は `references/`
4. **rubric を階層化** — 共通 / ドメイン / 個別を deep-merge
5. **生成と評価を分離** — `run-build-skill` と `assign-skill-design-evaluator` で context fork

---

# Part 4: 自分の plugin を作って配布する

## 4.1 Plugin root を作る

```bash
mkdir -p plugins/my-plugin/.claude-plugin
mkdir -p plugins/my-plugin/skills
```

## 4.2 manifest を置く

`plugins/my-plugin/.claude-plugin/plugin.json`:

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "チームで共有する workflow skill 集"
}
```

## 4.3 Skill を入れる

```text
plugins/my-plugin/skills/run-main-workflow/SKILL.md
plugins/my-plugin/skills/ref-domain-rules/SKILL.md
plugins/my-plugin/skills/assign-main-evaluator/SKILL.md
```

## 4.4 marketplace catalog に登録

`.claude-plugin/marketplace.json` の `plugins[]` に追加:

```json
{
  "name": "my-plugin",
  "source": "./plugins/my-plugin",
  "description": "チームで共有する workflow skill 集",
  "version": "1.0.0"
}
```

## 4.5 ローカル検証

```bash
# JSON 構文
python3 -m json.tool .claude-plugin/marketplace.json >/dev/null
find plugins -path '*/.claude-plugin/plugin.json' -print \
  -exec python3 -m json.tool {} >/dev/null \;

# Claude Code 公式 validator (使える環境のみ)
claude plugin validate ./plugins/my-plugin
```

Claude Code セッションで local marketplace から install できることを確認:

```text
/plugin marketplace add /path/to/xl-skills
/plugin install my-plugin@xl-skills
/my-plugin:run-main-workflow
```

## 4.6 GitHub へ push して配布

```bash
git add plugins/my-plugin .claude-plugin/marketplace.json
git commit -m "feat(plugin): add my-plugin"
git push origin main
```

利用者への案内:

```text
/plugin marketplace add your-org/your-repo
/plugin install my-plugin@your-repo
```

---

# Part 5: リポジトリ構成

```text
xl-skills/
├── .claude-plugin/
│   └── marketplace.json          # marketplace catalog
├── plugins/
│   ├── skill-creator/            # Skill 作成・評価・量産の中核
│   ├── prompt-creator/           # 7 層プロンプト生成
│   ├── skill-intake/             # 非エンジニア協働 intake
│   ├── skill-governance-config/  # adapter/rubric/routing 設定
│   ├── skill-governance-lint/    # SKILL.md/rubric/依存方向 lint
│   ├── skill-governance-hooks/   # Claude Code hook script
│   ├── skill-governance-automation/ # rubric 合成、eval-log、rollback
│   ├── skill-governance-adapters/   # local/http/Notion/Sheets/Slack
│   ├── skill-governance-migration/  # 既存 prompt → Skill 移行
│   └── skill-governance-secrets/    # secret 取得・leak 検査
├── doc/ClaudeCodeスキルの設計書/ # 設計思想と詳細仕様 (01〜35章)
├── CONVENTIONS.md                # 層 A/B/C と配布境界
└── README.md
```

## Plugin 一覧

| Plugin | 役割 |
|---|---|
| `skill-creator` | Skill 作成・評価・量産・改名・rubric governance の中核 |
| `prompt-creator` | brief.responsibilities[] ごとに 7 層プロンプトを生成 |
| `skill-intake` | 非エンジニアと協働して要件を引き出し Notion 連携 |
| `skill-governance-config` | adapter registry / rubric registry / routing 例 |
| `skill-governance-lint` | frontmatter / 命名 / 依存方向 / 責務 anchor 検査 |
| `skill-governance-hooks` | Claude Code hook 用検証・handoff script |
| `skill-governance-automation` | rubric 合成 / hash / eval-log / rollback / meta-harness |
| `skill-governance-adapters` | local/http/Notion/Sheets/Slack 出力 adapter |
| `skill-governance-migration` | 既存 prompt / CLAUDE.md / docs を Skill へ移行 |
| `skill-governance-secrets` | secret 取得と leak 検査 |

---

# Part 6: 設計の指針

## 6.1 複数 Skill の実行制御

複数 Skill を同じ plugin に入れても「ユーザーが手で順番に呼ぶ」設計にしないでください。**親オーケストレーター** を必ず置きます。

このリポジトリでは `plugins/skill-creator/skills/run-skill-create/` が親で、brief 作成 → 生成 → lint → 評価 → governance を順に呼びます。

設計上のルール:

- ユーザー向け入口は `run-*` の親 Skill に集約
- 子 Skill は入出力 contract を固定
- 評価 Skill は `assign-*` に分離し `context: fork` を使う
- 機械的に検査できるものは `scripts/` と hook へ
- 出力先は workflow から直書きせず `ref-output-routing` と adapter で解決
- 途中状態は handoff / eval-log に残し compact/再開に耐える

## 6.2 再現性の 3 軸

| 軸 | 保証する仕組み |
|---|---|
| Schema | `skill-brief-schema.json` の allOf 条件で kind ↔ responsibilities を強制 |
| Path | `prompt-placement-convention.md` + `validate-build-trace.py` の regex |
| Hash | per_responsibility.sha256 を 2 回生成で一致確認 (dogfooding test) |

## 6.3 参考 (Claude Code 公式)

- Plugin 作成: <https://code.claude.com/docs/en/plugins>
- Plugin reference: <https://code.claude.com/docs/en/plugins-reference>
- Marketplace 作成と配布: <https://code.claude.com/docs/en/plugin-marketplaces>
- Plugin の発見とインストール: <https://code.claude.com/docs/en/discover-plugins>

---

# 運用メモ

- `plugins/` は配布対象の **正本** です。
- `doc/`, `eval-log/`, `.claude/` はこの repository の設計・評価・ローカル運用です。
- plugin はインストール時にキャッシュへコピーされるため、plugin root の外側を `../` で参照しないでください。
- 他 plugin と共有したい共通ファイルは marketplace 内の sibling plugin として置くか、同一 plugin 内に取り込んでください。
- `installers/creator-kit/` は旧配置向け。新規ユーザーは `plugins/` 前提の本 README に従ってください。
