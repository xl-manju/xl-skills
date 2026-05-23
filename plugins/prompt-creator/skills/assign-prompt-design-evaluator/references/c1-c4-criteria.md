# C1-C4 評価基準 (人間向け詳細)

> `prompt-rubric.json` の機械可読版を解説。doc/prompt-creator/references/quality-criteria.md と整合。

## C1: Layer 整合

L1-L7 が `seven-layer-format.md` と整合し、Layer 番号と役割名の対応が崩れていないか。

**Failing シグナル**:
- L3 を「ドメイン定義」と書いている (本来 L3 はインフラ)
- Layer が 8 つ以上ある / 6 つ以下に潰れている
- メタ表に name / skill / responsibility / layers_covered のいずれかが欠落

## C2: 依存方向 (L7→L1 単方向)

外側 Layer (L7) が内側 (L1) を参照するのは OK。逆方向参照は CA 違反。

**Failing シグナル**:
- L1 不変定義の中で L5 エージェント名を直接参照
- L3 (インフラ) が L6 (オーケストレーション) のフェーズ名を hardcode
- ID 参照 (@agent_1) ではなく名前参照で曖昧性を残す

## C3: 再現性

同じ入力で同じ出力を得る根拠が揃っているか。

**Failing シグナル**:
- reproducible: false (本当に確率的でない限り FAIL)
- output_schema 未指定または存在しないパス
- 5.2 推論手順が「適宜判断」「状況に応じて」などの曖昧語で終わる
- script_refs が空で全工程 LLM 判断

## C4: Self-Evaluation 充足

L5.3 self_evaluation_checklist が客観判定可能な 5-8 項目か。

**Failing シグナル**:
- 「品質が高いか?」のような主観項目
- checklist が 4 項目以下 (不足) または 9 項目以上 (冗長)
- placeholder `{{...}}` / `TODO(human)` / 英語仮文の残存

## 自動承認との関係

`prompt-rubric.json` の `global_thresholds` を満たすと `prompt_specific_auto_approve_conditions` が全 PASS となり、Gate 4 で `solo_operator_auto` となる。
