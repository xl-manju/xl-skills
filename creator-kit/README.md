# skill-creator-kit

Claude Code Skill を「**作る**」「**評価する**」「**承認する**」「**出力先にルーティングする**」ためのメタスキル群一式。**プロジェクトに依存しない portable kit** として設計されている。

## 何が入っているか

`manifest.json` が正本。サマリ:

| カテゴリ | Skill |
|---|---|
| オーケストレーター | `run-skill-create` (E2E: 要望→完成) |
| 生成系 | `run-skill-elicit`, `run-build-skill`, `run-skill-rename` |
| 評価系 | `assign-skill-design-evaluator`, `run-elegant-review` |
| ガバナンス | `run-skill-rubric-governance` |
| 参照系 (ref-*) | `ref-skill-design-rubric`, `ref-claude-code-skill-spec`, `ref-skill-naming-convention`, `ref-skill-glossary`, `ref-yaml-spec-fetcher`, `ref-output-routing` |
| Scripts | adapters (sink_*), secrets (keychain_helper), lint, hooks |
| Config | `adapter-registry.json`, `output-routing.json.example` |

## クイックスタート (別プロジェクトで使う)

### Pattern A: git submodule (推奨, version追従)

```bash
cd ~/projects/your-new-project
git submodule add <kit-repo-url> creator-kit
git submodule update --init
bash creator-kit/install.sh
```

### Pattern B: 単純コピー (オフライン環境)

```bash
cd ~/projects/your-new-project
cp -R /path/to/xl-skills/creator-kit ./creator-kit
bash creator-kit/install.sh --mode copy
```

### Pattern C: symlink (同一マシン内で実体共有)

```bash
cd ~/projects/your-new-project
ln -s /path/to/xl-skills/creator-kit ./creator-kit
bash creator-kit/install.sh   # mode=symlink がデフォルト
```

## 動作の仕組み

現在の `xl-skills` リポジトリは、kit 正本 + symlink 構成へ移行済みである。`.claude/skills/` と root `scripts/` は Claude Code / workflow からの安定した参照先で、実体は `creator-kit/` に置く。

```
[your-new-project]/
├── creator-kit/                    ← この kit (submodule/cp/ln)
│   ├── manifest.json
│   ├── CONVENTIONS.md
│   ├── install.sh
│   └── skills/, scripts/, config/
│
├── .claude/skills/                 ← Claude Code が探索する場所
│   ├── run-skill-create ──→ ../../creator-kit/skills/run-skill-create  (symlink)
│   ├── run-build-skill  ──→ ../../creator-kit/skills/run-build-skill   (symlink)
│   ├── ...
│   └── run-your-domain/            ← プロジェクト固有 (kit外、実体)
│
├── scripts/adapters/  ──→ kit/scripts/adapters/  (symlink)
├── scripts/secrets/   ──→ kit/scripts/secrets/   (symlink)
└── .claude/config/    ──→ kit/config/            (symlink)
```

Claude Code は `.claude/skills/` 配下を探索し、symlinkも追跡する。つまり**Claude Codeの標準仕様だけ**で kit-symlink構成が動く (独自loader不要)。

## install.sh のオプション

| Flag | 効果 |
|---|---|
| (default) | symlink で配置。kit更新が即座に反映される |
| `--mode copy` | 実体コピー。kitと独立して進化させたい時 |
| `--force` | 既存ファイル衝突時に上書き |

## アンインストール

```bash
bash creator-kit/uninstall.sh
```

kit由来のsymlinkのみ削除し、プロジェクト固有ファイルは保持する。

## 既存プロジェクトの移行

このリポジトリのように、既に `.claude/skills/` 配下に実体ファイルがある状態から kit化したい場合:

```bash
# まずdry-runで確認
bash creator-kit/migrate-from-project.sh --dry-run

# 問題なければ実行
bash creator-kit/migrate-from-project.sh
```

`.claude/skills/<meta-skill>/` の実体を `creator-kit/skills/` に移動し、元の位置にsymlinkを張り直す。プロジェクト固有skillはそのまま残る。

## kitの境界線 (再利用 vs プロジェクト固有)

### kit化する (再利用)
- メタスキル (生成/評価/ガバナンス)
- 汎用フレームワーク (routing/adapter/secret管理)
- Lint/Hook scripts
- adapter-registry / routing雛形

### kit化しない (プロジェクト固有)
- 業務workflow skill (`run-task-spec`, `run-meeting-minutes` 等)
- プロジェクト設計書 (`doc/`)
- 業務分析 (`analysis/`)
- 評価履歴 (`eval-log/`)
- 具体的な output-routing.json の中身 (DB ID等)

判断基準: **複数プロジェクトで同じものを使うか?** Yes → kit、No → プロジェクト直下。

## 依存 (追加ライブラリ禁止)

- macOS / Linux / Windows を対象にする。OS差分は `ref-cross-platform-runtime` と `creator-kit/scripts/cross_platform_secret.py` に集約する。
- Python 3.9+ stdlib のみ。PyYAMLや requests 等は使わない。
- Bash 利用箇所は `/bin/bash` 3.2+ 互換で書く。Windows では PowerShell または Python フォールバックを使う。
- `security` CLI は macOS の Keychain 操作用。Linux / Windows では標準ライブラリ実装または環境変数フォールバックを使う。
- `git` (オプション、submodule取得用)

詳細ルール: `CONVENTIONS.md` 参照。「Bash か Python か」で迷ったらここを見る。

## 設計書

本kitの設計根拠は親リポジトリの `doc/ClaudeCodeスキルの設計書/` を参照:

- 23-26章: meta-skill architecture (kit の中身の設計)
- 28章: script execution model (scripts/ の責務)
- 29章: rubric multi-project composition (rubric_refs)
- 31章: output routing & adapter architecture (Hexagonal Arch)

## バージョニング

`manifest.json` の `kit_version` で semver管理。後方互換破壊時は major up。

## ライセンス

(プロジェクトに合わせて設定)
