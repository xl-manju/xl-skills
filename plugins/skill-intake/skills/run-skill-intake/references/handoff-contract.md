# Handoff Contract (run-skill-intake 11 phase)

各 phase の JSON schema 概要。詳細スキーマは旧 aggregator `references/handoff-contract.md` を継承する (Phase C で本ファイルへ統合予定)。

## Phase 1: kickoff.json

```json
{"pattern":"A|B|C|D|E","depth":"quick|standard|detailed","skill_name_hint":"...","pain_ranking":[{"task":"...","frequency_per_week":N,"minutes_per_run":N}],"initial_utterance":"...","timestamp":"ISO8601"}
```

## Phase 2: assumption.json

```json
{"surface_request":"...","deep_candidates":[{"id":"D1","label":"..."}],"user_picked":"D1","confirmed_deep_problem":"...","time_freed_intent":"...","blind_spots":["..."]}
```

## Phase 3: profile.json

```json
{"dimensions":{"expertise":{"level":"low","evidence":"...","confidence":"high"},"role":{...},"context":{...},"constraints":{...},"motivation":{...},"sharing_intent":{...}},"vocabulary_tier":"beginner|intermediate|expert"}
```

## Phase 4: interview.json

```json
{"filled_ratio":0.85,"five_axes_complete":true,"unresolved":["..."],"needs_excavation":true,"abstract_answers":["..."]}
```

## Phase 5: purpose.json

```json
{"techniques_used":["5whys"],"rounds":4,"agreement_loop_detected":false,"true_purpose":{"verb_object":"...","underlying_motivation":"...","time_freed_minutes_per_week":N,"use_of_freed_time":"..."},"remaining_doubts":[]}
```

## Phase 6: options.json

```json
{"selected_integrations":[{"id":"...","name":"...","tier":"required|optional"}],"rejected":[{"id":"...","reason":"..."}]}
```

## Phase 7: visuals.json

```json
{"sections":[{"section_id":"§3","mermaid_refs":["mtmpl-flow"],"svg_refs":["cvis-axes"],"png_paths":["visuals/§3.png"]}]}
```

## Phase 8: summary.json

```json
{"five_axes":{"output_target":"...","info_source":"...","share_target":"...","true_problem":"...","knowledge_assets":{"needed":true,"existing_sources":["..."]}},"approval_status":"approved|revision_requested","user_feedback":"..."}
```

## Phase 9: next-action.json

```json
{"mode":"A|B|C|D|E","reason":"...","multi_skill_suspicion":false,"split_candidates":[{"name":"...","responsibility":"..."}],"skill_creator_handoff_phase":"Phase 1 (kickoff)"}
```

## Phase 10: intake.json

旧 aggregator `references/handoff-contract.md` の `intake-final-schema.json` に準拠。

## Phase 11: notion-url.txt

Notion ページ URL を 1 行で記録。
