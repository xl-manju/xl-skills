---
name: run-skill-intake-aggregator
description: 非エンジニアと協働してスキル要件を引き出すとき、Markdown/JSON/Notion ページを Keychain 経由で短時間に一括生成したいときに使う。
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - AskUserQuestion
kind: run
user-invocable: true
# local-ext: frontmatter-fields.md 未掲載の独自フィールド。要governance届出
effect: external-mutation
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-21
audit-trigger: monthly
hierarchy_level: orchestrator
rubric_refs: [quality-rubric, sink-contract]
role_suffix: aggregator
owner: team-platform
since: 2026-05-20
---

# run-skill-intake-aggregator

## Purpose & Output Contract

skill-creator (`run-skill-create`) の Step 1 (`run-skill-elicit`) を非技術者向けに拡張するメタスキル。完全非技術者を含む不特定多数から、本人も言語化できていない真の課題を引き出し、3 つの成果物を一括生成する。

**入力**: ユーザーの「スキルを作りたい」要望 (topic 引数任意)

**成果物 (3 系統)**:

| 成果物 | パス | 利用者 |
|--|--|--|
| Markdown 正本 | `output/<skill-name-hint>/intake.md` | 人間 (ヒアリングシート) |
| JSON 副本 | `output/<skill-name-hint>/intake.json` | skill-creator (Phase 0-0 簡略化) |
| Notion ページ URL | `output/<skill-name-hint>/notion-url.txt` | チーム共有 |
| Notion ブロック JSON (中間生成物) | `output/<skill-name-hint>/notion-blocks.json` | publisher 入力 |
| self-update メタログ | `output/<skill-name-hint>/self-update.json` | skill-intake-self-updater (question-bank 更新証跡) |

**完了条件**: 5 軸全充足 + 各セクションに必要十分図解 + `scripts/quality_gate.py` PASS + `scripts/verify_notion_assets.py` PASS + Notion 公開成功。

## 既存スキルとの責務境界

| Skill | 責務 | 非技術者対応 | 図解マスト | Notion 公開 |
|---|---|---|---|---|
| `run-skill-elicit` | brief.json 生成 | △ (技術者前提) | ❌ | ❌ |
| **`run-skill-intake-aggregator`** (本スキル) | intake.md + intake.json + Notion 公開 | ✅ | ✅ (Mermaid 12+SVG 8) | ✅ |
| `run-skill-create` | スキル本体生成オーケストレーション | — | — | — |

`run-skill-create` から Step 1 を呼ぶ際、非技術者ヒアリングが必要なら `run-skill-elicit` ではなく本スキルを起動する。両者の出力 JSON は `references/handoff-contract.md` で互換性を保つ。

## Key Rules

1. **Problem First**: 表層要望を仮説扱いし、本質的問題を最優先で発掘。
2. **Structure-Reduces-Drift**: 「言語化されているのは1割」を前提に、問い構造で誤り訂正する。
3. **Script First**: 決定論処理はすべて `scripts/*.py` (Python 3 標準ライブラリのみ; macOS 標準 `/usr/bin/python3`)。LLM 判断は補助。
4. **Visualization Mandatory**: 全セクションに 1〜3 図 (Mermaid 12+SVG 8 カタログから選択)。非エンジニア対応マスト 8 ルール強制。
5. **Self-Evolving**: question-bank がヒアリング毎に成長する自己進化ループ。
6. **Secret-Out-of-Repo**: API シークレットはコード/`.env`/環境変数に置かず macOS Keychain から都度取得。`scripts/keychain_get_secret.py` 経由のみ。
7. **5 軸必須**: 出力先・情報源・共有相手・真の課題・ナレッジ資産。1 軸でも欠けたら `scripts/check_completeness.py` で FAIL。
8. **All-or-Nothing 公開**: Notion 公開は PNG 1 枚でも欠けたら停止 (`scripts/verify_notion_assets.py`)。

## 責務分担: challenger × excavator

| SubAgent | 責務 | やらないこと |
|---|---|---|
| `skill-intake-assumption-challenger` | ユーザーの表層要望を**仮説扱い**し、前提を疑う問いを投げる (例: 「本当に Notion が出力先か?」) | 深掘り質問・8技法の運用 (excavator の領域) |
| `skill-intake-purpose-excavator` | 8 elicitation 技法 (5 Whys / Job-To-Be-Done / Pre-mortem / 反例提示 等) を用いて **真の課題を発掘** | 表層を疑う初期スクリーニング (challenger の領域) |

境界: challenger は「Yes/No で軌道修正できる広い問い」、excavator は「具体例と深さを取りに行く問い」。両者は順序固定 (challenger → excavator) で重複質問を避ける。

## End-to-End Flow (11 phase / 12 SubAgent — interviewer⇄excavator はペア稼働で 1 phase)

```
[起動] /intake または run-skill-create 経由
  ↓ skill-intake-kickoff          パターン選択・深度確認
  ↓ skill-intake-assumption-challenger  仮説扱い・表層を疑う
  ↓ skill-intake-user-profiler    熟練度推定・後続語彙難易度調整
  ↓ skill-intake-interviewer ⇄ skill-intake-purpose-excavator  対話 (最大5往復)
  ↓ skill-intake-option-presenter 外部連携カタログ提示
  ↓ skill-intake-visualizer       1〜3 図/セクション配置
  ↓ skill-intake-summarizer       Gate A サマリ → ユーザー承認
  ↓ skill-intake-next-action-advisor  skill-creator 引き渡しモード判定
  ↓ skill-intake-handoff          Markdown 正本 + JSON 副本生成
  ↓ skill-intake-notion-publisher Keychain→Notion REST API でページ作成
  ↓ skill-intake-self-updater     question-bank に不足質問を追記
[完了]
```

各 phase は `agents/skill-intake-<role>.md` の SubAgent として独立 context で起動。SubAgent 一覧は plugin ルートの `agents/` 配下。

## 認証契約 (macOS Keychain × Notion)

Notion トークンは Keychain から都度取得。コード・コミット履歴・`.env`・環境変数に平文を残さない。

| 項目 | 既定値 | 上書き環境変数 |
|--|--|--|
| service | `notion-api-key` | `INTAKE_KEYCHAIN_SERVICE` |
| account | `skill-intake` | `INTAKE_KEYCHAIN_ACCOUNT` |
| Notion DB ID | (必須・既定値なし) | `INTAKE_NOTION_DATABASE_ID` |
| Notion-Version | `2022-06-28` | `INTAKE_NOTION_VERSION` |

初回セットアップは `references/keychain-setup.md`。

## Steps (orchestrator として)

### Step 0: 前提検証
```bash
python3 plugins/skill-intake/scripts/keychain_get_secret.py --check   # トークン有無確認 (中身は表示しない)
python3 plugins/skill-intake/scripts/verify_notion_schema.py --on-conflict skip-warn   # database_id は schema.database_id_default を fallback で使用
```
exit 44 なら `references/keychain-setup.md` を案内して停止。

### Step 1-11: 12 SubAgent 順次起動 (Step 4 で interviewer⇄excavator がペア稼働)
各 SubAgent 完了後に `python3 plugins/skill-intake/scripts/quality_gate.py output/<hint>/intake.json` で自己採点 PASS を必須化。

### Step 12: cross-check + 公開 (single entry pipeline)
```bash
python3 plugins/skill-intake/scripts/cross_check.py output/<hint>/intake.json output/<hint>/intake.md
python3 plugins/skill-intake/scripts/verify_notion_assets.py output/<hint>/notion-manifest.json
python3 plugins/skill-intake/scripts/intake_publish_pipeline.py \
  --intake output/<hint>/intake.json \
  --manifest output/<hint>/notion-manifest.json
```
`intake_publish_pipeline.py` が内部で render → quality_gate (blocks 網羅性込) → publish を順に exec し、いずれかが exit !=0 ならその時点で停止する。SubAgent `skill-intake-notion-publisher` はこの pipeline の単一発火点を呼ぶ。

## Slash Commands

| コマンド | 用途 |
|--|--|
| `/intake [topic]` | 本スキルを起動 (= 12 phase 全実行) |
| `/intake-publish <hint>` | 既存 intake を Notion 再公開のみ |
| `/intake-status <hint>` | 進行中ヒアリングの状況確認 |

定義は plugin ルートの `commands/` 配下。

## Hooks

- `hooks/pre-publish-secret-scrub.sh` — Notion 公開前に intake.json / notion-blocks.json に Bearer/PAT/secret_ パターンが混入していないか走査
- `hooks/post-keychain-add.sh` — Keychain 登録直後に `security find-generic-password` で取得可否を検証

配線方法は `hooks/README.md` 参照 (`~/.claude/settings.json` または project `.claude/settings.json` の `hooks` セクション)。

## Gotchas

1. **`run-skill-elicit` との混同禁止**: 既存 `run-skill-elicit` は技術者向け簡易 brief 生成。本スキルは非技術者対応 + 図解 + Notion 公開の重装版。Q1「ヒアリング対象が完全非技術者か」が判断基準。
2. **PAT のチーム共有非推奨**: 個人 PAT を Keychain 経由でチーム共有すると監査ログ汚染・権限スコープ過大のリスク。チーム本番運用はサービスアカウント PAT または Internal Integration を使う。
3. **SVG 直貼り禁止**: Notion は SVG ネイティブ表示不可。`scripts/render_to_image.py` で必ず PNG 化。
4. **5 軸 1 つでも欠けたら停止**: ナレッジ資産軸は表層の情報源軸と独立。両方の充足を `check_completeness.py` が検証。
5. **DB プロパティ衝突は skip + 警告**: 既存 DB を破壊しない。`verify_notion_schema.py --on-conflict skip-warn` 既定。

## Additional Resources

### references/ (本スキル直下、20 個)

| 用途 | ファイル |
|--|--|
| 問い設計 | elicitation-techniques.md |
| ユーザー軸 | user-profile-dimensions.md |
| JSON スキーマ | handoff-contract.md |
| Notion 連携 | notion-integration.md |
| Keychain 設定 | keychain-setup.md |
| Notion DB スキーマ | notion-db-schema.json |
| 質問銀行 | question-bank.md |
| 語彙難易度 | vocabulary-tiers.md |
| 類似判定 | pattern-recognition-rules.md |
| 完了判定 | completeness-criteria.md |
| 失敗パターン | failure-modes.md |
| 外部連携カタログ | integration-catalog.md |
| 表層→深層変換 | surface-vs-deep-patterns.md |
| 価値判定 | value-realization-criteria.md |
| 図解選択 | mermaid-visualization-guide.md |
| 5 次元ルブリック | quality-rubric.md |
| アンチパターン | anti-patterns.md |
| 図解マスト 8 ルール | visualization-mandatory-rules.md |
| セクション必要十分 | section-completeness-rules.md |
| 非技術者言い換え | non-tech-vocabulary.md |
| Progressive Disclosure | resource-map.yaml |

### SubAgent (plugin 直下 `agents/`, 12 個)

`skill-intake-kickoff` / `skill-intake-assumption-challenger` / `skill-intake-user-profiler` / `skill-intake-interviewer` / `skill-intake-purpose-excavator` / `skill-intake-option-presenter` / `skill-intake-visualizer` / `skill-intake-summarizer` / `skill-intake-next-action-advisor` / `skill-intake-handoff` / `skill-intake-notion-publisher` / `skill-intake-self-updater`

### Scripts (plugin 直下 `scripts/`, 27 本)

`keychain_get_secret.py` / `create_notion_database.py` / `verify_notion_schema.py` / `notion_http.py` / `render_notion_page.py` / `verify_notion_assets.py` / `publish_notion_page.py` (Notion×Keychain 系 新規 7 本) + 旧 20 本 (slack-notifier SubAgent と compose_slack_message.py は廃止、必要時は hook 層 `hooks/post-publish-notify.sh` で opt-in 通知)。一覧は `scripts/README.md`。

### Assets (本スキル直下 `assets/`)

- `assets/mtmpl-*.mmd` — Mermaid テンプレ 12 種
- `assets/cvis-*.svg` — 独自 SVG 8 種
- `assets/msample-*.mmd` — 完成例 8 種
- Skill 規約 (lint-skill-tree 第13条) により nested dir 禁止のため flat 配置 + プレフィックス分類

### 関連スキル

- `run-notion-intake-publish` — Notion 再公開専用 sibling skill (kind=run, 非冪等処理あり)
- `run-skill-elicit` — 技術者向け簡易 brief 生成 (本スキルと併存)
- `run-skill-create` — Step 1 から本スキルを呼ぶオーケストレーター
