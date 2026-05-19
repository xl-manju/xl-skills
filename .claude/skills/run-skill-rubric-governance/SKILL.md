---
name: run-skill-rubric-governance
description: rubric変更を提案するとき、rubric改正を施行するときに使う。
disable-model-invocation: false
allowed-tools: [Read, Write, Edit, Bash(python3 *), Bash(git *)]
kind: run
owner: team-skills
since: 2026-05-17
effect: local-artifact
---

# run-skill-rubric-governance

## Purpose & Output Contract

`ref-skill-design-rubric/rubric.json` の改正 Runbook（27章）。
提案 → 影響評価 → 猶予期間 → 発効 の4フェーズを1本のワークフローで管理。

**入力**: `templates/proposal.json` を埋めた改正提案ファイル
**出力**: rubric.json のPR、 governance log（`$SKILL_DIR/log/*.jsonl`）

## Key Rules

1. **直接編集禁止**: rubric.json は本Runbook経由でのみ更新。
2. **semver**: minor=緩和（しきい値↓、ルール削除）、major=厳格化（ルール追加、weight↑）、patch=文言のみ。
3. **猶予期間**: major は最低14日、minor は7日、patch は即時可。
4. **影響評価必須**: `scripts/diff-rubric-impact.py` で過去 eval-log の合否変動率を測る。
5. **承認ボード**: 提案者 / 第三者レビュア / 承認者 / tooling役 の4ロール（`references/governance-board.md`）。

## Steps

### Step 0: 出力先解決

```bash
# SKILL_DIR を確立する (governance log / scripts/ の親ディレクトリ)
source creator-kit/scripts/resolve-skill-dirs.sh
# SKILL_DIR が run-build-skill を指すため、本スキル用に上書き:
SKILL_DIR="${CLAUDE_SKILL_DIR:-}"
if [ -z "$SKILL_DIR" ]; then
  if [ -f "creator-kit/skills/run-skill-rubric-governance/scripts/lint-rubric-violation.py" ]; then
    SKILL_DIR="creator-kit/skills/run-skill-rubric-governance"
  elif [ -f ".claude/skills/run-skill-rubric-governance/scripts/lint-rubric-violation.py" ]; then
    SKILL_DIR=".claude/skills/run-skill-rubric-governance"
  fi
fi
```

### Step 1: 提案

`templates/proposal.json` をコピーして埋める:
- rule_id, change_type (add/modify/remove), bump (major/minor/patch), rationale, sunset_days

### Step 2: 影響評価

```bash
python3 "$SKILL_DIR/scripts/lint-rubric-violation.py" \
  --logs "$SKILL_DIR/log" \
  --rule "$RULE_ID"

python3 "$SKILL_DIR/scripts/diff-rubric-impact.py" \
  --proposal proposal.json --logs "$SKILL_DIR/log"
```

合否変動率が 30% 超なら major 強制昇格。

### Step 3: 猶予期間アナウンス

- governance log にエントリ追加（jsonl 1行）
- `aliases` 的に旧ルールを残し warning にダウングレード（severity→low）

### Step 4: 発効

- `ref-skill-design-rubric/rubric.json` を編集
- `rubric_version` を bump（semver）
- `assign-skill-design-evaluator/references/rubric.json` を同期（deep-merge upstream更新）
- **版ずれ検証**: `python3 creator-kit/scripts/check-rubric-sync.py` を実行し
  exit 0（OK）であることを必ず確認。`RUBRIC_DRIFT:` で落ちた場合は commit 前に
  派生 rubric を再同期すること。
- `git commit` し governance log を closed に

## Gotchas

- **patchで内容変更は禁則**: 文言のみ。閾値や severity 変更は最低 minor。
- **assign 側 override をrebaseし忘れる事故**: deep-merge の most-specific-wins が壊れる（29章）。
- **eval-log がない**: 影響評価できないので `diff-rubric-impact.py` は exit 2 でフェイルセーフ。
- **緊急パッチ**: high severity の誤検出固定は patch 例外（log に `emergency: true`）。

## Additional Resources

- `templates/proposal.json` — 改正提案テンプレ
- `scripts/lint-rubric-violation.py` — 違反率集計
- `scripts/diff-rubric-impact.py` — 影響評価
- `references/governance-board.md` — ボード構成
- `references/version-rules.md` — semver規約
- 27章: `xl-skills/doc/スキルの設計書/27-rubric-governance-runbook.md`
- `creator-kit/scripts/resolve-skill-dirs.sh` — SKILL_DIR 解決スクリプト
