---
name: run-build-skill
description: 新規Skillを作成するとき、既存Skillを更新するときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[skill-name] [kind?] [--mode create|update] [--with-subagent] [--with-evaluator] [--with-hooks] [--model opus|sonnet]"
arguments: [skill_name, kind, mode, with_subagent, with_evaluator, with_hooks, model]
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash(python3 *)
  - Skill(assign-skill-design-evaluator *)
pair: assign-skill-design-evaluator
kind: run
effect: local-artifact
owner: team-skills
since: 2026-05-17
script_refs:
  - scripts/render-frontmatter.py
  - scripts/validate-naming.py
  - scripts/build-subagent.py
  - scripts/validate-build-trace.py
# context-budget (CD-005): 章一括ロード禁止。必要な章のみ参照すること。
# max-reference-chapters: 3  # 同時に読む設計書章の上限
---

# run-build-skill

> ※ creator-kit Phase 0 移行中は `creator-kit/skills/` が正本、`.claude/skills/` への配置は派生。本SKILL.mdは両配置で動作するよう self-relative パスを使用。

## Purpose & Output Contract

ユーザー要求からClaude Code Skillを1本構築するワークフロー。

**入力**: skill_name (kebab-case), kind (run|ref|assign|wrap|delegate),
         mode (create|update, デフォルト: create),
         with_subagent (フラグ、指定時のみStep7実行),
         model (opus|sonnet, デフォルト: opus)
**出力**:
- `$OUT_BASE/<name>/SKILL.md`（Phase 0 は `creator-kit/skills/`、移行後は `.claude/skills/` または plugin 配置。300行以下、frontmatter完備）
- 必要に応じ `templates/`, `references/`, `scripts/`, `examples/`
- `eval-log/skill-build-trace.json`（task→refs map、01aフロー、02/03/04/05/06/07/08/09/10/11/13/14/15/16 concern への対応証跡）
- assign-skill-design-evaluator による評価レポート (`./build-report.json`)

**完了条件**: rubric score >= 80 かつ high severity 0件。

## Key Rules

1. **300行制約**: SKILL.md本文は300行以下。超過分は `references/` へ分割（07章）。
2. **descriptionは発動条件のみ**: 動作詳細は本文化（08章）。
3. **triggerは2〜3個**: description内のUse when句は2〜3個の動詞ベース条件（08章 hard rule）。
4. **ディレクトリ名 == frontmatter.name**: 第8条。
5. **Mac専用**: zsh/bash + python3 stdlibのみ（22章）。
6. **評価分離**: 生成本体は評価しない。`assign-skill-design-evaluator` をforkで呼ぶ（09章 Goodhart対策）。
7. **kindに応じたテンプレ選択**: 11章テンプレを `templates/` から展開。
8. **context予算制約 (CD-005)**: 全章一括ロード禁止。各Stepで必要な章のみ参照。
9. **--mode update**: 既存Skillへの増分改修。既存SKILL.mdを読んでdiffを適用する。
10. **モデル既定値**: build-subagent.py は --model opus で実行（PF-F3-001）。
11. **横展開候補は登録案を作る**: 生成物が Skill Creator 基盤、hook、lint、adapter、rubric、reference に該当する場合は `run-skill-create` の creator-kit 登録判定へ戻し、manifest更新をユーザー確認に委ねる。
12. **正本トレース必須**: 生成・更新ごとに task→refs map の選択、Intent / Contract / Boundary / Execution / Feedback、01a Step 1〜9、02 Skill構造、03 frontmatter、04 invocation/permissions、05 execution layer、06 classification/naming、07 progressive disclosure、08本文設計、09評価編成、10Subagent/Hook連携、11テンプレ適用、13チェックリスト/lint、14 dynamic injection、15公式参照追跡、16公式Skills仕様 の対応を `skill-build-trace.json` に残す。
13. **実行レイヤー判断を固定化**: Skill / Subagent / Hook / MCP / CLI / script の配置理由を trace に記録し、決定論で落とせる検査は script/hook へ分離する。
14. **再現性ゲートは機械検証**: `scripts/validate-build-trace.py` で source_docs / build_flow_coverage / doc_coverage / layer_decisions / gates を検証し、空欄・未読・N/A理由なしを通さない。

## Steps

### Step 1: 要求ヒアリング

> **[MANDATORY - ch15/ch16 公式参照確認]** このステップの最初に `ref-yaml-spec-fetcher` を呼び出して
> `yaml-spec-cache.md` を Read すること。スキップは禁止。
> `validate-build-trace.py` が `15-official-source-notes` / `16-official-skills-reference` を検証し、
> 未実施の場合 exit 1 となる。
>
> ```
> Skill(ref-yaml-spec-fetcher)
> ```

- skill_name の kebab-case とprefix妥当性を確認 → `scripts/validate-naming.py`
- kind を確定（run/ref/assign/wrap/delegate）
- mode を確定（create / update、デフォルト: create）
- `references/resource-map.yaml` を最初に読み、task category と読む設計書を決める
- 01章の5要素（Intent / Contract / Boundary / Execution / Feedback）を1文ずつ埋める
- 01a Step 2 の実行レイヤー判断表で、Skill / Subagent / Hook / MCP / CLI / script の分担を決める
- 02章で配置スコープ / reference-task 境界 / Additional Resources を決める
- 03章で frontmatter の trigger 2〜3個、独自メタデータ、依存注入フィールドを決める
- 04章で `allowed-tools` と `permissions.deny` / hook の責務分離を決める
- 詳細仕様が不足する場合は `references/build-steps.md` を参照
- **context予算**: 設計書は `references/resource-map.yaml` が選んだものだけ読む。同時に読む設計書は原則3章以下。
- **章番号の事前特定**: task category から読むべき章番号を特定してから Read する (CD-005)。

### Step 2: テンプレ展開（create）/ 既存読込（update）

**create モード**:
```bash
# P0-4: パス解決ロジックを外部スクリプトに移譲 (300行 cap 対策)
# SKILL_DIR / OUT_BASE を確立する
source creator-kit/scripts/resolve-skill-dirs.sh
mkdir -p "$OUT_BASE/$SKILL_NAME"
python3 "$SKILL_DIR/scripts/render-frontmatter.py" \
  --name "$SKILL_NAME" --kind "$KIND" \
  --brief eval-log/skill-brief.json \
  --template "$SKILL_DIR/templates/${KIND}.md" \
  > "$OUT_BASE/$SKILL_NAME/SKILL.md"
```

**update モード (CD-002)**:
```bash
# 既存SKILL.mdを読み込み、findingsを差分適用する
# 1. 既存ファイルをバックアップ
cp "$OUT_BASE/$SKILL_NAME/SKILL.md" "$OUT_BASE/$SKILL_NAME/SKILL.md.bak"
# 2. findingsに基づき Edit で差分適用（新規作成しない）
# 3. validate-frontmatter.py で整合性確認
```

### Step 3: 補助ファイル生成

- run系: `templates/`, `scripts/`, `examples/`
- ref系: `references/articles-full.md` 等の長文置き場
- assign系: `references/rubric.json`, `scripts/render-findings-score.py`
- いずれも本文100行超なら `references/` に追い出す
- `references/` は `skill-build-trace.json` の `source_docs` / `doc_coverage` に対応付ける
- **context予算**: このステップで読む設計書は11章のみ。

### Step 3.5: 再現性トレース生成

`references/build-steps.md#reproducibility-trace` の schema に従い、以下を `eval-log/skill-build-trace.json` に保存する:

- `design_model`: 01章5要素（Intent / Contract / Boundary / Execution / Feedback）
- `context_map_decision`: resource-map が選んだ task category / selected_docs / 理由
- `build_flow_coverage`: 01a Step 1〜9 の PASS/FAIL と証跡パス
- `doc_coverage`: 02 / 03 / 04 / 05 / 06 / 07 / 08 / 09 / 10 / 11 / 13 / 14 / 15 / 16 章の設計判断をどこへ反映したかの PASS/FAIL と証跡パス
- `layer_decisions`: Skill / Subagent / Hook / MCP / CLI / script の採否理由、deterministic判定、fallback、依存方向、macOS stdlib 適合
- `variant_support`: run/ref/assign/wrap/delegate と role-suffix の適用可否
- `pattern_decisions`: `pattern_refs` の採否、量産対象パターン、再利用先、negative cases
- `reproducibility_gates`: lint / evaluator / elegant-review / governance の結果

### Step 4: 命名・構造Lint

```bash
python3 creator-kit/scripts/lint-skill-name.py "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 creator-kit/scripts/lint-skill-description.py "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 creator-kit/scripts/lint-skill-tree.py "$OUT_BASE/$SKILL_NAME"
python3 creator-kit/scripts/validate-frontmatter.py "$OUT_BASE/$SKILL_NAME/SKILL.md"
python3 "$SKILL_DIR/scripts/validate-build-trace.py" eval-log/skill-build-trace.json
```

5つすべて exit 0 でなければ Step 2 または Step 3.5 へ戻る。

### Step 5: フォーク評価

`assign-skill-design-evaluator` をforkで呼び出し、rubric採点:

```
Skill(assign-skill-design-evaluator) target=$OUT_BASE/$SKILL_NAME
```

出力JSON:
```json
{"rubric_id":"skill-design","rubric_version":"1.0.0","score":N,"findings":[...]}
```

評価時は `skill-build-trace.json` も対象に含め、01/01a の正本フローに未対応の Step があれば C2 漏れとして扱う。

### Step 6: ゲート判定

- score >= 80 かつ high=0 → 完了
- それ以外 → findings を本文に反映 → Step 4 へ戻る（最大3周）

### Step 7: subagent自動生成と検証（`--with-subagent` 指定時のみ）

`--with-subagent` フラグが指定された場合に実行する (PF-G3-001: 条件明確化):

```bash
# Step 2 で確定した $SKILL_DIR / $OUT_BASE を再利用 (self-relative + fallback)。
python3 "$SKILL_DIR/scripts/build-subagent.py" \
  --skill-name "$SKILL_NAME" \
  --skill-md "$OUT_BASE/$SKILL_NAME/SKILL.md" \
  --output-dir .claude/agents/ \
  --model "${MODEL:-opus}"
python3 creator-kit/scripts/lint-skill-description.py ".claude/agents/$SKILL_NAME-subagent.md"
```

SKILL.md frontmatter (description / allowed-tools) と `## Steps` / `## Purpose & Output Contract` から
`.claude/agents/<skill-name>-subagent.md` を派生し、派生物も lint 対象にする。詳細は `references/build-steps.md`。

### Step 8: evaluator ペア自動生成（`--with-evaluator` 指定時 または brief.generate_pair_evaluator=true）

generator として作った skill に対し、対称な evaluator を同時生成して **孤児 evaluator** / 孤児 generator を防ぐ (設計書09章 pair 設計)。

```bash
# 条件: role_suffix=generator かつ prefix in {run, assign-*-generator}
# 注意: jq は forbidden_dependencies (manifest.json)。python3 stdlib のみ使用。
GEN_PAIR=$(python3 -c "import json,sys; b=json.load(open('$BRIEF_PATH')); print('true' if b.get('generate_pair_evaluator') else 'false')")
if [[ "$WITH_EVALUATOR" == "true" ]] || [[ "$GEN_PAIR" == "true" ]]; then
  PAIR_NAME="assign-${SKILL_NAME#run-}-evaluator"  # run-foo → assign-foo-evaluator
  RUBRIC_CSV=$(python3 -c "import json; print(','.join(json.load(open('$BRIEF_PATH')).get('rubric_refs',[])))")
  python3 "$SKILL_DIR/scripts/render-frontmatter.py" \
    --template "$SKILL_DIR/templates/assign-evaluator.md" \
    --pair "$SKILL_NAME" \
    --rubric-refs "$RUBRIC_CSV" \
    --out "$OUT_BASE/$PAIR_NAME/SKILL.md"
  # 生成 generator の frontmatter に pair: を上書き
  python3 "$SKILL_DIR/scripts/set-frontmatter-field.py" \
    --file "$OUT_BASE/$SKILL_NAME/SKILL.md" --key pair --value "$PAIR_NAME"
fi
```

### Step 9: Hook 配線自動生成（`--with-hooks` 指定時 または brief.hook_events 非空）

Hook 統合スキルの場合、scripts/hook-<name>-<event>.py スケルトンと settings.json マージ案を生成する (10章§設計判断5)。

```bash
# jq 不使用 (forbidden_dependencies)。python3 stdlib で hook_events を抽出。
HOOK_EVENTS=$(python3 -c "import json; print(' '.join(json.load(open('$BRIEF_PATH')).get('hook_events',[])))")
if [[ "$WITH_HOOKS" == "true" ]] || [[ -n "$HOOK_EVENTS" ]]; then
  for event in $HOOK_EVENTS; do
    python3 "$SKILL_DIR/scripts/render-hook-skeleton.py" \
      --skill-name "$SKILL_NAME" --event "$event" \
      --out "scripts/hook-${SKILL_NAME}-$(echo $event | tr 'A-Z' 'a-z').py"
  done
  # settings.json マージ案を .claude/settings.proposal.json に出力 (人間承認後に手動マージ)
  python3 "$SKILL_DIR/scripts/render-settings-proposal.py" \
    --skill-name "$SKILL_NAME" --brief "$BRIEF_PATH" \
    --out ".claude/settings.proposal.json"
fi
```

**Note**: settings.json への自動 merge は行わない（permissions 系の決定はユーザー承認必須）。proposal を提示して手動 merge とする。

## 配置先（plugin 移行ロードマップ準拠）

| フェーズ | 出力先 | 正本 |
| **現在（Phase 0 未完了）** | `creator-kit/skills/<skill>/SKILL.md` | `creator-kit/skills/` |
| **Phase 0 完了後** | `plugins/<plugin-name>/skills/<skill>/SKILL.md` | `plugins/<name>/` |

- **正本/派生**: Phase 0 完了後、`.claude/skills/<skill>/` は `plugins/*/skills/` への symlink 経由派生。直接書き込まない
- **`name:` には plugin 名を含めない**: kebab-case の Skill 名のみ。所属 plugin は配置パスで表現（06章第17条）
- 詳細: 34章 § plugin 物理レイアウトと symlink 戦略

## Gotchas

- **frontmatter順序事故**: `disable-model-invocation: true` と `user-invocable: true` の共存は手動呼び出し専用の珍しい構成。禁止ではないが、意図を本文に明記する。
- **description長文化**: 動作詳細を書くと invocation時のtoken浪費（08章）。
- **ref系のbody肥大**: ref-*はSKILL.md本文をサマリに留め、原文は `references/`。300行制約はSKILL.md本文のみに適用。
- **scripts内のyaml import禁止**: stdlibだけで簡易パーサを書く（28章）。
- **fork評価の自己採点禁止**: 同じcontextで採点するとGoodhart罠（09章）。
- **update時の全書き換え禁止 (CD-002)**: --mode update ではEditで差分適用のみ。Writeで上書きしない。
- **全章一括ロード禁止 (CD-005)**: token超過を防ぐため、各Stepで必要な章だけを Read する。

## Additional Resources

- `references/design-docs-index.md` — 設計書00〜35への索引
- `references/resource-map.yaml` — task category → 読む設計書の決定論的map
- `references/build-steps.md` — 詳細手順、再現性trace schema、02/03/04 coverage
- `templates/` — kind別雛形
- `examples/minimal-ref.md`, `examples/workflow-with-evaluator.md` — 完成例
- `scripts/render-frontmatter.py`, `scripts/validate-naming.py`, `scripts/validate-build-trace.py`
- 共通lint: `scripts/lint-skill-name.py` 他
- manifest登録案: `scripts/build-manifest-registration-plan.py`
