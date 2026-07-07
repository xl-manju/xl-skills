# task-graph 契約 (第3の射影・producer=plugin-dev-planner 所有)

plan 成果物の 3 射影のうち第3。13 phase ファイル (人間可読ライフサイクル軸) と component-inventory.json
(機械 SSOT・実体軸) に加え、タスク単位の依存エッジ・成果物連結・並列実行可能性を型付けした
**task-graph** を導入する。本 skill (producer) が schema/導出/検証/ready-set 計算/graph_hash 算出を
所有し、L4 実行系 (consumer=harness-creator) はそれを消費するのみで再実装しない (SSOT)。

## schema (schemas/・producer 所有 SSOT)
| schema | 役割 |
|---|---|
| task-graph.schema.json | nodes(id/title/phase_ref/entity_ref/state/write_scope) + edges(parent_of/depends_on/produces/consumes)。`blocks` は独立宣言禁止の派生ビューゆえ edge type に非列挙。永続 state は pending/running/done/blocked の4値で、ready は compute-ready-set.py が返す computed-only の一時値として扱う |
| discovered-task.schema.json | build 中発見タスク (E4)。discovering_task_id/reason/discovered_at_artifact/proposed_node/change_level(additive\|structural)。provenance.route_id は optional additive |
| handoff-notes.schema.json | went_well/friction_points/downstream_watchouts。各 maxItems 3 / maxLength 200 の**単一正本** (task-state の handoff_notes が $ref する) |
| plan-ledger.schema.json | cycle 台帳 (cycle_id/status/plan_dir/summary)。status=active/finished/superseded |
| task-state.schema.json | runtime state (C16)。永続 state 4 値 (ready 除外)。graph_hash pin・running→lease 必須・blocked→blocked_reason(origin-failure\|propagated) 必須。node は additionalProperties:true (consumer の route_report/handoff_notes 拡張を許容) |

## edge 方向の意味論 (from/to の読み方)
edge の `from`/`to` は type ごとに意味が異なる。初見の誤読 (特に depends_on の向き) を防ぐため固定表とする:

| type | from | to | 読み方 |
|---|---|---|---|
| depends_on | 待つ側 task | 待たれる側 task | **from が to の done を待つ** (to が先行) |
| parent_of | 親 (phase 仮想ルート) | 子 task | from が親・to が子 |
| produces | producer task | artifact id | **from が to (artifact) を生産する** |
| consumes | consumer task | artifact id | **from が to (artifact) を消費する** (実在検査対象) |

## write_scope の 2 用法
`write_scope` は並列衝突判定キーとして全 node 必須だが、node 種別で意味が異なる:

1. **entity 紐づき task node** = **排他書込パス** (component-inventory の build_target)。同一パスを持つ候補は
   ready-set で直列化される (単一 winner)。
2. **checkpoint node** (entity_ref=null の task・phase 仮想ルート) = **自 node id の擬似 scope**。実パスを
   書かないため node id を scope に流用し、定義上他 node と衝突しない (一意)。

## scripts (scripts/)
- **derive-task-graph.py**: 13 phase §5 チェックリスト項目 + inventory → task-graph.json を**決定論導出**。`canonicalize()` が唯一の正準 writer (nodes=id 昇順 / edges=(type,from,to) 昇順 / 固定 key 順)。`graph_hash(graph)="sha256:"+sha256(canonical_json)`。
  - **phase ライフサイクル順序 edge**: 「1 task 完了 → done 記述 → それが次 task の発火条件」という event 駆動チェーンを graph 構造で保証するため、component 依存 (inventory) とは別に phase 順序 depends_on を焼く: (1) phase marker (root) は自 phase の全 leaf に depends_on (marker done = phase 完了の集約点。parent_of と同じ marker→leaf 向きゆえ DAG 閉路を作らない)。(2) 各 phase の leaf は直前 phase marker に depends_on (前 phase の全 leaf done → marker ready→done → 次 phase leaf ready の直列チェーン)。これで後段 phase (final-review 等) が実装 phase 完了前に ready 化する順序逆転を封じる。compute-ready-set は readiness を depends_on のみで判定し parent_of を無視するため marker↔leaf の parent_of は readiness に干渉しない。
- **validate-task-graph.py**: DAG 非循環 / orphan 0 / producer 一意 / inventory depends_on 実現性 / consumes producer 実在 / 非正準拒否 (canonicalize 再適用と不一致)。
- **compute-ready-set.py**: depends_on 完了 + consumes 成果物実在 (`os.path.exists` で producer state==done の代理述語にせず独立検査) の ready-set を決定論計算。候補内 write_scope 衝突は「fail-closed 全除外」ではなく**決定論 tie-break (id 昇順) で単一 winner のみ ready・残りは deferred** として次周回へ持ち越す (直列化。winner done 化で scope が解放され deferred が昇格するため ready 0 件デッドロックを構造的に排除。非決定的タイブレークは禁止のまま)。deferred は winner との衝突ペアを `conflicts` に記録する。
- **accept-discovered-task.py**: additive は即時反映 (canonicalize)、structural は `--approved` 必須の二段受理。`--form` 単発受理に加え **`--inbox <dir>` で discovered-task inbox を一括ドレイン** (外ループ帰路 FC-6)。ドレインは filename 昇順で走査し additive を累積受理・各 form へ `status`(accepted/rejected)・`resulting_graph_hash` を書き戻す (structural 未承認は pending 据置)。
- **apply-handoff-notes.py**: 直接 depends_on/consumes 先行タスクへ有界伝播 + advisory/actionable 分類。
- **check-plan-ledger.py** / **migrate-plan-layout.py**: cycle 台帳検証 (同時 active 高々1) / flat→cycle-id 配置移行。
- **check-shape-non-regression.py**: 新旧 shape 非劣化 (受入基準携帯率 + byte一致再現性)。C14(b) 品質 genuine 判定は assign-plugin-plan-evaluator。
- **render-task-graph-mermaid.py**: canonical 順序で mermaid 導出 (byte一致・graph 外要素非描画)。
- **check-task-state-schema.py**: task-state schema 整合 + graph_hash pin 整合。

## consumer 向け安定 CLI 契約 (FC-4/FC-5・破壊禁止)
consumer=harness-creator の L4 実行系は build 開始時の graph_hash pin を **read-only サブコマンドのみ**で取得する
(canonicalize()/graph_hash() を直接 import・subprocess 消費しない):

```
derive-task-graph.py --print-graph-hash <task-graph.json>
  argv:   --print-graph-hash <path>
  stdout: sha256:<64hex>\n
  exit:   0=成功 / 1=graph 不正で hash 算出不能 / 2=引数不足・IO エラー
```

`compute-ready-set.py` も consumer が subprocess 消費する (固定パス起動・stdout schema):

```
compute-ready-set.py <plan_dir> [--repo-root <path>]
  argv:   <plan_dir> 位置引数 (固定・<plan_dir>/task-graph.json を読む) + optional --repo-root
  stdout: {"ready_set":[id,...],"conflicts":[[id,id],...]} JSON (ready_set は sorted 決定論)
  exit:   0=OK (ready 空でも正常) / 1=読込不能 / 2=usage error
```

consumes 成果物実在検査における**相対パス write_scope の解決基点は `--repo-root` (未指定時 cwd)**。
consumer は起動 cwd への依存 (cwd anchoring) を避けるため `--repo-root` に repo root を明示指定して
呼び出す (絶対パス write_scope は `--repo-root` の影響を受けない)。これらの
argv 形状 / stdout schema / exit codes を破壊すると consumer が沈黙破綻するため安定契約として固定する
(optional flag の追加は additive・既定挙動不変で許容)。

## 所有 / 書込分離 (C12/C16 と同型)
- **schema・graph_hash 算出規約・pin 検査ロジック**の所有 = producer (本 skill)。
- **task-state.json への実書込** (state 遷移・lease 更新・blocked_reason 記録・graph_hash pin) = consumer (harness-creator) が**単独 writer**。
- consumer は `blocked_reason` を第一級 schema field へ直接書き込む (notes.reason や advisory handoff_notes に混ぜない・状態理由と advisory を分離)。
- discovered-task の反映は producer が次の `--mode update` 周回で graph を更新する一方向 writer 契約 (consumer は emit のみ・graph 本体を直接編集しない)。

## 内ループ / 外ループ (2 ループ構造・改善還流)

task-graph の実行は 2 つの入れ子ループで駆動する。producer=本 skill は**外ループの改善器**、consumer=harness-creator は**内ループの実行器**を所有し、両者は 2 つの機構的ジョイントで縫合される。

- **内ループ (build-execution loop・consumer 所有)**: ready-set 計算 → 並列 dispatch → state write-back → 成果物注入を `ready_batch` が空になるまで反復し、現 task-graph を完了へ駆動する。1 周=1 dispatch batch。
- **外ループ (spec-improvement loop・producer↔consumer 横断)**: 現 task-graph が不十分 (build 中に plan 未網羅タスクを発見) なとき、consumer が discovered-task を emit → 完了ゲートで block → **producer が `--mode update --discovered-inbox` でドレインし task-graph を改善** → 新 `graph_hash` → consumer が改善済 graph を再消費。1 周=1 spec 改善。

**2 つのジョイント (両ループの結合点)**:
1. **完了ゲート = C08 (consumer)**: 未処理 discovered-task (status が accepted/rejected/superseded 以外) が inbox に 1 件でも残る間、consumer は build を completed にできない。これが内ループの完了を外ループの決着まで強制的に遅延させる縫合点。
2. **再入トリガ = graph_hash (provenance-gated)**: producer のドレインで graph が変わると canonical `graph_hash` が変化し、ドレインは accepted form の `resulting_graph_hash` に最終 graph_hash を焼く。consumer の pin 検証 (C07) は不一致検知時、現 graph の hash が accepted form の `resulting_graph_hash` と一致する場合のみ正当な再入として pin を再設定 (`repinned`)、一致しない差替えは不正混入として `mismatch` 拒否する。`resulting_graph_hash` を認可述語にして「不正改変の拒否」と「正当改善の受容」を両立させる。

一巡: consumer emit → consumer block(C08) → **producer drain(`--discovered-inbox`)** → consumer 再消費。stall (ready_batch 空だが未完了残存) のうち仕様不備由来のものは consumer が structural discovered-task として emit し、この単一ジョイントへ合流させる (外ループのトリガを discovered-task inbox に一本化)。

## cycle_id 携帯 (C13)
handoff トップレベル `cycle_id: str|None` (additive・null=flat 後方互換)。consumer はレイアウト判断に
必要な cycle-id を本フィールドから読み、plan_dir パス末尾解析は禁止 (二重実装防止)。goal-spec↔handoff の
cycle_id parity は check-build-handoff.py が検証する。
