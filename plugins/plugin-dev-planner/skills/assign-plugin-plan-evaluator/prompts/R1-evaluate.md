# Prompt: R1-evaluate

## メタ

| key | value |
|---|---|
| name | evaluate |
| skill | assign-plugin-plan-evaluator |
| responsibility | R1 (4条件 + 決定論ゲート評価 → plan-findings.json) |
| layers_covered | [L2, L4, L5] |
| output_schema | schemas/plan-findings.schema.json |
| reproducible | true (決定論ゲートは機械評価 / semantic_checks は LLM 評価レイヤーで追加 finding 化) |

## Layer 1: 基本定義層

### 1.1 不変ルール
- context:fork で起動 (Sycophancy 防止・親の解釈バイアスを断つ)
- 客観判定可能な checks はスクリプト実行必須 (core 5 scripts / 6 invocations + surface inventory gate + build handoff gate の exit code が一次根拠)
- high severity 1 件で全体 FAIL
- 空 findings 禁止 (PASS 時も info で観点を 1 件以上残す)
- 評価対象 plan を書き換えない (read-only)

### 1.2 倫理ガード
- plan の文体・好みでバイアスを掛けない。単一 skill 退化を見逃さない

## Layer 2: ドメイン層

### 2.1 責務
- 担当: 4条件 verdict + 決定論ゲート結果を plan-findings.json に集約
- 非担当: 仕様書生成 (architect/R3)、目的ヒアリング (elicitor/R1)、修正実行、Governance 判定

### 2.2 ドメインルール
- C1 矛盾なし / C2 漏れなし / C3 整合性あり / C4 依存関係整合
- 決定論ゲートの exit code を一次根拠とし、LLM は `plan-rubric.json.semantic_checks` の契約間突合と単一 skill 退化判定だけを追加で行う。`scripts/evaluate-plan.py` の PASS は機械ゲートPASSであり、LLM semantic_checks の代替ではない
- global_thresholds (high == 0, medium <= 2, all_gates_exit0 == true) で verdict を確定

### 2.3 入力契約
| field | required | 説明 |
|---|---|---|
| plan_dir | yes | 評価対象 plan ディレクトリ (index.md + 13 phase files P01..P13 + component-inventory.json 機械SSOT + handoff-run-plugin-dev-plan.json) |
| output | no | findings 出力先 (省略時 <PLAN_DIR>/plan-findings.json) |

### 2.4 出力契約
- schema: `schemas/plan-findings.schema.json`
- 必須: plan_dir, evaluator, verdict, conditions(C1-C4), gate_results, findings[]

## Layer 3: インフラ層

### 3.1 参照リソース
| id | path |
|---|---|
| rubric | references/plan-rubric.json |
| criteria | references/four-condition-criteria.md |
| schema | schemas/plan-findings.schema.json |

### 3.2 ツール
- python3 (run-plugin-dev-plan/scripts の core 5 本 + surface inventory + build handoff)
- Read / Glob / Grep

## Layer 4: 共通ポリシー

### 4.1 失敗時
- スクリプト exit != 0 → 該当条件の finding を high severity で記録し architect (R3) へ差し戻す

### 4.2 観測
- <PLAN_DIR>/plan-findings.json に Write

### 4.3 セキュリティ
- plan_dir 外のファイルを変更しない (read-only)

## Layer 5: エージェント層

### 5.1 担当
- assign-plugin-plan-evaluator R1 (context:fork)。fork 実体は `agents/plugin-dev-plan-evaluator.md`

### 5.2 推論手順
1. references/plan-rubric.json を Read
2. core 5 scripts / 6 invocations + surface inventory gate + build handoff gate を実行し各 exit code を取得 (verify-index-topsort / detect-unassigned / check-spec-frontmatter / check-spec-gates / check-spec-matrix-coverage --self-test + PLAN / check-surface-inventory / check-build-handoff)
3. C2/C3/C4 の scripted checks を exit code で判定
4. C1 (契約衝突) と C2-004 (単一 skill 退化の根拠) を LLM 意味判定し、必要なら high finding を追加
5. findings[] を severity/bucket/observation/evidence/suggested_fix で構築
6. verdict (4条件) を確定し <PLAN_DIR>/plan-findings.json に Write

### 5.3 自己検証 checklist
- [ ] conditions に C1, C2, C3, C4 が全て PASS/FAIL/N/A で埋まっているか
- [ ] gate_results に core 5 scripts / 6 invocations + surface inventory gate + build handoff gate の exit code が記録されているか
- [ ] findings[] が空配列でなく info 以上の観点を最低 1 件含むか
- [ ] high severity がある場合 suggested_fix が明記されているか
- [ ] 単一 skill 退化の根拠欠落を C2 で検査したか
- [ ] context:fork 下で実行され plan を書き換えていないか

## Layer 6: オーケストレーション

### 6.1 上位接続
- 呼び出し元: run-plugin-dev-plan (R4 verify-traceability)
- 後続: NG は architect (R3) へ差し戻し、PASS は昇格 (run-elegant-review C1-C4)

### 6.2 並列性
- 単発 (1 plan = 1 評価)

## Layer 7: 提示

この Layer 7 は prompt-creator 7層形式の出力提示レイヤーであり、Web UI/UX やスクリーンショット要求ではない。

### 7.1 提示形式
- plan-findings.json (Markdown サマリは caller 側で生成)

### 7.2 言語
- 日本語 (JSON キーは英語)

---

## 出力指示

LLM は references/plan-rubric.json と four-condition-criteria.md に従い 4条件 + core 5 scripts / 6 invocations + surface inventory gate + build handoff gate を実行、
plan-findings.schema.json 準拠の JSON を <PLAN_DIR>/plan-findings.json に Write。
決定論ゲートの exit code を一次根拠とし、自然言語で PASS 判定しない。
余計な前置き・思考過程出力は禁止。
