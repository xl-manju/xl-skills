---
name: delegate-codex-skill-review
description: 自セッションで評価せず外部LLMに委譲したいとき、Sycophancyを避けたいときに使う。
disable-model-invocation: false
user-invocable: true
allowed-tools:
  - Read
  - Bash(python3 *)
kind: delegate
effect: none
delegate_agent: codex-cli
owner: team-platform
since: 2026-05-18
# doc/21 source-traceability
source: doc/ClaudeCodeスキルの設計書/06-classification-and-naming.md
source-tier: internal
last-audited: 2026-05-19
audit-trigger: source-update
hierarchy_level: L1
# delegate-* prefix の最小実例。Skill レビューを外部 codex CLI に委譲する。
---

# delegate-codex-skill-review

## Purpose & Output Contract

評価対象 Skill (SKILL.md) を任意の外部 `codex` CLI に渡すための手順と入力を作り、Sycophancy を避けた第三者レビューの準備をする。

**入力**: target_skill_path (SKILL.md への絶対パス)
**出力**: `eval-log/delegate-codex-request.json` (ユーザーが任意で実行する codex review 入力)

**完了条件**: codex CLI が標準フローの必須依存ではないことを保ったまま、任意実行用の入力とコマンド例が提示されている。

## Key Rules

1. **委譲先は任意**: `delegate_agent: codex-cli` は外部拡張の識別子であり、標準フローでは起動しない。
2. **入力のみ準備**: SKILL.md 本文と rubric パスを記録するが、自セッションで採点しない。
3. **結果はユーザー管理**: codex 実行はユーザーが明示的に行い、返答を eval-log/ に保存する。
4. **任意拡張**: Node / npm / shell script / codex CLI を標準依存にしない。存在確認は Python 標準ライブラリで行う。

## Steps

### Step 0: codex 存在確認 (決定論)

```bash
python3 plugins/skill-creator/skills/delegate-codex-skill-review/scripts/check-codex-installed.py
```
exit 2 が返ったら BLOCK。標準フローではなく任意拡張であることを案内して停止。

### Step 1: target 検証

`target_skill_path` が存在し SKILL.md であることを確認。

### Step 2: 任意実行コマンドの提示

```bash
codex review --input "$TARGET_PATH" --rubric plugins/skill-creator/skills/ref-skill-design-rubric/rubric.json \
  > eval-log/delegate-codex-review.json
```
このコマンドは自動実行しない。codex CLI を導入済みのユーザーが任意で実行する。

### Step 3: 結果提示

書き出した JSON のサマリをユーザーに返す。修正判断は委ねる。

## Gotchas

- **委譲結果を再評価しない**: 自セッションでスコア改竄をしない (09章 Sycophancy 防止)。
- **codex 未インストール時**: BLOCK するが、Node/npm を案内しない。公式に確認済みの配布元をユーザーが選ぶ。
- **L1 階層**: codex CLI 抽象 (L1)。プロジェクト固有の review 観点は L2 で wrap する。

## Additional Resources

- 設計書: `06-classification-and-naming.md` (delegate-* prefix), `09-evaluation-orchestration.md`
- 委譲先: codex CLI (https://github.com/openai/codex 等、要別途インストール)
