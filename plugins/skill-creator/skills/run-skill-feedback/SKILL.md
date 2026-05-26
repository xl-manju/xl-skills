---
name: run-skill-feedback
description: 既存スキルへの「こう直してほしい」要望を受け取って Notion 改善要望 DB にプッシュしたいとき、利用者発端のフィードバックループを起動したいときに使う。
triggers:
  - "skill改善要望"
  - "プラグイン要望"
  - "skill feedback"
  - "こう直してほしい"
  - "改善提案"
disable-model-invocation: true
user-invocable: true
argument-hint: "[plugin] [skill-name?]"
arguments: [plugin, skill_name]
allowed-tools:
  - Read
  - Bash(python3 *)
  - Bash(security *)
kind: run
prefix: run
effect: external-mutation
owner: team-platform
since: 2026-05-25
version: 0.1.0
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-05-25
audit-trigger: on-change
manifest: workflow-manifest.json
completeness_exempt:
  - "prompts: 対話手順 SSOT は doc/notion-schema/skill-list.schema.json#feedback_protocol (Notion §7 と同一正本)。本 SKILL.md は schema を参照し scripts/notion-submit-improvement.py へ橋渡しするのみ。prompt-creator の R-id 単位 7 層プロンプトは適用外 (二重定義禁止 [[project_ssot_dedup_mechanism]])。"
---

# run-skill-feedback

## Purpose & Output Contract

利用者が既存スキルに対して「こう直してほしい」と感じた瞬間に発火し、構造化フィードバックを Notion 改善要望 DB へ N:1 relation 付きでプッシュする。スキル一覧の `未対応要望数` rollup が自動更新され、優先度判断シグナルになる。

## 発火条件 (SSOT)

発火条件・対話項目・状態遷移は `doc/notion-schema/skill-list.schema.json` の `feedback_protocol` を唯一の正本 (SSOT) とする。本 SKILL.md / `scripts/notion-upsert-plugin.py` / Notion スキル一覧ページ本文 §7 の三者は全てこの正本から派生し、`scripts/lint-feedback-protocol.py` が整合を機械検証する。

具体的な発火条件 (schema `feedback_protocol.firing_conditions` 抜粋):
- プラグインを使って「ここが分かりにくい」と感じた
- 「こう直してほしい」「この挙動はバグでは」と思った
- プロンプト出力品質に不満 / ドキュメントの誤記を見つけた
- 新機能・挙動変更の要望が浮かんだ

発火条件の追加・変更は **schema を編集 → lint 通過 → 派生物 (triggers / SKILL.md / 本文) を同期** の順で行うこと。

**入力**:
- `plugin` (必須): 対象プラグイン名。スキル一覧 DB の TITLE と一致すること
- `skill_name` (任意): プラグイン内の個別スキル名

**出力**: Notion 改善要望 DB の新規ページ 1 件 (URL を返す)

**冪等性**: 改善要望はタイトルが重複しても別レコードとして扱う(時系列ログとしての性質)。重複除去は人手で実施。

## Key Rules

1. **SSOT 厳守**: 発火条件・対話項目は `doc/notion-schema/skill-list.schema.json` の `feedback_protocol` を唯一の正本とし、本 SKILL.md / スクリプト / Notion 本文の三者は派生のみ。
2. **対象プラグイン存在確認必須**: スキル一覧 DB に未登録なら `run-build-skill --notion-register` を案内して中断 (孤児レコード防止)。
3. **token / DB ID は notion-config SSOT 経由**: `plugins/skill-creator/scripts/notion_config.py` の `require_or_skip()` が解決順 (CLI 引数 > env `NOTION_TOKEN` / `NOTION_*_DATABASE_ID` > per-repo `.notion-config.json` > macOS Keychain slug-namespaced key) を一元管理。`scripts/notion-submit-improvement.py` は同 loader を import 済み。symlink 共有された他 repo (`.notion-config.json` 分離) でも DB ID 解決が動作する。token / DB ID をコンテキストに乗せない。
4. **重複除去は人手**: 時系列ログ性質を保つため AI は重複判定せず投入する。
5. **people 型は UI で人手追加**: API 経由でメール宛指定不可のため起票者/担当者は完了通知時に案内。

## ゴールシーク実行

固定手順は書かず、ゴール+チェックリストへ向け都度手順を生成・反復する。正本: `../run-build-skill/references/goal-seek-paradigm.md`。

### ゴール (Goal)

利用者の「こう直してほしい」要望が、`doc/notion-schema/improvement-request.schema.json` 準拠の構造化フィードバックとして Notion 改善要望 DB にプッシュされ、スキル一覧 DB の `未対応要望数` rollup が更新され、起票完了通知 (ページ URL + 人手追加項目案内) がユーザーに返された状態になっている。

### 目的・背景 (Why)

利用者発端のフィードバックループを摩擦最小で起動するため。要望は時系列ログとして 1:N で集約し、優先度判断シグナル (`未対応要望数` rollup) に直結させる。固定手順では「対象プラグイン未登録」「token 未設定」などの実行時文脈に脆いため、未達条件を局面カタログから都度埋める。

### 完了チェックリスト (Checklist)

- [ ] 要望タイトル / 種別 / 内容 / 優先度 / 重要度 が `feedback_protocol` 必須項目として収集済み
- [ ] 対象プラグインがスキル一覧 DB に存在することを `--dry-run` で確認済み (未登録なら中断して案内)
- [ ] Notion 改善要望 DB に 1 ページが新規作成され URL が取得できている
- [ ] スキル一覧 DB との N:1 relation が貼られ `未対応要望数` rollup が増分している
- [ ] 完了通知に「起票者・担当者は Notion UI で人手追加」案内が含まれている
- [ ] token / DB ID は `notion_config.require_or_skip()` 経由 (CLI > env > per-repo `.notion-config.json` > Keychain slug-namespaced key の解決順) で取得しており context に露出していない

### ゴールシークループ

正本 5 ステップ (現状評価→手順生成→実行→検証→反復) に従う。本スキル固有差分: 未達評価の単位はチェックリスト項目。投入失敗 (404/401/schema 違反) 時は原因を `feedback_protocol` SSOT に照らして特定し再実行。下記局面は順序固定ではなく未達条件から都度選ぶ。

## 局面カタログ (順序は都度判断)

### 要望収集 (対話)

以下を順に質問し、回答を構造化する:

1. **要望タイトル** (30字目安、何を直したいかを1行で)
2. **要望種別**: `バグ` / `機能追加` / `プロンプト改善` / `ドキュメント` / `挙動変更` の中から1つ
3. **やってほしいこと**: "こう直してほしい" を一段落で
4. **背景・困っていること**: なぜそれが必要か (任意)
5. **優先度**: `高` / `中` / `低` (デフォルト中)
6. **重要度**: `高` / `中` / `低` (デフォルト中)
7. **関連 PR/コミット URL** (任意)

### 対象プラグインの存在確認

```bash
# スキル一覧 DB に対象プラグインが登録済みか確認
python3 scripts/notion-submit-improvement.py --plugin <plugin> --dry-run \
  --title "<title>" --type <type> --desire "<desire>"
```

存在しない場合は `run-build-skill --notion-register` を先に走らせる旨を案内して中断。

### 改善要望投入

```bash
python3 scripts/notion-submit-improvement.py \
  --plugin "<plugin>" --skill-name "<skill_name>" \
  --title "<title>" --type "<type>" \
  --desire "<desire>" --background "<background>" \
  --priority "<priority>" --importance "<importance>" \
  --pr-url "<pr-url>"
```

token / DB ID は `notion_config.require_or_skip()` 経由 (CLI > env > per-repo `.notion-config.json` > Keychain slug-namespaced key の解決順)。`notion-submit-improvement.py` 内で自動解決され、unresolvable なら skip + 利用者通知。

### 完了通知

投入された Notion ページ ID を提示し、起票者・担当者プロパティは Notion UI 側で人手追加するよう案内 (people 型は API 経由でメール宛指定不可のため)。

## Gotchas

1. **孤児レコード禁止**: 対象プラグインがスキル一覧 DB 未登録のまま要望だけ投入しない。必ず `--dry-run` で先に存在確認。
2. **token / DB ID を context に乗せない**: スクリプト内で `notion_config.require_or_skip()` (CLI > env > `.notion-config.json` > Keychain) 経由で取得し、Claude の応答や log に出力しない。
3. **重複除去を AI 判定しない**: 似た要望でも別レコードとして投入する (時系列ログ性質を破壊しない)。
4. **people 型を API で埋めない**: 起票者・担当者は UI 側案内のみ。API でメール宛指定はサポート外。
5. **発火条件追加は schema 経由**: `feedback_protocol.firing_conditions` 直接編集 → lint 通過 → 派生物同期の順。SKILL.md / triggers の先行編集禁止。
6. **rollup 更新は Notion 側非同期**: 完了通知時に「rollup は数秒〜数分遅延あり」と添える。

## Additional Resources

- 上流: 利用者の口頭・Slack・PR コメントなど任意の発火源
- 下流: スキル一覧 DB の `未対応要望数` rollup → `skill-improve` skill による着手判断
- スキーマ正本: `doc/notion-schema/improvement-request.schema.json`
- 物理スクリプト: `scripts/notion-submit-improvement.py`
- 1:1 で生成元を辿りたい場合は `紐づくヒアリングシート` → `Skillヒアリングシート` DB
