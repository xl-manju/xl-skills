# Open-world system-design knowledge lifecycle

## 目的

現行の知識領域を閉じた完全リストと誤認せず、プロジェクトの目的・制約・技術変化から未知または追加の手段知識を発見し、一次資料で裏付け、目的適合で選べる深さまで育てる。

## 責務境界

- C04 (`ref-system-design-knowledge`): seed、card schema、catalog、発見・昇格・鮮度監査の規則をReadで返す。ネットワーク検索、candidate書込、curated更新を実行しない。
- C01 (`run-system-spec-elicit`): ヒアリング中の未知語、未決定事項、goal/constraintとのgapを発見シグナルとして記録し、project candidateを所有する。
- C02 (`run-system-spec-doc-fetch`): candidateごとに公式publisher/host、一次資料、version/updated、checked_atを取得・再照合する。
- 保守担当: project candidateをレビューし、汎用性・重複・一次資料・深度・ライセンスを確認してC04 curated catalogへ昇格する。自動昇格は禁止。

## Lifecycle

1. **Discover**: U1-U9、未決定事項、カテゴリmatrix、障害/非機能要件、既存カードの `related_topics` から不足知識を候補化する。現行6領域は探索開始点であり探索終了条件ではない。
2. **Qualify**: 公式標準、仕様、原著者、標準化団体、公式vendor docsを優先する。検索結果要約や二次ブログだけの候補は `unqualified` のまま仕様判断に使わない。書籍由来は書名・著者・版・年を記録する。
3. **Deepen**: `knowledge-card.schema.json` の `purpose/background/problems/core_concepts/applies_when/does_not_apply_when/tradeoffs/failure_modes/goal_contribution/primary_sources/freshness` を埋める。名称と短い要点だけでは完了しない。
4. **Goal map**: candidateが資する `goal_ids`、守る `constraint_ids`、解決するproblem、採用しない条件を明示する。goalに結べない候補は探索メモに留める。
5. **Project candidate**: C01のproject-local stateへ `candidate` として保存する。推奨の前にC02のqualificationを通し、事実・推論・ユーザー決定を分離する。
6. **Curated promotion**: 複数projectへ再利用可能、既存カードと非重複、深度必須欄充足、一次資料あり、freshness policyあり、担当者承認済みの場合だけC04へ昇格する。類似カードは新設せず既存へ統合する。
7. **Freshness audit**: `review_by` またはtrigger到来時に一次資料を再照合する。破壊的変更、標準改訂、security advisory、vendor EOL、価格/無料枠変更は即時trigger。未確認は `stale` と明示し、最新推奨の根拠に使わない。

## Project candidate 最小形

```json
{
  "knowledge_id": "candidate-example",
  "status": "project-candidate",
  "discovery_signal": "未決定の認証方式",
  "goal_ids": ["G1"],
  "constraint_ids": ["budget-zero"],
  "card": {"$ref": "knowledge-card.schema.json"},
  "qualification": {
    "official_or_primary": true,
    "checked_at": "RFC3339",
    "evidence_refs": ["target-id"]
  },
  "promotion": {"decision": "pending", "reviewer": null}
}
```

## 停止条件

- 候補の各必須深度欄が具体的で、同義反復や「適宜検討」だけでない。
- 一次資料と鮮度が追跡可能で、goal/constraintへ結ばれている。
- 適用条件と非適用条件の両方があり、万能解として提示されていない。
- project candidateとcurated cardの境界、昇格判断、重複統合先が明示されている。

