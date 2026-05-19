# 33. Change Governance

最終更新: 2026-05-18

## 目的

本章は、Skill / script / config / rubric / 設計書の変更を**統制ある形で**進めるためのガバナンス機構を定義する。

「何でもかんでも改善できてしまうと、設計DNAが侵食され、Goodhart罠が再生産される」という問題に対し、27章 (rubric governance) のワークフローを**rubric以外にも横展開**し、変更を P0-P3 の4カテゴリで分類して機械強制する。

## 正本の分担

| 領域 | 正本 | 本章で扱うこと |
|---|---|---|
| rubric固有のgovernance | `27-rubric-governance-runbook.md` | rubric以外への横展開ルール |
| script命名規約 | `28-script-execution-model.md` §4 | 命名違反のlint連携 |
| 実装状態 | `32-creator-kit-implementation-ledger.md` | 残課題の優先度との接続 |
| ポリシー本体 | `creator-kit/config/governance-policy.json` | 全カテゴリ・cooldown・blast_radius |

## 中核原則

| 原則 | 意味 |
|---|---|
| **分類→承認→記録** | 変更は必ずカテゴリ分類し、必要な承認を経て、changelogに記録する |
| **cooldown** | 同一ファイルへの連続変更を制限し、振動的改善を防ぐ |
| **blast radius lint** | 変更前に依存先への影響を機械算出し、無自覚な破壊を防ぐ |
| **bypass禁止** | P0/P1 を後追いで P2 に格下げしてバイパスすることを禁止 |

## 変更カテゴリ

正本は `creator-kit/config/governance-policy.json`。本章は概要のみ。

| カテゴリ | 意味 | 例 | ワークフロー | cooldown |
|---|---|---|---|---|
| **P0 Breaking** | 破壊的変更 | Skill name変更、Sink Contract変更、required field削除 | proposal + human承認 (team+solo) | 7日 |
| **P1 Structural** | 構造変更 | 新Skill追加、rubric改正、命名規則変更、forbidden_deps追加 | proposal + solo承認 | 3日 |
| **P2 Content** | 内容更新 | rubric項目追加、examples更新、README修正 | auto + 事後review | なし |
| **P3 Cosmetic** | 整形/typo | typo、indent、comment | auto | なし |

## ワークフロー

```
変更要求
   │
   ▼
[分類] ── governance-policy.json の change_categories を参照
   │
   ├─ P0/P1 ─→ proposal作成 ─→ human承認 ─→ cooldown確認 ─→ apply ─→ changelog記録
   │
   └─ P2/P3 ─→ blast_radius_lint ─→ auto_apply ─→ changelog記録 ─→ 事後review
```

## 機械強制機構

| 機構 | 役割 | 場所 |
|---|---|---|
| `lint-script-naming.py` | 28章命名規約違反検出 | `scripts/lint-script-naming.py` |
| `lint-forbidden-deps.py` | 禁止依存検出 | `creator-kit/scripts/lint-forbidden-deps.py` |
| `lint-manifest-contents.py` | manifest整合性検査 | `scripts/lint-manifest-contents.py` |
| `lint-dependency-direction.py` | 依存方向違反検出 | `scripts/lint-dependency-direction.py` |
| `governance-policy.json` | ポリシー正本 | `creator-kit/config/governance-policy.json` |
| pre-commit hook | カテゴリ判定+ガード | `scripts/guard-change-category.py` (TODO) |
| CI workflow | 全lint一括実行 | `.github/workflows/governance-check.yml` (TODO) |

## changelog

すべての変更は `.claude/changelog/governance-log.jsonl` に1行JSONで記録する。

### 必須フィールド

```json
{
  "timestamp": "2026-05-18T14:00:00Z",
  "category": "P1_structural",
  "target_path": "creator-kit/skills/run-elegant-review/",
  "approver": "solo_operator",
  "rationale": "収束ループ設計の追加 (正負FB両輪)",
  "rollback_plan": "convergence-policy.json削除でPhase 2ループの旧挙動に戻る"
}
```

## blast radius lint

変更前に影響範囲を機械算出する。

### 算出ルール

1. 対象ファイルを `script_refs` / `reference_refs` / `rubric_refs` から逆引きする
2. 依存している Skill を列挙
3. 同名scriptが他ディレクトリにも存在する場合は重複箇所を警告
4. `manifest.json` の kit対象なら version bump 必須を提示
5. 31章 Sink Contract 対象なら adapter 全数を検査

## 反パターン

| 反パターン | リスク |
|---|---|
| P0/P1変更をP2扱いに格下げ | バイパス成立。設計DNA侵食 |
| cooldownを `incident_fix=true` で形骸化 | 振動的改善が再発 |
| approver=auto をP0/P1に適用 | 自己採点罠 (Phase I で指摘済み) |
| blast_radius_lintをスキップして局所commit | 依存先破壊 |

## 既知の未消化違反 (命名規約)

28章 §4.1の動詞リストに反するscriptが現存する。`scripts/lint-script-naming.py --report` で全数取得可。リネームは P1_structural として段階的に実施する (`32-creator-kit-implementation-ledger.md` 残課題テーブル参照)。

| パターン | 件数概算 | 対応カテゴリ |
|---|---|---|
| `hook-*.py` (動詞リスト外) | 6 | P1 リネーム計画中 (PENDING_RENAME 暫定例外) |
| `plan-*.py` / `detect-*.py` / `assess-*.py` / `generate-*.py` / `score-*.py` / `fetch-*.py` / `check-*.py` | 8+ | P1 リネーム or 動詞リスト拡張 (要決定) |
| `adapters/dispatch.py` / `adapters/resolve_route.py` | 2 | P1 §4.4例外節への追記 or リネーム (要決定) |

## plugin 境界 governance MECE 表（Phase 0 完了後に適用）

> **前提**: 下記ルールは 34章 Phase 0（`classify_change` 実装 + 全 SKILL.md 外部参照棚卸し）完了後に適用する。Phase 0 未完了時は従来の P0-P3 ワークフローのみが有効。

plugin 移行を進める場合、plugin 境界を越える変更は追加のガバナンスを要する。以下は MECE で分類した境界ルール。

| 変更の性質 | plugin 境界 | カテゴリ | 追加ルール |
|---|---|---|---|
| plugin 内 Skill の新規追加 | 境界内 | P1_structural | 通常 P1 ワークフロー |
| plugin 内 Skill の rubric 更新 | 境界内 | P2_content | 通常 P2 ワークフロー |
| plugin 間の依存追加 | 境界をまたぐ | **P0_breaking** | plugin 境界違反として proposal 必須 |
| plugin 外 Skill からの plugin 内参照 | 境界をまたぐ | **P0_breaking** | 公式制約 e 違反。棚卸し未完了なら実施禁止 |
| plugin 名変更 | 境界定義変更 | **P0_breaking** | 全参照先の更新 + cooldown 7日 |
| plugin の新規作成 | 境界の新設 | P1_structural | 06章第17条 namespace 衝突チェック必須 |
| plugin 内 scripts の追加 | 境界内 | P1_structural | 28章 §4 命名規約 + plugin 外参照禁止 |
| plugin 外 → plugin 内移行 | 境界移動 | **P0_breaking** | 外部参照棚卸し完了の証跡必須 |

**自己適用ルール（再強調）:**
本章 33-change-governance.md を変更する場合、その変更自体が P1_structural に該当する（本章のワークフローに従う）。plugin 境界に関するルール変更は P0_breaking とみなす。これは 34章のゲート判定においても同様に適用する。

`classify_change` stub（`scripts/guard-change-category.py` の TODO(human)）が未実装である限り、plugin 境界をまたぐ変更は全て **手動で P0_breaking として扱い**、changelog への記録を必須とする。

## log-driven ref-* 改善（Meta-Harness 最小着手）

> **位置づけ**: Stanford IRIS Lab の Meta-Harness（execution traces → harness 最適化）や Hermes Agent（経験から Skill 自己生成）の問題意識に対する**ガバナンス境界**。フルパイプライン（log 収集・failure-mode 分類器・自動PR 生成・Phase 0-4 ロードマップ）は `35-meta-harness-feedback-loop.md` で扱う。本節は**ガバナンス境界（変更カテゴリ）のみ**を扱う。

### 背景

`ref-*` Skill 群（および全 Skill）の品質は、本来であれば**セッションログ上の観測**から駆動されるべきである:

- 発動すべき状況だったのに呼ばれなかった → `description` の発動条件が不足
- 呼ばれたが出力が不十分だった → 本文の判断材料が不足
- 同じ指摘を別セッションで何度もした → `gotchas` に固定すべき

しかし現状、設計書・Skill いずれにも**セッションログを根拠とした改善フロー**は存在しない（`amplified-patterns.json` は elegant-review 周回内に閉じている）。

### Goodhart 罠の予防

ログを観測対象に組み込む際、**全イベントを等価に扱うとログ映えする発動だけが最適化される**罠が発生する。これを防ぐため、観測対象の failure mode は**閉じた列挙**でなければならない。

観測対象の failure mode 列挙は `.claude/config/meta-harness-observables.json`（新設予定）で正本管理する。本節では列挙の**設計判断**を別管理（TODO(human)）として温存する。

### ルール（暫定 / Phase 0）

| 変更の種別 | カテゴリ | 追加ルール |
|---|---|---|
| `ref-*` の `description` をログ由来の根拠で変更 | **P1_structural** | rationale に観測 failure mode ID（後述の閉じた列挙の ID）を必須記載 |
| `ref-*` 本文の判断材料追記をログ由来で実施 | **P1_structural** | 同上 |
| `gotchas` セクションをログ横断観測から固定化 | **P1_structural** | 同上。最低3セッション以上での再現を rationale に記載 |
| log 観測スキーマ自体の変更 | **P0_breaking** | 観測軸が変わると全 ref-* 改善履歴の比較性が失われるため |
| 観測スキーマ未確定段階での log 由来改善 | **禁止** | 暫定的に人間判断のみで実施（rationale に「観測スキーマ未確定」明記） |

### 暫定スコープ（Phase 0）

- log 収集機構は**実装しない**。本節は「もし log 由来で改善する場合のガバナンス」だけを定める
- `.claude/config/meta-harness-observables.json` は **TODO(human) 完了後に新設**
- 35章 `meta-harness-feedback-loop.md`（フルパイプライン章）は observables 列挙確定後に着手

### 反パターン

| 反パターン | リスク |
|---|---|
| 観測対象 failure mode を無制限に拡張 | Goodhart 罠（ログ映えする発動の最適化） |
| 単一セッションの観測で `gotchas` 固定化 | 偶発的事象を恒久ルール化 |
| log 由来改善を P2_content として処理 | 自己採点罠の再来（27章の禁則と同型） |
| ログ収集機構を先に作って観測対象未確定のまま運用 | 観測軸が定まらず、改善の方向性が振動 |

## 更新ルール

1. `governance-policy.json` の `change_categories` が変わったら、本章のカテゴリ表と27章を同時に確認する
2. 新しい lint script を `machine_enforcement.linked_lints` に追加したら、本章の機械強制機構表も更新する
3. P0/P1 変更は changelog に記録した上で、本章「既知の未消化違反」セクションも更新する
4. blast radius の算出ルールが変わったら、`lint-script-naming.py` 等のlint側も同時更新する
5. 本章を変更する場合は、自分自身が P1_structural になるため、本章のワークフローに従う (自己適用ルール)
