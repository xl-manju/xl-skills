---
name: run-prompt-creator-7layer
description: SubAgent向け7層プロンプトを生成・更新するとき、Prompt Templates/Self-Evaluation を充填するときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[--responsibility-id <R-id>] [--output <path>] [--target-agent <path>] [--skill-brief <path>] [--format yaml|md|json|xml] [--inject-sections <list>]"
arguments: [responsibility_id, output, target_agent, skill_brief, format, inject_sections]
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash(node *)
  - Bash(python3 *)
  - AskUserQuestion
kind: run
effect: local-artifact
owner: team-platform
since: 2026-05-20
script_refs:
  - ../../scripts/merge_layers.js
  - ../../scripts/validate_prompt.js
  - ../../scripts/convert_format.js
  - ../../scripts/verify_completeness.js
  - ../../scripts/generate_sheet.js
  - ../../scripts/validate_sheet.js
  - ../../scripts/scaffold_prompt.js
  - ../../scripts/log_usage.js
reference_refs:
  - references/resource-map.yaml
  - references/seven-layer-format.md
  - references/quality-criteria.md
  - references/workflow-guide.md
  - references/writing-style-principles.md
  - references/prompt-sheet-template.md
# context-budget (CD-005): 章一括ロード禁止 / max-reference-chapters: 3
source: doc/prompt-creator/  # 4 scripts (generate_sheet/validate_sheet/scaffold_prompt/log_usage) + LOGS.md を含めて再取り込み済み
source-tier: internal
last-audited: 2026-05-20
audit-trigger: quarterly
responsibility_refs:
  - prompts/main.md
schema_refs:
  - schemas/output.schema.json
  - schemas/hearing-result.schema.json
manifest: workflow-manifest.json
---

# run-prompt-creator-7layer

> doc/prompt-creator/ を skill-creator 仕様準拠で plugins/prompt-creator/ へ移植した正本。SKILL.md/SubAgent 各 300 行以下、Progressive Disclosure 厳守。

## Purpose & Output Contract

skill-brief またはユーザー要求から **7 層プロンプト** (Role/Context/Principles/Workflow/Constraints/Output/Evaluation) を生成し、SubAgent .md の Prompt Templates / Self-Evaluation を自動充填。

**入力**: `--responsibility-id <R-id>` (skill-local-v1 既定で必須、`brief.responsibilities[].id` と 1:1) / `--output <path>` (省略時は規約パス自動解決) / `--target-agent` (任意、owner_agent がある場合のみ注入) / `--skill-brief` / `--format` (yaml 既定) / `--inject-sections` (既定: "Prompt Templates,Self-Evaluation")

**出力 (path_convention で切替)**:
- `skill-local-v1` (既定): `plugins/<plugin>/skills/<skill>/prompts/<R-id>.yaml` — `references/prompt-placement-convention.md` (skill-creator 側) 準拠、`validate-build-trace.py` が正規表現と sha256 で機械検証
- `agents-legacy` (`--responsibility-id` 省略時のみ): `plugins/<plugin>/agents/prompts/<role>.yaml` — 後方互換、brief.responsibilities[] が空の ref/wrap/delegate 用
- 対象 SubAgent .md への自動注入 (Edit、owner_agent がある場合のみ)
- `eval-log/prompt-creator-trace.json` (必須フィールド: `path_convention`, `responsibility_id`, `layer_yaml_path`, `sha256`)

**完了条件**: `verify_completeness.js` PASS + `validate_prompt.js` PASS + `lint-agent-prompt-section.py` PASS。

## Key Rules

1. **Script First**: 決定論的処理は Node スクリプト。LLM は意味判断のみ。
2. **1 Layer = 1 出力**: 一括生成禁止、Layer 単位生成→merge。
3. **質ベース判定**: 「実行可能か/検証可能か」。数量カウント禁止。
4. **Progressive Disclosure**: `references/` は Phase 直前で必要分のみ読込。
5. **目的+背景併記**: 全ルール/制約に併記 (`writing-style-principles.md`)。
6. **300 行制約**: SKILL.md / SubAgent 各 300 行以下。
7. **ループ整合性**: run-build-skill 呼出時は `lint-agent-prompt-section.py` 通過必須。FAIL 時最大 3 回自律修正→未達なら orchestrator 差戻。
8. **責務境界**: 担当は Prompt Templates / Self-Evaluation の 2 セクションのみ。9 セクション骨格は run-build-skill 責務。
9. **Markdown 既定**: prompt 出力は **Markdown 形式 (`.md`) を既定**とし、骨格は `references/seven-layer-markdown-template.md` を写経する (`.yaml` は legacy フォールバックのみ許容、新規作成禁止)。

## End-to-End Flow

```
Phase 1 interview-user (3-5問+優先度)        [LLM] brief あれば skip 可
   ↓
Phase 2 Prompt 作成シート生成+導出確認       [script→LLM]
   ↓
Phase 3 フォーマット選択 (yaml/md/json/xml)  [LLM] ループ時 skip
   ↓
Phase 4-A Layer 単位生成 (L1→L7)             [script→LLM] generate-prompt
   ↓
Phase 4-B 4 パス品質レビュー                 [script→LLM] review-prompt
   ↓
Phase 4-C 自律改善 (最大 3 回反復)           [LLM]
   ↓
Phase 4-D フォーマット変換+注入             [script + Write/Edit]
   ↓
Phase 5 戻り検証 lint-agent-prompt-section.py
```

詳細: `references/workflow-guide.md`

## Steps

### Phase 1: ヒアリング

SubAgent: `prompt-creator-interview-user`

brief 既知部分は重複質問せず差分のみ。出力: `eval-log/prompt-creator-trace.json#phase1`。

### Phase 2: シート生成

```bash
node scripts/validate_prompt.js --input eval-log/prompt-creator-trace.json --phase hearing
```

AI 推定は導出確認→ユーザー承認。

### Phase 3: フォーマット選択

ループ呼出時 `--format yaml` 既定で skip。それ以外は AskUserQuestion。

### Phase 4-A: Layer 単位生成

SubAgent: `prompt-creator-generate-prompt`

Layer 役割 (Clean Architecture / DDD):

| Layer | 役割 | DDD |
|---|---|---|
| L1 Role | Enterprise Rules | Value Objects |
| L2 Context | Entities | ユビキタス言語 |
| L3 Principles | Frameworks | ACL |
| L4 Workflow | App Rules | 横断的関心事 |
| L5 Constraints | Use Cases | 境界 Context |
| L6 Output | Controllers | Saga |
| L7 Evaluation | Adapters | App Service |

依存方向: L7→L6→...→L1。詳細: `references/seven-layer-format.md`。

合算: `node scripts/merge_layers.js --layers tmp/prompt-layers/ --output tmp/prompt.yaml`

### Phase 4-B: 4 パスレビュー

SubAgent: `prompt-creator-review-prompt`

Pass 0 (動的基準生成) → Pass 1 網羅性 → Pass 2 整合性 → Pass 3 深度 → Pass 4 実用性。詳細: `references/quality-criteria.md`。

### Phase 4-C: 自律改善

```bash
node scripts/verify_completeness.js --input tmp/prompt.yaml
```

未充足あれば generate-prompt 再起動 (最大 3 回)。

### Phase 4-D: 変換+注入

```bash
node scripts/convert_format.js --input tmp/prompt.yaml --format ${FORMAT} --output ${OUT}
```

ループ呼出時は対象 SubAgent .md へ Edit 注入。

### Phase 5: 戻り検証

```bash
python3 plugins/skill-governance-lint/scripts/lint-agent-prompt-section.py "${TARGET_AGENT}"
```

exit 0 でループ完了。FAIL は Phase 4-A 再起動 (最大 3 周)。

実行後 `node scripts/log_usage.js --result <success|fail> --phase "Phase 5"` で `LOGS.md` に記録 (利用統計/失敗パターン蓄積)。

## Gotchas

1. 7 層一括生成禁止 (Layer 単位→merge)。
2. 「3 つ以上」型禁止→質ベース判定。
3. 長文フィールド禁止 (要素原子性、1 値 50 文字目安)。
4. package.json 不持込 → YAML は手書きシリアライズ。
5. doc/prompt-creator/ は deprecated、正本は plugins/。
6. 自律修正 3 回上限、超過時 orchestrator 差戻。
7. 9 セクション骨格生成禁止 (run-build-skill 責務)。

## Additional Resources

- `references/seven-layer-format.md` — 7 層 YAML 正本テンプレ (Phase 4-A 直前読込)
- `references/workflow-guide.md` — Phase 1-4 詳細
- `references/quality-criteria.md` — 4 パス評価基準
- `references/writing-style-principles.md` — 記述スタイル
- `references/prompt-sheet-template.md` — シート項目
- `schemas/hearing-result.schema.json` — Phase 1 スキーマ
- 子 agent: `plugins/prompt-creator/agents/prompt-creator-{interview-user,generate-prompt,review-prompt}.md`
- caller: `plugins/skill-creator/skills/run-build-skill` (Step 7.5)
- 戻り検証: `plugins/skill-governance-lint/scripts/lint-agent-prompt-section.py`
