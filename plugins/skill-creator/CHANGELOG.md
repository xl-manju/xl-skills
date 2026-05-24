# CHANGELOG

本ファイルは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に準拠し、`skill-creator` plugin の変更履歴を記録する。設計書 33 章 `change-governance` に紐付き、SemVer に従う。

## [Unreleased] - 2026-05-22

着手中。本 PR 完了後にバージョンを確定する。

### Added

- **Capability 統一抽象**: `Capability` / `CapabilityManifest` / `CapabilityBundle` の三層モデルを導入し、skill/agent/hook/command/prompt/workflow/plugin-composition を単一語彙で表現可能にした。
- **plugin-composition.yaml**: plugin 間の依存・公開 capability・consume 関係を宣言する composition manifest を新設。
- **target_type 7 種対応 rubric**: `skill` / `agent` / `hook` / `command` / `plugin-composition` / `prompt` / `workflow` の 7 種に対し、共通核 + kind 固有 addendum の rubric を提供。
- **governance/feedback hook 配線**: 7 種すべてに対し governance gate と feedback ループの hook を配線。
- **lessons-learned 自動記録**: review/executor 実行ログから lessons を抽出し自動追記する経路を実装。
- **EVALS → rubric 自動 PR 経路**: EVALS 結果から rubric の改訂 PR を自動生成するパイプラインを追加。
- **依存グラフ生成**: capability 間の依存を DAG として出力する仕組みを追加。
- **dogfooding メトリクス**: 自己適用率・rubric 充足率・lessons 反映率を計測する初期メトリクスを導入。
- **ナレッジループ機構 (knowledge-loop)**: 生成スキルに「知見を蓄積・検索・§12改善し使うほど良くなる」ループを注入する横断 capability を追加。
  - **Loop A (生成物側)**: `run-build-skill --with-knowledge index-search|router-registry` で `knowledge/` 雛形 + 3 段階検索 (Stage1/2=決定論 script、Stage3=AI) + §12 フィードバックループを注入。正本 `ref-knowledge-loop`、雛形 `templates/knowledge-skeleton/`、横断 combinator `with-knowledge.patch`(新 kind を増やさず和空間で全 kind に伝搬)。
  - **Loop B (メタ側)**: `plugins/skill-creator/knowledge/`(build-patterns + lessons-index)を新設し、`run-skill-elicit` が build-time に蓄積知見を検索して設計判断へ反映 (dogfooding)。
  - **SSOT**: Loop A/B は同一スクリプトを共有。検索/記録/index 各スクリプトに `--dir <store>` を追加し複製を排除。`lint-knowledge-loop.py` に `--store-only` モードを追加し共有スクリプト構成 (Loop B) を正当化。
  - **検証**: KL-001..006 (`lint-knowledge-loop.py`)、`knowledge-loop.schema.json`、`skill-brief.schema.json` の `knowledge_loop` / `consult_build_knowledge`、rubric `KL-*` ルール。
  - **日々のブラッシュアップ機構 (elegant-review 反映)**: 生成スキル側でも知見を日々更新・追加できるよう片開きループを両開き化。`add_entry.py`(必須6フィールド検証つき追加=JSON手編集を排除)を雛形に追加し KL-006(warn)で推奨。`record_usage.py --analyze --emit-queue`(要改善エントリの brushup キュー出力)+ `--mark-needs-update`(status 付与) を追加。検出は決定論・内容改善は AI の二層分離を維持。
  - **配置の抽象階層を明示**: Loop A(生成物側=自己完結ユニットゆえ scripts/ を同梱)と Loop B(メタ側=正本を `--dir` 共有・複製しない)は排他でなく抽象階層が異なる旨を `knowledge-construction.md` §0a と `with-knowledge.patch` 脚注で明文化。全集約による死蔵を回避。
  - **再現性の機構化**: `governance-check.yml` に lint-knowledge-loop `--self-test` / 雛形4スクリプト `--self-test` / Loop B `--store-only --strict` を配線。lint↔schema の必須6フィールド二重定義を `--self-test` 内 drift 検出で SSOT 化、lint↔CI 配線忘れも `--self-test` のメタ検査で再発防止。汎用雛形からペルソナ固有語彙(`sakamoto_*`)を除去し汎用フィールド名(`expressions`/`voice`)へ。
  - **量産時の注入を決定論化 (毎回の再現性)**: `render-combinators.py` に `with-knowledge.patch` の semantic handler と `--with-knowledge` フラグを追加。これまで他9 combinator が `apply_semantic_patch` の決定論ハンドラを持つ一方、knowledge-loop 注入だけハンドラ不在で AI 解釈依存(`ComposeError: unknown combinator` 経路)だった穴を塞いだ。注入内容(frontmatter `knowledge_loop` ブロック + `## ナレッジループ` 節)は同梱4スクリプト(`search_knowledge`/`build_index`/`record_usage`/`add_entry`)のみを参照し、skill-creator 内部(`ref-knowledge-loop`/`templates/`/Loop B/`--dir`)へ一切依存しない=配布スキル自己完結。冪等(再適用しても二重注入なし)。`run-build-skill` Step 10 のコピー対象を3→4スクリプトへ修正し注入本文と一致させ、KL 表記を `KL-001..007` へ揃えた。

### Fixed

- **`with-run.patch` の世代ずれ解消 (`run` kind 描画失敗)**: semantic handler が旧世代の固定手順(`### Step 1/2/3` を `## 手順` アンカーへ)を注入しようとし、goal-seek 化済みの現 `_base.md`(`## ゴールシーク実行` を全 kind が継承)とアンカー不整合で `run` kind が必ず `ComposeError` で落ちていた。固定手順注入は goal-seek 原則「固定手順は書かない」と矛盾するため廃止し、run handler は run 固有 frontmatter(`effect`/`role_suffix`)付与のみに責務を限定。手順は `_base.md` から継承するため情報欠落なし。レビュー用 `with-run.patch` diff も実 semantic 挙動へ一致(diff↔handler SSOT)。これにより全 18 kind×フラグ組合せ(run/ref/wrap/delegate/assign-gen/assign-eval × none/knowledge/all)が決定論合成 PASS。

### Changed

- **rubric 構造再編**: 単一 rubric から「共通核 + kind 固有 addendum」構造へ再編し、target_type ごとに必要項目を最小化。
- **validate-build-trace.py 汎化**: skill 専用検証から kind 対応の汎用検証へリファクタし、7 種すべての build trace を検証可能にした。

### Status

着手中。本 PR マージ後に `0.x.0` を確定し本セクションを正式リリースへ昇格する。
