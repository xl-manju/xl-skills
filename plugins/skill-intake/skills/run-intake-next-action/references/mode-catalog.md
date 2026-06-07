# Mode Catalog (next-action)

| mode | 名称 | skill-creator 渡し先 phase |
|--|--|--|
| A | 完全新規 | Phase 1 (kickoff) |
| B | 既存類似 80%+ | Phase 2 (existing reuse) |
| C | プロンプト改善のみ | Phase 7 (prompt-only update) |
| D | マルチスキル分離疑い | Phase 1 (split first) |
| E | 判定不能 | Phase 1 (re-intake) |

> **軸の独立性**: ここで定義する `mode` の A-E は「skill-creator への次アクション判定」軸であり、Notion 正本 (`notion-db-schema.json`) の **ワークフロー** (A 単体 / B 自動収集配信 / …) や **パターン** とは **独立した分類** である。記号 (A-E) が一致しても意味は別軸なので相互に読み替えてはならない。
