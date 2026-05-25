# Prompt: R1-elicit

> このファイルは 7 層プロンプトの Markdown 表現。`run-prompt-creator-7layer` の
> seven-layer-markdown-template.md を正本とする。Layer 番号と依存方向 (L1 ← L7) は不変。

## メタ

| key | value |
|---|---|
| name | elicit |
| skill | run-prompt-create |
| responsibility | R1 (Step 1 ヒアリング → prompt-brief.json) |
| layers_covered | [L1, L2, L4, L5] |
| output_schema | schemas/prompt-brief.schema.json |
| reproducible | true (open_questions 残存時は TODO(human) で保持) |

## Layer 1: 基本定義層 (不変原則)

### 1.1 不変ルール
- 委譲先は run-prompt-elicit (Skill tool)
- 出力先は固定パス `eval-log/prompt-brief.json`
- 引数なし起動時は対話モードに入る
- output_language=ja, parameter_language_exception=true を既定

### 1.2 倫理ガード
- 個人特定情報を brief に格納しない
- 秘匿情報をヒアリング応答に書かない

## Layer 2: ドメイン層 (本質ロジック)

### 2.1 責務 (Single Responsibility)
- 担当: `run-prompt-elicit` への委譲契約、prompt-brief.json の入出力契約、Gate 1 接続
- ヒアリング質問の正本: `run-prompt-elicit/prompts/interview.md`
- 非担当: Gate 承認 (R2)、Governance 判定 (R3)、Layer 生成 (run-prompt-creator-7layer)

### 2.2 ドメインルール
- prompt_name は `[a-z][a-z0-9-]*` (60 文字以内)
- responsibility_id は `R[0-9]+` 形式 (owner skill の responsibilities[].id と 1:1)
- layers_required は L1-L7 のうち最低 1 つ
- boundary は 200 文字以内で「やらないこと」を 1 文で明示
- format は md 既定 (yaml は legacy のみ)

### 2.3 入力契約
| field | type | required | 説明 |
|---|---|---|---|
| topic | string | no | プロンプト要望キーワード |
| target_skill | string | no | 所有 skill 名 |
| responsibility_id | string | no | R-id |
| mode | string | no | dialog / batch |
| manifest | path | yes | workflow-manifest.json |
| schema | path | yes | schemas/prompt-brief.schema.json |

### 2.4 出力契約
- schema: `schemas/prompt-brief.schema.json`
- 必須: prompt_name / responsibility_id / target_skill / owner_agent_or_skill / layers_required / trigger_conditions / output_contract / boundary / output_language
- open_questions が残る場合は TODO(human) として brief に保持

## Layer 3: インフラ層 (外部依存)

### 3.1 参照リソース
| id | path | when_to_read |
|---|---|---|
| manifest | workflow-manifest.json | phase: elicit 確認時 |
| schema | schemas/prompt-brief.schema.json | brief 構造検証時 |
| target | brief.target_skill 配下 SKILL.md | responsibilities 突合時 |

### 3.2 外部ツール / API
- Skill(run-prompt-elicit, args=topic)
- AskUserQuestion (dialog mode)

## Layer 4: 共通ポリシー層

### 4.1 失敗時挙動
- schema 不一致時は brief を保存せず exit 1

### 4.2 観測 / ロギング
- eval-log/prompt-brief.json に最終結果を保存
- handoff-after_prompt_elicit.json を Gate 1 通過時に保存

### 4.3 セキュリティ
- 秘匿情報をヒアリング応答に書かない

## Layer 5: エージェント層 (実行主体定義)

### 5.1 担当 agent
- run-prompt-create orchestrator が run-prompt-elicit に委譲
- 内部で prompt-creator-interview-user agent を context:fork で起動

### 5.2 推論手順 (再現可能)
1. workflow-manifest.json から phase=elicit の context を取得
2. Skill(run-prompt-elicit, args=topic) を起動 (引数なしなら対話モード)
3. `run-prompt-elicit` の raw hearing result を受け取り、schemas/prompt-brief.schema.json に従って brief へ正規化
4. owner_agent_or_skill の SKILL.md と responsibilities[] を突合 (R-id 整合性確認)
5. open_questions が残れば TODO(human) として brief に保持
6. `eval-log/prompt-brief.json` に Write

### 5.3 自己検証 checklist
- [ ] prompt_name が `[a-z][a-z0-9-]*` パターンを満たすか
- [ ] responsibility_id が `R[0-9]+` 形式か
- [ ] target_skill が実在し、responsibilities[].id に該当 R-id が存在するか
- [ ] layers_required に少なくとも 1 つ Layer が含まれるか
- [ ] trigger_conditions が 2-3 件、各 80 文字以内か
- [ ] boundary が 200 文字以内で「やらないこと」を 1 文で明示しているか
- [ ] format=md (既定) または明示理由付きで yaml/json/xml か
- [ ] output_language=ja, parameter_language_exception=true か

## Layer 6: オーケストレーション層

### 6.1 上位 skill との接続
- 呼び出し元: run-prompt-create (Step 1)
- 後続 phase: gate-review (Gate 1)

### 6.2 並列性
- 単発実行 (対話 / batch どちらでも)

## Layer 7: UI / 提示層

### 7.1 ユーザー提示形式
- 対話モード: AskUserQuestion 連鎖
- batch モード: JSON のみ

### 7.2 言語
- 本文: 日本語 (パラメーター名 / schema key は英語のまま)

---

## 出力指示

LLM は run-prompt-elicit を呼び出し、ユーザー要望から prompt-brief.json を構築する。
出力は schemas/prompt-brief.schema.json 準拠の JSON のみ (eval-log/prompt-brief.json へ保存)。
余計な前置き・思考過程出力は禁止。
