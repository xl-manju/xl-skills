---
id: P04
phase_number: 4
phase_name: test-design
category: テスト
prev_phase: 3
next_phase: 5
status: 未実施
gate_type: tdd-red
entities_covered: [C01, C02]
applicability:
  applicable: true
  reason: ""
---

# P04 — test-design (テスト設計・TDD Red)

## 目的
C01/C02 の `feedback_contract.criteria` (IN1-IN13/OUT1-OUT3) を test-first で確定し、未達状態 (Red) として明示する。C2 (導出→validator exit0 の受入例) と C4 (ready-set 計算の 4 ケース) を、下流 builder AI が追加質問なしで実装着手できる具体度で本 phase 本文へ内包する。C14 (新旧shape非劣化ゲート) は旧shape (13 phase 固定) と新shape (task-graph 駆動可変構成) の A/B 比較受入例を本 phase へ内包する。C15 (graph 可視化 renderer) は byte一致 render + graph 外要素非描画の受入例を、C16 (実行時契約 schema SSOT) は task-state schema 整合 + graph_hash pin 整合の受入例を本 phase へ内包する。

## 背景
goal-spec の checklist は verify_by=script/test/human の 3 種を持つ。script/test 系は本 phase で具体的なテストケース (入力/期待出力) を確定し、P05 で最小実装設計を Green にする対象とする。human 系 (C8) は C02 の意味判定プロンプト手順として P05 で設計する。

## 前提条件
- P03 の design-review が PASS している。

## ドメイン知識

### C2 受入例 (task-graph 導出 → validator exit0)
derive-task-graph.py の決定論導出ルール: 各 phase ファイルの `## 完了チェックリスト` 直下の箇条書き 1 項目を task node 候補とし、`node.phase_ref` = 当該 phase の id、`node.entity_ref` = 当該 phase frontmatter の `entities_covered` (複数なら複数 node を生成、空なら `entity_ref: null` の component 非依存タスクとする)。`parent_of` エッジは同一 phase 内の task node を当該 phase の仮想ルートノードの子として結ぶ。`depends_on` エッジは component-inventory.json の component 粒度 `depends_on` を、entity_ref が一致する task node 集合間の順序制約として反映する。`produces`/`consumes` エッジは task 完了成果物 (build_target 配下ファイル / plan 中間成果物ファイル) の生成・消費関係を表す。

本 plan 自身の一部を入力とした受入例 (満たす例):
| id | title | phase_ref | entity_ref | depends_on | produces | consumes |
|---|---|---|---|---|---|---|
| T1 | C01/C02 component-inventory 確定 | P02 | C01 | [] | A1=component-inventory.json | [] |
| T2 | derive-task-graph.py 設計確定 | P05 | C01 | [T1] | A2=derive-task-graph 設計節 | [A1] |
| T3 | R1-evaluate.md C8判定ステップ設計確定 | P05 | C02 | [T1] | A3=R1-evaluate 設計節 | [A1] |
| T4 | handoff task_graph_ref 検証設計確定 | P05 | C01 | [T2, T3] | A4=check-build-handoff 拡張設計節 | [A2, A3] |

この 4 node・4 depends_on エッジ・4 produces エッジ・4 consumes エッジに対し validate-task-graph.py を実行すると: DAG 非循環 (T1→T2→T4, T1→T3→T4 のいずれのパスも閉路を作らない)・orphan ノード 0 (全ノードが parent_of で phase ルートに、depends_on/produces/consumes のいずれかで他ノードに連結)・同一成果物の producer 一意 (A1-A4 各 1 producer)・component-inventory.json の depends_on (C02 depends_on C01) との矛盾 0 (T3/T4 の entity_ref=C02/C01 の task 間順序が component 粒度の depends_on 方向と矛盾しない) が全て検証され、**exit0** となる。満たさない例: T3 の depends_on を空 ([]) にすると、component-inventory.json の C02 depends_on C01 と矛盾するため validate-task-graph.py は inventory 矛盾を 1 件検出し exit1 となる。

### C4 受入例 (ready-set 計算・4 ケース)
上表の T1-T4 に加え、write_scope 衝突検証用の T5 (T1 にのみ depends_on、T2 と同一 write_scope) を追加する。

| id | write_scope | depends_on | state |
|---|---|---|---|
| T1 | component-inventory.json | [] | done |
| T2 | scripts/derive-task-graph.py | [T1] | pending |
| T3 | prompts/R1-evaluate.md | [T1] | pending |
| T4 | handoff-run-plugin-dev-plan.json | [T2, T3] | pending |
| T5 | scripts/derive-task-graph.py (T2 と同一) | [T1] | pending |

4 テストケースと期待 ready-set:
1. **直列チェーン**: T5 を除外し T3 も未定義とした T1(done)→T2(pending)→T4(pending, depends_on=[T2]) のみの単純チェーンで検証。期待 ready-set = `{T2}` (T4 は T2 未完了のため対象外)。
2. **ダイヤモンド依存**: T1(done)→{T2, T3}(いずれも pending・write_scope 非重複)→T4(depends_on=[T2,T3])。期待 ready-set = `{T2, T3}` (両者 write_scope 非重複のため並列投入可能・T4 は未対象)。
3. **blocked 伝播**: ケース2 の T2.state を `blocked` に変更。期待 ready-set = `{T3}` (T2 は blocked のため pending への遷移を経ず ready-set から除外され、depends_on=[T2] を持つ T4 も T2 未完了のため対象外のまま。blocked は「未完了」より強い除外状態として扱われ、T2 自身の depends_on 充足有無に関わらず ready-set に入らない)。
4. **write_scope 衝突**: T1(done)→{T2, T5} (両者 depends_on=[T1] のみ・write_scope が同一)。期待 ready-set = `{}` (T2/T5 は depends_on 条件のみでは両者 ready 相当だが write_scope が重複するため、compute-ready-set.py は衝突ペア `(T2, T5)` を明示し両者を自動並列対象から除外し、直列解決を要求する。安全側 (fail-closed) のタイブレークとして「どちらか一方を選ぶ」非決定的選択は行わない)。
5. **done だが成果物欠落 (負例)**: T1(state=done・`produces` A1=component-inventory.json)→T2(state=pending・depends_on=[T1]・`consumes` A1)。T1.state=done であっても producer 成果物 A1 の解決パスがファイルシステム上に存在しない (異常終了・部分書込・route-build-report 未生成) 場合。期待 ready-set = `{}` (T2 は depends_on 条件 T1=done を充足するが、compute-ready-set.py の `os.path.exists` による consumes 成果物実在検査が A1 欠落を検出して T2 を除外する)。この負例は「producer state==done を成果物実在の代理述語にせず artifact 実パスを独立検査する」設計 (P05 の compute-ready-set.py 節) を固定し、done だが成果物欠落の異常状態を ready-set が誤って並列投入候補にしないことを保証する。

### C13 受入例 (plan-ledger.json 検証)
`plugin-plans/<slug>/plan-ledger.json` の満たす例:
```json
{
  "schema_version": "1.0",
  "entries": [
    {"cycle_id": "20260601-task-graph", "status": "finished", "plan_dir": "plugin-plans/plugin-dev-planner/20260601-task-graph", "summary": "task-graph 第3射影の初回導入サイクル"},
    {"cycle_id": "20260705-cycle-ledger", "status": "active", "plan_dir": "plugin-plans/plugin-dev-planner/20260705-cycle-ledger", "summary": "plan 出力ディレクトリ規約の導入サイクル"}
  ]
}
```
`check-plan-ledger.py` を実行すると: cycle_id が `CYCLE_ID_RE` (`^\d{8}-[a-z0-9-]+$`) に一致・各 status が `LEDGER_STATUSES` (active/finished/superseded) に属する・active status のエントリが 1 件のみであることが確認され、**exit0** となる。満たさない例: 2 件目の `status` を `"active"` のまま 1 件目にも `"status": "active"` を設定 (同時 active 重複) すると、`check-plan-ledger.py` は「同時 active 重複」を fail-closed で検出し exit1 となる。`plan_output_dir(name, out_dir=None, base=PLAN_OUTPUT_BASE, cycle_id=None)` は `cycle_id` 省略時に現行の `plugin-plans/<plan_slug(name)>` (flat 配置) を返し、`cycle_id` 指定時のみ `plugin-plans/<plan_slug(name)>/<cycle_id>` を返す (既存呼出元は無改修で現状動作を維持)。

### C14 受入例 (A/B比較・新旧shape非劣化)
同一構想「T2: derive-task-graph.py 設計確定」を旧shape/新shapeそれぞれで生成した fixture ペア:

**旧shape fixture** (13 phase 固定・phase-05-implementation.md §5 の 1 項目):
```
- [ ] derive-task-graph.py の決定論導出ルールを実装する。
```

**新shape fixture** (task-graph 駆動・task node):
```json
{"id": "T2", "title": "derive-task-graph.py 設計確定", "phase_ref": "P05", "entity_ref": "C01",
 "depends_on": ["T1"], "produces": ["A2=derive-task-graph 設計節"], "consumes": ["A1"],
 "acceptance_criterion": "phase ファイル各 `## 完了チェックリスト` 項目 1 件を task node 候補とし node.phase_ref/entity_ref を仮想ルートへ parent_of で連結する導出ルールが疑似コードで確定し、C2 受入例 (本 phase 上表) の 4 node に対し derive-task-graph.py を実行した出力が当該テーブルと一致する"}
```

(a) 精度比較: 旧shape fixture は検証可能成果物・受入基準のいずれも文中に携帯していない (二値判定=0/1 のうち 0)。新shape fixture は `acceptance_criterion` フィールドに検証可能な成果物 (derive-task-graph.py の出力が上表と一致) を携帯する (二値判定=1)。`check-shape-non-regression.py` は旧shape §5 全項目中の携帯率 (本例では 0/1 = 0%) を基準線とし、新shape task node 集合の携帯率がこれを下回らないことを機械計測する。満たす例: 新shape 携帯率 1/1 = 100% ≥ 0%。満たさない例: 新shape task node から `acceptance_criterion` を削ると携帯率 0/1 = 0% となり旧shape基準線と同値のため「同等」は満たすが、意図的に基準線未満 (負値) を作る欠陥 fixture (例: acceptance_criterion はあるが検証不能な自然文 "がんばる" のみ) は携帯率カウントから除外され 0/1 = 0% 未満相当として exit1。
(c) 再現性比較: 同一 goal-spec/component-inventory.json を入力に `derive-task-graph.py` を 2 回連続実行し、出力 task-graph.json が byte 一致 (ノード集合 {T1,T2,T3,T4}・エッジ集合が両実行で完全同一) することを検証する。満たさない例: 2 回目の実行で dict 反復順序に依存した非決定的な key 順が出力に混入し 1 バイトでも異なれば `check-shape-non-regression.py` は再現性軸で exit1。
(b) 品質比較 (C02 genuine 判定・script では計測不可のため参考記載): fork evaluator が上記 2 fixture を A/B 比較し、新shape fixture の `acceptance_criterion` が「derive-task-graph.py の出力が具体的にどのテーブルと一致すべきか」という下流 builder AI の追加質問を要さない事前解決済み判断を内包しているか、旧shape fixture の抽象記述と比べ実効性が劣化していないかを genuine 判定する (plan-findings.json の bucket `shape-ab-comparison` へ計上)。

**block/fallback**: (a)(c) いずれかが exit1、または (b) で C02 が劣化ありと genuine 判定した場合、shape_marker は `task-graph-derived` を採用せず `fixed-13-phase` へ fallback する (C10⇔C14 相互参照)。

### C15 受入例 (byte一致 render + graph 外要素非描画)
C2 節の T1-T4 task-graph (state は C4 節の表: T1=done, T2/T3/T4=pending) を入力に `render-task-graph-mermaid.py` を実行すると、node id・エッジ種別を C11 の canonical 順序 (安定 key 順) のまま走査し、以下の mermaid を決定論生成する:
```
graph TD
    classDef pending fill:#eee
    classDef running fill:#bbf
    classDef done fill:#bfb
    classDef blocked fill:#fbb
    T1["C01/C02 component-inventory 確定"]:::done
    T2["derive-task-graph.py 設計確定"]:::pending
    T3["R1-evaluate.md C8判定ステップ設計確定"]:::pending
    T4["handoff task_graph_ref 検証設計確定"]:::pending
    T1 --> T2
    T1 --> T3
    T2 ==> T4
    T3 ==> T4
```
線種区別: `parent_of`=細実線矢印 (`-->`)、`depends_on`=太実線矢印 (`==>`)、`produces`=破線矢印 (`-.->`)、`consumes`=円形終端 (`--o`) の 4 種を個別に割り当てる (本例は depends_on のみのため `-->`/`==>` の 2 種が出現)。クリティカルパス強調: `depends_on` のみを辺とする最長路 (T1→T2→T4 と T1→T3→T4 はいずれも長さ 2 で tie。tie 時は node id の辞書順で先行する経路 T1→T2→T4 を採用) を `linkStyle` で太線・強調色に上書きする。

満たす例 (byte一致): 同一 task-graph.json に対し `render-task-graph-mermaid.py` を 2 回連続実行した出力が byte 一致する (node/edge の走査順が C11 canonical 順序に固定されているため非決定的な dict 反復順の混入がない)。
満たさない例 (graph 外要素非描画): 出力 mermaid からノード id 集合を抽出し、入力 graph の `nodes[].id` 集合と set 一致することを検証する。renderer が graph に存在しない装飾ノード・ラベル文言 (node.title 以外の独自解釈テキスト) を追加すると、抽出集合が graph の id 集合と不一致になり検査は fail-closed で検出する。

### C16 受入例 (task-state schema 整合 + graph_hash pin 整合)
`task-state.schema.json` 準拠の満たす例:
```json
{
  "schema_version": "1.0",
  "graph_hash": "sha256:3f9a...",
  "nodes": [
    {"id": "T1", "state": "done"},
    {"id": "T2", "state": "running", "started_at": "2026-07-05T10:00:00Z", "lease_expires_at": "2026-07-05T10:30:00Z"}
  ]
}
```
1. **schema 整合 (満たす例/満たさない例)**: 満たす例=上記 fixture (schema_version が文字列・graph_hash が `sha256:` 接頭+16進文字列・各 node.state が `TASK_NODE_STATES` 値域内・`state:"running"` の node が `started_at`/`lease_expires_at` を両方携帯) を `check-task-state-schema.py` に通すと exit0。満たさない例=`state:"running"` の T2 から `started_at` を欠落させると、lease 不整合 (孤児 running を機械判別できない) として fail-closed で検出し exit1。
2. **graph_hash pin 整合 (満たす例/満たさない例)**: 満たす例=`task-state.json.graph_hash` が現在の `task-graph.json` の canonical bytes から C11 のロジックで再計算した hash と一致する場合 exit0。満たさない例=discovered-task 受理で task-graph.json にノードが追加された後も `task-state.json.graph_hash` が更新されないまま残ると、再計算 hash との不一致を `check-task-state-schema.py` の pin 検査が fail-closed で検出し exit1 (反映は次周回のみという constraints を機械強制する)。

## 成果物
- feedback_contract.criteria IN1-IN13 (inner, verify_by=script) / OUT1-OUT3 (outer, verify_by=test) の確定 (component-inventory.json に反映済み)。
- 上記 C2/C4/C13/C14/C15/C16 の受入例テーブル・fixture (本 phase 本文が正本)。

## スコープ外
- 実装コード (P05 で設計プローズとして確定し、L4 build で実コード化)。

## 完了チェックリスト
- [ ] C2 の受入例 (満たす例/満たさない例) が具体的な node/edge データで内包されている。
- [ ] C4 の 4 テストケース (直列チェーン/ダイヤモンド/blocked伝播/write_scope衝突) + 「done だが成果物欠落」負例 (os.path.exists による consumes 成果物実在検査) が期待 ready-set 付きで内包されている。
- [ ] IN1-IN13/OUT1-OUT3 が component-inventory.json の C01.feedback_contract.criteria と一致する。
- [ ] C13 の plan-ledger.json fixture (満たす例/満たさない例) と `plan_output_dir()` の cycle_id 省略時後方互換動作が具体的に内包されている。
- [ ] C14 の A/B比較受入例 (旧shape fixture/新shape fixture) が (a)精度携帯率・(b)品質genuine判定・(c)再現性byte一致の3軸それぞれで満たす例/満たさない例付きで内包され、block/fallback 条件が明記されている。
- [ ] C15 の byte一致 render 例と graph 外要素非描画検査 (node id 集合の set 一致) が満たす例/満たさない例付きで内包されている。
- [ ] C16 の task-state schema 整合例と graph_hash pin 整合例 (満たす例/満たさない例) が具体的な fixture 付きで内包されている。

### 受入例 (満たす例 / 満たさない例)
- 満たす例: 上記の C2/C4/C13/C14/C15/C16 テーブル・fixture の通り、具体的な node id・write_scope・depends_on・期待 ready-set・cycle_id・status・acceptance_criterion 携帯率・graph_hash・lease フィールドが数値/文字列で確定している。
- 満たさない例: 「ready-set 計算のテストケースを複数用意する」とだけ記され、具体的な期待値が未確定のまま P05 へ進む。

### 事前解決済み判断
- 分岐点: write_scope 衝突時に片方を自動選択 (非決定的タイブレーク) するか、両者除外し直列解決を要求するか → 判断: 両者除外 (fail-closed。非決定的選択は再現性 (constraints: 毎回同一の最適構造が構築される要求) と矛盾するため)。

## 参照情報
- `plugin-plans/plugin-dev-planner/component-inventory.json` (C01.feedback_contract.criteria)。
- P02 (design)。
- 後続 P05 (implementation)。
