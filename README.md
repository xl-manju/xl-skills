# xl-skills

`xl-skills` は、Claude Code Skill を作る、評価する、量産する、共有するためのプラグイン群です。

このリポジトリは「ひとつの marketplace パッケージ」として配布し、その中に複数の plugin を入れる構成です。中核は `plugins/skill-creator/` で、ここに Skill 作成用の複数 Skill が入っています。lint、hook、adapter、secret、migration などの運用部品は companion plugin として `plugins/skill-governance-*` に分けています。

## 現在の状態

確認した結果、`plugins/<name>/.claude-plugin/plugin.json` は各 plugin に存在します。つまり plugin 単体としての形はできています。

一方で、リポジトリ全体を共有インストールするための marketplace catalog は不足していたため、`.claude-plugin/marketplace.json` を追加しました。これにより、ユーザーはこのリポジトリを marketplace として追加し、必要な plugin を install できます。

注意点として、`installers/` 配下は旧 `creator-kit` 配置向けの installer です。現在の正本は `plugins/` 配下です。新規ユーザーには Claude Code の plugin / marketplace 経由の導入を推奨します。

参考: Claude Code 公式ドキュメント

- Plugin 作成: https://code.claude.com/docs/en/plugins
- Plugin reference: https://code.claude.com/docs/en/plugins-reference
- Marketplace 作成と配布: https://code.claude.com/docs/en/plugin-marketplaces
- Plugin の発見とインストール: https://code.claude.com/docs/en/discover-plugins

## 構成

```text
xl-skills/
├── .claude-plugin/
│   └── marketplace.json          # この repo を marketplace として配る catalog
├── plugins/
│   ├── skill-creator/            # Skill 作成・評価・量産の中核 plugin
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/
│   │   └── agents/
│   ├── skill-governance-config/  # 共有設定、rubric registry、routing 例
│   ├── skill-governance-lint/    # SKILL.md / rubric / 依存方向 lint
│   ├── skill-governance-hooks/   # Claude Code hook 用 script
│   ├── skill-governance-automation/
│   ├── skill-governance-adapters/
│   ├── skill-governance-migration/
│   └── skill-governance-secrets/
├── doc/ClaudeCodeスキルの設計書/ # 設計思想と詳細仕様
├── CONVENTIONS.md                # 層 A/B/C と配布境界
└── README.md
```

Claude Code の plugin では、`.claude-plugin/plugin.json` 以外の `skills/`, `agents/`, `hooks/`, `bin/`, `settings.json` などは plugin root 直下に置きます。`skills/<skill-name>/SKILL.md` が Skill の実体です。

## ユーザー向け: インストール方法

### 1. まず local marketplace として試す

この repository を clone した状態で Claude Code から実行します。

```text
/plugin marketplace add /path/to/xl-skills
/plugin install skill-creator@xl-skills
```

`skill-creator` だけで、Skill 作成の主要フローは使えます。運用検査も使う場合は companion plugin も入れます。

```text
/plugin install skill-governance-config@xl-skills
/plugin install skill-governance-lint@xl-skills
/plugin install skill-governance-hooks@xl-skills
/plugin install skill-governance-automation@xl-skills
/plugin install skill-governance-adapters@xl-skills
/plugin install skill-governance-migration@xl-skills
/plugin install skill-governance-secrets@xl-skills
```

Claude Code CLI から入れる場合は同等の操作を `claude plugin marketplace add ...` / `claude plugin install ...` で実行できます。

### 2. チーム共有する

GitHub などにこの repository を置き、チームメンバーには marketplace として追加してもらいます。

```text
/plugin marketplace add your-org/xl-skills --scope project
/plugin install skill-creator@xl-skills --scope project
```

`--scope project` は `.claude/settings.json` に marketplace / plugin 有効化情報を残すため、同じ repository を clone したチームメンバーにも共有できます。個人だけで使うなら `user` scope、特定 project の自分だけなら `local` scope を使います。

### 3. インストール後の呼び方

Plugin 由来の Skill は名前空間付きで呼びます。

```text
/skill-creator:run-skill-create
/skill-creator:run-build-skill
/skill-creator:run-skill-rename
```

自動発火する Skill もありますが、初回は `/skill-creator:run-skill-create` を明示実行するのが分かりやすいです。

## Skill を作る人向け: 最短フロー

新しい Skill を作る場合は、手作業でいきなり `SKILL.md` を書くのではなく、`run-skill-create` を入口にします。

```text
/skill-creator:run-skill-create
```

このオーケストレーターは、次の順で進みます。

1. `run-skill-elicit`: 何を自動化したいかを brief にする
2. `run-build-skill`: `SKILL.md`, `references/`, `scripts/` などを生成する
3. lint scripts: 命名、frontmatter、依存方向、rubric 参照を検査する
4. `assign-skill-design-evaluator`: rubric に沿って独立評価する
5. `run-elegant-review`: 大きめの変更では構造レビューを追加する
6. governance: rubric や共通基盤変更なら承認フローに乗せる

低リスクの小変更では `--fast` を使える設計になっていますが、条件を満たさない場合は通常フローに戻します。

## Skill の基本形

```text
plugins/<your-plugin>/
├── .claude-plugin/
│   └── plugin.json
├── skills/
│   └── run-your-workflow/
│       ├── SKILL.md
│       ├── references/
│       └── scripts/
└── agents/
```

`SKILL.md` は必須です。最小構成は次の通りです。

```markdown
---
name: run-your-workflow
description: 何をしたいときに使うかを、発火条件が分かるように書く。
kind: run
---

# run-your-workflow

## Purpose & Output Contract

入力、出力、完了条件を書く。

## Steps

手順を書く。決定論的な処理は scripts/ に寄せる。
```

この repository では `kind` を次のように使い分けます。

| kind | 用途 |
|---|---|
| `run` | 手順を実行する workflow |
| `ref` | 参照用の知識、仕様、rubric |
| `assign` | 評価や採点を担当する独立 Skill |
| `delegate` | Codex など外部 agent / CLI に委譲する Skill |
| `wrap` | 既存 workflow の前後に安全策を追加する Skill |

詳細な命名・frontmatter・参照規則は `plugins/skill-creator/skills/ref-claude-code-skill-spec/` と `plugins/skill-creator/skills/ref-skill-naming-convention/` を参照します。

## Skill を量産する考え方

量産で重要なのは、Skill を単発プロンプトとして増やすことではなく、生成・評価・修正の pipeline を固定することです。

### 1. 入口をひとつにする

新規作成は `run-skill-create` に集約します。個別に `run-skill-elicit` や `run-build-skill` を直接呼ぶのは、調査やデバッグ時だけにします。

### 2. 種別を分ける

作る前に `run/ref/assign/delegate/wrap` のどれかを決めます。参照用の知識を `run` に混ぜたり、評価用の観点を生成 Skill に混ぜると、量産時に品質が崩れます。

### 3. 詳細を progressive disclosure する

`SKILL.md` には入口、契約、手順だけを書きます。長い仕様、rubric、schema、例は `references/` へ移します。決定論的な処理は `scripts/` に移します。

### 4. rubric を階層化する

共通品質は `ref-skill-design-rubric`、ドメイン固有品質は `ref-domain-*-rubric`、個別 evaluator の上書きは `references/rubric.json` に分けます。合成は `compose-rubrics.py` で deep-merge します。

### 5. 評価を生成から分離する

生成担当と評価担当を分けます。`run-build-skill` と `assign-skill-design-evaluator` は `pair` ですが、評価側は生成物を改変しません。これにより、自分で作って自分で甘く採点する状態を避けます。

## 複数 Skill をひとつの plugin に入れるときの実行制御

複数 Skill を同じ plugin に入れても、手順通りに進めるには「ユーザーが順番に呼ぶ」設計にしない方がよいです。必ず親オーケストレーターを置きます。

この repository では `plugins/skill-creator/skills/run-skill-create/` が親オーケストレーターです。親 Skill が brief 作成、生成、lint、評価、governance を順に呼ぶことで、複数 Skill が入っていても実行順が崩れにくくなっています。

設計上のルール:

- ユーザー向け入口は `run-*` の親 Skill に集約する
- 子 Skill は入出力 contract を固定する
- 評価 Skill は `assign-*` に分離し、`context: fork` を使う
- 機械的に検査できるものは `scripts/` と hook に寄せる
- 成果物の出力先は workflow から直書きせず、`ref-output-routing` と adapter で解決する
- 途中状態は handoff / eval-log に残し、compact や再開に耐えるようにする

## Plugin 化して共有する手順

### 1. Plugin root を作る

```bash
mkdir -p plugins/my-plugin/.claude-plugin
mkdir -p plugins/my-plugin/skills
```

### 2. manifest を置く

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "チームで共有する workflow skill 集"
}
```

### 3. Skill を入れる

```text
plugins/my-plugin/skills/run-main-workflow/SKILL.md
plugins/my-plugin/skills/ref-domain-rules/SKILL.md
plugins/my-plugin/skills/assign-main-evaluator/SKILL.md
```

### 4. marketplace に登録する

`.claude-plugin/marketplace.json` の `plugins[]` に追加します。

```json
{
  "name": "my-plugin",
  "source": "./plugins/my-plugin",
  "description": "チームで共有する workflow skill 集",
  "version": "1.0.0"
}
```

### 5. ローカルで検証する

```bash
claude --plugin-dir ./plugins/my-plugin
```

または marketplace 経由で検証します。

```text
/plugin marketplace add /path/to/xl-skills
/plugin install my-plugin@xl-skills
```

### 6. 配布する

GitHub などに push し、ユーザーには次の形で案内します。

```text
/plugin marketplace add your-org/xl-skills
/plugin install my-plugin@xl-skills
```

## この repository の plugin 一覧

| Plugin | 役割 |
|---|---|
| `skill-creator` | Skill 作成、評価、量産、改名、rubric governance の中核 |
| `skill-governance-config` | adapter registry、rubric registry、routing 例、governance policy |
| `skill-governance-lint` | frontmatter、命名、依存方向、rubric 参照などの検査 |
| `skill-governance-hooks` | Claude Code hook 用の検証・handoff script |
| `skill-governance-automation` | rubric 合成、hash、eval-log、rollback、meta-harness |
| `skill-governance-adapters` | local/http/Notion/Sheets/Slack への出力 adapter |
| `skill-governance-migration` | 既存 prompt / CLAUDE.md / docs から Skill へ移行 |
| `skill-governance-secrets` | secret 取得と secret leak 検査 |

## 配布前チェック

最低限、次を確認します。

```bash
python3 -m json.tool .claude-plugin/marketplace.json >/dev/null
find plugins -path '*/.claude-plugin/plugin.json' -print -exec python3 -m json.tool {} >/dev/null \;
```

Claude Code が使える環境では、公式 validator も実行します。

```bash
claude plugin validate ./plugins/skill-creator
```

複数 plugin を marketplace として配る場合は、local marketplace install まで確認します。

```text
/plugin marketplace add /path/to/xl-skills
/plugin install skill-creator@xl-skills
/skill-creator:run-skill-create
```

## 運用メモ

- `plugins/` は配布対象の正本です。
- `doc/`, `eval-log/`, `.claude/` はこの repository の設計・評価・ローカル運用です。
- plugin はインストール時に cache へコピーされるため、plugin root の外側を `../` で参照しないでください。
- 他 plugin と共有したい共通ファイルは、marketplace 内の sibling plugin として置くか、同一 plugin 内に取り込んでください。
- 旧 `creator-kit` installer 前提の説明は、今後 `plugins/` 前提へ移行していく対象です。
