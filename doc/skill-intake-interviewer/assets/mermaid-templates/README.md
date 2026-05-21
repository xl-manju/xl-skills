# Mermaid Templates

skill-intake-interviewer の visualizer エージェントが利用する Mermaid 12種テンプレート。
各テンプレ冒頭の `%%---` メタブロックを `select_diagram_type.js` がパースし、用途・必須変数・スコアを読み取る。

## 12種テンプレ一覧

| # | テンプレ | 用途 | 非エンジニア親和性 | 主な必須変数 |
|---|--------|-----|------------------|-----------|
| 1 | flowchart-with-gates | 承認ゲート入り業務フロー | ★★★ | start_label, step1, step2, gate_label, approve_path, reject_path, end_label |
| 2 | sequence-oauth-api | OAuth + API のやり取り | ★★ | user, app, auth_server, api_server, resource_name |
| 3 | journey-non-tech | 非エンジニア向け体験 | ★★★ | title, actor, step1〜3, score1〜3 |
| 4 | timeline-evolution | 時系列の進化・段階展開 | ★★★ | title, period1〜3, event1〜3 |
| 5 | gantt-rollout | 導入スケジュール | ★★ | title, phase1〜3 系 |
| 6 | mindmap-purpose-tree | 真の課題ツリー | ★★★ | root, branch1〜3, leaf 群 |
| 7 | er-io-contract | 入出力契約 | ★★ | input_entity, output_entity, relation_label, fields |
| 8 | architecture-system | システム構成 | ★★ | user_label, frontend_label, backend_label, db_label, external_label |
| 9 | sankey-info-flow | 情報の流れと量 | ★★ | src1, mid1, dst1, val1（最低2系統） |
| 10 | quadrant-priority | 重要度×実現性配置 | ★★★ | title, x_axis, y_axis, item1〜3 + 座標 |
| 11 | state-approval | 承認状態遷移 | ★★ | initial_state, review_state, approved_state, rejected_state |
| 12 | pie-composition | 構成比 | ★★★ | title, label1〜3, val1〜3 |

## 図種選択フローチャート

```
セクションの主目的は？
├─ 流れ／手順を示す
│   ├─ 分岐あり → flowchart-with-gates
│   ├─ アクター間のやり取り → sequence-oauth-api
│   └─ 体験・感情変化 → journey-non-tech
├─ 時間軸を示す
│   ├─ 抽象的な進化 → timeline-evolution
│   └─ 具体的な期間 → gantt-rollout
├─ 構造を示す
│   ├─ 階層・分解 → mindmap-purpose-tree
│   ├─ データ構造 → er-io-contract
│   └─ システム構成 → architecture-system
├─ 量・配分を示す
│   ├─ 流量 → sankey-info-flow
│   └─ 構成比 → pie-composition
└─ 状態・優先度を示す
    ├─ 状態遷移 → state-approval
    └─ 2軸配置 → quadrant-priority
```

## 共通ルール（マスト）

- 1図あたりノード数は **7±2 上限**
- ノードラベルは **日本語10文字以内**
- 色は意味付き（赤=注意 / 緑=完了 / 青=進行中 / 黄=判定）
- 凡例必須
- 絵文字禁止（FontAwesome のみ）
- 各図に「言いたい一言」を `%% 言いたい一言:` コメントで付記

## メタブロック仕様

```
%%---
%% template: <テンプレ名>
%% required_vars: [<必須変数のリスト>]
%% optional_vars: [<任意変数のリスト>]
%% score_formula: "<セクションスコア計算式>"
%% non_tech_friendliness: ★〜★★★
%% use_case: <ユースケース>
%%---
```

`compose_diagram.js` は `required_vars` を全て埋めないとエラーを返す。
