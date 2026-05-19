# Orchestration Flow: Phase1 → Phase2 → Phase3

```
[target_type, target_path]
        │
        ▼
┌─────────────────────────────────┐
│ Phase 1: 思考リセット俯瞰        │
│ Agent 1 elegant-reset-observer  │
│ → raw_observations.json         │
└─────────────────────────────────┘
        │
        ├──────────┬──────────┐  (並列起動)
        ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Agent 2  │ │ Agent 3  │ │ Agent 4  │
│ 論理+構造│ │ メタ+発想│ │ Sys+戦略 │
│ 9思考法  │ │ 9思考法  │ │ 12思考法 │
└──────────┘ └──────────┘ └──────────┘
        │          │          │
        └──────────┴──────────┘
                   ▼
        scripts/build-paradigm-scorecard.py
                   │
                   ▼
        scripts/validate-paradigm-coverage.py (==30)
                   │
                   ▼
┌─────────────────────────────────┐
│ Phase 3: 改善実行                │
│ Agent 5 elegant-improvement-... │
│  - findings重大度順              │
│  - C1〜C4 FAIL 項目にパッチ      │
│  - 4条件 PASS or loop<=3 で復帰  │
└─────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │ ALL PASS?           │
        ├── yes → 完了        │
        └── no  → Phase2 再実行│
                              (max 3 loops, 超過時 escalate)
```

## ループ制御
- max_loops = 3
- 各ループで Agent5 のパッチを適用後、Phase2 を再実行
- 3ループでも 4条件未達なら `escalate-to-human` イベント発火

## ファイル受け渡し
- Phase1出力: `/tmp/elegant-review/phase1.json`
- Phase2出力: `/tmp/elegant-review/phase2-agent{2,3,4}.json`
- 集約: `/tmp/elegant-review/findings.json`
- 最終: 対象ディレクトリ直下に `findings.json` + `review-<type>.md`
