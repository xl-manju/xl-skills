# CONVENTIONS

このファイルは、リポジトリ直下で共有する運用規約を記録する。

## 三層モデル

`xl-skills` では、plugin 移行中のファイル責務を層 A / 層 B / 層 C に分ける。以後の変更は、まずこの三層モデルで所属を判定してから実施する。

### 層定義

| 層 | 役割 | 主なパス | 判定基準 |
|---|---|---|---|
| 層 A: 配布対象 plugin 本体 | marketplace で配布する plugin の正本。配布先でも単独で動作する必要がある | `plugins/<name>/`, 将来の `plugins/<name>/.claude-plugin/plugin.json`, `plugins/<name>/skills/`, `plugins/<name>/agents/`, `plugins/<name>/commands/`, `plugins/<name>/hooks/`, `plugins/<name>/scripts/`, `plugins/<name>/references/` | 他プロジェクトへ持って行きたい再利用単位か |
| 層 B: プロジェクト固有運用 | このリポジトリの設計、評価、派生生成、ログ、CI、運用補助 | `.claude/`, `.github/`, `doc/`, `eval-log/`, `scripts/`, `references/`, `CONVENTIONS.md`, `README.md`, `Makefile` | このリポジトリでだけ成立する運用物か |
| 層 C: 移行中 drift | Phase 0-2 の間だけ残す旧構造・暫定領域。Phase 4 で撤廃対象 | `creator-kit/`, 旧構造由来のルート `scripts/`, 旧構造由来のルート `references/` | まだ A/B に仕分け切れていない旧構造か |

層 C は恒久的な置き場ではない。層 C に新規責務を追加する場合は、移行先が層 A か層 B かを同時に記録する。

#### 層 A-internal: リポジトリ実体だが marketplace 非配布

層 A のうち `distributable: false` を宣言した plugin を **層 A-internal** と呼ぶ。リポジトリには実体として存在し、lint / CI / 社内利用の対象になるが、**marketplace 一覧・配布 bundle には現れず `/plugin install <name>@xl-skills` の対象外**である。現時点では `plugins/skill-creator/` と `plugins/prompt-creator/` (Skill / plugin を量産するための社内開発基盤) が該当し、利用は repo を clone した環境に限る (`.claude/` symlink 経由)。

この区別が示すのは **「配布 ≠ リポジトリ存在」** という原則である。ここでいう「配布」とは `.claude-plugin/marketplace.json` / `.claude-plugin/bundles.json` への登録のみを指す。公開 git repo 上にソースが物理存在することは配布とは独立であり、`distributable: false` の plugin もソースは repo に残り clone 開発に用いる。層 A-internal は「リポジトリには在るが (両 JSON へ登録しないため) 配布しない」状態を指す。現状の層 A-internal は `skill-creator` / `prompt-creator` が該当する (= `distributable: false` を宣言した plugin。固有名は `scripts/validate-plugin-completeness.py` の `NEVER_DISTRIBUTE` でロックされ、フラグが漂流しても fail-closed で再配布を阻止する)。件数を断定しないのは、層 A-internal が増減しても本節が silent に陳腐化しないためである。

### パス列挙

- `plugins/<name>/`: 層 A。plugin として配布する正本。ただし `distributable: false` を宣言した plugin は層 A-internal (リポジトリ実体・lint 対象だが marketplace 非配布。skill-creator / prompt-creator が該当)。
- `.claude/`: 層 B。開発環境で使う symlink、自動生成 settings、ローカル運用情報。
- `doc/`: 層 B。設計書とタスク仕様書の正本。
- `eval-log/`: 層 B。検証ログ、レビュー承認、移行証跡。
- `scripts/`: 層 B。ただし旧構造からの未仕分け script は層 C として扱い、Phase 4 までに A/B へ移すか除却する。
- `references/`: 層 B。ただし旧構造からの未仕分け reference は層 C として扱い、Phase 4 までに A/B へ移すか除却する。
- `creator-kit/`: 層 C。試験移行前の暫定正本であり、最終形では `plugins/skill-creator/` に吸収する。

### 参照規則

| 参照元 \ 参照先 | 層 A | 層 B | 層 C |
|---|---|---|---|
| 層 A | 同一 plugin 内のみ許容 | 禁止 | 禁止 |
| 層 B | 許容。派生 symlink や生成処理から参照してよい | 許容 | 許容 |
| 層 C | 許容 | 許容 | 許容。ただし Phase 0-2 の時限扱い |

必須規則:

- A -> A: 同一 `plugins/<name>/` 内の参照のみ許容する。別 plugin への直接参照は plugin 間依存 governance が整うまで禁止する。
- A -> B: 禁止する。plugin 配布物は `.claude/`, `doc/`, `eval-log/`, ルート `scripts/`, ルート `references/` に依存してはならない。
- B -> A: 許容する。`.claude/` 派生生成、CI、検証、設計書は `plugins/<name>/` を参照してよい。
- C -> 任意: 許容する。ただし移行期間中だけの暫定参照であり、Phase 4 までに撤廃または A/B へ分類する。

Phase 0-2 では A -> B 禁止に例外を作らない。例外が必要な場合は、設計書 33 章の change governance に従い P1_structural proposal として扱う。

### 配布判定フローチャート

```text
変更対象ファイル X
   |
   +-- 他プロジェクトに持って行きたい? -- Yes --> 層 A (plugins/)
   |                                             |
   |                                      Plugin 名は決まっている?
   |                                         +-- Yes --> plugins/<name>/
   |                                         +-- No  --> タスク 08 で確定
   |
   +-- No
       |
       +-- このリポジトリの運用ログ/設計書? -- Yes --> 層 B
       |
       +-- 旧構造 (creator-kit/, scripts/, references/)? -- Yes --> 層 C (Phase 4 で除却)
       |
       +-- どれにも該当しない --> P1_structural proposal で分類を先に決める
```

### 運用原則

1. 新規 plugin 配布物は層 A に置く。
2. このリポジトリ固有の設計、検証、ログ、生成補助は層 B に置く。
3. 層 C は移行中 drift の観測場所としてのみ使い、恒久仕様にしない。
4. 層 A から層 B/C への参照を見つけた場合は、配布前 gate で失敗扱いにする。
5. 層 C の残存は Phase 4 で撤廃対象として棚卸しする。

## Phase 2 本番 (発効待ち: 層C 退役)

> **発効条件**: 本セクションは `doc/migration/phase2/07-creator-kit-removal.md` (タスク 07) の DoD 全 PASS をもって発効する。タスク 07 完了前にこのセクションの内容を運用に適用してはならない。旧三層定義 (層 A / 層 B / 層 C, 空白付き表記) は削除せず、本セクションは発効待ち差分として追記する。

| 項目 | 内容 |
|---|---|
| 適用条件 | `doc/migration/phase2/07-creator-kit-removal.md` DoD 全 PASS |
| 層C 退役後の正本 | `plugins/<name>/` (層A) のみ |
| 層B との関係 | 層B (= `.claude/settings.json` user セクション等) は不変 |
| 縮退後の参照ルール | 層A 内の plugin 間参照は禁止。層B から層A は symlink 経由でのみ参照 |

### 二層モデル縮退後の責務境界 (Phase 2 本番後)

| 層 | 配置 | 責務 |
|---|---|---|
| 層A | `plugins/<name>/` | 配布対象。skill / agent / command / hook の正本 |
| 層B | `.claude/` のうち手編集領域 | プロジェクト固有運用。settings.json user セクション、ローカル CLAUDE.md など |

### 層C 退役 (retire) チェックリスト

- [ ] `creator-kit/` が物理削除済 (`test ! -d creator-kit`)
- [ ] `git log -- creator-kit/` が削除 commit を含む
- [ ] CONVENTIONS.md の旧「層 C」(空白付き) 記述は本セクションへの参照に置換 (07 発効後)

### 縮退後の plugin 一覧 (partition-plan.json v1.1 由来)

層A 配下に並ぶ plugin 7 件 + 既存試験移行済 1 件:

- `plugins/skill-creator/` (試験移行済)
- `plugins/skill-governance-adapters/`
- `plugins/skill-governance-hooks/`
- `plugins/skill-governance-lint/`
- `plugins/skill-governance-migration/`
- `plugins/skill-governance-secrets/`
- `plugins/skill-governance-config/`
- `plugins/skill-governance-automation/`
