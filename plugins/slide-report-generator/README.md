# slide-report-generator

presentation-slide-generator v8.4.2 の全機能を移植した共通コア + `output_mode = slide | report` の 2 モード・ビジュアル生成ハーネス。意匠/技術層 (Kanagawa 配色 / 16:9 / GSAP / インライン SVG2 / Codex Image2 / 決定論レンダラ / A4 印刷 / style genome) を**単一 SSOT で共有**し、コンテンツ意図層のみ mode 別に分岐する。

- **slide モード**: 1スライド1メッセージ / chip 強制 / 長文禁止 (BP11-13) / 16:9 / 97 slideType。
- **report モード**: 読み物 (文章多め可) / セクション+段落 / 1項目1ビジュアル最適化 / 4 reportType / Mermaid 統合。

Node 製レンダリング/画像/印刷/検証エンジンは `vendor/` に **byte 携行** し、skill/agent から `Bash(node *)` で起動する (Python-stdlib へ書き換えない = 既存資産の毀損回避)。

## 構成

| surface | 実体 |
|---|---|
| skills | `run-slide-report-generate` (主オーケストレータ) / `run-slide-report-modify` / `run-cross-deck-review` |
| agents | 17 thin Task adapters (詳細 7 層 prompt は各 owner skill の `prompts/R*.md`) |
| commands | `/slide-report-generate` / `/slide-report-status` |
| hooks | `hook-postgen-eval.py` (PostToolUse・生成後評価の自動起動・fail-soft) |
| scripts | 5 plugin-root scripts: `validate-output-mode.py` / `lint-vendor-parity.py` / `validate-plugin-completeness.py` / `lint-reference-attribution.py` / `validate-report-visual.py` |
| schemas | `structure.schema.json` (slide) / `report-structure.schema.json` (report・共通コア共有) ほか |
| references | 42 upstream + report 新規 4 (report-types / report-writing-rules / report-visual-strategy / mermaid-integration) |
| vendor | Node engine 一式 (195 files byte 携行) + report 新規 Node 2 (render-report.js / mermaid-render.js) |

## 使い方 (概要)

```
/slide-report-generate --mode slide  <topic>     # HTML スライド生成
/slide-report-generate --mode report --report-type internal-analysis <topic>   # HTML レポート生成
/slide-report-status <project-dir>               # 進行状況/フェーズ確認
```

`run-slide-report-generate` skill が hearing → 構成設計 → 仕様確定ゲート → 生成 (HTML / 決定論 render-slide.cjs / Codex 画像 / report render-report.js) → 生成後評価 (deck-evaluator・30種思考法・mode-aware) を駆動する。

## 初回セットアップ

Node engine は `vendor/` に携行済みだが `node_modules` は再 install が必要:

```bash
cd "$CLAUDE_PLUGIN_ROOT/vendor" && npm ci
npx playwright install chromium   # render/verify 系のヘッドレス実行に必要
python3 "$CLAUDE_PLUGIN_ROOT/scripts/validate-output-mode.py" --preflight
```

すべての実行パスは `$CLAUDE_PLUGIN_ROOT` 起点で解決する (install 先非依存)。

`vendor/package.json` は upstream byte-parity 対象なので `npm test` などの scripts は追加しない。検証の正本は `EVALS.json` の `harness.mechanical[]` と下記の品質コマンド。

Mermaid は runtime 依存を増やさず、`mermaid-render.js` が CDN 初期化 + `<pre class="mermaid">` fallback を出力する。オフラインでは図が SVG 化されない場合があるが、定義テキストは可読な fallback として残る。

## reportType (report モード 4 骨格)

| reportType | 骨格 |
|---|---|
| `internal-analysis` | 要約 → 背景 → 現状分析 → 所見 → 次アクション |
| `client-proposal` | 課題 → 解決策 → 効果実績 → 導入ステップ → CTA |
| `tech-doc` | 概要 → 前提 → 手順構造 → 注意点 → 参照 |
| `learning` | 問い → 核心概念 → 図解理解 → 例応用 → まとめ |

## 品質・再現性

- **vendor byte-parity**: `python3 "$CLAUDE_PLUGIN_ROOT/scripts/lint-vendor-parity.py"` が `vendor/vendor-digest-manifest.json` (195 files sha256 pin) と照合する。runtime schema は重複を避けて plugin-root `schemas/` を正本にし、upstream digest もそこで検証する。
- **plugin completeness**: `python3 "$CLAUDE_PLUGIN_ROOT/scripts/validate-plugin-completeness.py"` が manifest 名・entry_points・hook 実体・必須 surface を検証する。
- **mode 検証**: `validate-output-mode.py` が `output_mode`/`reportType` の値域を fail-closed 検証。
- **生成後評価**: `hook-postgen-eval.py` が deck/report 中核ファイル書込を検知し deck-evaluator を mode 判定つきで起動を促す。
- **改善要望ループ**: `run-skill-feedback`（`skills/run-skill-feedback` は harness-creator の SSOT へ symlink 配備）で本プラグインの skill への改善要望を起票・集約できる。発火は `run-skill-feedback` skill を起動する。

`distributable: false` (社内専用・marketplace/bundle 非登録)。

## ドキュメントとリリース状態

このプラグインは `plugin-plans/slide-report-generator/` の L3 計画から、ユーザー指示により実体 build まで進めたローカル plugin 版。公開 marketplace / bundle / PR 配布は非スコープで、release 判定は local plugin としての manifest・composition・EVALS・vendor parity・mechanical tests の PASS を基準にする。

中学生向けに言うと、slide は「発表用の1枚ずつの紙」、report は「読み物のレポート」。どちらも同じ色・部品・描画エンジンを使い、内容の組み立て方だけを `output_mode` で切り替える。
