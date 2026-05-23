---
name: run-elegant-review
description: 新規Skillを提案するとき、大規模アーキテクチャ変更を行うときに使う。
disable-model-invocation: false
user-invocable: true
argument-hint: "[target-type] [target-path]"
arguments: [target_type, target_path]
allowed-tools:
  - Read
  - Write
  - Grep
  - Glob
  - Bash(python3 *)
  - Skill(assign-skill-design-evaluator *)
kind: run
prefix: run
effect: local-artifact  # findings.json/review-*.md をローカル生成。外部 API 呼び出しなし
owner: team-platform
since: 2026-05-18
manifest: workflow-manifest.json
responsibility_refs:
  - prompts/phase1-reset.md
  - prompts/phase2-parallel.md
  - prompts/phase3-execute.md
agent_refs:
  - ../../agents/elegant-reset-observer.md
  - ../../agents/elegant-logical-structural-analyst.md
  - ../../agents/elegant-meta-divergent-analyst.md
  - ../../agents/elegant-system-strategic-analyst.md
  - ../../agents/elegant-improvement-executor.md
schema_refs:
  - schemas/findings.schema.json
  - schemas/phase-output.schema.json
rubric_refs:
  - ref-skill-design-rubric
  - references/elegant-4-conditions.json
reference_refs:
  - references/30-paradigms-full.md
  - references/agent-roles.md
  - references/orchestration-flow.md
  - references/convergence-policy.json
  - references/amplified-patterns.json
script_refs:
  - scripts/build-paradigm-scorecard.py
  - scripts/validate-paradigm-coverage.py
merge_strategy: deep-merge
conflict_policy: most-specific-wins
# auto-backfilled by backfill-source-tier.py (doc/21)
source: doc/ClaudeCodeスキルの設計書/09-evaluation-orchestration.md
source_refs:
  - doc/ClaudeCodeスキルの設計書/09-evaluation-orchestration.md
  - doc/ClaudeCodeスキルの設計書/17-agent-teams-reference.md
  - doc/ClaudeCodeスキルの設計書/20-migration-path.md
  - doc/ClaudeCodeスキルの設計書/21-source-traceability.md
  - doc/ClaudeCodeスキルの設計書/22-cross-platform-runtime.md
  - doc/ClaudeCodeスキルの設計書/30-paradigm-analogy-map.md
source-tier: internal
last-audited: 2026-05-19
audit-trigger: quarterly
---

# run-elegant-review

## Purpose & Output Contract

新規Skill / rubric改訂 / アーキテクチャ提案 / creator-kit構成要素を、**30種の思考法**で多角的に検証し、**4条件 (矛盾なし / 漏れなし / 整合性あり / 依存関係整合)** をすべてPASSさせるまで改善する。

本Skillの改善は、対象固有の事実をそのまま埋め込むのではなく、必ず **具体値 → 変数 → テンプレート → 横展開条件** に戻して設計する。対象固有情報は証跡として残し、再利用可能なプロンプト・Skill・SubAgent・script・config では変数名と既定値で表現する。

### Output Contract
- `findings.json`: paradigm別findings + 4-condition gates + variable abstraction + total score (`templates/findings.json` 準拠)
- `review-<target-type>.md`: 人間可読レポート (target_type に応じた template を採用)
- 完了条件: 4条件すべて PASS かつ 30思考法すべてに構造化 findings が存在 (coverage script で検証)

### 引数
- `target_type` ∈ {skill, rubric, proposal, kit-component, script, config, agent, custom}
- `target_path`: 対象ファイル/ディレクトリの絶対パス

### 変数化ポリシー

| 具体情報 | テンプレート変数 | 例 |
|---|---|---|
| プロジェクトルート | `{{PROJECT_ROOT}}` | `/path/to/project` |
| kitルート | `{{KIT_ROOT}}` | `{{PROJECT_ROOT}}/creator-kit` |
| 対象種別 | `{{target_type}}` | `skill`, `script`, `config` |
| 対象パス | `{{target_path}}` | 絶対パスまたは `{{PROJECT_ROOT}}` 基準相対パス |
| レビュー作業領域 | `{{review_workspace}}` | OS別一時ディレクトリ配下 |
| 所有者 | `{{owner}}` | チーム名または個人名 |
| 実行OS | `{{os_kind}}` | `mac`, `linux`, `windows`, `unknown` |
| 外部ツール名 | `{{external_executor}}` | `codex`, `claude-code`, `none` |

禁止: 実プロジェクト名、個人名、固定絶対パス、固定API URL、固定ownerを、再利用されるプロンプト・Skill・SubAgent・script・configへ直接埋め込むこと。必要な場合は `source_trace` に証跡として残す。

---

## 30思考法カテゴリ (7カテゴリ / 計30)

詳細定義は `references/30-paradigms-full.md` を参照 (Progressive Disclosure)。

### A. 論理分析系 (5)
1. 批判的思考 (Critical)
2. 演繹思考 (Deductive)
3. 帰納的思考 (Inductive)
4. アブダクション (Abductive)
5. 垂直思考 (Vertical)

### B. 構造分解系 (4)
6. 要素分解 (Decomposition)
7. MECE
8. 2軸思考 (Two-axis)
9. プロセス思考 (Process)

### C. メタ抽象系 (3)
10. メタ思考 (Meta)
11. 抽象化思考
12. ダブル・ループ思考 (Double-loop)

### D. 発想拡張系 (6)
13. ブレインストーミング
14. 水平思考 (Lateral)
15. 逆説思考 (Paradox)
16. 類推思考 (Analogy)
17. if思考 (What-if)
18. 素人思考 (Beginner's mind)

### E. システム系 (3)
19. システム思考
20. 因果関係分析 (Causal analysis)
21. 因果ループ (Causal loop)

### F. 戦略価値系 (4)
22. トレードオン思考 (Trade-on)
23. プラスサム思考 (Positive-sum)
24. 価値提案思考 (Value proposition)
25. 戦略的思考 (Strategic)

### G. 問題解決系 (5)
26. why思考 (Why)
27. 改善思考 (Improvement)
28. 仮説思考 (Hypothesis)
29. 論点思考 (Issue)
30. KJ法 (KJ method)

---

## 検証4条件

機械可読定義は `references/4-conditions.json` / rubric表現は `references/elegant-4-conditions.json` を参照。

| # | 条件 | 定義 | check method |
|---|------|------|--------------|
| C1 | 矛盾なし (Consistency) | 内部の主張・ルール間で論理矛盾がない | claim graph で contradiction edge を検出 |
| C2 | 漏れなし (Completeness) | 対象スコープに必要な要素がMECEに揃う | required-element checklist を全件PASS |
| C3 | 整合性あり (Coherence) | 上位仕様 (24章正本 / rubric) と整合 | rubric_refs と diff し violation=0 |
| C4 | 依存関係整合 (Dependency) | 参照・前提・順序が破綻していない | DAG topological sort が成立 |

**完了条件**: C1〜C4 すべて PASS。1つでもFAILなら Phase3 改善ループへ。

---

## 実行フロー

フェーズ定義・依存・入出力スキーマ・ゲートはすべて `workflow-manifest.json` を正本とする。本文は概要のみ。

| Phase | Agent | parallel | prompt | gate |
|---|---|---|---|---|
| phase1-reset | elegant-reset-observer | no | prompts/phase1-reset.md | schema-validate |
| phase2-parallel | logical-structural / meta-divergent / system-strategic | yes (3並列) | prompts/phase2-parallel.md | paradigm-coverage==30 |
| phase3-execute | elegant-improvement-executor | no | prompts/phase3-execute.md | C1-C4 PASS (max_iter=3) |

### 副作用境界

- Phase1/Phase2 は read-only。対象を編集しない。
- Phase3 のみ write 可。編集は集約済み findings に紐づく最小パッチに限定。
- Phase2 単独監査時は、ユーザー指定の出力先がない限り対象ディレクトリを書き換えない。

詳細フローは `references/orchestration-flow.md`、エージェント責務は `references/agent-roles.md`、収束判定は `references/convergence-policy.json` を参照。

---

## 収束ループ設計 (正負フィードバック両輪)

詳細は `references/convergence-policy.json` を参照。本Skillは「PASS/FAIL の1bit判定」ではなく、**解像度3層 + 両輪フィードバック + 安全弁** で収束を判定する。

### 解像度3層

| 層 | 出力 | 用途 |
|---|---|---|
| L1 | C1-C4 の PASS/FAIL (4bit) | 最終判定 |
| L2 | 各C条件・各思考法のスコア (0.0-1.0) | 周回内の精緻評価 |
| L3 | 周回間のΔベクトル (正/負両方向) | 収束兆候の検出 |

### 両輪フィードバック

- **負のフィードバック (Detector)**: C1-C4違反・パラダイム破綻を検出 → 修正パッチ適用 → 品質ラインに到達させる
- **正のフィードバック (Amplifier)**: 良い設計判断・再利用可能パターンを抽出 → `amplified-patterns.json` に蓄積 → 他章/他Skillへ横展開

両輪を備えて初めて「減点を避ける運用」から「加点を取りに行く運用」に転換できる。

### 停止条件

1. **収束完了** (`Δneg < 0.10 AND Δpos < 0.10`): 減らす問題も増やす良点もなくなった → `status: complete`
2. **発散** (`Δneg が2周連続で増加`): 改善方針自体に欠陥 → `human_escalate`
3. **安全弁発火** (`iteration_count >= max_iterations(=3)`): 上限到達 → `status: incomplete`、**force_pass禁止**、`human_review`必須

**重要**: 安全弁発火を成功扱いにすると Goodhart 罠が再生産される。max到達は**失敗**として扱う。

### 出力アーティファクト
- `findings.json` (機械可読)
- `review-<target-type>.md` (人間可読、template採用)
- `paradigm-scorecard.csv` (paradigm × condition matrix)
- `variable-abstraction` (具体値をテンプレート変数へ置換した対応表。`findings.json` と review に含める)

---

## Gotchas

1. **30思考法すべて省略禁止** — JSONでは `paradigm_findings` 30件、各 observations / issues の構造を `scripts/validate-paradigm-coverage.py` が検証し、欠落あれば非ゼロ終了。
2. **Phase1 を飛ばさない** — 先入観のまま rubric チェックに入ると C2/C3 が偽陽性 PASS する。
3. **Goodhart の罠** — score 最大化のために本質を歪めない。低score でも本質が正しいなら C1〜C4 のみで判定。
4. **並列前提** — Phase2 の3エージェントは互いの中間結果を参照しない (独立性確保)。
5. **rubric_refs の継承** — `ref-skill-design-rubric` と `elegant-4-conditions.json` は deep-merge / most-specific-wins。
6. **具体値の直書き禁止** — 横展開を阻害する固有名詞・固定パス・固定URL・固定ownerは、テンプレート変数か config example に移す。例外は証跡・引用・source trace のみ。

---

## Additional Resources

- `references/30-paradigms-full.md` — 30思考法すべての定義
- `references/4-conditions.json` — 4条件の機械可読定義
- `references/elegant-4-conditions.json` — rubric rule 表現
- `references/agent-roles.md` — エージェント1〜5の責務
- `references/orchestration-flow.md` — Phase1→2→3 詳細フロー
- `references/variable-template-contract.md` — 具体情報を変数化して横展開する契約
- `templates/review-skill.md` / `review-rubric.md` / `review-proposal.md` — 出力雛形
- `templates/findings.json` — JSON出力スキーマ
- `scripts/build-paradigm-scorecard.py` — matrix 生成
- `scripts/validate-paradigm-coverage.py` — 30思考法カバレッジ検査
- `examples/example-review-output.md` — 模擬レビュー完成例
- 関連: `assign-skill-design-evaluator`, `ref-skill-design-rubric`
