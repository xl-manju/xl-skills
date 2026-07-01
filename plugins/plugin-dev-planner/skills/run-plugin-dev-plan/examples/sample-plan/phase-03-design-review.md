---
id: P03
phase_number: 3
phase_name: design-review
category: レビュー
prev_phase: 2
next_phase: 4
status: 未実施
gate_type: design-gate
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P03 — design-review (設計レビューゲート)

## 目的
P02 の設計 (inventory と envelope draft) を design-gate として elegant-review C1-C4 で審査し、proposer≠approver の原則で独立レビュアが通過判定を下す。設計段階の欠陥を実装前に止める gate フェーズ。

## 実行タスク
- 設計成果物 (`component-inventory.json` / `envelope-draft/plugin.json`) を独立 context のレビュアへ渡す。
- elegant-review C1 (矛盾なし) / C2 (漏れなし) / C3 (整合性) / C4 (依存整合) を評価する。
- 単一 skill への退化や不要な水増しが無いか (5 種写像の妥当性) を確認し、指摘があれば P02 へ差し戻す。

## 成果物
- design-gate の判定記録 (C1-C4 全 PASS / 差し戻し理由)。

## 完了条件
- elegant-review C1-C4 が全 PASS し、proposer と異なる approver が設計を承認している。
- 差し戻しが解消され後続フェーズへ進める状態になっている。
