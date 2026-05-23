# Elicit Question Bank

> doc/prompt-creator/references/prompt-sheet-template.md と writing-style-principles.md を起点に整理した質問テンプレ。3-5 問 + 評価優先度に絞る。質ベース判定 (実行可能か / 検証可能か) を基準にする。

## 必須質問 (3-5 問に圧縮)

1. **prompt_name** — このプロンプトの slug (kebab-case) は?
   - 例: `elicit`, `gate-review`, `governance-decide`
2. **target_skill + responsibility_id** — どの skill のどの responsibility (R-id) を充填しますか?
   - 例: `run-skill-create` の `R2 (gate-review)`
3. **layers_required** — どの Layer を生成しますか? (L1-L7 から複数)
   - 既定推奨: 担当責務に応じて L4/L5/L6 中心、または全層
4. **boundary** — このプロンプトが**やらない**ことは何ですか? (1 文 200 字以内)
   - 例: 「ヒアリングと Governance 判定は対象外」
5. **output_contract** — 出力すべき成果物 (JSON schema / artifact パス) は?

## 評価優先度 (Pass 0 動的基準用)

`evaluation_priorities` として 2-3 個ピック:
- 網羅性 / 整合性 / 深度 / 実用性 / 再現性 / 自己検証充足 / Layer 依存方向 / 要素原子性

## 任意追加質問 (必要時のみ)

- self_evaluation_checklist (L5.3 自己検証 5-8 項目)
- inject_sections (既定: `Prompt Templates, Self-Evaluation`)
- format (既定: `md`、yaml/json/xml は legacy のみ)
- trigger_conditions (2-3 件、各 80 字以内、kind と整合)

## 導出確認テンプレ

AI が target_skill の SKILL.md から推定した値は次の形でユーザーに確認:

```
[導出確認] target_skill=<x> の responsibilities[<i>] から以下を推定しました:
- responsibility_id: R<n>
- layers_required: [L<...>]
- boundary: <推定文>
この内容で進めて良いですか? (はい / 修正)
```

## アンチパターン

- 「3 つ以上挙げて」のような数量カウント要求 (質ベースに反する)
- 7 層全部を 1 回で埋めようとする (Layer 単位生成原則違反)
- ユーザーが回答済みの項目を再質問する
- AI 推定値を導出確認なしに confirm 扱いする
