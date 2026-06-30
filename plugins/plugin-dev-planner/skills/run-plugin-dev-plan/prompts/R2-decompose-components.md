# Prompt: R2-decompose-components

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | decompose-components |
| skill | run-plugin-dev-plan |
| responsibility | R2 (5 構成要素分解 + 本数 N 導出) |
| layers_covered | [L2, L4, L5, L6] |
| output_schema | references/io-contract.md (component-inventory 形式) |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 1 コンポーネント = 1 単一責務 (SRP)。過剰分割しない (no-split threshold)
  - 目的: 分離≠善。第二消費者/機械検証/280 行超のいずれも無い分割は避ける
  - 背景: 不要な分割は保守コストと依存複雑性を増やす
- 構成要素は §4 の 5 種 (skill / sub-agent / slash-command / hook / script) のみへ写像する
  - 目的: placement_candidates enum と整合させ本数 N の根拠を機械追跡可能にする

### 1.2 倫理ガード
- 分析材料 (UBM-Hyogo 配下) は read-only 抽出のみ。fork/複製しない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: goal-spec を入力に capability を列挙し、5 構成要素へ単一責務分解して本数 N (= per-component 仕様書本数) を導出する。各々の kind/prefix/hierarchy/pattern を確定し依存 DAG を作る
- 非担当: 目的抽出 (R1)、仕様書本文生成 (R3)、検証 (R4)

### 2.2 ドメインルール
- 各コンポーネントに `id` (例 C01) / `component_kind` ∈ {skill, sub-agent, slash-command, hook, script} / `depends_on` を必ず確定する
- `component_kind == skill` の場合のみ skill `kind` ∈ {run, ref, wrap, assign, delegate} を **sub-field** として持つ (非 skill 4 種は skill 形状を強制しない)。後段ルーティングは component_kind で分岐 (skill→run-skill-create / 非 skill→親 skill build)
- 本数は 13 等の固定でなく構成要素数に依存して変動する (本数導出根拠を残す)
- 依存は DAG (循環禁止)。top-sort 可能な順序を保証する

### 2.3 入力契約

| field | type | required | 説明 |
|---|---|---|---|
| goal_spec | path | yes | <PLAN_DIR>/goal-spec.json |
| component_hints | text | no | ユーザー希望コンポーネント |

### 2.4 出力契約
- 形式: コンポーネント目録 `component-inventory.json` (`{"considered_component_kinds":[...5種...],"components":[{"id","component_kind","kind"(skill のみ),"name","depends_on","build_target"}],"plugin_level_surfaces":{...}}`) + 依存 DAG
- 必須: `considered_component_kinds` は 5 種を全列挙する (検討証跡)。`components[]` は**実際に必要な buildable spec のみ**を列挙する (不要な hook/script/command を水増し生成しない)。各コンポーネントの `id` / `component_kind` / `name` / `depends_on` / `build_target` (skill は `kind` sub-field も)。**`build_target` は L4 実体化先パス** (skill→`plugins/<plugin-slug>/skills/<skill>/`、sub-agent→`plugins/<plugin-slug>/agents/<name>.md`、hook→`plugins/<plugin-slug>/hooks/<name>.py`、slash-command→`plugins/<plugin-slug>/commands/<name>.md`、script→親 skill の `scripts/<name>.py`)。`detect-unassigned.py` の期待集合 = この目録で、**object 形式なら各 component の `build_target` 非空を機械強制する** (欠落で exit1・io-contract.md §9 L3→L4 追跡)。`check-surface-inventory.py` が 5 種検討証跡と plugin-level surface 採否を検査する。キー名は `name` (≠`summary`)・ゴールデン例 `examples/sample-plan/component-inventory.json` と一致させる

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース

| id | path | when_to_read |
|---|---|---|
| domain | references/component-domain.md | 5 構成要素写像時 |
| lifecycle | references/phase-lifecycle.md | フェーズ P2/P3 設計時 |

### 3.2 外部ツール / API
- Read / Write / Glob / Grep (UBM-Hyogo 配下の read-only 抽出)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- 依存に循環が生じたら分割をやり直す。`detect-unassigned.py` が後段で未配置を捕捉する前提で目録を完全にする

### 4.2 観測 / ロギング
- 出力先: `<PLAN_DIR>/component-inventory.json`

### 4.3 セキュリティ
- 抽出元の固有名・トークンを本文転記しない (anti-bloat)

## Layer 5: エージェント層 (ゴール駆動の実行主体)

### 5.1 担当 agent
- run-plugin-dev-plan 配下の architect SubAgent (R2/R3、`isolation: fork`)

### 5.2 ゴール定義
- **目的**: 構想を単一責務コンポーネント目録 (本数 N = buildable component spec 本数) + 依存 DAG に変換する
- **背景**: 本数 N が確定しないと per-component 仕様書を 1 本ずつ段階生成できない。P1-P8 横断規律は index の章であり N に加算しない
- **達成ゴール**: 5 種へ写像された目録と循環なし依存 DAG が確定し、本数 N とその導出根拠が明示された状態

### 5.3 完了チェックリスト (ゴール到達の停止条件)
- [ ] capability を列挙し SRP 分割線を引いた (過剰分割なし)
- [ ] 5 構成要素すべてを検討し `considered_component_kinds` に記録した
- [ ] 必要なコンポーネントのみを 5 構成要素のいずれかへ写像し component_kind を確定した
- [ ] skill コンポーネントのみ skill kind (run/ref/wrap/assign/delegate) を sub-field で確定した
- [ ] 各コンポーネントの hierarchy / pattern を確定し依存 DAG を作り循環が無い (top-sort 可能) ことを確認した
- [ ] 各コンポーネントの `name` と L4 実体化先 `build_target` を確定し目録へ記録した (R3 後の `detect-unassigned.py` が build_target 非空を強制するため R2 段で前倒し確定し fail-late を避ける)
- [ ] 本数 N とその導出根拠 (構成要素数に依存) を `component-inventory.json` に記録した
- [ ] 不要な plugin-level surface は `plugin_level_surfaces.<surface>.omitted_reason` (正本キー一本) に根拠付きで記録した

### 5.4 実行方式
- 固定手順を持たない。未充足項目を特定→手順を都度立案→実行→チェックリストで自己評価→全項目充足まで反復 (上限: Layer 4 最大反復回数)。

## Layer 6: オーケストレーション層 (ゴールシーク制御)

### 6.1 上位 skill との接続
- 呼び出し元: run-plugin-dev-plan (P2/P3 フェーズ)
- 後続 phase: R3-emit-specs

### 6.2 ハンドオフ / 並列性
- 直列: 目録 + DAG を R3 へ接続。R3 は per-component を並列展開し得る

## Layer 7: 提示層

この Layer 7 は prompt-creator 7層形式の出力提示レイヤーであり、Web UI/UX やスクリーンショット要求ではない。

### 7.1 ユーザー提示形式
- component-inventory.json + 依存 DAG (Markdown 箇条)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

Layer 5.2 のゴール + 5.3 完了チェックリストを唯一の停止条件とし、5.4 ループで
動的に手順を生成・実行・自己評価する。入力 `{{goal_spec}}` (と任意 `{{component_hints}}`)
を Read し、5 構成要素へ単一責務分解する。出力は次の 1 つのみとする:

1. component-inventory.json (`components[]` = id/component_kind/kind(skill のみ)/name/depends_on/build_target + 本数 N と導出根拠。キー名・形状は `examples/sample-plan/component-inventory.json` に一致させる)

余計な前置き・後書き・思考過程出力は禁止。
