# Prompt: R1-seven-layer-prompt-emit-and-inject

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> `references/seven-layer-format.md` を正本とし、骨格は
> `references/seven-layer-markdown-template.md` を写経している。
> Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | main |
| skill | run-prompt-creator-7layer |
| responsibility | R1-seven-layer-prompt-emit-and-inject |
| layers_covered | [L2, L4, L5, L6] |
| output_schema | schemas/output.schema.json |
| reproducible | true (同入力 → 同出力を保証) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 1 Layer = 1 出力。7 層を 1 度のレスポンスで生成してはならない (背景: Layer 間の依存方向 L7→L1 を可視化し、レビュー単位を独立化するため)。
- 決定論部分 (scaffold / merge / validate / lint) は Node/Python スクリプトに委譲し、LLM は意味判断のみ行う (背景: 再現性とテスト容易性を担保するため)。
- 出力契約は `schemas/output.schema.json` (additionalProperties:false) を唯一の正本とする。

### 1.2 倫理ガード
- skill-brief に含まれる利用者個人情報・社外秘識別子は trace.json / prompt 本文に転記しない。
- 既存 SubAgent .md を上書きする際は対象セクション (`Prompt Templates`, `Self-Evaluation`) 以外を変更しない。

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: skill-brief またはヒアリング結果から 7 層プロンプトを Layer 単位で生成し、merge → validate → owner_agent .md へ注入するまでの単一フロー。
- 非担当: 9 セクション骨格生成 (run-build-skill 責務) / brief 自体の作成 (run-skill-elicit 責務) / governance lint 本体 (skill-governance-lint 責務)。

### 2.2 ドメインルール
- `--responsibility-id` が指定された場合は `skill-local-v1` 規約で
  `plugins/<plugin>/skills/<skill>/prompts/<R-id>.md` を既定出力先とする。
- `--responsibility-id` 省略時のみ `agents-legacy` フォールバックを許可する
  (発火条件: brief.responsibilities[] が空である ref/wrap/delegate 系 skill)。
- 全ルール / 制約は「目的 + 背景」併記とする (`writing-style-principles.md` 準拠)。

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| skill-brief | path | yes | `run-skill-elicit` 産出の brief.json |
| responsibility-id | string | conditional | `skill-local-v1` 既定で必須、`brief.responsibilities[].id` と 1:1 |
| target-agent | path | no | owner_agent がある場合のみ注入対象として指定 |
| format | enum(yaml/md/json/xml) | no | 既定 md (本テンプレ準拠)、ループ呼出時は呼出側既定値を尊重 |
| inject-sections | csv | no | 既定 "Prompt Templates,Self-Evaluation" |

### 2.4 出力契約
- schema: `schemas/output.schema.json` (additionalProperties:false)
- 必須フィールド: `path_convention`, `responsibility_id`, `layer_md_path`, `sha256`
- 補助出力: `eval-log/prompt-creator-trace.json` (Phase 別 trace)

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| seven-layer-format | references/seven-layer-format.md | Phase 4-A 直前 |
| markdown-template | references/seven-layer-markdown-template.md | Phase 4-A scaffold 前 |
| quality-criteria | references/quality-criteria.md | Phase 4-B 直前 |
| writing-style | references/writing-style-principles.md | Phase 4-A 全域 |
| hearing-schema | schemas/hearing-result.schema.json | Phase 1 終了時 validate |

### 3.2 外部ツール / API
- `node scripts/scaffold_prompt.js` — Layer 別雛形生成
- `node scripts/merge_layers.js` — 1 prompt md/yaml へ統合
- `node scripts/validate_prompt.js` — schema/構造検証
- `node scripts/verify_completeness.js` — Layer 充足検証
- `python3 plugins/skill-governance-lint/scripts/lint-agent-prompt-section.py` — 戻り検証
- `node scripts/log_usage.js` — `LOGS.md` への利用統計記録

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- `validate_prompt.js` / `verify_completeness.js` / `lint-agent-prompt-section.py` のいずれかが FAIL した場合は Phase 4-A から最大 3 回まで自律修正を反復する。
- 3 回超過時は exit 非 0 で orchestrator に差戻し、trace.json に `status: "deferred"` を残す。

### 4.2 観測 / ロギング
- `eval-log/prompt-creator-trace.json` に Phase 単位で append (sha256 を含む)。
- 成功 / 失敗を `LOGS.md` へ `log_usage.js` 経由で記録 (失敗パターン蓄積)。

### 4.3 セキュリティ
- skill-brief 内の秘匿フィールドはハッシュ化して trace に格納。
- target-agent への Edit 注入時、`inject-sections` 範囲外への副作用を diff 確認する。

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- `prompt-creator-interview-user` / `prompt-creator-generate-prompt` / `prompt-creator-review-prompt`
- context-fork: Phase 4-A の Layer 別生成は agent ごとに分離 context で行う。

### 5.2 推論手順 (再現可能)
1. ヒアリング結果を `schemas/hearing-result.schema.json` で検証する。
2. `scaffold_prompt.js` で Layer 別 .md 雛形を生成する。
3. 1 Layer = 1 出力で本文を充填する (一括生成禁止)。
4. `merge_layers.js` で 1 つの prompt .md に統合する。
5. `validate_prompt.js` → `verify_completeness.js` → `lint-agent-prompt-section.py` を順に実行する。
6. `owner_agent` がある場合のみ対象 SubAgent .md へ Edit で注入する。
7. `eval-log/prompt-creator-trace.json` を `schemas/output.schema.json` に従い出力する。

### 5.3 自己検証 checklist
- [ ] 1 Layer = 1 出力を遵守したか (一括生成していないか)
- [ ] 全ルール / 制約に目的 + 背景を併記したか (`writing-style-principles.md`)
- [ ] SKILL.md / SubAgent .md が各 300 行以下に収まっているか
- [ ] `validate_prompt.js` / `verify_completeness.js` / `lint-agent-prompt-section.py` が全 PASS したか
- [ ] trace.json の sha256 が layer .md の実体と一致するか

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: `run-skill-create` / `run-build-skill` (Step 7.5) / 手動 user-invocation
- 後続 phase: `lint-agent-prompt-section.py` 戻り検証 → orchestrator への完了報告

### 6.2 並列性
- Layer 単位生成は Layer 内では並列化可、Layer 間は依存方向 (L7→L1) を保持して逐次。
- 同一 responsibility-id への同時実行は排他 (trace.json の競合を避けるため)。

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 生成 prompt: Markdown (本テンプレ準拠)
- trace / output: JSON (`schemas/output.schema.json`)

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key / Layer 識別子は英語のまま)

---

## 出力指示 (LLM 実行時に読む箇所)

LLM はここから下の指示のみを実行し、Layer 1〜7 はコンテキストとして参照する。

入力 `{{skill-brief}}` / `{{responsibility-id}}` / `{{target-agent}}` / `{{format}}` /
`{{inject-sections}}` を受け取り、Layer 5.2 の手順に従って 7 層プロンプトを生成・
注入・trace 出力する。出力は Layer 2.4 で宣言した
`schemas/output.schema.json` に準拠した JSON のみとし、前置き・後書き・思考過程は
出力しない。Markdown 生成物は `references/seven-layer-markdown-template.md` の
骨格を写経し、本文を responsibility 固有の domain で置換する。
