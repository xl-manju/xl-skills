---
name: ref-intake-option-catalog
description: 外部連携カタログから候補を引いて選択肢化したいとき、purpose.json を基に options.json を生成したいときに使う。
allowed-tools:
  - Read
  - Write
kind: ref
disable-model-invocation: false
effect: local-artifact
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-22
audit-trigger: monthly
hierarchy_level: L1
rubric_refs: []
owner: team-platform
since: 2026-05-22
responsibility_refs:
  - prompts/search-summarize.md
---

# ref-intake-option-catalog

## Purpose & Output Contract

Phase 6 担当。purpose.json の `true_purpose.verb_object` を基に、`references/integration-catalog-pointer.md` 経由で外部連携候補 (Slack / Notion / Gmail / Drive / Linear 等) を引き、ユーザーに提示して `options.json` を生成する。

**入力**: `purpose.json`, integration カタログ
**出力**: `output/<hint>/options.json` (selected_integrations / rejected)
**完了条件**: 必須 (tier=required) 連携が全て選択済み + ユーザーが選択肢確認に応答。

## Key Rules

1. **カタログ参照のみ**: 新規連携の追加・カタログ書き換えはしない。読み取り専用。
2. **必須/任意の明示**: 各候補に tier (required / optional) を付ける。
3. **rejected の理由必須**: ユーザーが除外した候補は `reason` を必ず記録する。

## Steps

### Step 1: purpose.json 読込

`true_purpose.verb_object` と `time_freed_intent` を抽出。

### Step 2: カタログから候補抽出

`integration-catalog-pointer.md` 経由で旧 aggregator references/integration-catalog.md を読み、verb_object に親和する連携候補を抽出。

### Step 3: ユーザー選択取得

候補を AskUserQuestion で提示し、selected / rejected を確定。

### Step 4: options.json 書き出し

```json
{
  "selected_integrations": [{"id": "notion-publish", "name": "Notion 公開", "tier": "required"}],
  "rejected": [{"id": "slack-notify", "reason": "通知不要"}]
}
```

## Gotchas

1. **新規連携を提案しない**: カタログ外の連携を引き出したい場合は別 phase で Skill 拡張を検討する。
2. **tier=required の自動採用**: 必須連携は提示するが除外も認める (reason 必須)。

## Additional Resources

- `references/integration-catalog-pointer.md` — 旧 aggregator references への参照ガイド
- `references/tier-criteria.md` — required / optional の判定基準
