# scripts/ — 実行ガイド

このディレクトリのスクリプトは Claude Code / Codex / 手動 CLI の 3 経路で動く。
正本契約は `../references/execution-contract.md`。

## クイック実行

```bash
# Claude Code（Bash ツール経由・自動）
node scripts/quality_gate.js --agent interviewer --in output/foo/sheet.json

# Claude Code（ユーザーが手動で実行）
!node scripts/quality_gate.js --agent interviewer --in output/foo/sheet.json

# Codex（shell 経由）
node scripts/quality_gate.js --agent interviewer --in output/foo/sheet.json

# 手動 CLI（shebang 直叩き）
./scripts/quality_gate.js --agent interviewer --in output/foo/sheet.json
```

## 前提
- Node.js ≥ 18（`node --version` で確認）
- cwd はスキルルート（`.../skill-intake-interviewer/`）
- 全スクリプトは shebang 付き・実行権限付与済み
- 依存は `package.json` 参照（標準ライブラリのみで動作するものが大半）

## スクリプト一覧と役割

| スクリプト | 役割 | exit code |
|-----------|-----|----------|
| validate_intake.js | JSON スキーマ検証 | 0/1/2 |
| check_completeness.js | 5軸完全性チェック | 0/1 |
| detect_contradictions.js | 矛盾検出 | 0/1 |
| extract_open_questions.js | 未解決抽出 | 0 |
| convert_md_to_json.js | Markdown→JSON | 0/2 |
| render_notion_page.js | Notion ページ整形 | 0/1 |
| compose_slack_message.js | Slack 文生成 | 0 |
| update_question_bank.js | 質問銀行更新 | 0/1 |
| measure_value_realized.js | 価値計測 | 0 |
| select_diagram_type.js | 図種選択 | 0 |
| select_diagrams_per_section.js | セクション別図解配置 | 0 |
| compose_diagram.js | 図解生成 | 0/1 |
| validate_mermaid.js | Mermaid 構文検証 | 0/1 |
| optimize_layout.js | レイアウト最適化 | 0 |
| render_to_svg.js | SVG 書き出し | 0/1/3 |
| render_to_image.js | SVG→PNG（Notion 添付用） | 0/1/3 |
| prepare_notion_assets.js | Notion 公開用マニフェスト | 0/1 |
| verify_notion_assets.js | Notion 添付検証ゲート（PNG 欠損で停止） | 0/1 |
| quality_gate.js | 共通品質ゲート | 0/1 |
| cross_check.js | agent 間整合検証 | 0/1 |
| enforce_visualization_rules.js | 図解マスト要件強制 | 0/1 |
| section_quality_check.js | セクション必要十分検証 | 0/1 |
| apply_section_template.js | シートテンプレ一括適用 | 0 |

## エラー時のフォールバック

`exit code = 3 (DEPENDENCY_ERROR)` または `node` 不在時は LLM ソフト判定にフォールバックする。
詳細は `../references/execution-contract.md` の「LLM フォールバック」節。

## 新規環境セットアップ

```bash
cd .claude/skills/skill-intake-interviewer
node --version            # ≥18 確認
chmod +x scripts/*.js     # クローン直後のみ
```
