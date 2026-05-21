---
name: prompt-placement-convention
description: skill-creator が生成する skill 配下に責務単位 prompt を再現性高く格納するためのディレクトリ・命名規約。SKILL.md 本文には載せず、skill 配下サブディレクトリで物理的に隔離する。
type: reference
version: 1.0.0
---

# Skill 配下 prompt 配置規約

prompt-creator が brief.responsibilities[] ごとに生成する 7 層 YAML を、**各 skill のサブディレクトリ** に格納する規約。再現性 (同 brief → 同パス → 同 sha256) を機械検証できる形に固定する。

## 配置パス

正規パスパターン:

```
plugins/<plugin-name>/skills/<skill-name>/prompts/<responsibility-id>.yaml
```

例:

```
plugins/skill-intake/skills/run-skill-intake-aggregator/prompts/R1.yaml
plugins/skill-intake/skills/run-skill-intake-aggregator/prompts/R2.yaml
plugins/prompt-creator/skills/run-prompt-creator-7layer/prompts/R1.yaml
```

正規表現 (`validate-build-trace.py` が照合):

```
^plugins/[a-z][a-z0-9-]*/skills/(ref|run|wrap|assign|delegate)-[a-z0-9]+(-[a-z0-9]+)*/prompts/R[0-9]+\.yaml$
```

## ディレクトリ規約

| 項目 | 値 | 根拠 |
|---|---|---|
| ディレクトリ名 | `prompts/` (固定) | `agents/` は plugin 直下既存ディレクトリ。SubAgent 実体 (.md) と prompt 生成物 (.yaml) を物理的に分離するため別名 |
| ディレクトリ階層 | 1 階層のみ (ネスト禁止) | lint-skill-tree.py 第 13 条に準拠 |
| ファイル名 | `<responsibility.id>.yaml` | brief.responsibilities[].id (R1, R2, ...) と 1:1 対応 |
| 拡張子 | `.yaml` 固定 | seven-layer-format.md 正本フォーマット |
| インデックス | `prompts/index.json` (任意) | 全 yaml の sha256 + responsibility メタを一覧。`build-trace.json` への突合補助。任意生成 |

## 命名規則の根拠

- **`R[0-9]+`**: brief.responsibilities[].id の正規表現と同一 (skill-brief-schema.json `pattern: "^R[0-9]+$"`)
- **`prompts/` の選択理由**: 
  - `agents/` は `plugins/<plugin>/agents/` として既存 plugin 直下に確保済み (SubAgent .md 用)
  - skill 内部の責務 prompt は **skill 単位の成果物** であり、skill ディレクトリ配下に隔離するのが SRP に適う
  - `templates/` (kind 別正本) と区別: templates は生成入力、prompts は生成出力

## SKILL.md との関係

- **SKILL.md には prompts/ ディレクトリの内容を直接転記しない** (ユーザー要件)
- SKILL.md の `## Additional Resources` 節に「`prompts/<id>.yaml` — prompt-creator が生成する責務単位 7 層プロンプト (validate-build-trace.py で sha256 検証)」のような **案内 1 行のみ** 追加可
- SKILL.md は責務単位 prompt の内容を一切重複させない (300 行制約 + DRY)

## 再現性保証

| 検証項目 | 検証主体 | 失敗時の挙動 |
|---|---|---|
| パスが正規表現にマッチ | `validate-build-trace.py` | exit 1 (trace.prompt_generation_model.per_responsibility[].layer_yaml_path) |
| responsibility.id 集合 == prompts/*.yaml ファイル名集合 | `validate-build-trace.py` | exit 1 (anchor_coverage 相当) |
| 同 brief で 2 回生成して sha256 一致 | `validate-build-trace.py` + dogfooding test | escalation 非 none 必須 |
| SubAgent.md anchor 集合 == prompts/*.yaml ファイル名集合 | `lint-agent-prompt-section.py --strict-coverage --brief <brief>` | exit 1 |

## 既存実装との橋渡し

`run-prompt-creator-7layer` SKILL.md は出力先を `plugins/<plugin>/agents/prompts/<role>.yaml` と既定しているが、本規約導入以降は次のように切替:

| brief.responsibilities[] の有無 | 出力先 |
|---|---|
| 1 件以上あり | `plugins/<plugin>/skills/<skill>/prompts/<R-id>.yaml` (本規約) |
| 空配列 (ref/wrap で legacy) | `plugins/<plugin>/agents/prompts/<role>.yaml` (旧来パス、後方互換) |

切替は `--responsibility-id <R-id>` 引数で明示する。旧来パスは deprecated とし、`prompt-creator-trace.json` に `path_convention: "skill-local-v1" | "agents-legacy"` を必須記録する。

## 検証コマンド例

```bash
# 配置確認
ls plugins/skill-intake/skills/run-skill-intake-aggregator/prompts/

# 再現性ハッシュ確認
sha256sum plugins/*/skills/*/prompts/*.yaml

# trace との突合
python3 plugins/skill-creator/skills/run-build-skill/scripts/validate-build-trace.py \
  eval-log/skill-build-trace.json
```

## 関連参照

- `skill-brief-schema.json#responsibilities` — id 仕様
- `reproducibility-trace-schema.md#prompt_generation_model` — per_responsibility[].layer_yaml_path
- `agent-template.md#prompt-creator-連携` — SubAgent.md 側 anchor 規約
- `plugins/prompt-creator/skills/run-prompt-creator-7layer/SKILL.md` — 出力フォーマット (7 層 YAML)
