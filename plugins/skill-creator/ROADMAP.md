# ROADMAP

`skill-creator` plugin の短期 / 中期 / 長期ロードマップ。設計書 33 章 `change-governance` の運用方針に従い、各層は目標・成果物・成功指標 (KPI) を明示する。

## 短期 (本 PR 〜 次 1-2 スプリント)

**目標**: governance/feedback hook を 7 種 target_type へ配線完了し、改善ループを自走させる基盤を確立する。**成果物**: 7 種 hook 配線済み plugin、lessons-learned 自動記録パイプライン、本 CHANGELOG.md の運用開始 (各 PR で Unreleased セクションを更新する運用ルール)。**KPI**: hook 配線カバレッジ 100% (7/7 種)、lessons 自動記録の取りこぼし率 < 5%、CHANGELOG 更新率 100% (governance ラベル付き PR 基準)。

## 中期 (3-6 ヶ月)

**目標**: composition manifest の plugin 横断採用と review→executor の自動チェインにより、改善サイクルを人手介入最小で回す。**成果物**: 全 plugin での `plugin-composition.yaml` 採用、review エージェントから executor エージェントへの自動 handoff 機構、EVALS 結果から rubric 改訂 PR を生成する feedback パイプライン。**KPI**: composition manifest 採用率 100% (全 plugin)、review→executor 自動チェインの収束率 (max 3 周回内) >= 80%、EVALS→rubric PR の月次マージ数 >= 2 本。

## 長期 (6 ヶ月以降)

**目標**: target_type 7 種を composition manifest 上で宣言的に運用し、cross-plugin 依存と dogfooding 状況を可視化する自己改善基盤を確立する。**成果物**: 7 種すべてを宣言できる composition schema、cross-plugin 依存グラフの自動可視化 UI、dogfooding ダッシュボード (自己適用率・rubric 充足率・lessons 反映率)。**KPI**: composition schema 7 種網羅率 100%、依存グラフ生成の自動更新頻度 >= 週次、dogfooding 自己適用率 >= 90%・rubric 充足率 >= 85%。
