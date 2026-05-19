# combinators/ — Atomic Composer 差分パッチ

`_base.md` (骨格) に対して kind 固有・フラグ固有の差分を適用するための combinator 群。

## 設計原則

- 各 `.patch` は `_base.md` を対象とした **unified diff**（`patch -p1` 適用可能）。
- 1 つの combinator は **1 つの関心** のみ扱う（kind | flag | project）。
- 適用順序は `run-build-skill` Step 8 で固定:
  1. **kind-specific**（必ず 1 つ適用）: `with-ref.patch` / `with-run.patch` / `with-wrap.patch` / `with-assign-evaluator.patch` / `with-assign-generator.patch` / `with-delegate.patch`
  2. **optional flag**（0〜N 個）: `with-evaluator.patch` / `with-hooks.patch` / `with-subagent.patch`
  3. **project flag**（0〜N 個）: `with-cross-platform.patch` / `with-rubric.patch`
- 同一セクションを複数 combinator が触る場合は **順序保証** により後勝ち（flag combinator が kind-specific を上書き可）。

## なぜテンプレ展開ではなく combinator か

- 旧設計: 9 種テンプレ × N 個フラグ = **積空間** （メタ分析 C1 issue 参照）
- 新設計: 1 atom + 9 combinator + N flag combinator = **和空間**
- kind に新フラグを追加するとき、旧設計では 9 ファイル全て更新が必要だったが、新設計では combinator を 1 つ追加するだけで全 kind に伝搬する。

## 移行戦略（Phase 0）

現状の `run.md` / `ref.md` / `wrap.md` / `assign-*.md` / `delegate.md` / `hook-integrated.md` / `agent-team.md` / `orchestrator.md` は **引き続き使用可能**。
combinator は **新規スキル生成時の代替経路** として並行運用し、Phase 0 終了時に旧テンプレを deprecate する。

`run-build-skill` の Step 6 で `composer_mode` を選べる:

```bash
# 旧フロー (default)
COMPOSER_MODE="template"

# 新フロー (試験運用)
COMPOSER_MODE="atomic"
```

`atomic` 選択時、Step 6 は `_base.md` を読み、brief の `kind` / `with_evaluator_pair` / `with_hooks` / `with_subagent_hint` に応じて combinator を順次適用する。

## ファイル一覧（Phase 0 着手分）

- `with-evaluator.patch` — pair=evaluator を持つ generator skill 用の差分
- `with-hooks.patch` — `PreToolUse` / `PostToolUse` 配線 + security セクション強化
- `with-subagent.patch` — `agent`, `context: fork`, Subagent body 連携の差分

kind-specific combinator (`with-ref.patch` 等) は Phase 1 で追加予定。
