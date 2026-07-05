# リソースマップ（Progressive Disclosure）

**責務**: 全リソースの一覧と読み込み条件を定義

---

## 原則

リソースは**必要な時のみ**読み込む。SKILL.mdのみで概要を把握し、詳細は該当フェーズで参照。

---

## references/（41ファイル）

### v7.0.0 新規 SSoT・分類系（4ファイル）

| ファイル | 行数 | Phase | 読み込み条件 |
|----------|------|-------|-------------|
| **spec-registry.md** | 243 | 全 Phase | SSoT・SR-ID 62項目（仕様参照時必読） |
| **slide-type-decision-tree.md** | ~600 | P2 | スライドタイプ選択時（DT-ID 98、79種網羅） |
| **unit-system.md** | ~300 | P3 | スタイル設計時（vw 統一・換算表 49） |
| **bp-classification.md** | ~250 | 全 Phase | BP 確認時（V-ID 30 機械検証 + LLM 10 条） |


### スライドタイプ系（12ファイル）

| ファイル | 行数 | 読み込み条件 |
|----------|------|-------------|
| slide-types-overview.md | 80 | タイプ選択時（最初に参照） |
| slide-types-basic.md | 460 | 基本スライド作成時 |
| slide-types-extended.md | 650 | 拡張スライド作成時 |
| slide-interactions.md | 820 | ホバー・アニメーション実装時 |
| slide-text-guidelines.md | 280 | テキスト調整・オーバーフロー対策時 |
| diagram-cycle-flow.md | 960 | サイクル・フロー図解時（**SVG2版**） |
| diagram-comparison.md | 940 | 比較・マトリックス図解時 |
| diagram-business.md | 1410 | ビジネス系図解時（PREP・STAR含む） |
| diagram-fabe.md | 1360 | FABE型（5バリエーション）使用時 |
| diagram-visual.md | 1440 | ビジュアル系図解時（**SVG2+CSSハイブリッド版**） |
| chart-types.md | 1510 | グラフ作成時 |
| agenda-navigation.md | 340 | アジェンダナビ実装時 |

### SVG・画像系（5ファイル）

| ファイル | 行数 | 読み込み条件 |
|----------|------|-------------|
| svg-diagram-primitives.md | 350 | SVG図解作成時（基本パーツ・マーカー・フィルター・座標計算） |
| image-format-guide.md | 183 | 画像追加時（SVG/WebP/PNG選択基準・WebP変換手順・SVG背景レイヤ） |
| ai-image-diagram-workflow.md | 252 | ユーザーの明示指示により事前確認済みtext-to-imageバックエンドで図解・ビジュアルを画像生成して差し替える時 |
| full-image-deck-method.md | 255 | 全面/部分AI画像化、STYLE BIBLE、世界観統一、画像生成プロンプトキット作成時 |
| style-genome-packaging.md | 177 | `slide-2026-06-13-skill-mass-production/assets/generated/` 画像群の漫画チック図解スタイルを再現する時 |

### デザイン原則系（4ファイル）

| ファイル | 行数 | 読み込み条件 |
|----------|------|-------------|
| visual-hierarchy-principles.md | 350 | 視覚階層・フォーカルポイント設計時 |
| composition-patterns.md | 350 | 構図・CARP原則・グリッド設計時 |
| color-strategy.md | 300 | 配色戦略・色彩心理適用時 |
| slide-design-patterns.md | 350 | スライドデザインパターン選択時 |

### スタイル・レイアウト系（6ファイル）

| ファイル | 行数 | 読み込み条件 |
|----------|------|-------------|
| theme-style.md | 960 | テーマ・カラー設定時 |
| **design-quality-guide.md** | **380** | **デザイン品質適用時（ビビッドカラー・シャドウ・アニメーション・アクセシビリティ）** |
| layout-visual.md | 465 | レイアウト調整時 |
| print-layout.md | 730 | PDF出力時 |
| icons.md | 485 | アイコン選択時 |
| writing-rules.md | 400 | テキスト作成ルール確認時 |

### 構造・戦略系（4ファイル）

| ファイル | 行数 | 読み込み条件 |
|----------|------|-------------|
| structure.md | 300 | 構成設計（Phase 2）時 |
| strategy.md | 350 | プレゼン戦略設計時 |
| diagram-chart.md | 1100 | 図解・グラフ選択ガイド時 |
| d3-integration.md | 600 | D3.js使用時 |

### その他（2ファイル）

| ファイル | 行数 | 読み込み条件 |
|----------|------|-------------|
| llm-script-separation.md | 200 | 責務分離確認時 |
| changelog.md | 150 | 変更履歴確認時 |

---

## agents/（13ファイル）

| ファイル | 行数 | Phase | 読み込み条件 |
|----------|------|-------|-------------|
| hearing-facilitator.md | 173 | P1 | ヒアリング開始時 |
| structure-designer.md | 217 | P2 | 構成設計時 |
| **structure-validator.md** | **150** | **P2.5（NEW v7.0.0）** | **仕様確定ゲート時** |
| d3-diagram-designer.md | 276 | P2.5 | D3図解使用時 |
| data-visualizer.md | 297 | P2.5 | データ可視化時 |
| html-generator.md | 417 | P3 | HTML生成時（従来経路） |
| **slide-renderer.md** | **~200** | **P3-determ（NEW v7.0.0）** | **決定論レンダラ起動時** |
| **ai-image-diagram-producer.md** | **~170** | **P3.2（明示指示時のみ / NEW v7.1.1）** | **ユーザーの明示指示により事前確認済みtext-to-imageバックエンドで図解・ビジュアルを画像生成して差し替える時** |
| layout-optimizer.md | 378 | P3 | レイアウト最適化時 |
| ui-quality-reviewer.md | 411 | P3.5 | UI品質検証時 |
| slide-modifier.md | 266 | P4 | 修正時 |
| cross-deck-reviewer.md | - | P5 | シリーズ横断検証 |

---

## scripts/（19ファイル）

| ファイル | 行数 | Phase | 用途 |
|----------|------|-------|------|
| **render-slide.cjs** | **365** | **P3-determ** | **決定論レンダラ本体（NEW v7.0.0）** |
| **template-engine.cjs** | - | P3-determ | テンプレートエンジン（NEW v7.0.0、24テンプレ） |
| **style-builder.cjs** | - | P3-determ | スタイル構築（NEW v7.0.0） |
| **svg-builder.cjs** | - | P3-determ | SVG構築（NEW v7.0.0） |
| **phase-gate.js** | **284** | 全 Phase | Phase 間ゲート（NEW v7.0.0） |
| **precheck-layout.js** | **109** | P3 着手前 | layout 事前検証（NEW v7.0.0、必須） |
| **validate-ai-image-assets.js** | **~80** | P3.2 | AI画像図解のprompt/meta/WebP機械検証 |
| validate-structure.js (拡張) | 558 | P2.5 | V-001〜V-030 構成検証（v7.0.0 拡張） |
| workflow-manager.js (拡張) | 332 | 全 Phase | P2.5 新設対応（v7.0.0 拡張） |
| layout-calculator.js (拡張) | 537 | P3 | レイアウト計算（v7.0.0 拡張） |
| utils.js | 239 | 共通ユーティリティ（DRY統合） |
| verify-slides.js | 380 | スライド検証・スクリーンショット |
| check-consistency.js | 335 | 統一感検証 |
| validate-structure.js | 233 | 構成案検証 |
| validate-d3.js | 358 | D3コンポーネント検証 |
| log_usage.js | 88 | フィードバック記録 |
| sync-checker.js | 275 | index.html⇔structure.md同期検証 |
| html-scaffold.js | 340 | 構成案からHTMLスケルトン生成 |
| auto-linebreak.js | 250 | 自動改行挿入 |
| layout-calculator.js | 285 | レイアウト計算（カード幅・フォントサイズ） |
| build-single-html.js | 145 | 分離形式→1ファイルHTML結合（GASデプロイ用） |
| convert-to-webp.js | 205 | PNG/JPG→WebP一括変換（cwebp使用、HTML参照自動更新） |

---

## assets/（13ファイル）

| ファイル | 用途 |
|----------|------|
| **pagination.html** | **不変ナビ HTML（NEW v7.0.0）** |
| **pagination.css** | **不変ナビ CSS（NEW v7.0.0）** |
| **pagination.js** | **不変ナビ JS（NEW v7.0.0、695行 計）** |
| ai-image-diagram-prompt-template.md | AI画像図解の標準プロンプトテンプレート（明示指示時のみ） |
| style-genome-kanagawa-comic-diagram.json | `slide-2026-06-13-skill-mass-production/assets/generated/` 由来の漫画チック図解スタイルゲノム。`patterns`（image-only/html-composite/html-primary）/ `textPolicies`（baked-with-overlay/overlay-only/none）/ `backgroundSources`（raster/svg/none）を含む。値域の正本は `scripts/validate-ai-image-assets.js` と `style-genome-packaging.md` §4 |
| structure-template.md | 構造化データテンプレート |
| print-styles.css | 印刷用CSS |
| gas-deploy-guide.md | GASデプロイ手順 |
| d3-components/base.js | D3共通ユーティリティ |
| d3-components/cycle.js | サイクル系図解 |
| d3-components/hierarchy.js | 階層系図解 |
| d3-components/flow.js | フロー系図解 |
| d3-components/charts.js | グラフ系 |
| d3-components/advanced.js | 高度な可視化 |
| d3-components/extended.js | 拡張図解 |

---

## schemas/（1ディレクトリ・3ファイル・NEW v7.0.0）

| ファイル | Phase | 用途 |
|----------|-------|------|
| **structure.schema.json** | P2/P2.5 | 入力契約（97 slideType, $defs 55） |
| **example.structure.json** | 学習時 | schema 例 |
| **README.md** | 学習時 | schema 利用ガイド |

---

## 読み込み優先度

### 必須（全タスク）
1. SKILL.md（170行）

### Phase別

| Phase | 必須リソース | オプション |
|-------|-------------|-----------|
| P1 | hearing-facilitator.md | - |
| P2 | structure-designer.md, slide-types-overview.md | diagram-chart.md |
| P2.5 | d3-diagram-designer.md, d3-integration.md | data-visualizer.md |
| P2 (デザイン) | visual-hierarchy-principles.md, composition-patterns.md | color-strategy.md, slide-design-patterns.md |
| P3 | html-generator.md, 該当スライドタイプファイル, **design-quality-guide.md** | theme-style.md, svg-diagram-primitives.md, visual-hierarchy-principles.md, composition-patterns.md, color-strategy.md, slide-design-patterns.md |
| P3（図解） | svg-diagram-primitives.md, 該当diagram-*.md | image-format-guide.md |
| P3.2（AI画像図解・明示指示時のみ） | ai-image-diagram-producer.md, ai-image-diagram-workflow.md, image-format-guide.md | style-genome-packaging.md, full-image-deck-method.md, design-quality-guide.md |
| P3.5 | ui-quality-reviewer.md, verify-slides.js | layout-visual.md |
| P4 | slide-modifier.md | - |

---

## 変更履歴

| Version | Date | Changes |
|---------|------|---------|
| **2.1.4** | **2026-06-24** | **AI画像サブシステムの正準モデル整合（elegant-review）**: `textPolicy` から `html-primary` を廃し `none` を追加、`backgroundSource`(raster/svg/none) を新設し SVG/CSS背景型に対応。`pattern`/`textPolicy`/`backgroundSource` の値域の正本を `scripts/validate-ai-image-assets.js`（機械）と `style-genome-packaging.md` §4（人間可読）に一本化。AI画像系 references の行数を実数へ更新（image-format-guide=183 / ai-image-diagram-workflow=252 / full-image-deck-method=255 / style-genome-packaging=177）、agents 表ヘッダを実数 13 に修正 |
| **2.1.3** | **2026-06-23** | **assets/generated由来のスタイルゲノム正式化**: `style-genome-packaging.md` と `assets/style-genome-kanagawa-comic-diagram.json` を追加。画像生成完結型（image-only + baked-with-overlay）とHTML合成型（html-composite + overlay-only）を分離し、漫画チック説明図・吹き出し・簡易表・角丸アイソメタイル・発光フローラインを再現可能にした |
| **2.1.2** | **2026-05-06** | **Script First補強**: AI画像図解のprompt/meta/WebP検証スクリプトと標準プロンプトテンプレートを追加 |
| **2.1.1** | **2026-05-06** | **AI画像図解差し替えの起動条件を明確化**: デフォルトはHTML/CSS/JS/SVG/D3で構成し、画像生成はユーザーが画像生成・Codex図解作成を明示した場合のみ実行 |
| **2.1.0** | **2026-05-06** | **AI画像図解差し替え統合**: references/ 34→35（ai-image-diagram-workflow追加）、agents/ 11→12（ai-image-diagram-producer追加）、P3.2としてtext-to-imageバックエンドによる図解・ビジュアル高品質化を追加 |
| **2.0.0** | **2026-05-03** | **v7.0.0 決定論アーキテクチャ統合**: references/ 30→34（spec-registry, slide-type-decision-tree, unit-system, bp-classification 追加）、agents/ 9→11（structure-validator, slide-renderer 追加）、scripts/ 13→19（render-slide.cjs / template-engine.cjs / style-builder.cjs / svg-builder.cjs / phase-gate.js / precheck-layout.js 追加）、assets/ 10→13（pagination.html/css/js 追加）、schemas/ 0→1（structure.schema.json + example + README） |
| 1.5.0 | 2026-02-15 | デザイン原則系4ファイル追加（visual-hierarchy-principles.md、composition-patterns.md、color-strategy.md、slide-design-patterns.md）、references/26→30 |
| 1.4.0 | 2026-02-15 | design-quality-guide.md追加（ビビッドカラー・シャドウ・アニメーション・アクセシビリティ統合リファレンス）、references/25→26 |
| 1.3.0 | 2026-02-15 | SVG2移行: svg-diagram-primitives.md・image-format-guide.md追加、convert-to-webp.js・build-single-html.js追加、diagram-cycle-flow.md/diagram-visual.mdをSVG2版に更新。references/23→25、scripts/11→13 |
| 1.2.0 | 2026-01-24 | diagram-fabe.md追加（FABE型独立化）、references/ファイル数22→23 |
| 1.1.0 | 2026-01-24 | workflow-manager.js追加、スクリプト数10→11 |
| 1.0.1 | 2026-01-23 | エージェント行数更新（html-generator: 552→417、ui-quality-reviewer: 544→411） |
| 1.0.0 | 2026-01-23 | 初版作成（v4.0.0リファクタリング時） |
