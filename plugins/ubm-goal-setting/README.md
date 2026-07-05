# ubm-goal-setting — 北原さん式ゴールセッティング

UBM（北原さん式ゴールセッティング）の**目標設定・振り返り対話**と**ナレッジ差分同期**を 1 つにした Claude Code プラグインです。ObsidianMemo vault で運用していた資産（skill / sub-agent / hook / script / knowledge JSON 一式）を移植したもので、**個人利用前提**（`distributable:false`・公開 marketplace 非掲載）です。

このドキュメントは「初めて使う人がインストールし、`UBM_VAULT_ROOT` を設定して最初の目標設定を回せる状態にする」までの導入ガイドです。**日々の運用（入口コマンド詳細・検証コマンド・復旧手順）は [`RUNBOOK.md`](./RUNBOOK.md) が正本**で、本 README とは役割を分担しています（README=初見導入 / RUNBOOK=運用）。

---

## Part 1 — これは何をするもの？（前提知識なしで読める説明）

**たとえ話**: 部活の顧問の先生（＝北原さん）が隣にいて、「今週は何をがんばる？」「先月は何がうまくいった？」と質問しながら、目標カードを一緒に作ってくれる道具です。

1. **目標設定・振り返り対話** (`/ubm-goal-setting`)
   - 「1 週間（週報）・1 ヶ月（月報）・2 ヶ月（期報）」の目標を、AI との短い対話で作ります。
   - できあがった目標は決まった型（**21 項目**）のチェックに**合格しないと保存されません**。「頑張る」「意識する」のようなあいまいな言葉は機械が弾き、「誰に・何を・いつまでに・何件」まで具体化させます。
   - 目標には「**やらないこと**」も 3 つ以上書きます。やることを増やすより、迷いを減らすほうが行動につながるからです。

2. **ナレッジ同期** (`/ubm-knowledge-sync`)
   - 北原さんの新しい教え（動画の議事録・合宿の記録・月報へのフィードバックなど）を読み取り、**6 つの引き出し**（原則 / 相談 / フェーズ別アドバイス / 行動ガイド / マインドセット / 事例）に整理して貯めます。
   - 貯めた知識は、次の目標設定の対話で自動的に引き出されます。**学ぶ→貯める→次の目標に生かす**、が一つのサイクルになります。

**なぜこの 2 つがセットか**: 目標は「作って終わり」だと忘れます。毎週の振り返り→次の目標→新しい学びの取り込み、というループを回し続けるための道具だからです。

---

## インストール（ローカル導入）

本プラグインは `distributable:false` のため、**公開カタログ（`.claude-plugin/marketplace.json`）には掲載していません**。リモートの `/plugin marketplace add xl-manju/xl-skills` からは導入**できず**、clone したローカル repo を起点に導入します。

### 方法 A — xl-skills repo 内で使う（開発・レビュー向け・最短）

repo を clone し、repo root で `.claude/` symlink を展開します（`harness-creator` と同じ project-local 方式）。

```bash
git clone https://github.com/xl-manju/xl-skills.git
cd xl-skills
make sync   # plugins/ubm-goal-setting/ の skills/commands/agents を .claude/ へ symlink 展開
```

この repo を開いた Claude Code セッションで `/ubm-goal-setting` などがそのまま使えます。

### 方法 B — vault 作業フォルダなど repo 外で使う（ローカル marketplace add 経由）

個人用のローカル marketplace カタログを作り、そこから install します（公開カタログには載せません）。

```bash
# 1. 個人用カタログを作る (plugin 実体は clone 済み xl-skills を symlink 参照)
mkdir -p ~/ubm-marketplace/.claude-plugin ~/ubm-marketplace/plugins
ln -s /path/to/xl-skills/plugins/ubm-goal-setting ~/ubm-marketplace/plugins/ubm-goal-setting
cat > ~/ubm-marketplace/.claude-plugin/marketplace.json <<'JSON'
{
  "name": "ubm-local",
  "owner": { "name": "personal" },
  "plugins": [
    { "name": "ubm-goal-setting", "source": "./plugins/ubm-goal-setting" }
  ]
}
JSON
```

Claude Code（CLI / Desktop 共通）のチャット欄で:

```
/plugin marketplace add ~/ubm-marketplace
/plugin install ubm-goal-setting@ubm-local
```

**完了確認**: `/plugin` の一覧に `ubm-goal-setting` が enabled で表示され、`/ubm-goal-setting` が補完に出れば成功です。書き込み保護 hook（後述）は plugin manifest の `hooks` ブロック経由で install と同時に有効化されます。

---

## 初回設定 — `UBM_VAULT_ROOT` 環境変数

`UBM_VAULT_ROOT` は **Obsidian vault（生ソース置き場）の root パス**です。次の 3 つに使われます。

| 用途 | パス（`UBM_VAULT_ROOT` 配下） |
|---|---|
| 目標設定ファイルの保存先 | `05_Project/UBM/目標設定/` |
| Daily ノートの embed 参照更新 | `02_Configs/Templates/Daily.md` |
| ナレッジ差分検知のソース | `05_Project/UBM/` 配下の `.md` 全般 |

シェルの profile に export を追記します（パスは自分の vault に合わせる）:

```bash
# ~/.zshrc など
export UBM_VAULT_ROOT="$HOME/dev/dev/ObsidianMemo"
```

**未設定でも壊れません（縮退動作）**: 北原ナレッジ本体（28 JSON + router）は plugin に**同梱済み**（L1 curated シード）のため、install 直後・vault 未接続でも目標設定対話の知識参照は機能します。vault 未接続時のナレッジ同期は「検知 0 件」の正常終了になります。vault を接続すると、目標の保存・Daily 更新・差分同期の全機能が有効になります。

**フィードバック設定（任意）**: 本プラグインの機能自体は Notion を使いません。改善要望ループ（`run-skill-feedback`）を使う場合のみ、設置先 repo root の `.notion-config.json` に improvement-request DB の ID を設定します（論理キーは plan 宣言・実 DB ID はローカル設定の二層）。

---

## 最初の一歩

```
/ubm-goal-setting weekly     # 週報の目標設定を対話で作成 (5〜8分)
/ubm-knowledge-sync --dry-run  # ナレッジ差分の検知だけ試す (書き込みなし)
```

引数なしの `/ubm-goal-setting` は、どの種別（週報/月報/期報）かの確認から始まります。

---

## Part 2 — 技術説明（運用者向け）

### Phase0-5 ワークフロー（目標設定）

`run-ubm-goal-setting` skill は次の Phase を順に実行します（正本: skill の `SKILL.md`）。

| Phase | 責務 | 実行体 |
|---|---|---|
| Phase0-init | 種別（weekly/monthly/bimonthly）と実行日を確定 | 本 skill / AskUserQuestion |
| Phase1-2-collect | 過去目標・合宿情報・ナレッジ・journal を並列収集 | `info-collector` sub-agent |
| Phase2b-review | 振り返り時に既存目標を 8 項目で再評価 | `goal-reviewer` sub-agent |
| Phase3-dialogue | step1〜5 対話（現状振り返り→ギャップ→目標→行動計画→最終確認） | `phase3-coordinator` + 責務プロンプト `prompts/R1-R5` |
| Phase4-format | テンプレート整形 + 15 項目コンテンツ品質チェック | `output-formatter` sub-agent |
| Phase5-validate | `validate-goal-output.py` で **21 項目**を決定論検証（最大 3 回改善） | script |
| Phase6-daily-update | `Daily.md` の種別該当 embed のみ最新目標へ置換 | 本 skill |

21 項目（出力構造）の定義正本は `skills/run-ubm-goal-setting/references/output-formats.md` + `data-contract.md`、15 項目（保存前コンテンツ検証）は `output-formatter` prompt の品質チェックリスト節です。

### デュアルパス検索（ナレッジ参照）

`info-collector` は `knowledge/router.json` を索引に、3 レイヤーを**並列**で検索します: Path A=具体キーワード（`quick_lookup.by_issue` の tags）/ Path B=課題キー・フェーズキー / Path C=メタテーマ（`abstraction_layers`）。全パスのヒットを重複除去して該当 `knowledge/*.json` だけを Read し、複数パスに同時ヒットしたエントリを高優先でマージします（全 28 JSON の総当たり読み込みをしない）。

### 差分同期の仕組み（ナレッジ同期）

`run-ubm-knowledge-sync` は次の 3 層データ構造を前提に動きます。

- **L1 curated**（plugin 同梱シード）: 6 カテゴリ 28 JSON + `router.json`。fresh-install 直後から機能する知識本体。
- **L2 raw vault sources**（`UBM_VAULT_ROOT` で外部解決）: YouTube 議事録・合宿記録・月報 FB 等の生ソース。
- **L3 bookkeeping**（plugin 同梱・mutable）: `registry.json`（処理済み台帳・初期値 67 ソース）/ `sync-log.jsonl`（append-only 同期ログ・空開始）/ `assets/kitahara-principles-db.md`。

同期フロー: `detect-knowledge-updates.py` が L2 の `.md` を `registry.json` の **MD5 ハッシュと照合**して NEW/MODIFIED を検知 → `knowledge-extractor` sub-agent が内容別 6 カテゴリへ分類し `knowledge/*.json` + `router.json`/`registry.json` を更新（最大 20 ファイル/バッチの 1 トランザクション扱い）→ `check-knowledge-split.py` が 500 行閾値の肥大を機械検査。MODIFIED は `extracted_entry_ids` を辿って旧エントリを削除してから再抽出します。

### 書き込み保護（fail-closed hook）

`hooks/ubm-write-path-guard.py` が PreToolUse（`Write|Edit|MultiEdit`）で `UBM_VAULT_ROOT` 配下への書き込みを検査し、許可 2 パス（`05_Project/UBM/目標設定/` 配下・`02_Configs/Templates/Daily.md`）以外は exit 2 で遮断します。vault 外（plugin 同梱 `knowledge/` 等）と `UBM_VAULT_ROOT` 未設定時は保護対象外です。判定不能な入力は**遮断側に倒します**（fail-closed）。

### 品質ゲート

- `validate-goal-output.py`: 統一ハイブリッド構造 21 項目・NG 表現・やらないこと 3 項目以上を保存前に決定論検証。
- `tests/`（pytest 44 件）: script×3 / hook×1 の機能テスト + knowledge 台帳整合 + golden-sample 回帰。
- `EVALS.json`: mechanical lint 13 本と受入基準（criteria-test）の配線宣言。実行手順は `RUNBOOK.md` の Verification 節。

### 構成

```text
plugins/ubm-goal-setting/
├── skills/run-ubm-goal-setting/     # 目標設定 skill (+ scripts/validate-goal-output.py + prompts/R1-R5 対話プロンプト正本)
├── skills/run-ubm-knowledge-sync/   # ナレッジ同期 skill (+ detect/check scripts)
├── agents/                          # sub-agent 5 本 (info-collector/goal-reviewer/phase3-coordinator/output-formatter/knowledge-extractor)
├── commands/                        # /ubm-goal-setting, /ubm-knowledge-sync
├── hooks/ubm-write-path-guard.py    # 書き込み保護 (PreToolUse)
├── knowledge/                       # L1 curated 28 JSON + router/schema/registry/sync-log
├── tests/                           # pytest 44 件
├── EVALS.json / plugin-composition.yaml / RUNBOOK.md / CHANGELOG.md
├── .claude-plugin/plugin.json       # 公式 plugin manifest (hooks 配線)
└── references/package-contract.json # harness metadata (distributable:false, entry_points)
```

---

## 次に読むもの

- 運用・検証・復旧: [`RUNBOOK.md`](./RUNBOOK.md)
- 変更履歴: [`CHANGELOG.md`](./CHANGELOG.md)
- 設計判断・受入基準の由来: `plugin-plans/ubm-goal-setting/`（13 phase 計画 + component inventory）
