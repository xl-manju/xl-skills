---
name: assign-skill-design-evaluator
description: 生成済みSKILL.mdを評価したいとき、rubric準拠を確認したいときに使う。
user-invocable: false
context: fork
agent: general-purpose
allowed-tools: [Read, Grep, Bash(python3 *)]
pair: run-build-skill
kind: assign
effect: conversation-output
role_suffix: evaluator
owner: team-skills
since: 2026-05-17
rubric_refs:
  - ref-skill-design-rubric
  - references/rubric.json
reference_refs:
  - references/evaluator-contract.md
script_refs:
  - scripts/render-findings-score.py
merge_strategy: deep-merge
conflict_policy: most-specific-wins
---

# assign-skill-design-evaluator

> ※ creator-kit Phase 0 移行中は `creator-kit/skills/` が正本、`.claude/skills/` への配置は派生。本SKILL.mdは両配置で動作するよう self-relative パスを使用。

## Purpose & Output Contract

生成済みSkillをrubricで採点し、構造化JSONを返す評価専用Skill。
forkコンテキストで動き、生成本体（run-build-skill）と context を共有しない。

**入力**: `target` = SKILL.md のパス もしくは スキルディレクトリ
**出力（STDOUT、JSON 1オブジェクト）**:
```json
{
  "rubric_id": "skill-design",
  "rubric_version": "1.0.0",
  "rubric_hash": "<sha256:rubric.json>",
  "target": "<path>",
  "score": 87,
  "threshold": 80,
  "passed": true,
  "findings": [
    {"id":"FM-003","severity":"medium","message":"trigger count=4 > 3","loc":"frontmatter.description"}
  ]
}
```

**禁則**: 生成・修正を行わない。Write/Edit toolは持たない。`pair: run-build-skill` が修正担当。

## Key Rules

1. **Goodhart対策**: 採点者は被採点物を改変しない（09章）。
2. **rubric は 1ファイル正本**: `ref-skill-design-rubric/rubric.json` を upstream とし、本Skill側 `references/rubric.json` は deep-merge override（29章）。
3. **TODO(human)残置**: BD-004 は人間判断待ち。検出時は finding severity=low で `pending_human` を立てる。
4. **severity weights固定**: high -20 / medium -10 / low -3、初期 100。負値は 0 にクランプ。
5. **rubric_hash必須**: 出力JSONに rubric.json の sha256 を載せる（再現性、27章）。

## Steps

### Step 1: rubric ロード

```bash
# self-relative: SKILL.md と同階層の scripts/ / references/ を解決。
# CLAUDE_SKILL_DIR が未設定なら creator-kit / .claude 両配置を fallback で探索。
SKILL_DIR="${CLAUDE_SKILL_DIR:-}"
if [ -z "$SKILL_DIR" ]; then
  if [ -f "creator-kit/skills/assign-skill-design-evaluator/scripts/render-findings-score.py" ]; then
    SKILL_DIR="creator-kit/skills/assign-skill-design-evaluator"
  elif [ -f ".claude/skills/assign-skill-design-evaluator/scripts/render-findings-score.py" ]; then
    SKILL_DIR=".claude/skills/assign-skill-design-evaluator"
  else
    SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
  fi
fi
python3 "$SKILL_DIR/scripts/render-findings-score.py" \
  --rubric "$SKILL_DIR/references/rubric.json" \
  --target "$TARGET" --emit-hash
```

`references/rubric.json` は `ref-skill-design-rubric/rubric.json` を継承（merge_strategy: deep-merge）。

### Step 2: 静的検査の実行

各ルールについて Read / Grep / lint-* スクリプト で findings を集める:

- FM-001..005: frontmatter検査（`validate-frontmatter.py`）
- BD-001..004: 本文検査（Output contract / Gotchas / 行数 / BD-004=TODO(human)）
- NM-001..003: 命名/構造（`lint-skill-name.py`, `lint-skill-tree.py`）
- PD-001: Progressive Disclosure（本文100行超なら references/ 必須）
- RG-001: rubric_hash の埋め込み

### Step 3: スコア計算

`render-findings-score.py` に findings リストを渡し、severity weight で減点。

### Step 4: JSON出力

`references/evaluator-contract.md` のスキーマ通りに STDOUT 1行で出す。
threshold 未達なら `passed=false`。run-build-skill が `findings[*].message` を元に再生成する。

## Gotchas

- **rubric.json内のTODO(human)はscoreに反映しない**: `pending_human` 配列に別建て。
- **forkでも /tmp は永続しない**: 中間ファイルは `--target` 内に置かない。STDOUT返却のみ。
- **stdlibのみ**: PyYAML不可。`scripts/render-findings-score.py` は標準ライブラリ `json` で `rubric.json` を読む。
- **rubric_refs の most-specific-wins**: 本Skill側で override したルールが優先（29章）。

## Additional Resources

- `references/rubric.json` — 機械可読rubric（BD-004 に TODO(human)あり）
- `references/evaluator-contract.md` — 出力JSONスキーマ・禁則
- `scripts/render-findings-score.py` — findings→score計算
- upstream: `ref-skill-design-rubric/rubric.json`
