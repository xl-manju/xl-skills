---
name: mermaid-visualization-guide
description: 20種図表（Mermaid 12 + 独自 8）の選択ルールとスコア式
type: reference
---

# 図解選択ガイド（20種カタログ）

`scripts/select_diagram_type.js` がこの表のスコア式に基づき各セクションへ最適な図を割り当てる。

## カタログ全体

| # | 種別 | カテゴリ | 非エンジニア度 | 主用途 |
|---|----|------|---|------|
| 1 | flowchart | Mermaid | ★3 | プロセス・分岐 |
| 2 | sequence | Mermaid | ★1 | API呼び出し順 |
| 3 | state | Mermaid | ★2 | 状態遷移 |
| 4 | class | Mermaid | ★1 | データ構造 |
| 5 | er | Mermaid | ★1 | DB関係 |
| 6 | gantt | Mermaid | ★3 | スケジュール |
| 7 | pie | Mermaid | ★3 | 構成比 |
| 8 | mindmap | Mermaid | ★3 | アイデア展開 |
| 9 | timeline | Mermaid | ★3 | 時系列イベント |
| 10 | journey | Mermaid | ★3 | ユーザー体験 |
| 11 | quadrant | Mermaid | ★2 | 二軸分類 |
| 12 | sankey | Mermaid | ★2 | 量の流れ |
| 13 | numbered-steps | 独自SVG | ★3 | 手順1〜N |
| 14 | persona-card | 独自SVG | ★3 | 人物像 |
| 15 | before-after | 独自SVG | ★3 | 改善対比 |
| 16 | comparison-table | 独自SVG | ★3 | 選択肢比較 |
| 17 | traffic-light | 独自SVG | ★3 | 状態判定 |
| 18 | progress-bar | 独自SVG | ★3 | 進捗％ |
| 19 | icon-grid | 独自SVG | ★3 | 連携先一覧 |
| 20 | sankey-aux | 独自SVG | ★3 | 量の流れ補助 |

★1: エンジニア向け（非技術者には自動代替）
★2: 中級向け
★3: 非エンジニアOK

## 選択フロー

```
セクション内容
  ├─ プロセス・順序 → flowchart / numbered-steps
  ├─ API/呼出順序   → sequence（★1なので非技術者には numbered-steps）
  ├─ 状態遷移       → state / traffic-light
  ├─ データ構造     → class（非技術者は表で代替）
  ├─ 関係性         → er / icon-grid
  ├─ 時間スケジュール → gantt / timeline
  ├─ 構成比         → pie / progress-bar
  ├─ アイデア展開   → mindmap
  ├─ ユーザー体験   → journey / persona-card
  ├─ 二軸分類       → quadrant / comparison-table
  ├─ 量の流れ       → sankey / sankey-aux
  └─ 改善前後       → before-after
```

## スコア式

```
score(diagram_type, section) =
    fit_purpose * 0.40    // 用途適合
  + fit_user_level * 0.30 // ユーザー熟練度との適合
  + node_count_fit * 0.15 // 7±2 ノードに収まるか
  + simplicity * 0.15     // シンプルさ（非技術者向けは加点）
```

最高スコアの図を選択。タイ時は **非エンジニア度が高い方** を優先。

## 各図の採用条件

### 1. flowchart

| 条件 | 重み |
|-----|-----|
| ノード5〜9個 | +0.4 |
| 分岐あり | +0.3 |
| 順序あり | +0.3 |
| 非技術ユーザー | -0.1（numbered-steps へ譲る） |

**サンプル**: google-forms-generator の Phase フロー（kickoff→profile→interview→summary→handoff）

### 2. sequence

| 条件 | 重み |
|-----|-----|
| API/サービス間呼出 | +0.5 |
| 上級ユーザー | +0.3 |
| 非技術ユーザー | -0.5（採用不可、numbered-steps に強制代替） |

### 3. state

| 条件 | 重み |
|-----|-----|
| 状態が3〜6個 | +0.4 |
| 状態遷移トリガあり | +0.4 |

### 6. gantt

| 条件 | 重み |
|-----|-----|
| 期間あり | +0.4 |
| タスク3〜7個 | +0.3 |
| 非技術ユーザー | +0.2（直感的） |

### 7. pie

| 条件 | 重み |
|-----|-----|
| 構成比データあり | +0.5 |
| 5要素以下 | +0.3 |

### 13. numbered-steps（独自）

| 条件 | 重み |
|-----|-----|
| 手順4〜7段 | +0.5 |
| 非技術ユーザー | +0.3 |
| 順序が線形 | +0.2 |

**サンプル**: Phase フロー（非技術者向け代替）

### 14. persona-card（独自）

| 条件 | 重み |
|-----|-----|
| user_profile セクション | +0.6 |
| 6軸全て埋まっている | +0.2 |

### 15. before-after（独自）

| 条件 | 重み |
|-----|-----|
| 価値セクション | +0.5 |
| 数値KPIあり | +0.4 |

### 16. comparison-table（独自）

| 条件 | 重み |
|-----|-----|
| 選択肢2〜4個 | +0.5 |
| 評価軸3〜5個 | +0.3 |

### 19. icon-grid（独自）

| 条件 | 重み |
|-----|-----|
| 連携先カタログ | +0.6 |
| 4〜9サービス | +0.3 |

## セクション別推奨

| セクション | 第一候補 | 第二候補 |
|--------|------|------|
| 目的 | flowchart | mindmap |
| ユーザー像 | persona-card | quadrant |
| 5軸回答 | comparison-table | quadrant |
| 外部連携 | icon-grid | er |
| 想定フロー | flowchart / numbered-steps | sequence |
| 価値 | before-after | progress-bar |
| 状態管理 | state | traffic-light |
| スケジュール | gantt | timeline |

## 自動代替ルール

非技術ユーザー向けで★1図種が選ばれた場合、以下に強制代替。

| ★1図種 | 代替先 |
|------|-----|
| sequence | numbered-steps |
| class | comparison-table |
| er | icon-grid |
