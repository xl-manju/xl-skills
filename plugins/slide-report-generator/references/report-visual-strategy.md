# ビジュアル三択最適化ルール（report / 両モード）

> 責務: `visual-strategist` が使う **SVG図解 / Mermaid / Codex生成画像 の三択最適化ルール**の正本。どの内容にどのビジュアル種別が最適かの選択規準・1項目1ビジュアル原則・配置（grid/zones/readingOrder/focalPoint）を定義する。固定比率を持たない。
> 関連: Mermaid 固有は [mermaid-integration.md](mermaid-integration.md)、SVG プリミティブは [svg-diagram-primitives.md](svg-diagram-primitives.md)、Codex 画像は [full-image-deck-method.md](full-image-deck-method.md) / [style-genome-packaging.md](style-genome-packaging.md)、schema は `schemas/report-structure.schema.json` の `visual`。

---

## 0. 三択とは（固定比率を持たない意思決定）

各項目のビジュアルは **SVG図解 / Mermaid / Codex生成画像 / なし（none）** の中から**内容適合で 1 種を選ぶ**。これは「何割を画像に」という配分ではなく、内容の性質に対する意思決定である（固定比率禁止）。構成設計者（structure-designer / report-structure-designer）が第一候補と意図を付し、`visual-strategist` が最終確定と配置を担う。

| kind | 実体 | 得意 |
|------|------|------|
| `svg` | インライン SVG2 図解（svg-builder トークン） | 独自構造・意匠制御・順序/依存/階層 |
| `mermaid` | Mermaid 図（render-report.js / mermaid-render.js） | 定型のフロー/シーケンス/状態/割合 |
| `codex-image` | Codex Image2 生成画像（gpt-image-2） | 情感・世界観・章扉的な概念 |
| `none` | ビジュアルなし | 文章と callouts で足りる |

---

## 1. 選択規準（どの内容に何が最適か）

### 1.1 一次判定（内容の性質 → 種別）

| 内容の性質 | 最適 kind | 理由 |
|-----------|-----------|------|
| 独自の関係構造で、配色・座標・アイコンを細かく効かせたい | `svg` | インライン SVG2 は意匠トークンをフル制御でき印刷・16:9 と親和 |
| フロー / シーケンス / 状態遷移 / ER / ガント / 割合 が**定型記法で素直に書ける** | `mermaid` | 記述量が少なく保守しやすい。定型構造を確実に再現 |
| 概念の情感・世界観・章扉的導入・被写体1点で語れる | `codex-image` | コンセプト画像で読み物/デッキの空気感を高める |
| 論述・要約・注意点の列挙で、文章と callouts で足りる | `none` | 図解過多を避け本文の可読性を優先 |
| 数値・料金・コードなど逐語が頻繁に変わる | `none`＋本文 | 画像に焼かず本文（表/コードブロック）で正確に持つ（退化耐性） |

### 1.2 svg か mermaid か（構造図の分かれ目）

両者は構造図で競合する。次で分ける。

| 判断 | svg | mermaid |
|------|-----|---------|
| 意匠を細かく制御したい（配色・アイコン・座標） | ○ | △（テーマ注入のみ） |
| 独自形状・非定型レイアウト | ○ | △ |
| 定型のフロー/状態/ER/ガント/割合 | △（手で座標） | ○（記法で簡潔） |
| 保守性（後修正の容易さ） | △ | ○（definition を直すだけ） |
| 記述量 | 多い | 少ない |

**目安**: 「意匠をきめ細かく作り込む1点」は svg、「定型構造を素早く確実に」は mermaid。

### 1.3 tie-break（競合時の決定順）
1. **正確性・退化耐性**: 逐語が変わる/精密なら画像を避ける（svg か本文）。
2. **保守性**: 定型構造なら mermaid。
3. **意匠制御の必要度**: 細かい制御が要るなら svg。
4. **情感の必要度**: 概念の空気感が価値なら codex-image。
5. **環境可用性**: codex CLI 不在なら codex-image を避け svg/mermaid へ、mermaid 不在なら svg かフォールバックへ。

---

## 2. 1項目1ビジュアル原則

- **1セクション/スライドにビジュアルは最大1つ**。読解を助ける1点に絞る。
- 複数の図が欲しくなったら、それは 1 節に情報を詰めすぎのサイン。構成設計へ差し戻してセクションを分けることを検討する。
- read-through（report）では特に図解過多を避ける。文章で足りる節は迷わず `none`。

---

## 3. 配置（placement）

`visual-strategist` は種別に加えて配置を決める。固定比率は持たないが、面内の役割割り当てと視線の一貫性は設計する。

### 3.1 grid / zones
- `grid`: 本文とビジュアルの分割（例 `2x1` = 左本文・右図、`1x1` = 図を単独ブロック）。report は縦スクロールなので、横並びが窮屈なら図を単独ブロックにして本文の下へ置く。
- `zones`: 面内領域に役割（`prose` / `visual` / `callout` / `caption`）を割り当て、本文・図・注記の関係を明示する。

### 3.2 readingOrder / focalPoint（デッキ/レポート内で一貫）
- `readingOrder`: 視線誘導の向き。**デッキ/レポート全体で1方向に統一**する（既定 `left-to-right`。循環図のみ `clockwise` の例外）。ページ/節ごとに向きを変えない。
- `focalPoint`: 主ビジュアルの重心（0-100%）。**同じ高さ帯に揃える**（例 縦 50〜58%）。章扉だけ重心を上げる等の差をつけない。
- これらは full-image-deck-method §1.11 のドリフト対策を三択全体へ適用したもの。連作としての一貫性を保つ。

### 3.3 emphasis
- `normal` / `highlight` / `muted`。強調は要所（結論を支える図など）に限り、多用しない。

---

## 4. 環境可用性（描けるものだけ確定）

- `codex-image` を選ぶ前に codex CLI の、`mermaid` を選ぶ前に mermaid（CLI/lib）の可用性を確認する（`validate-output-mode.py --preflight` 等）。
- 不在時は種別を現実的な代替へ寄せ、`rationale` に理由を残す。描画不能な種別を確定しない。
- codex-image が使えない環境では、概念図を svg（simplified）へ、割合を mermaid pie か svg chart へ寄せるなどして意図を近似する。

---

## 5. 退化耐性（画像に載せないもの）

full-image-deck-method / slide CONST_007 と同一方針。次は画像へ焼き込まず本文または svg で持つ。

- コード・コマンド・設定値（逐語が変わる）。
- 精密な数値・料金・対照表（更新で誤りが固定化する）。
- 長文・頻繁に変わる文言。

画像は「情感・世界観・被写体1点で語れる概念」に用途を絞る。

---

## 6. モード横断（slide でも機能する）

本ルールは両モードで機能する。slide では各 slide の図解ノード/aiVisual に、report では各 section の visual に三択最適化を適用する。意匠/技術コア（配色・aiVisual $defs・diagram $defs）は共有 SSOT を参照し、種別選択の規準・1項目1ビジュアル・配置一貫性は共通である。差分はコンテンツ密度（slide=1メッセージ / report=読み物）にのみ現れる。

---

## 7. チェックリスト

| 項目 | 基準 |
|------|------|
| 種別が内容適合で選ばれているか | 一次判定/tie-break で説明可能（rationale 記載） |
| 固定比率で割り当てていないか | 「N割画像」等の配分をしていない |
| 1項目1ビジュアルか | 各項目の非 none visual は最大1 |
| 退化耐性を守っているか | 逐語が変わる要素を画像に載せていない |
| 配置が一貫しているか | readingOrder 1方向・focalPoint 同帯 |
| 描画可能か | 確定種別が環境で描画可能（不在種別を残さない） |

---

## 8. 1.2.0 追補 — placement 正規化

### 8.1 正規化 placement field

`placement`（＝`visual.layout`）を **{grid, zones, emphasisZone, readingOrder, focalPoint}** の5 field に統一した。§3 で節側に置いていた `readingOrder`/`focalPoint` を placement へ移設し、配置決定を1オブジェクトに集約する（C18=幾何配置 owner の単一入力面）。

| field | 意味 | §参照 |
|---|---|---|
| `grid` | 本文/ビジュアルの分割（例 `2x1`） | §3.1 |
| `zones` | 面内領域の役割割り当て（prose/visual/callout/caption） | §3.1 |
| `emphasisZone` | ビジュアル配置の強調度（normal/highlight/muted） | §8.2 |
| `readingOrder` | 視線誘導の向き（デッキ/レポートで1方向統一） | §3.2 / §8.3 |
| `focalPoint` | 主ビジュアル重心（同帯に揃える） | §3.2 |

> section 直下の `readingOrder`/`focalPoint`（1.1.0）は後方互換で温存。render-report.js は section 直下を優先し、無ければ placement 側へフォールバックする。

### 8.2 `emphasis` → `emphasisZone` 改名

§3.3 の `emphasis`（normal/highlight/muted）を **`emphasisZone` に改名**した。理由は inline highlight の `==要点==`（本文の色強調）と **`emphasis` の字面が意味衝突**するため。前者は「本文フレーズの強調」、後者は「ビジュアル配置面の強調度」で別レイヤだが、語が同じだと owner 境界（C17 論理強調 vs C18 幾何配置）を跨いで混同する。`emphasisZone` は「zone の強調」であることを名前で明示する。

- 旧 `emphasis` は **deprecated alias** として温存（後方互換）。両指定時は `emphasisZone` を優先。
- render-report.js は `emphasisZone`→`emphasis` の順にフォールバックし、非 normal 値を `data-emphasis` 属性へ live 反映する（C25 が宣言↔反映を検査）。

### 8.3 `readingOrder` の consumer 配線

`readingOrder` は render-report.js が **`data-reading-order` 属性**へ反映する。section 直下（1.1.0）を優先し、無ければ placement へ移設された `layout.readingOrder`（1.2.0）を採る。

- **順序ヒントであり並び替えキーではない**: section は配列順でレンダされ、`readingOrder` は視線方向の宣言（CSS/レビューが参照）に留まる。実際の DOM 順序は変えない。
- 一貫性規律（§3.2）は不変: デッキ/レポート全体で1方向へ統一する。placement へ移設しても「ページごとに向きを変えない」原則は維持する。
