---
name: phase-lifecycle
description: 機能開発13フェーズ→プラグイン開発の読み替え表と、実ライフサイクルから導出した8フェーズ定義を読む。R2/R3 のフェーズ設計の正本。
kind: reference
owner: team-platform
since: 2026-06-29
source-tier: internal
---

# プラグイン開発ライフサイクル (§7 読替表 / §8 8 フェーズ)

> パスはすべて repo root 相対。borrow 元 (UBM-Hyogo `task-specification-creator`) は read-only 抽出のみで fork/複製しない。

## §7 ドメイン読み替え表 (機能開発13フェーズ → プラグイン開発)

keep=精神維持 / transform=対象ドメインへ写像 / drop=廃止 / replace=別機構へ置換。**TDD/カバレッジ は drop ではなく transform** (vitest/Cloudflare/IPC という実装基盤の固有性のみ捨て、TDD/品質保証の精神は写像する)。

| 旧 Phase | 判定 | 置換先 |
|---|---|---|
| P1 要件定義 | transform | 目的ドリブン要件定義 (`run-goal-elicit`→goal-spec)。taskType/visual 分類 DROP、kind/prefix/placement 分類へ |
| P2 設計 (validation matrix/type 互換) | transform | コンポーネント設計 (5 種写像 + kind/hierarchy/pattern)。type 互換 → schema 契約 |
| P3 設計レビューゲート | keep | `run-elegant-review` C1-C4 ゲートへ写像 |
| P4 テスト設計 (TDD Red) | transform | criteria を test-first 導出 (feedback_contract inner=lint exit0 / outer=verdict PASS)。Red=未達 criteria |
| P5 実装 (TDD Green) | transform | Green=criteria を goal-seek ループで充足。実 build は L4 へ委譲、本スキルは「Green の達成条件」を要件化 |
| P6 テスト実行 (vitest 80%) | transform | vitest/pnpm を DROP、pytest harness-coverage ≥80% (6 種別×二軸・kind 別パス) へ |
| P7 AC matrix 判定 | keep | 二値 AC を各仕様書 checklist へ |
| P8 リファクタリング (TDD Refactor) | transform | 重複排除 → `lint-ssot-duplication.py` (上書き一本化) へ写像 |
| P9 品質保証 | replace | P0 lint 8 本 + `validate-build-trace.py` + schema parity + content-review |
| P10 最終レビューゲート | keep | P3 と統合し elegant-review C1-C4 + governance に一本化 |
| P11 evidence (スクショ) | replace | スクショ DROP。Markdown evidence = lint exit0 ログ / schema parity / build-trace coverage / content-review verdict / `eval-log/coverage/*.json` |
| P12 ドキュメント 6 タスク (aiworkflow 同期) | keep+replace | 6 タスク雛形流用。aiworkflow 連携 DROP、反映先を `feedback_contract_ssot.py`/`lessons-learned`/`bundles.json` へ |
| P13 PR 作成 (PR/IPC/Cloudflare) | transform | IPC・Cloudflare 全 DROP。PR は xl-skills `feature→main + make validate + pytest` 完了条件として最終仕様書が言及 (本スキル責務外) |

### DROP (UBM 機能開発固有のみ)
Electron IPC・safeInvoke / Cloudflare・D1・Workers / Phase 11 スクリーンショット / aiworkflow-requirements SSOT 連携 / GitHub PR・deploy。**REPLACE**: スクショ → Markdown evidence (lint exit0 / schema parity / build-trace coverage / content-review verdict / coverage JSON)。この **5 要素集合** は P11 セル(上表)・`io-contract.md` §10 と一致させる (evidence 定義の単一 SSOT)。coverage JSON の表記は glob `eval-log/coverage/*.json` と具体パス `eval-log/coverage/skills/<plugin>__<skill>.json` の表層差を許容する (指す実体は同一)。

## §8 Phase 構成 (実ライフサイクルから導出・8 フェーズ)

導出原則: 13 固定でなく実ライフサイクルから必要十分な 8 フェーズを導出。各に存在理由。

| # | フェーズ | 目的 | 成果物 | 完了条件 | 存在理由 |
|---|---|---|---|---|---|
| **P1** | 目的ドリブン要件定義 | `run-goal-elicit` で purpose/background/goal/checklist を goal-spec に固める | 意図サマリ + goal-spec | 5 軸充足・checklist 各 verify_by 付き | 単語置換でなく目的駆動 |
| **P2** | スコープ & 責務境界 | capability 列挙 + SRP 分割線 | capability 一覧 + 分割線 | 単一責務・過剰分割なし (no-split threshold) | 1 skill=1 責務、分離≠善 |
| **P3** | コンポーネント設計 | 5 種へ写像し kind/prefix/hierarchy/pattern 確定 | コンポーネント目録 (**N**) + 依存 DAG | 各々 kind/placement 確定 | N が確定 = 本数導出根拠 |
| **P4** | 各コンポーネント build 仕様 | コンポーネントごと `run-skill-create` 投入用 brief 相当を 1 本ずつ起こす | per-component 仕様書 (× N) | skill-brief 14 フィールド相当 + criteria(test-first) を携帯 | 1 件ずつ段階実行できる粒度 (TDD Red) |
| **P5** | schema / lint 接続 | data schema・P0 lint・依存方向・frontmatter 整合・SSOT 重複排除 | 検証配線仕様 | P0 lint 8 本 exit0 設計 | 機械再現性は仕組み層で担保 |
| **P6** | 評価基準 / カバレッジ | feedback_contract criteria・harness ≥80%(kind 別)・content-review・evaluator(score≥80/high=0) | 評価基準仕様 | criteria が SSOT 形式・coverage 携帯 | 量産先に評価基準を焼き込む (TDD Green) |
| **P7** | ガバナンス / 配布 | `.claude-plugin/plugin.json` 契約・distributable 判定・marketplace/bundles 登録 or 非配布二重ロック・cachebuster update・rubric governance・Keychain | manifest / marketplace / 配布判定仕様 | manifest path/name/placeholder/validate と marketplace policy が一意決定・fail-closed | 配布境界の機械保証 |
| **P8** | レビュー / feedback | elegant-review C1-C4(30 思考法)・convergence-policy・unassigned-task 検出・skill-feedback 反映 | レビュー仕様 + 反映先 | C1-C4 全 PASS・未配置 0・反映先明示 | 収束と再発防止ループ |

**横断パラダイム (goal-seek)**: P1-P8 全体を `goal-seek-paradigm.md` の 6 ステップで回し、各周回末に中間成果物アンカー (jsonl) を追記。固定手順でなくゴール駆動。

**成果物本数モデル**: P1-P8 は process phase であり、P1-P3/P5-P8 の横断内容は `index.md` の章・完了条件・`plugin_meta` に集約する。独立した横断仕様書は作らない。`N` は `component-inventory.json` に列挙された buildable component ごとの per-component タスク仕様書本数のみを指す。

**index(main)**: P1-P3 設計成果 + P5-P8 横断規律 + P4 per-component 仕様書(× N)を**依存 top-sort 順**で並べた目次。本数根拠・各 status・全体完了条件を保持する。P1-P8 の横断規律は index の章であって、N に加算する別 spec ではない。

**出力先 (再現性)**: タスク仕様書 plan は repo-root 相対の `eval-log/plugin-dev-planner/<plugin-slug>/` に plugin ごとに隔離して作成する。`<plugin-slug>` は R1 が `goal-spec.json` の `target_plugin_slug` に固定し、P1-P8 と全 goal-seek 周回で不変にする。`--out-dir` 明示時のみ上書きでき、その場合も `goal-spec` に固定する。実プラグインディレクトリ (`plugins/<plugin-slug>/`) は本スキルでは作らず、L4 build 先は inventory/index の `build_target` で追跡する。

**本数導出 (13 でない理由)**: 生成 spec 総本数 = per-component build 仕様書(× N, P3 目録由来)。構成要素数に依存して変動し 13 に固定されない。ユーザーが「13個」を求めた場合は、旧 Phase 1-13 の読み替え要求なのか、成果物本数 13 本の固定要求なのかを R1 の `constraints` で分離してから展開する。`--force-13` 時のみ component spec を 13 本へ調整し、P1-P8 横断章を別 spec として水増ししない。
