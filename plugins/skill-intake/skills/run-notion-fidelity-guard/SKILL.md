---
name: run-notion-fidelity-guard
description: intake-final-context.json から Notion ページを描画する直前に、info-collector-agent ページと同等の粒度を持つかを section_canonical_map を一次基準として機械検証する。
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
kind: run
user-invocable: true
effect: read-only
source: plugins/skill-intake
source-tier: internal
last-audited: 2026-05-22
audit-trigger: template-change
hierarchy_level: L1
rubric_refs: [ref-output-routing, run-skill-intake-aggregator]
role_suffix: fidelity-guard
owner: team-platform
since: 2026-05-22
---

# run-notion-fidelity-guard

## Purpose & Output Contract

intake-final-context.json を Notion へ描画する直前に、`info-collector-agent` (Notion page_id=35195d6503b781788e31f59b4e05e705) と同等の構造粒度を保つかを機械検証する fidelity ガード。Notion API を叩かず、**`references/canonical-page-snapshot.json` との JSON 構造比較のみ**で判定する。

- 入力: `intake-final-context.json` + `references/canonical-page-snapshot.json` (+ aggregator の `section_canonical_map.json` を派生元として参照)
- 出力: `output/<hint>/fidelity-report.json` … `sections[].present/granularity_score/missing_slots/excess_slots` と `overall_score`, `verdict ∈ {pass, warn, fail}`
- 副次出力: `output/<hint>/fidelity-report.md` (R3 delta-report, 人間可読)
- 完了条件: `verdict=pass` のときのみ呼び出し元 (`render_notion_page.py`) が公開を許可する。`fail` は exit 2、`warn` は exit 1、`pass` は exit 0。

## 既存スキルとの責務境界

| Skill / Script | 責務 | 本スキルとの境界 |
|---|---|---|
| `run-skill-intake-aggregator` | intake の中身 (5 軸 / true_purpose 等) の品質判定 | 内容妥当性は委譲 (本スキルは構造粒度のみ) |
| `run-notion-intake-publish` / `render_notion_page.py` | Notion API 経由のページ公開 | 公開直前に本スキルを呼び、`verdict=pass` のみ通す |
| `intake.schema.json` | intake-final 必須フィールド存在検査 | スキーマ準拠は委譲 (本スキルは canonical との粒度差分のみ) |

## Key Rules

1. **Canonical SoT は section_canonical_map.json**: 12 section の `required_fields / char_bounds / viz_slots` は aggregator 配下を一次正本とし、本スキルは **派生スナップショット** (`references/canonical-page-snapshot.json`) を保持する (DRY)。
2. **Notion API 直接呼び出し禁止**: 検査は JSON 構造比較のみ。API 認証情報は本スキルでは扱わない。
3. **Fail-fast**: `verdict=fail` で exit 2、呼び出し元は即停止すること。
4. **Script First**: 全判定は `scripts/*.py` (Python 3, jsonschema/jinja2 許容) で決定論実行。
5. **300 行制約**: SKILL.md は 300 行以下。詳細ルールは `references/` に分割し、`when_to_read` で誘導 (Progressive Disclosure)。
6. **命名規約**: 全 script ファイル名はハイフン区切り (28 章 §4.3, no underscore)。

## 評価ルブリック (granularity score 0-100)

| 比率 | 観点 | 評価軸 |
|---|---|---|
| 30% | char_bounds 一致 | section 本文の文字数が canonical の [min,max] に収まるか |
| 40% | required_fields 充足 | canonical の required_fields[] が context.json に全て存在し型整合するか |
| 30% | viz_slots 一致 | mandatory な viz_slots が figures/viz の配置に存在するか |

詳細は `references/granularity-rubric.md`。verdict 閾値は `references/fidelity-check-rules.md` (pass≥0.85 / warn≥0.70 / fail<0.70)。

## Responsibilities (3 layer)

| ID | 名前 | スコープ | 7-layer prompt |
|---|---|---|---|
| R1 | canonical-snapshot-extraction | aggregator の `section_canonical_map.json` から `canonical-page-snapshot.json` を派生固定 | `prompts/R1.yaml` (L2/L4/L6) |
| R2 | fidelity-check | intake-final-context.json と canonical-page-snapshot.json の section 粒度比較 + verdict 判定 | `prompts/R2.yaml` (L1/L2/L4/L5/L6) |
| R3 | delta-report | missing/excess/granularity_warnings を Markdown と exit code に変換 | `prompts/R3.yaml` (L5/L6/L7) |

## Steps

### Step 1: canonical snapshot を再生成 (template-change trigger 時のみ)

```bash
python3 plugins/skill-intake/skills/run-notion-fidelity-guard/scripts/extract-canonical-snapshot.py \
  --source plugins/skill-intake/skills/run-skill-intake-aggregator/references/section_canonical_map.json \
  --out    plugins/skill-intake/skills/run-notion-fidelity-guard/references/canonical-page-snapshot.json
```

### Step 2: fidelity check を実行 (Notion 公開直前のフック)

```bash
python3 plugins/skill-intake/skills/run-notion-fidelity-guard/scripts/validate-notion-fidelity.py \
  <intake-final-context.json>
# exit 0 = pass / 1 = warn / 2 = fail
```

レポートは `<context.json と同階層>/fidelity-report.json` + `fidelity-report.md` に出力。

### Step 3: 粒度スコア単体取得 (CI のメトリクス用、optional)

```bash
python3 plugins/skill-intake/skills/run-notion-fidelity-guard/scripts/extract-granularity-score.py <intake-final-context.json>
# stdout に overall_score (0-100) を 1 行で出力
```

## Abstraction Variables (量産時の差し替え点)

| 変数 | 既定値 | 用途 |
|---|---|---|
| `canonical_page_id` | `35195d6503b781788e31f59b4e05e705` | 派生元 Notion ページ ID (info-collector-agent) |
| `canonical_snapshot_path` | `references/canonical-page-snapshot.json` | スナップショット保存位置 |
| `fidelity_threshold_pass` | `0.85` | pass 判定の overall_score 下限 |
| `fidelity_threshold_warn` | `0.70` | warn 判定の overall_score 下限 (未満は fail) |

仕様は `references/abstraction-contract.md` を参照。

## Gotchas

1. **canonical の更新タイミング**: `section_canonical_map.json` (v2) が変わったら本スキルの `extract-canonical-snapshot.py` を再走させる。手で snapshot を書かない。
2. **char_bounds の計測対象**: Notion ブロック化前の context.json 上での該当 section の本文相当文字列 (json.dumps の長さではない — `scripts/validate-notion-fidelity.py` 内の `section_text_length()` を使用)。
3. **viz_slots は mandatory=true のみ評価**: `mandatory=false` は missing でも減点しない (warn 列にのみ記録)。
4. **fail でも report.md は出力する**: 呼び出し元が原因を読めるよう、exit=2 でも JSON/MD は必ず書き出す (fail-fast ≠ silent-fail)。

## Additional Resources (Progressive Disclosure)

| 用途 | パス | when_to_read |
|---|---|---|
| 正本構造マップ | `references/canonical-page-snapshot.json` | 各 section の required_fields / char_bounds / viz_slots を参照するとき |
| スコア算出ルール | `references/granularity-rubric.md` | 0-100 score の重み付けを確認するとき |
| verdict 閾値 | `references/fidelity-check-rules.md` | pass/warn/fail の境界とエスカレーション規約を確認するとき |
| 量産規約 | `references/abstraction-contract.md` | canonical_page_id 等のテンプレ変数を差し替えるとき |
| Progressive Disclosure 地図 | `references/resource-map.yaml` | references 全体の読み順を確認するとき |

## 関連スキル

- `run-skill-intake-aggregator` — canonical SoT (`section_canonical_map.json`) の所有者
- `run-notion-intake-publish` — 本スキルを公開直前フックとして呼ぶ予定の sibling
