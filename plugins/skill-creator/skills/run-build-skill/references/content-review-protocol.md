# 内容 adequacy 検査プロトコル (Step 12 content-review)

機械 lint だけでは「ひな形通り」だけ確認で内容空虚を素通りさせる欠陥がある。
本プロトコルは **LLM 評価 → verdict 成果物 → 機械検査** の 3 段リレーで「内容の良さ」を build harness に組み込む。

## 役割境界 (機械 vs LLM)

| 層 | 検査対象 | 実行場所 | 実装 |
|----|---------|---------|------|
| 機械層 | ファイル構造 / frontmatter / 命名 / 行数 / symlink drift / **verdict json の存在と PASS** | CI + pre-push | lint 群 + `lint-content-review.py` |
| LLM 層 | **内容 adequacy** (ユーザー要望が SKILL.md に最適反映されているか / 30 思考法 elegance / rubric 規範) | **ローカル Claude Code のみ** | `run-elegant-review` + `assign-skill-design-evaluator` SubAgent |

リモート CI で LLM を起動しない (API 課金・所要時間回避)。ローカルで評価して json を commit し、CI は存在のみ機械検査する。

## build 完了直後の必須実行 (default-ON)

新規/更新 build 完了直後、対象 skill ごとに以下 2 評価をローカルで起動する:

### 1. elegance review (30 思考法 × 4 条件)

```
Agent({
  subagent_type: "elegant-improvement-executor",
  prompt: "<plugin>/<skill> を 30 思考法 4 条件で検証。max_iter=3。
    verdict json を eval-log/<plugin>/<skill>/content-review/elegance-verdict.json に
    schemas/content-review-verdict.schema.json 準拠で保存すること。"
})
```

### 2. rubric review (規範採点)

```
Agent({
  subagent_type: "assign-skill-design-evaluator",
  prompt: "<plugin>/<skill> を rubric (ref-skill-design-rubric) で採点。
    verdict json を eval-log/<plugin>/<skill>/content-review/rubric-verdict.json に
    schemas/content-review-verdict.schema.json 準拠で保存すること。"
})
```

## verdict 成果物

`schemas/content-review-verdict.schema.json` 準拠。最小:

```json
{
  "target": {"plugin": "skill-foo", "skill": "run-bar", "skill_md_sha256": "..."},
  "review_kind": "elegance",
  "verdict": "PASS",
  "reviewer": "elegant-improvement-executor",
  "reviewed_at": "2026-05-26T12:00:00Z",
  "iterations": 2
}
```

## 機械検査 (CI / pre-push)

`scripts/lint-content-review.py --changed-only --base origin/main`:

- `git diff origin/main...HEAD` から `plugins/*/skills/*/SKILL.md` 変更を抽出
- 各変更 skill について `eval-log/<plugin>/<skill>/content-review/{elegance,rubric}-verdict.json` の存在 + `verdict=="PASS"` を検査
- skill-creator 自身 / `kind: ref` / symlink skill は対象外 (内容評価非該当)
- 違反時 exit 1 → merge ブロック

## skip / opt-out

- `brief.skip_content_review: true` または CLI `--skip-content-review` を build 時に明示時のみ skip
- 必ず `trace.layer_decisions` に理由記録 (例: 「typo 修正のみで内容変更なし」)
- skip した skill は `git diff` で SKILL.md 変更が出ない場合のみ整合 (内容変更があれば必ず評価する)
- ローカルで skip 通そうとしてもリモート CI が成果物不在で block する (二重防御)

## ループ until pass

verdict=FAIL の場合:
- AI が指摘内容に従い SKILL.md / references を改善
- 再評価して PASS まで反復 (max_iter=3)
- max_iter 到達で INCOMPLETE → `human_review_required: true` で停止 (force_pass 禁止)

## 関連

- `workflow-manifest.json` phase `content-review` (step 12, default_on: true)
- `schemas/content-review-verdict.schema.json`
- `/scripts/lint-content-review.py` (top-level)
- `plugins/skill-creator/skills/run-elegant-review/`
- `plugins/skill-creator/skills/assign-skill-design-evaluator/`
- `ref-skill-design-rubric`
