# Custom Visuals (SVG 8種)

Mermaid で表現しづらい意匠（番号付きステップ、ペルソナ、ビフォアフ、比較表など）を独自 SVG テンプレで補完する。
全テンプレ `viewBox="0 0 1200 600"` を基本とし、`{{var}}` プレースホルダーを `compose_diagram.js` が置換する。

## 8種一覧

| # | テンプレ | 用途 | 必須変数の概要 |
|---|--------|-----|--------------|
| 1 | numbered-steps | IKEA説明書風の手順（最大7） | title, step1〜step5 |
| 2 | persona-card | ユーザーペルソナ | name, role, challenge, goal |
| 3 | before-after-split | 横並びビフォー/アフター | before_title, before_item1〜3, after_title, after_item1〜3 |
| 4 | comparison-table | 選択肢×属性比較表（3×3） | title, attr1〜3, opt1〜3 + 各値 |
| 5 | traffic-light | 3色信号 | title, red_label, yellow_label, green_label |
| 6 | progress-bar | 達成度バー | title, percent, current_label, target_label |
| 7 | icon-grid | アイコン格子（3×3 = 最大9マス） | title, icon1〜9, label1〜9（FontAwesome Unicode） |
| 8 | sankey-supplement | Mermaid sankey の凡例＋注釈補助 | title, src/mid/dst それぞれの label/color, note1, note2 |

## 共通制約

- 絵文字禁止。アイコンは **FontAwesome の Unicode コードポイント**（例: `&#xf007;`=user, `&#xf00c;`=check, `&#xf00d;`=times）を `<text>` で参照
- 色は意味付き＋凡例必須:
  - 赤 (`#c62828` / `#ffebee`) = 注意・課題・NG
  - 緑 (`#2e7d32` / `#e8f5e9`) = 完了・OK・目標
  - 青 (`#1976d2` / `#e3f2fd`) = 進行中・本人情報
  - 黄 (`#f9a825` / `#fff8e1`) = 判定・注意喚起
- 各 SVG 末尾に「凡例」と「言いたい一言: {{message}}」を必ず記載
- ノードラベル日本語10文字以内

## 選択基準（Mermaid との使い分け）

| 状況 | 推奨 |
|-----|-----|
| アクター・課題・目標を一枚で示したい | persona-card |
| 番号付きの厳密な手順 | numbered-steps |
| 導入前後の対比を強調 | before-after-split |
| 3つ以上の選択肢を属性ごとに比較 | comparison-table |
| 状態を信号で直感的に | traffic-light |
| 達成率を1値で示す | progress-bar |
| 機能・ツール群をカード状に | icon-grid |
| Mermaid sankey に凡例を追加 | sankey-supplement |

## サンプル画像

`compose_diagram.js` でレンダリング後のサンプルは（生成時）`output/<skill-name-hint>/visuals/` に出力される。

## メタブロック

各 SVG は冒頭の HTML コメントでメタ情報を記述する:

```xml
<!--
  template: <name>
  required_vars: [...]
  optional_vars: [...]
  use_case: ...
-->
```

このコメントを `select_diagram_type.js` がパースする。
