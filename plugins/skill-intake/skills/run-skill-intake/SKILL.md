---
name: run-skill-intake
description: 非エンジニアからスキル要件を引き出すとき、intake 11 段階ワークフローを順次起動して intake.md と Notion ページを生成したいときに使う。
allowed-tools:
  - Read
  - Write
  - Bash
  - AskUserQuestion
kind: run
user-invocable: true
disable-model-invocation: true
effect: external-mutation
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-22
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
role_suffix: orchestrator
owner: team-platform
since: 2026-05-22
responsibility_refs:
  - prompts/main.md
schema_refs:
  - schemas/output.schema.json
manifest: workflow-manifest.json
---

# run-skill-intake

## Purpose & Output Contract

intake 11 phase を子 Skill / SubAgent に順次委譲し、最終成果物 `intake.md` / `intake.json` / Notion URL を生成する**薄い orchestrator**。各 phase の業務ロジックは持たない。

**入力**: ユーザーの「スキルを作りたい」要望 (topic 引数任意)
**成果物**:

| 成果物 | パス | 生成 phase |
|--|--|--|
| kickoff.json | `output/<hint>/kickoff.json` | Phase 1 |
| assumption.json | `output/<hint>/assumption.json` | Phase 2 |
| profile.json | `output/<hint>/profile.json` | Phase 3 |
| sheet.md + interview.json | `output/<hint>/` | Phase 4 |
| purpose.json | `output/<hint>/purpose.json` | Phase 5 |
| options.json | `output/<hint>/options.json` | Phase 6 |
| visuals.json + PNG 群 | `output/<hint>/visuals/` | Phase 7 |
| summary.{md,json} | `output/<hint>/` | Phase 8 |
| next-action.json | `output/<hint>/next-action.json` | Phase 9 |
| intake.{md,json} | `output/<hint>/` | Phase 10 |
| notion-url.txt | `output/<hint>/notion-url.txt` | Phase 11 |
| intake-trace.json | `eval-log/intake-trace.json` | 全 phase 共通 |

**完了条件**: 11 phase 全成功 + `quality_gate.py` PASS + `cross_check.py` PASS + Notion 公開成功。

## Key Rules

1. **業務ロジックを持たない**: 各 phase の質問雛形 / 技法選択 / 採点基準は子 Skill / SubAgent / references に閉じる。本スキルは起動順序と handoff JSON の受け渡しのみ。
2. **失敗で停止**: phase が exit != 0 / handoff JSON 検証 fail なら停止し、`intake-trace.json` に再開ポイントを記録する。
3. **handoff JSON 必須**: 各 phase 完了時に対応 JSON ファイルが存在し schema validate に通ること。違反時はその phase に戻す。
4. **SubAgent は fresh context 必須箇所のみ**: Phase 2 / 3 / 5 / 8 は同意ループ・バイアス回避のため SubAgent 起動。Phase 1 / 4 / 6 / 7 / 9 / 10 / 11 は主スレッド Skill。
5. **Secret-Out-of-Repo**: Notion トークンは Keychain から都度取得 (`scripts/keychain_get_secret.py`)。

## Workflow (11 phase 順序固定)

```
[起動] /intake [topic]
  ↓
[Phase 1]  Skill        run-intake-kickoff             → kickoff.json
  ↓
[Phase 2]  SubAgent     skill-intake-assumption-challenger → assumption.json
  ↓
[Phase 3]  SubAgent     skill-intake-user-profiler     → profile.json
  ↓
[Phase 4]  Skill        run-intake-interview           → sheet.md + interview.json
  ↓                                                    (needs_excavation=true なら Phase 5 へ、false ならスキップ可)
[Phase 5]  SubAgent     skill-intake-purpose-excavator → purpose.json
  ↓
[Phase 6]  Skill        ref-intake-option-catalog      → options.json
  ↓
[Phase 7]  Skill        run-intake-visualize           → visuals.json + PNG 群
  ↓
[Phase 8]  SubAgent     skill-intake-summarizer (Gate A) → summary.{md,json} + ユーザー承認
  ↓
[Phase 9]  Skill        run-intake-next-action         → next-action.json
  ↓
[Phase 10] Skill        run-intake-finalize            → intake.{md,json}
  ↓
[Phase 11] Skill        run-notion-intake-publish      → notion-url.txt
[完了]
```

各 phase の I/O contract と handoff JSON schema は `references/handoff-contract.md` 参照。

## Steps (orchestrator として)

### Step 0: 前提検証

```bash
python3 plugins/skill-intake/scripts/keychain_get_secret.py --check
python3 plugins/skill-intake/scripts/verify_notion_schema.py --on-conflict skip-warn
```
exit 44 なら `references/keychain-setup.md` を案内して停止。

### Step 1: hint 確定と output ディレクトリ作成

topic から `skill_name_hint` を仮決定し `output/<hint>/` と `eval-log/intake-trace.json` を初期化。

### Step 2-12: 各 phase の順次起動

phase ごとに以下のループを実行:

1. handoff 前提 JSON の存在検証
2. 対象 Skill / SubAgent を Skill / Task tool で起動
3. 完了後、対応 JSON の schema validate (`scripts/validate-phase-handoff.py --phase N`)
4. `eval-log/intake-trace.json` に `{phase, agent, started_at, finished_at, handoff_path, status}` を追記
5. fail 時は停止し再開ポイントを表示

**主スレッド Skill (Phase 1/4/6/7/9/10/11)**: `Skill(<skill-name>)` で起動
**SubAgent (Phase 2/3/5/8)**: 対応 agent (`plugins/skill-intake/agents/skill-intake-*.md`) を Task tool で起動

### Step 13: 完了検証

```bash
python3 plugins/skill-intake/scripts/quality_gate.py output/<hint>/intake.json
python3 plugins/skill-intake/scripts/cross_check.py output/<hint>/intake.json output/<hint>/intake.md
```
両者 PASS で完了レポートを出力。

## 既存スキルとの関係

| Skill | 関係 |
|---|---|
| `run-skill-intake-aggregator` | 本スキルの**前身**。Phase C 完了時に deprecate 予定 (置き換え) |
| `run-skill-elicit` | 技術者向け簡易 brief 生成。本スキルと併存 (用途別) |
| `run-skill-create` | Step 1 から本スキル or run-skill-elicit を呼ぶ上位 orchestrator |
| `run-notion-intake-publish` | Phase 11 で起動する sibling |
| `run-notion-fidelity-guard` | Notion 公開前 lint。Phase 11 内部で起動 |

## Slash Commands

| コマンド | 用途 |
|--|--|
| `/intake [topic]` | 本スキルを起動 (= 11 phase 全実行) |
| `/intake-publish <hint>` | 既存 intake を Notion 再公開のみ |
| `/intake-status <hint>` | 進行中ヒアリングの状況確認 |

## Gotchas

1. **業務ロジックを本スキルに書かない**: 質問雛形 / 採点基準 / Notion blocks 生成は子 Skill 配下にとどめる。違反は SRP 違反として lint で警告。
2. **Phase 4→5 スキップ判定**: `interview.json.needs_excavation=false` なら Phase 5 をスキップして Phase 6 へ進める。
3. **Gate A (Phase 8) で停止可能**: ユーザーが summary を否認した場合は Phase 4 へ戻り再ヒアリング (最大 2 周)。
4. **SubAgent fresh context**: Phase 2/3/5/8 は必ず Task tool 経由で起動し、主スレッド context を渡さない (バイアス回避)。

## Additional Resources

- `references/workflow-sequence.md` — 11 phase の起動順序と前提 JSON 依存図
- `references/handoff-contract.md` — 各 phase の handoff JSON schema 一覧 (旧 aggregator references から移管)
- `references/resource-map.yaml` — 他 reference を読む前の最小読込先マップ
- 子 Skill: `run-intake-kickoff` / `run-intake-interview` / `ref-intake-option-catalog` / `run-intake-visualize` / `run-intake-next-action` / `run-intake-finalize` / `run-notion-intake-publish`
- SubAgent: `skill-intake-assumption-challenger` / `skill-intake-user-profiler` / `skill-intake-purpose-excavator` / `skill-intake-summarizer`
