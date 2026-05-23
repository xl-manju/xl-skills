---
name: skill-intake-interviewer
description: スキル作成前のヒアリングを行うメタスキル。完全非技術者を含む不特定多数から、本人も言語化できていない真の課題を引き出し、Markdown ヒアリングシート（人間用・正本）と JSON（skill-creator 用・副本）を生成し、Notion に公開して Slack に通知する。各セクションに必要十分な図解（Mermaid 12種＋独自 SVG 8種＝20種カタログ）を自動配置し、非エンジニア向けマスト要件を機械検証する。skill-creator の前段に位置し、要件抽出だけを責務とする。
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - AskUserQuestion
---

# skill-intake-interviewer

## このスキルの価値（責務境界の宣言）

スキルを作ること自体に価値はない。価値は依頼者の時間が浮いた瞬間に生まれる。
このスキルは「ヒアリングのズレを構造で減らす装置」であり、依頼者本人も言語化できていない真の課題を炙り出すことを最優先する。

設計・実装は skill-creator の責務。このスキルは要件抽出だけを担う。

| このスキルの責務 | skill-creator の責務 |
|---------------|------------------|
| 真の課題の発掘・構造化・共通言語化 | 設計・スケルトン生成・本実装 |
| Markdown 正本＋JSON 副本の二重出力 | JSON を読んで Phase 0-0 以降を簡略化 |
| Notion 公開＋Slack 通知 | スキル本体の構築 |

## 設計原則

| 原則 | 説明 |
|-----|-----|
| Problem First | 表層要望を仮説扱いし、本質的問題を最優先で発掘 |
| Structure-Reduces-Drift | 「言語化されているのは1割」という構造的問題を、問い構造で誤り訂正する |
| Script First | 決定論的処理（Markdown↔JSON変換、図解生成、検証）はすべてスクリプト |
| Visualization Mandatory | 全セクションに必要十分な図解を配置。非エンジニア理解度をマストで担保 |
| Self-Evolving | question-bank がヒアリング毎に成長する自己進化ループ |

## 必須品質ゲート

- 全 agent は出力前に `references/quality-rubric.md` の5次元（完全性／一貫性／深度／検証可能性／簡潔性）で自己採点
- 全 agent 出力後に `scripts/quality_gate.js` が機械検証（PASS必須）
- 全フェーズ終了後に `scripts/cross_check.js` で agent 間整合を検証
- 図解は `scripts/enforce_visualization_rules.js` で非エンジニア対応マスト8ルールを強制
- セクション粒度は `scripts/section_quality_check.js` で「必要十分」原則を強制
- 反復上限: 各 agent 内3回、フェーズ全体で2回

## 実行環境契約（Claude Code / Codex / 手動 CLI）

このスキルの全 `scripts/*.js` は次の3経路で同一に動く。詳細は `references/execution-contract.md`。

| 経路 | 起動 | コマンド例 |
|------|-----|-----------|
| Claude Code（Bash ツール） | agent の `allowed-tools: Bash` 経由で自動実行 | `node scripts/quality_gate.js --agent interviewer --in output/foo/sheet.json` |
| Claude Code（`!` 手動） | チャット欄に `!` を付けてユーザーが直接実行 | `!node scripts/check_completeness.js --in output/foo/intake.json` |
| Codex（shell） | Codex の shell 実行 | `node scripts/quality_gate.js --agent interviewer --in output/foo/sheet.json` |
| 手動 CLI | shebang 直叩き | `./scripts/quality_gate.js --agent interviewer --in output/foo/sheet.json` |

前提: Node.js ≥18 / cwd=スキルルート / `chmod +x scripts/*.js` 済 / 標準ライブラリのみで動作。
終了コード: 0=PASS, 1=FAIL, 2=INPUT_ERROR, 3=DEPENDENCY_ERROR（→LLM フォールバック）。
agent から `node scripts/...` を呼ぶ際は `references/execution-contract.md` のテンプレートに従うこと。

## 必ず満たす5軸（記事準拠＋ナレッジ資産軸）

ヒアリング完了の判定に必須の5軸（ナレッジ資産軸は MUST 追加項目）:

| 軸 | 質問 |
|---|------|
| 出力先 | どこに出力されたら一番嬉しい？ |
| 情報源 | その情報、今どこから取ってる？ |
| 共有相手 | 誰に伝わったら成功？ |
| 真の課題 | それで何が浮く？それが浮いたら次に何をする？ |
| ナレッジ資産 | あなたの思考プロセス・考え方・外部情報を、このスキルにナレッジとして食わせる必要はある？／既にナレッジ化されたものはどこにある？／無ければどう抽出してナレッジ化したい？ |

ナレッジ資産軸の意図: 表層の「情報源」（≒今どこから引っ張っているか）と異なり、暗黙知・思考プロセス・外部情報を解析してナレッジ化しスキルに注入する流れの有無を扱う独立軸。これが欠けるとスキルは毎回ゼロから判断するだけになり、依頼者の知見が蓄積されない。

責務帰属: ナレッジ資産軸の質問列挙・回答記録は interviewer の責務。purpose-excavator は補助として「暗黙知抽出（Tacit Extraction）」モードを提供するのみで、シート補完は行わない。

## 非エンジニア対応マスト要件

- 1図あたり 7±2 ノード上限
- ノードラベルは日本語10文字以内
- 色は意味付き（赤=注意/緑=完了/青=進行中）凡例必須
- アイコンは FontAwesome（絵文字禁止）
- 専門用語は `references/non-tech-vocabulary.md` で言い換え
- 最終出力は SVG/PNG レンダリング済み（生 Mermaid 構文を見せない）
- 各図に「言いたい一言」を1行付記
- 視覚理解度★1の図種は非エンジニア向けで自動代替

## 実行フロー

```
[起動] ユーザー「スキル作りたい」
  ↓
1. kickoff              パターン選択・深度確認
  ↓
2. assumption-challenger 最初の依頼を仮説扱いし表層を疑う
  ↓
3. user-profiler        熟練度・役割・制約を推定し後続の語彙難易度を調整
  ↓
4. interviewer ⇄ purpose-excavator   対話ループ（最大5往復・ズカズカ深掘り）
  ↓
5. option-presenter     外部連携カタログから選択肢を提示
  ↓
6. visualizer           各セクションに必要十分な図解を配置（1〜3図/セクション）
  ↓
7. summarizer           Gate A サマリ提示 → ユーザー承認
  ↓
8. next-action-advisor  skill-creator への引き渡しモード判定
  ↓
9. handoff              Markdown 正本 + JSON 副本を生成
  ↓
10. notion-publisher    Notion MCP でページ作成
  ↓
11. slack-notifier      Slack 固定チャンネル通知
  ↓
12. self-updater        question-bank に不足質問を追記（自己進化）
  ↓
[完了]
```

## 主要エントリポイント

| 用途 | リソース |
|-----|---------|
| 起動・パターン選択 | agents/kickoff.md |
| 依頼仮説検証 | agents/assumption-challenger.md |
| 対話ヒアリング | agents/interviewer.md |
| 真の課題発掘 | agents/purpose-excavator.md |
| 外部連携選択肢提示 | agents/option-presenter.md |
| ユーザー属性推定 | agents/user-profiler.md |
| 図解生成判断 | agents/visualizer.md |
| Gate A サマリ | agents/summarizer.md |
| 次アクション判定 | agents/next-action-advisor.md |
| 二重出力 | agents/handoff.md |
| Notion 公開 | agents/notion-publisher.md |
| Slack 通知 | agents/slack-notifier.md |
| 質問銀行更新 | agents/self-updater.md |

## リソース一覧

### references/（18個）

| 用途 | ファイル |
|-----|--------|
| 問い設計の正本 | elicitation-techniques.md |
| ユーザー軸の定義 | user-profile-dimensions.md |
| JSON スキーマ | handoff-contract.md |
| Notion/Slack 連携手順 | notion-slack-integration.md |
| 質問銀行（自己進化対象） | question-bank.md |
| 語彙難易度辞書 | vocabulary-tiers.md |
| 既存スキル類似判定 | pattern-recognition-rules.md |
| 完了判定基準 | completeness-criteria.md |
| 失敗パターン | failure-modes.md |
| 外部連携カタログ | integration-catalog.md |
| 表層→深層変換 | surface-vs-deep-patterns.md |
| 価値判定基準 | value-realization-criteria.md |
| 図解選択ルール | mermaid-visualization-guide.md |
| 共通5次元ルブリック | quality-rubric.md |
| アンチパターン辞書 | anti-patterns.md |
| 図解マスト8ルール | visualization-mandatory-rules.md |
| セクション必要十分ルール | section-completeness-rules.md |
| 非技術者言い換え辞書 | non-tech-vocabulary.md |

### scripts/（23個）

| 用途 | ファイル |
|-----|--------|
| JSON スキーマ検証 | validate_intake.js |
| 完全性チェック | check_completeness.js |
| 矛盾検出 | detect_contradictions.js |
| 未解決抽出 | extract_open_questions.js |
| Markdown→JSON | convert_md_to_json.js |
| Notion 整形 | render_notion_page.js |
| Slack 文生成 | compose_slack_message.js |
| 質問銀行更新 | update_question_bank.js |
| 価値計測 | measure_value_realized.js |
| 図種選択 | select_diagram_type.js |
| 図解生成 | compose_diagram.js |
| Mermaid 構文検証 | validate_mermaid.js |
| レイアウト最適化 | optimize_layout.js |
| SVG 書き出し | render_to_svg.js |
| 共通品質ゲート | quality_gate.js |
| agent 間整合検証 | cross_check.js |
| セクション別図解配置 | select_diagrams_per_section.js |
| 非エンジニア対応強制 | enforce_visualization_rules.js |
| セクション必要十分検証 | section_quality_check.js |
| シートテンプレ一括適用 | apply_section_template.js |
| SVG→PNG 変換（Notion 添付用・複数レンダラ自動フォールバック） | render_to_image.js |
| Notion 公開用マニフェスト生成（SVG は全て PNG 化） | prepare_notion_assets.js |
| Notion 添付検証ゲート（PNG 欠損で公開停止） | verify_notion_assets.js |

### assets/

| カテゴリ | 内容 |
|--------|-----|
| skillヒアリングシート/ | 既存シートを参照（assets 上位階層） |
| mermaid-templates/ | Mermaid 12種テンプレート |
| custom-visuals/ | 独自 SVG 8種（numbered-steps / persona-card / before-after / comparison-table / traffic-light / progress-bar / icon-grid / sankey補助） |
| mermaid-samples/ | google-forms-generator 完成例 |

## 引き渡し（skill-creator への契約）

- Markdown 正本: `output/<skill-name-hint>/intake.md` （人間用）
- JSON 副本: `output/<skill-name-hint>/intake.json` （skill-creator 用・スキーマは `references/handoff-contract.md`）
- Notion ページ URL: `output/<skill-name-hint>/notion-url.txt`
- Slack 通知ログ: `output/<skill-name-hint>/slack-log.json`

skill-creator はこの JSON を受け取り Phase 0-0 を簡略化または飛ばせる。
