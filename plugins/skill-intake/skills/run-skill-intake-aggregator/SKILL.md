---
name: run-skill-intake-aggregator
prefix: run
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
disable-model-invocation: true
effect: external-mutation
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-21
audit-trigger: monthly
hierarchy_level: orchestrator
rubric_refs:
  - references/quality-rubric.md
  - references/execution-surface-rubric.md
  - references/rubric.json
subagent_template: references/seven-layer-subagent-template.md
shared_schemas:
  - schemas/handoff.schema.json
  - schemas/findings.schema.json
  - schemas/intake-final.schema.json
lint_scripts:
  - ../../scripts/lint_subagent_seven_layer.py
role_suffix: aggregator
owner: team-platform
since: 2026-05-20
responsibility_refs:
  - prompts/R2-main.md
  - prompts/R1.md
schema_refs:
  - schemas/intake-final.schema.json
manifest: workflow-manifest.json
---

# run-skill-intake-aggregator

## Purpose & Output Contract

skill-creator (`run-skill-create`) の Step 1 (`run-skill-elicit`) を非技術者向けに拡張するメタスキル。完全非技術者を含む不特定多数から、本人も言語化できていない真の課題を引き出し、3 つの成果物を一括生成する。

**入力**: ユーザーの「スキルを作りたい」要望 (topic 引数任意) + 任意の Notion 明示指定 (`--page-url` / `--page-id` / `--database-id`)。Notion 明示指定は Phase 11 の `intake_publish_pipeline.py` までそのまま伝搬し、指定 page がある場合は update 専用で create へフォールバックしない。

**成果物 (5 種類)**:

| 成果物 | パス | 利用者 |
|--|--|--|
| Markdown 正本 | `output/<skill-name-hint>/intake.md` | 人間 (ヒアリングシート) |
| JSON 副本 | `output/<skill-name-hint>/intake.json` | skill-creator (Phase 0-0 簡略化) |
| Notion ページ URL | `output/<skill-name-hint>/notion-url.txt` | チーム共有 |
| Notion ブロック JSON (中間生成物) | `output/<skill-name-hint>/notion-blocks.json` | publisher 入力 |
| self-update メタログ | `output/<skill-name-hint>/self-update.json` | skill-intake-self-updater (question-bank 更新証跡) |

**完了条件**: 5 軸全充足 + 各セクションに必要十分図解 + `scripts/quality_gate.py` PASS + `scripts/render-intake-final.py` PASS (JSON Schema + adopted 一意性検証) + `scripts/verify_notion_assets.py` PASS + Notion 公開成功。

### 本文テンプレ = intake-final-template.md.tmpl §0〜§11

正本: `references/intake-final-template.md.tmpl` + `references/intake-final-schema.json` + `references/section_canonical_map.json` (v2)。生成は `scripts/render-intake-final.py`、Notion 投影は `scripts/render_notion_page.py` (v2: intake-final-context.json を入力)。

旧 v1 (`section-templates.json` + 6ブロック格子 + `apply_section_template.py` + `section_quality_check.py`) は本リリースで廃止・削除済み。

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
3. **Script First**: 決定論処理はすべて `scripts/*.py` (Python 3 + `jsonschema` / `jinja2` を許容 — pip-installable, JSON Schema 検証と Jinja2 テンプレ駆動に必須; macOS 標準 `/usr/bin/python3`)。LLM 判断は補助。
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
  ↓ skill-intake-handoff          Markdown 正本 + JSON 副本生成
  ↓ skill-intake-notion-publisher Keychain→Notion REST API で指定 page へ公開
  ↓ skill-intake-next-action-advisor  Notion 公開完了後に skill-creator 引き渡しモード判定
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
| Notion DB ID | per-repo: `<repo-root>/.notion-config.json#databases.hearing-sheet.db_id` (gitignore対象) | `--database-id` CLI > `INTAKE_NOTION_DATABASE_ID` env > config > schema default(null)。setup: `plugins/skill-intake/references/notion-per-repo-setup.md` |
| Notion-Version | `2022-06-28` | `INTAKE_NOTION_VERSION` |

初回セットアップは `references/keychain-setup.md`。

## ゴールシーク実行

固定 Steps を持たず、`workflow-manifest.json` の `phases[]` (R1-R11) を SSOT として参照する。orchestrator は完了チェックリストを唯一の停止条件とし、未達 phase を都度埋めて反復する。

### ゴール (Goal)

非エンジニアの skill 要望から、`intake.md` (Markdown 正本) + `intake.json` (JSON 副本) + Notion ページが揃い、`intake-final.schema.json` 準拠・5 軸全充足・quality-rubric 閾値以上・図解マスト 8 ルール充足・Keychain 認証経由の Notion 公開が成功している状態。

### 目的・背景 (Why)

完全非技術者を含む不特定多数から「本人も言語化できていない真の課題」を引き出すには、11 phase 直列固定ではなく `quality_score` / completeness / asset 検証の未達点を都度ピンポイントで埋める必要がある。固定 Steps は phase 間の差し戻し (例: R8 で section 充足 FAIL → R4 elicitation 再実行) に弱く、回帰リスクが高い。

### 完了チェックリスト (Checklist)

- [ ] `workflow-manifest.json` の全 R-phase (R1-R11) が PASS で完了し、`output/<hint>/intake.md` `intake.json` `notion-url.txt` `notion-blocks.json` `self-update.json` が揃っている
- [ ] `python3 plugins/skill-intake/scripts/render-intake-final.py` が JSON Schema (`intake-final.schema.json`) + adopted 一意性検証で PASS
- [ ] `python3 plugins/skill-intake/scripts/check_completeness.py` で 5 軸 (出力先・情報源・共有相手・真の課題・ナレッジ資産) 全充足
- [ ] `python3 plugins/skill-intake/scripts/quality_gate.py output/<hint>/intake.json` が rubric 閾値以上で PASS、`validation.quality_score` に書き戻し済み
- [ ] `python3 plugins/skill-intake/scripts/cross_check.py output/<hint>/intake.json output/<hint>/intake.md` PASS (md/json 整合)
- [ ] `python3 plugins/skill-intake/scripts/verify_notion_assets.py output/<hint>/notion-manifest.json` で PNG/Mermaid 12 + SVG 8 のうち使用分が全て生成済み (All-or-Nothing)
- [ ] `python3 plugins/skill-intake/scripts/keychain_get_secret.py --check` exit 0、Notion トークンは平文で成果物・ログに残置なし
- [ ] `python3 plugins/skill-intake/scripts/intake_publish_pipeline.py --intake … --manifest …` が単一発火点として render→quality_gate→publish を完走し Notion URL 取得済み。`--page-url` / `--page-id` が入力に含まれる場合は `--revise` と共に渡され、指定 page 以外へ出力していない
- [ ] 12 SubAgent (kickoff / assumption-challenger / user-profiler / interviewer ⇄ purpose-excavator / option-presenter / visualizer / summarizer / next-action-advisor / handoff / notion-publisher / self-updater) 各々の出力 handoff が `schemas/handoff.schema.json` 準拠で残されている
- [ ] orchestrator-trace.json に各 phase の入出力パス・exit code・所要時間が記録され、再実行で順序一致 (determinism)
- [ ] 固有名詞 (個人名 / 社名 / 固定 page_id) を成果物に直書きしていない (variable_abstraction)

### ゴールシークループ

本スキル内の完了チェックリストと `workflow-manifest.json` を正本として、現状評価→手順生成→実行→検証→反復/差し戻しを行う。skill-creator が未インストールの単独 install でも、intake→Notion publish のコアフローは本 plugin 内の契約だけで完結する。本スキル固有の差分:

- **未達評価の単位は phase**: `workflow-manifest.json` の `phases[]` を SSOT とし、checklist 未充足項目 → 対応 phase (R1-R11) を特定 → 起動 → exit code と handoff を trace へ追記 → 自己評価を反復。
- **fatal_exit_codes**: 各 phase の `fatal_exit_codes: [2, 3]` を受けたら即中断し `orchestrator-trace.json` に error を残す。schema 違反は 3 回まで自己修正後 `skill-intake-handoff` へ escalate。
- **差し戻しパス**: R8 (completeness) FAIL → R4 (elicitation) 再実行 / R9 (quality) 閾値未達 → R7 (visualize) または R4 へ / R11 (publish) FAIL → R10 (render) または asset 再生成へ。
- **context:fork**: 12 SubAgent は分離 context で起動し、親へは差分と exit code のみ返却 (中間ログを親に流さない)。
- **単一発火点**: Notion 公開は `intake_publish_pipeline.py` のみを発火点とし、SubAgent `skill-intake-notion-publisher` と sibling `run-notion-intake-publish` から二重に render/publish を直叩きしない。指定 page がある場合、`--page-id` / `--page-url` を最優先で渡し、page_id 解決不能時は exit 51 で停止する。
- **Notion target 正本化**: `--page-url` / `--page-id` / `--database-id` は `notion_target` として intake.json / intake-final-context.json に保持する。update mode では `notion_target.page_id` と publish result の page_id 一致を必須とし、create fallback を禁止する。
- **skill-creator 引き渡しゲート**: `run-skill-create` 等の skill 本体生成へ進む判断は、`notion-log.json.status=="published"` と `notion-publish-result.json.page_id` を確認した後に限る。Notion 未公開のまま skill を作り始めない。
- **All-or-Nothing 公開**: PNG 1 枚でも欠けたら `verify_notion_assets.py` で停止。途中まで公開せず asset 再生成へ戻す。
- **自動修正禁止**: quality_gate / completeness FAIL は根本原因をユーザーに提示し、LLM 判断で内容を勝手に直さない (推測補完禁止)。

各 phase の `id` / `dependsOn` / `resourceIds` / `fatal_exit_codes` は `workflow-manifest.json` 参照。R-phase 詳細責務は `prompts/R<n>.md`、entry orchestration は `prompts/R2-main.md`。

## Slash Commands

| コマンド | 用途 |
|--|--|
| `/intake [topic]` | 本スキルを起動 (= 11 phase / 12 SubAgent 全実行。interviewer ⇄ excavator はペア稼働で 1 phase) |
| `/intake-publish <hint>` | 既存 intake を Notion 再公開のみ |
| `/intake-revise <hint> [--dry-run]` | 既存 intake へ追加要望を聞き取り、同一 Notion ページを update mode で PATCH 上書き (create fallback 禁止) |
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

### references/ (本スキル直下。実体が正本、以下は主要分の抜粋)

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

### Scripts (plugin 直下 `scripts/`。本数・分類の正本は `scripts/README.md`)

決定論処理は plugin 直下 `scripts/` に集約する (本スキル直下に `scripts/` は持たない)。Notion×Keychain 系の主要分は `keychain_get_secret.py` / `create_notion_database.py` / `verify_notion_schema.py` / `notion_http.py` / `render_notion_page.py` / `verify_notion_assets.py` / `publish_notion_page.py`。slack-notifier SubAgent と compose_slack_message.py は廃止し、通知は hook 層 `hooks/post-publish-notify.sh` で opt-in。スクリプト本数・カテゴリ別内訳は `scripts/README.md` を唯一の正本とする。

### Assets (本スキル直下 `assets/`)

- `assets/mtmpl-*.mmd` — Mermaid テンプレ 12 種
- `assets/cvis-*.svg` — 独自 SVG 8 種
- `assets/msample-*.mmd` — 完成例 8 種
- Skill 規約 (lint-skill-tree 第13条) により nested dir 禁止のため flat 配置 + プレフィックス分類

### 関連スキル

- `run-notion-intake-publish` — Notion 再公開専用 sibling skill (kind=run, 非冪等処理あり)
- `run-skill-elicit` — 技術者向け簡易 brief 生成 (本スキルと併存)
- `run-skill-create` — Step 1 から本スキルを呼ぶオーケストレーター
