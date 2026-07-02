# harness-creator

Claude Code の**ハーネス** — Capability (Skill / Agent / Hook / Command / Plugin-Composition / Prompt / Workflow) と、その評価・統治機構 (rubric / verdict / lint / feedback loop) を束ねた**構築物の総体** — を構築・評価・統治するメタプラグイン。

## ハーネスとは / なぜ skill-creator から改名したか

本 plugin は 2026-07-02 に `skill-creator` から `harness-creator` へ改名した。理由: このプラグインが構築しているのは単体のスキルではなく、スキル・エージェント・フック・コマンド・評価・統治を束ねた**ハーネス全体**だから。

用語は次の意味論境界に従う (正本: `skills/ref-skill-glossary/references/terms.md` の「ハーネス」エントリ、規約: リポジトリ root の `CONVENTIONS.md`):

| 概念 | 表現 | 例 |
|---|---|---|
| 単体スキルを作る (部品単位) | スキル / skill | `run-skill-create`, `run-build-skill`, `run-skill-rename` |
| 総体を構築する (メタ能力) | ハーネス / harness | plugin 名 `harness-creator`, `harness-creator-kit` |

内部 skill 名 (`run-skill-*` 等) が skill 語を保つのは中途半端な改名ではなく**意図的設計**: それらの操作対象は単体 skill であり、`SKILL.md` / `skills/` / Skill tool は Claude Code プラットフォームの予約語彙でもある。既存の harness 語 (`doc/harness-coverage-spec.md` = 構築物総体の品質装具) は同系譜の概念で、本 plugin 名はその系譜に連なる。

## 改名の移行手順 (ローカル環境)

plugin 名には aliases 機構が無いため、改名前から使っている開発環境では enabledPlugins キーの切替が必要:

1. `.claude/settings.json` の `"skill-creator@xl-skills": true` を削除 (旧キーは無害だが plugin が未ロードになり hooks が黙って発火しなくなる)
2. `"harness-creator@xl-skills": true` を追加
3. `make sync` で `.claude/` symlink を再生成

過去の評価履歴は `eval-log/skill-creator/` に凍結保存されている (遡及書換なし)。改名後の新規 run は `eval-log/harness-creator/` に記録される。

## 構成

- `skills/` — 33 skill (生成: run-* / 評価: assign-* / 参照知識: ref-* / 委譲: delegate-*)
- `agents/` — elegant-review 系 5 体 + run-build-skill-subagent
- `commands/` — /capability-build, /capability-review, /skill-improve, /plugin-compose, /install-bundle
- `scripts/` — feedback_contract_ssot.py (dogfooding 境界 SSOT・vendored byte 一致 lint 対象) ほか
- `plugin-composition.yaml` — CapabilityBundle 宣言 (リファレンス実装)

単独配布非対応 (`distributable: false`, NEVER_DISTRIBUTE denylist 登録済み)。repo を clone した開発環境でのみ `.claude/` symlink 経由で利用する。
