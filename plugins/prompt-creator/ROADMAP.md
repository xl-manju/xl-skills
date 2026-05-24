# ROADMAP

`prompt-creator` plugin の短期 / 中期 / 長期ロードマップ。設計書 33 章 `change-governance` の運用方針に従い、各層は目標・成果物・成功指標 (KPI) を明示する。

## 短期 (本 PR 〜 次 1-2 スプリント)

**目標**: skill-creator 仕様準拠化を完遂し、独立 evaluator + ゲート制御 orchestrator を自走させる。**成果物**: 4 SKILL.md commonCore 化 / `plugin-composition.yaml` / Script First (python3) 全面移行 / CI 配線 / 移行スクリプトの正式リネーム (PENDING 解除)。**KPI**: P0 lint 全緑率 100%、design-evaluate overall=PASS 率 >= 90%、PENDING_RENAME 残数 0。

## 中期 (3-6 ヶ月)

**目標**: 7 層プロンプトの冪等更新ループを完成させ、既存プロンプトの肥大化を抑制しながら継続改善を回す。**成果物**: 冪等更新 policy の lint 化 (重複要素検出)、prompt-rubric.json L1 (ドメイン層) の整備、prompt-creator → skill-creator への評価 feedback 自動化。**KPI**: 同一スキルの 2 回目以降更新で要素重複増加率 <= 5%、L1 rubric 採用プロンプト割合 >= 50%、feedback PR 月次マージ >= 1 本。

### Follow-up (elegant-review v2 / 2026-05-24 検出)
- **責務境界の明確化**: `run-prompt-creator-7layer` Phase 1 と `run-prompt-elicit` が同一 agent (`prompt-creator-interview-user`) を呼ぶ二重経路を解消。7layer の Phase 1 を elicit への単純委譲に統合するか、skip 条件を invariant で明文化する。
- **scaffold-prompt.py の Step 明示**: SKILL.md 本文 Steps に scaffold-prompt.py 呼び出し例を 1 行追加し `script_refs` との対応を可視化。
- **`parse_known_args` 統一見直し**: 8 移行スクリプトの未知 flag 黙殺設計を `parse_args() + allow_abbrev=False` の failfast へ転換し、CI でのタイポ検出力を強化。
- **frontmatter コメント正規化**: 7layer SKILL.md の YAML コメント (`# context-budget (CD-005)`) を正式フィールド (`context_budget`) に昇格。
- **shared scripts 表記**: `plugin-composition.yaml` に `shared_scripts` セクションを追加し、`run-prompt-create` から `run-prompt-creator-7layer/scripts/` への cross-skill 参照意図を明示。

## 長期 (6 ヶ月以降)

**目標**: 7 層構造を他プラグインへ横展開し、SubAgent / Skill 全体のプロンプト品質を底上げする。**成果物**: 7 層 schema の plugin 横断採用、cross-plugin プロンプト品質ダッシュボード、prompt-creator 自体の dogfooding (自プロンプトを自評価)。**KPI**: 7 層採用プラグイン数 >= 5、ダッシュボード evaluator pass 率 >= 85%、dogfooding 自己適用率 >= 90%。
