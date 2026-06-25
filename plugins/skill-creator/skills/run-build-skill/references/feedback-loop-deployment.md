# feedback-loop 配備 (default-ON)

量産プラグインに `run-skill-feedback` を 100% 再現性で同梱する仕組みの詳細。SKILL.md Step 11.5 から参照される。

## 5 層設計

| 層 | 目的 | 実装 |
|----|------|------|
| L1 SSOT 同期 | 発火条件文言の正本一本化 | `doc/notion-schema/skill-list.schema.json#feedback_protocol` を `notion-upsert-plugin.py` の `_load_feedback_protocol()` 経由で全派生物が引く |
| L2 周知 | 発火経路 (`/run-skill-feedback <plugin>`) を量産先で見える化 | `plugin.json` description / README / commands / agents いずれかに記載 |
| L3 配備 | 量産先に skill を物理配置 | phase `feedback-deploy` が `plugins/<plugin>/skills/run-skill-feedback` を skill-creator 正本への相対 symlink で冪等配備 |
| L4 強制 | 周知/配備の有無を CI で機械検査 | `scripts/lint-feedback-protocol.py --strict` の R6 (周知) / R7 (配備存在) |
| L5 検証 | schema / SKILL.md / upsert 三者整合 | 同 lint の R1-R5 (offline、NOTION_TOKEN 不要) |

## 配備フロー

```
brief.kind ∈ {run, ref, assign, delegate, wrap}
  └─ build pipeline (workflow-manifest.json)
       └─ phase: feedback-deploy (default_on: true, dependsOn: trace-write)
            └─ scripts/render-combinators.py apply_feedback_loop(<plugin>)
                 └─ plugins/<plugin>/skills/run-skill-feedback
                      → ../../skill-creator/skills/run-skill-feedback (relative symlink)
```

skill-creator 自身は自動除外 (正本側に symlink を貼ると循環)。

## opt-out

`brief.no_feedback_loop: true` または CLI `--no-feedback-loop` 指定時のみ skip。

- trace.layer_decisions に理由 (drift リスクを引き受ける明示的判断) を必須記録。
- CI で R7 が WARN になり、`--strict` で fail。

## 禁止

- 物理コピー: `cp -r skill-creator/skills/run-skill-feedback plugins/<plugin>/skills/` 等。R3/R4 lint が即時 fail する。
- 量産先 SKILL.md での `feedback_protocol` 文言再定義: SSOT を持たない drift の温床。
- 発火条件追加を SKILL.md / triggers 先行編集で行うこと: 必ず schema → lint → 派生物同期の順。

## 関連

- `workflow-manifest.json` phase `feedback-deploy`
- `schemas/build-flags.schema.json#no_feedback_loop`
- `scripts/render-combinators.py apply_feedback_loop()`
- `/scripts/lint-feedback-protocol.py` (top-level、R1-R7)
- `plugins/skill-creator/skills/run-skill-feedback/SKILL.md`
