---
name: completeness-criteria
description: skill-creator へ引き渡してよい完了判定基準
type: reference
---

# 完了判定基準

ヒアリング結果が「skill-creator に渡してよい」状態か機械的に判定する。
`scripts/check_completeness.js` がこの基準で PASS/FAIL を出す。

## 必須項目チェック表（24項目・5軸版）

| # | カテゴリ | 項目 | 判定 |
|---|--------|-----|-----|
| 1 | メタ | skill_name_hint がkebab-case | 正規表現 |
| 2 | メタ | workflow_pattern が A〜E のいずれか | enum |
| 3 | 目的 | purpose.stated が30字以上 | length |
| 4 | 目的 | purpose.excavated が stated と異なる | diff |
| 5 | 目的 | jtbd.when が具体時点 | 時刻/契機含む |
| 6 | 目的 | jtbd.want_to が動詞で開始 | verb |
| 7 | 目的 | jtbd.so_i_can が「次の行動」 | 動詞含む |
| 8 | 目的 | pain_stories が1件以上 | array length >= 1 |
| 9 | プロファイル | technical_level 確定 | enum |
| 10 | プロファイル | role 確定 | string |
| 11 | プロファイル | context 確定 | enum |
| 12 | プロファイル | share_target 確定 | enum |
| 13 | 5軸 | output_target.verified=true | bool |
| 14 | 5軸 | info_source.verified=true | bool |
| 15 | 5軸 | share_target.verified=true | bool |
| 16 | 5軸 | true_problem.verified=true | bool |
| 17 | 5軸 | true_problem.depth が deep | enum |
| 17a | 5軸 | knowledge_assets.verified=true（**MUST**） | bool |
| 17b | 5軸 | needed=true なら existing_sources/external_inputs/tacit_knowledge のいずれか1つ以上充足 | array |
| 18 | 図解 | visualizations が3つ以上 | array length |
| 19 | 図解 | 全 visualization に one_liner（60字以内） | length |
| 20 | 推奨 | recommended_next.mode 確定 | enum |
| 21 | 推奨 | recommended_next.skip_to_phase 確定 | string |
| 22 | 価値 | 時間短縮または品質向上 KPI が数値 | numeric |
| 23 | 雛形 | 最小入力雛形（コピペ可テンプレ）が intake 成果物に含まれる | template_block 存在 |
| 24 | 雛形 | 初回30秒で何ができるかの説明文が intake.md に含まれる | string length >= 50 |

すべて PASS で「完了」。1つでも FAIL があれば未完了。

## 5軸全充足ルール

`five_axes` の5キーすべてで:

- `answer` が空でない
- `verified === true`（Reverse Brief で確認済）
- `depth` が **少なくとも standard 以上**

`true_problem` のみ **deep 必須**。

### ナレッジ資産軸の充足基準（MUST）

`knowledge_assets`:
- `verified === true` 必須
- `needed === false`（不要と明示確認）でも PASS
- `needed === true` の場合は以下のいずれか **1つ以上** を充足:
  - `existing_sources.length >= 1`
  - `external_inputs.length >= 1`
  - `tacit_knowledge.length >= 1`
  - `extraction_pipeline.needed === true`
- `extraction_pipeline.needed === true` のときは `ingest_format` / `analysis_method` / `storage` / `retrieval` 全て埋まること
- `exclusions` は明示的に確認（空配列でもよいが verified=true を要件）

## 深度3段階の意味

| 深度 | 定義 | サンプル |
|-----|-----|--------|
| quick | 1問で得た回答 | 「Sheetsへ」 |
| standard | 2-3問追加で文脈付き | 「セミナー専用フォルダのSheetsへ。終わった後も保管」 |
| deep | 5 Whys 等で真因まで掘った | 「Sheetsで集計→当日朝に参加者リスト確定→受付作業90分削減」 |

## アンチパターン回避チェック

| アンチパターン | 検出シグナル | NG 判定 |
|------------|-----------|------|
| 表層要望のまま | excavated == stated | NG |
| 同意ループ | Reverse Brief 訂正回数 = 0 | 警告（必ずしもNGではない） |
| 抽象度暴走 | jtbd.so_i_can に「色々」「効率化」のみ | NG |
| 完了主義 | open_questions に blocking=true 残存 | NG |
| マジックナンバー | 「だいたい」「いつも」のみで数値ゼロ | NG |
| 共有相手不明 | share_target.answer が空 | NG |

## 判定アルゴリズム

```javascript
function isComplete(intake) {
  const checks = [
    /* 必須22項目 */,
    fourAxesAllVerified(intake),
    trueProblemIsDeep(intake),
    noBlockingOpenQuestions(intake),
    antiPatternsNotMatched(intake)
  ];
  const failed = checks.filter(c => !c.pass);
  return {
    complete: failed.length === 0,
    failed,
    score: (checks.length - failed.length) / checks.length
  };
}
```

## 最小入力雛形セクション（メタフィードバック 2026-05-10）

intake 成果物 `intake.md` の末尾に以下のテンプレート枠を含める:

```markdown
## 最小入力例（コピペ可・初回30秒価値到達）

\`\`\`
（生成スキルに渡す最小サンプル入力）
\`\`\`

実行コマンド:
\`\`\`bash
（コピペで動く起動コマンド）
\`\`\`
```

不在の場合は完了判定 FAIL（項目 23, 24）。

## 部分完了の扱い

`recommended_next.mode` で表現する。

| mode | 条件 |
|------|-----|
| fast-track | 必須22項目全PASS + 類似スキルあり |
| full | 必須22項目全PASS + 類似スキルなし（新規設計が必要） |
| verify-only | 必須22項目PASS率 >= 0.9 |
| 未完了→差戻 | PASS率 < 0.9 |

## サンプル: google-forms-generator 完了時のスナップショット

| カテゴリ | 状態 |
|--------|-----|
| 必須22項目 | 22/22 PASS |
| 5軸 | 全 verified=true（knowledge_assets 含む）、true_problem=deep |
| visualizations | 5図（flowchart, persona-card, comparison-table, icon-grid, before-after） |
| 価値 KPI | 「告知準備時間 90分→10分」（数値あり） |
| recommended_next | fast-track |
| open_questions | 0件 |

→ 完了。skill-creator を fast-track で起動可。
