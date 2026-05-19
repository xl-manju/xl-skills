---
name: run-migrate-audit
description: 既存 CLAUDE.md/prompt 集を Skill 群へ移行したいとき、棚卸し分類を機械化したいときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash(python3 *), Grep, Glob]
kind: run
owner: {{owner}}
since: 2026-05-19
# doc/21 source-traceability
source: doc/ClaudeCodeスキルの設計書/20-migration-path.md
source-tier: article-text
last-audited: 2026-05-19
audit-trigger: source-update
role_suffix: orchestrator
hierarchy_level: L1
pair: assign-skill-design-evaluator
rubric_refs:
  - ref-skill-design-rubric
reference_refs:
  - ref-claude-code-skill-spec
  - ref-skill-naming-convention
  - ref-cross-platform-runtime
---

# run-migrate-audit

## Purpose & Output Contract
肥大化した prompt / CLAUDE.md / docs を doc/20-migration-path.md の 8 区分に
自動分類し、移行先 Skill 候補（ref-* / run-* / wrap-* / assign-* / delegate-*）と
Hook/CI/CLI 化候補を JSON で出力する。

### 出力 contract
`.claude/handoff/migrate-audit-<session>.json`:
```json
{
  "input_file": "{{path}}",
  "sections": [
    {
      "heading": "...",
      "classification": "always-on|ref|run|wrap|assign|delegate|hook|docs",
      "rationale": "...",
      "suggested_skill_name": "ref-..."
    }
  ],
  "summary": {
    "ref_candidates": 0,
    "run_candidates": 0,
    "hook_candidates": 0,
    "kept_in_claude_md": 0
  }
}
```

## Boundary
- **入口**: 既存 CLAUDE.md / prompt ファイルパス（複数可）
- **出口**: 分類 JSON + 各候補に対する空 SKILL.md スケルトン提案
- **非責務**: 実際の SKILL.md 生成 → `run-build-skill` に委譲

## Key Rules
1. 入力を物理削除しない（思考リセット ≠ ファイル削除）
2. doc/20 Step 1 の 8 区分以外を勝手に作らない
3. **抽象化レベル**: 入力中の具体的なプロジェクト名 / ドメイン語は `{{var}}` 化して提案する
4. 分類根拠を 1 行以内で明示する（後段 evaluator が judge できるよう）

## Steps

### Step 1: 入力棚卸し
```bash
python3 creator-kit/scripts/migrate/audit.py \
  --input <CLAUDE.md path> \
  --output .claude/handoff/migrate-audit-$(date +%s).json
```

### Step 2: 分類結果のレビュー
ユーザーに JSON を提示し、誤分類があれば手動修正。

### Step 3: SKILL.md スケルトン生成提案
分類結果から `run-build-skill` 起動 brief を生成:
```bash
python3 creator-kit/scripts/migrate/to-brief.py \
  --audit-json .claude/handoff/migrate-audit-<session>.json
```

### Step 4: Hook/CI 昇格候補の抽出
Gotchas 累積閾値超え → `frontmatter lint -> Hook -> CI -> CLI` の昇格パスを示す。

### Step 5: 移行後 lint
```bash
python3 creator-kit/scripts/lint-dependency-direction.py --skills-dir .claude/skills/
```

## Gotchas
- 中間状態（Step1〜4 部分完了）で lint を fail させない（`--allow-partial` モード）
- 具体ドメイン語を Skill 名に焼き込まない（横展開不能になる）
- `kept_in_claude_md` が 0 になったら警告（CLAUDE.md は repo identity 等で最低限残すべき）

## Additional Resources
- 設計書 20 章 全 7 ステップ
- `references/classification-rules.md` — 8 区分判定ルール
- `references/abstraction-checklist.md` — 具体名 → 変数化の判定基準
