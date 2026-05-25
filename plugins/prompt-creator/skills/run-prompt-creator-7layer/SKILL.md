---
name: run-prompt-creator-7layer
description: 7 層構造プロンプトを生成・更新するとき、owner_agent 向けに Prompt Templates/Self-Evaluation を充填するときに使う。
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
  - Bash(python3 *)
  - AskUserQuestion
kind: run
version: 2.1.0
effect: local-artifact
owner: team-platform
contract:
  intent: ユーザー要求またはヒアリング結果から、エンドユーザー向け成果物としての 7 層構造プロンプトを生成するため、Layer 単位生成 worker を提供する。
  interface:
    inputs: [responsibility_id, output, target_agent, skill_brief, format, inject_sections]
    outputs: [seven-layer-prompt.md, prompt-build-trace.json, prompt-creator-trace.json]
  invariant:
    - 7 層構造 (L1→L7) を厳守し、一括生成せず Layer 単位生成→merge とすること
    - Layer 5 は固定手順を持たず、達成ゴール + 完了チェックリストで宣言すること
    - Layer 依存方向は L7→L1 の単方向のみとすること
    - 既存改善は冪等更新 (分解→類似は上書き統合・無ければ新規) で同一意図要素を重複させないこと
    - ゴールシーク反復は SubAgent / チームで分離 context で実行し、親へは最終差分のみ返すこと
    - SKILL.md / SubAgent 各 300 行以下を保つこと
since: 2026-05-20
script_refs:
  - scripts/merge-layers.py
  - scripts/validate-prompt.py
  - scripts/convert-format.py
  - scripts/verify-completeness.py
  - scripts/generate-sheet.py
  - scripts/validate-sheet.py
  - scripts/scaffold-prompt.py
  - scripts/log-usage.py
reference_refs:
  - references/resource-map.yaml
  - references/seven-layer-format.md
  - references/quality-criteria.md
  - references/workflow-guide.md
  - references/writing-style-principles.md
  - references/prompt-sheet-template.md
  - references/idempotent-update-policy.md
# context-budget (CD-005): 章一括ロード禁止 / max-reference-chapters: 3
source: doc/prompt-creator/
source-tier: internal
last-audited: 2026-05-24
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-main.md
schema_refs:
  - schemas/output.schema.json
  - schemas/hearing-result.schema.json
responsibilities:
  - id: R1
    name: main
    prompt_required: true
manifest: workflow-manifest.json
---

# run-prompt-creator-7layer

> doc/prompt-creator/ を skill-creator 仕様準拠で plugins/prompt-creator/ へ移植した正本。SKILL.md/SubAgent 各 300 行以下、Progressive Disclosure 厳守。

## Purpose & Output Contract

ユーザー要求またはヒアリング結果から、**成果物としての 7 層構造プロンプト** を生成する。
7 層: L1 基本定義 / L2 ドメイン定義 / L3 インフラストラクチャ / L4 共通ポリシー / L5 エージェント定義 / L6 オーケストレーション / L7 ユーザーインタラクション。
Layer 5 はゴールシーク型 (達成ゴール+完了チェックリスト+実行方式)。固定手順は書かず、手順はエージェントが実行時に自律生成する。

本スキルの責務は **エンドユーザー向け成果物プロンプトの生成** に純化する。SubAgent .md の Prompt Templates / Self-Evaluation への注入は、owner_agent 指定時のみ行う付随機能 (legacy) であり、本スキルの主目的ではない。

**入力**: `--responsibility-id <R-id>` (skill-local-v1 既定で必須、`brief.responsibilities[].id` と 1:1) / `--output <path>` (省略時は規約パス自動解決) / `--target-agent` (任意、owner_agent がある場合のみ注入) / `--skill-brief` / `--format` (md 既定、yaml は内部正規形または legacy 互換) / `--inject-sections` (既定: "Prompt Templates,Self-Evaluation")

**出力 (path_convention で切替)**:
- `skill-local-v1` (既定): `plugins/<plugin>/skills/<skill>/prompts/<R-id>-<slug>.md` — `references/prompt-placement-convention.md` (skill-creator 側) 準拠、`validate-build-trace.py` が正規表現と sha256 で機械検証
- `agents-legacy` (`--responsibility-id` 省略時のみ): `plugins/<plugin>/agents/prompts/<role>.yaml` — 後方互換、brief.responsibilities[] が空の ref/wrap/delegate 用
- 対象 SubAgent .md への自動注入 (Edit、owner_agent がある場合のみ)
- `eval-log/prompt-build-trace.json` (`run-prompt-create/schemas/build-trace.schema.json` 互換)
- `eval-log/prompt-creator-trace.json` (worker-local trace。必須フィールド: `path_convention`, `responsibility_id`, `layer_artifact_path`, `sha256`)

**完了条件**: `verify-completeness.py` PASS + `validate-prompt.py` PASS + `lint-agent-prompt-section.py` PASS。

## Key Rules

1. **Script First**: 決定論的処理は python3 スクリプト。LLM は意味判断のみ。
2. **1 Layer = 1 出力**: 一括生成禁止、Layer 単位生成→merge。
3. **質ベース判定**: 「実行可能か/検証可能か」。数量カウント禁止。
4. **Progressive Disclosure**: `references/` は Phase 直前で必要分のみ読込。
5. **目的+背景併記**: 全ルール/制約に併記 (`writing-style-principles.md`)。
6. **300 行制約**: SKILL.md / SubAgent 各 300 行以下。
7. **ループ整合性**: run-build-skill 呼出時は `lint-agent-prompt-section.py` 通過必須。FAIL 時最大 3 回自律修正→未達なら orchestrator 差戻。
8. **責務境界**: 担当は Prompt Templates / Self-Evaluation の 2 セクションのみ。9 セクション骨格は run-build-skill 責務。
9. **Markdown 既定**: prompt 出力は **Markdown 形式 (`.md`) を既定**とする。論理構造の正本は `references/seven-layer-format.md`。内部正規形は YAML (scaffold/merge/verify の前提) とし、最終成果物は `convert-format.py` で Markdown へ変換する。`references/seven-layer-markdown-template.md` は提示形式の補助テンプレ。
10. **ゴールシーク**: Layer 5 に固定手順 (思考プロセスのステップ列挙) を書かない。達成ゴール+完了チェックリストを宣言し、手順は実行時にエージェントが自律生成する。`verify-completeness.py` が固定手順を検出したら FAIL。
11. **冪等更新 (重複回避・上書き優先)**: 既存プロンプトを改善するときは闇雲に追加せず、先に既存を原子要素へ分解・分析し、類似要素があれば上書き統合・無ければ新規追加する。同一意図の要素が 2 つ以上残ったら FAIL。正本 `references/idempotent-update-policy.md`。
12. **セッション分離**: ゴールシーク反復は SubAgent / エージェントチームで分離 context で実行する。中間探索情報を親 context に流さず、親へは最終差分と完了判定のみ返す (現セッション汚染防止)。

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
python3 scripts/validate-prompt.py --input eval-log/hearing-result.json --phase hearing --schema plugins/prompt-creator/skills/run-prompt-elicit/schemas/hearing-result.schema.json
```

AI 推定は導出確認→ユーザー承認。

### Phase 3: フォーマット選択

ループ呼出時 `--format md` 既定で skip。それ以外は AskUserQuestion。YAML は内部正規形または legacy 互換に限定する。

### Phase 4-A: Layer 単位生成

SubAgent: `prompt-creator-generate-prompt`

Layer 役割 (Clean Architecture / DDD):

| Layer | 役割 | Clean Arch / DDD |
|---|---|---|
| L1 基本定義 | 最上位の不変原則・倫理ガード | Enterprise Rules / Value Objects |
| L2 ドメイン定義 | 本質ロジック・用語集・ビジネスルール | Entities / ユビキタス言語 |
| L3 インフラストラクチャ | 外部ツール・API 接続 | Frameworks / ACL |
| L4 共通ポリシー | 横断的関心事 (失敗時挙動・観測・セキュリティ) | App Rules / 横断的関心事 |
| L5 エージェント定義 | ゴール駆動の実行主体 (ゴール定義+完了チェックリスト) | Use Cases / 境界 Context |
| L6 オーケストレーション | ゴールシーク制御・ハンドオフ | Controllers / Saga |
| L7 ユーザーインタラクション | 初回入力・提示形式 | Adapters / App Service |

依存方向: L7→L6→...→L1。Layer 5 は固定手順を持たず、ゴールと完了チェックリストで宣言する。詳細: `references/seven-layer-format.md`。

合算: `python3 scripts/merge-layers.py --layers tmp/prompt-layers/ --output tmp/prompt.yaml`

### Phase 4-B: 4 パスレビュー

SubAgent: `prompt-creator-review-prompt`

Pass 0 (動的基準生成) → Pass 1 網羅性 → Pass 2 整合性 → Pass 3 深度 → Pass 4 実用性。詳細: `references/quality-criteria.md`。

### Phase 4-C: 自律改善

```bash
python3 scripts/verify-completeness.py --input tmp/prompt.yaml
python3 scripts/validate-prompt.py --input tmp/prompt.yaml --phase prompt
```

未充足あれば generate-prompt 再起動 (最大 3 回)。既存改善時は冪等更新 (`idempotent-update-policy.md`): 分解→類似は上書き統合・無ければ新規。反復は SubAgent/チームで分離 context で回し、親へは最終差分のみ返す。

### Phase 4-D: 変換+注入

```bash
python3 scripts/convert-format.py --input tmp/prompt.yaml --format ${FORMAT} --output ${OUT}
```

ループ呼出時は対象 SubAgent .md へ Edit 注入。

### Phase 5: 戻り検証

```bash
python3 plugins/skill-governance-lint/scripts/lint-agent-prompt-section.py "${TARGET_AGENT}"
```

exit 0 でループ完了。FAIL は Phase 4-A 再起動 (最大 3 周)。

実行後 `python3 scripts/log-usage.py --result <success|fail> --phase "Phase 5"` で `LOGS.md` に記録 (利用統計/失敗パターン蓄積)。

## Gotchas

1. 7 層一括生成禁止 (Layer 単位→merge)。
2. 「3 つ以上」型禁止→質ベース判定。
3. 長文フィールド禁止 (要素原子性、1 値 50 文字目安)。
4. 外部依存不持込 → YAML は python3 標準ライブラリのみで手書きシリアライズ。
5. doc/prompt-creator/ は deprecated、正本は plugins/。
6. 自律修正 3 回上限、超過時 orchestrator 差戻。
7. 9 セクション骨格生成禁止 (run-build-skill 責務)。
8. Layer 5 固定手順禁止 (思考プロセスのステップ列挙)。ゴール定義+完了チェックリストで宣言。
9. ヒアリングで固定手順を収集しない (goals/checklist を収集、steps は廃止)。
10. 既存改善時の重複追加禁止 (分析せず追加で肥大化させない)。類似は上書き統合。
11. ゴールシークを現セッション直書きで回さない (SubAgent/チームで分離、中間情報を親に漏らさない)。

## Additional Resources

- `references/seven-layer-format.md` — 7 層 YAML 正本テンプレ (Phase 4-A 直前読込)
- `references/workflow-guide.md` — Phase 1-4 詳細
- `references/quality-criteria.md` — 4 パス評価基準 + §8 冪等更新基準
- `references/idempotent-update-policy.md` — 既存改善時の重複回避・上書き優先・セッション分離 (Phase 4-B/4-C 直前読込)
- `references/writing-style-principles.md` — 記述スタイル
- `references/prompt-sheet-template.md` — シート項目
- `schemas/hearing-result.schema.json` — Phase 1 スキーマ
- 子 agent: `plugins/prompt-creator/agents/prompt-creator-{interview-user,generate-prompt,review-prompt}.md`
- caller: `plugins/skill-creator/skills/run-build-skill` (Step 7.5)
- 戻り検証: `plugins/skill-governance-lint/scripts/lint-agent-prompt-section.py`
