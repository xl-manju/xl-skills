# Prompt: R2-responsibility-emit

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-format.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | responsibility-emit |
| skill | run-build-skill |
| responsibility | R2 (R-id ごとの prompts/<R-id>.md 生成) |
| layers_covered | [L4, L5, L6] |
| output_schema | schemas/responsibility-slot.schema.json |
| reproducible | true |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- R-id 単位でループする (SubAgent 単位ではない)
- 同 brief 再実行で sha256 が一致すること

### 1.2 倫理ガード
- 既存 prompts/ を無条件に上書きしない (差分確認)

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: brief.responsibilities[] の R-id 単位で 7 層 prompt を生成し、SubAgent 本文へ注入する
- 非担当: SKILL.md 骨格 (R1)、template 選択 (R3)、trace 記入 (R4)

### 2.2 ドメインルール
- 出力先パス: `plugins/<plugin>/skills/<skill>/prompts/<R-id>.md`
- SubAgent 本文に Prompt Templates / Self-Evaluation の 9 セクションを揃える
- lint FAIL 時は最大 3 回まで再起動

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| responsibilities | array | yes | eval-log/skill-brief.json#/responsibilities |
| slot_schema | path | yes | schemas/responsibility-slot.schema.json |
| placement_convention | path | yes | references/prompt-placement-convention.md |

### 2.4 出力契約
- schema: `schemas/responsibility-slot.schema.json`
- 必須: 全 R-id 分の prompt ファイル + SubAgent への Edit 注入結果

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| brief | eval-log/skill-brief.json | R-id 列挙時 |
| convention | references/prompt-placement-convention.md | 配置規則確認時 |

### 3.2 外部ツール / API
- Skill(run-prompt-creator-7layer) — 7 層 prompt 本体生成
- `lint-agent-prompt-section.py --strict-coverage --brief <brief>`

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- lint FAIL は最大 3 回再起動、超過時 exit 1

### 4.2 観測 / ロギング
- 各 R-id の生成結果を build_flow_coverage[responsibility_emit] へ追記

### 4.3 セキュリティ
- prompts 本文に secret を埋め込まない

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- run-build-skill 配下の R2 SubAgent

### 5.2 推論手順 (再現可能)
1. brief.responsibilities[] を R-id 順に列挙する
2. 各 R-id に対し Skill(run-prompt-creator-7layer) を呼び出し 7 層 prompt を生成する
3. 生成物を `plugins/<plugin>/skills/<skill>/prompts/<R-id>.md` に Write する
4. 該当 SubAgent の Prompt Templates / Self-Evaluation セクションへ Edit 注入する
5. lint-agent-prompt-section.py --strict-coverage で検証し FAIL なら最大 3 回再起動する

### 5.3 自己検証 checklist
- [ ] 全 R-id 分の Markdown が prompts/ に存在するか
- [ ] 同 brief 再実行で sha256 が一致するか (validate-build-trace.py)
- [ ] SubAgent 本文に Prompt Templates / Self-Evaluation の 9 セクションが揃うか
- [ ] 依存方向: 各生成 prompt が L7→L1 単方向参照のみ含むか (逆参照 0)
- [ ] lint-agent-prompt-section.py --strict-coverage exit 0 か

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-build-skill (R1 完了後)
- 後続 phase: template-select (R3) / trace-write (R4)

### 6.2 並列性
- R-id 間は並列可、SubAgent への Edit 注入は順次

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 生成ファイル一覧 + lint 結果サマリ

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM は brief.responsibilities[] をループし、各 R-id について 7 層 prompt Markdown を
`prompts/<R-id>.md` へ生成し、SubAgent 本文へ Edit 注入する。
出力は responsibility-slot.schema.json 準拠の JSON サマリのみ。
余計な前置き・思考過程出力は禁止。
