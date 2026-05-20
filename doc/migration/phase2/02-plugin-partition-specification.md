# タスク 02: plugin 分割境界仕様

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| ID | phase2-02 |
| 名称 | plugin 分割境界仕様 |
| 担当 | AI (草案) + solo_operator (境界承認) |
| 期限 | 01 完了から 5 営業日以内 |
| 依存タスク | phase2-01 |
| ステータス | 未着手 |

## Section 2. 目的と背景

01 の inventory で `verdict == "migrate-to-plugin"` と判定された全資産を、複数 plugin に再編するための **境界 (partition)** を確定する。境界が曖昧だと:

- 同一 skill が複数 plugin に重複定義され INV-9 (namespace 重複) で 06 が止まる
- plugin 間の参照が発生し公式制約 e (plugin 境界外参照ゼロ) を満たさない
- creator-kit/skills/ の責務分類 (`ref-*` / `run-*` / `assign-*` / `wrap-*` / `delegate-*`) が plugin 単位で混在する

ため、本タスクで「どの skill / agent をどの plugin にまとめるか」「plugin 名はどうするか」を機械検証可能な partition-plan.json として固定する。

根拠: `doc/ClaudeCodeスキルの設計書/05-layering-skill-subagent-hook-mcp-cli.md` (レイヤ責務分離)、`doc/ClaudeCodeスキルの設計書/06-classification-and-naming.md` (命名規約)、`doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md` (公式制約 e)。

## Section 3. 用語集 (本タスク固有)

| 用語 | 定義 |
|---|---|
| partition | 残資産を複数 plugin に分割する単位。1 partition = 1 plugin |
| 境界 | partition 間で資産が排他であること。同一資産が複数 partition に属してはならない |
| 親類 (kin) | 同じ責務クラスに属する skill 群 (例: `ref-*` 全部、`run-*` 全部) |
| 命名根拠 | 各 partition の plugin 名を選んだ理由 (06章命名規約への適合根拠) |
| 結合度 | partition 間の参照本数。0 が望ましい (公式制約 e) |

共通用語は README 参照。

## Section 4. スコープ

含む:

- 01 inventory の `migrate-to-plugin` 群を partition に割り当て
- 各 partition の plugin 名、責務、含む資産 (skills/agents/commands/hooks) の確定
- partition 間の重複・境界外参照ゼロの機械検証
- `partition-plan.json` の生成と固定 (本タスク承認後は P0_breaking)

含まない:

- 各 plugin の物理移行手順 (03 の責務)
- rollback 戦略 (04 の責務)
- partition に属さない `keep-non-plugin` 資産の扱い (07 で個別判断)

## Section 5. 前提条件

1. phase2-01 が DoD-1〜7 全 PASS
2. `eval-log/task/phase2-01/residual-inventory.json` が存在し、`migrate-to-plugin` 件数 >= 1
3. `creator-kit/skills/<skill>/SKILL.md` の frontmatter `name` がディレクトリ名と一致 (Phase 0 で確認済)

### 依存ツールCLI契約確認

- 本タスクは新規 CLI を導入しない
- frontmatter 読み出しは `python3 -c "import yaml"` (PyYAML) または独自パーサで実施
- PyYAML 未導入の場合、`grep -E "^name:"` で代替可

## Section 6. 完了条件 (DoD)

| DoD | 内容 | 機械検証 |
|---|---|---|
| DoD-1 | `eval-log/task/phase2-02/partition-plan.json` が存在し JSON valid | `python3 -c "import json;json.load(open('eval-log/task/phase2-02/partition-plan.json'))"` |
| DoD-2 | 全 partition の `name` が `doc/ClaudeCodeスキルの設計書/06-classification-and-naming.md` の plugin 命名規約に適合 | partition-plan.json の各 name に対する正規表現検査 |
| DoD-3 | 01 の `migrate-to-plugin` 全件が asset kind (skills/agents/commands/hooks) ごとに exactly 1 つの partition に割当 (重複なし、欠落なし) | partition-plan.json と residual-inventory.json の集合一致 |
| DoD-4 | partition 間の依存参照本数 = 0 (公式制約 e) | 各 SKILL.md の plugin 外参照 grep |
| DoD-5 | 各 partition に責務 1 行サマリと命名根拠を記載 | `description` と `naming_rationale` フィールド必須 |
| DoD-6 | `plugins/skill-creator/` (試験移行済) と partition 名が重複しない | name の集合検査 |
| DoD-7 | `review-approval.json` が `decision == "approved"` で生成 | 内容検査 |

## Section 7. 実行手順

### Step 7.1 親類グルーピング草案

責務クラス別に skill を初期グルーピング:

```bash
python3 <<'PY' > eval-log/task/phase2-02/kin-grouping-draft.json
import json, pathlib
inv = json.loads(pathlib.Path('eval-log/task/phase2-01/residual-inventory.json').read_text())
groups = {}
for r in inv['records']:
    if r['verdict'] != 'migrate-to-plugin': continue
    rel = r['rel']
    if not rel.startswith('skills/'): continue
    name = rel.split('/')[1]
    prefix = name.split('-')[0]  # ref / run / assign / wrap / delegate / ...
    groups.setdefault(prefix, []).append(name)
print(json.dumps(groups, indent=2, ensure_ascii=False))
PY
```

### Step 7.2 partition 草案策定

親類グルーピングをそのまま plugin にする案、責務横断で 1 plugin にする案など複数案を作る。命名は 06章命名規約 (kebab-case、`<verb>-<target>` 系) に従う。

候補 plugin 名 (例、TODO(human) で確定):

- `skill-references` (ref-* 親類を集約)
- `skill-runners` (run-* 親類を集約)
- `skill-governance` (assign-* / delegate-* / wrap-* を集約)

solo_operator がこの案を確定する (本ファイル単独では命名を決定しない)。

### Step 7.3 partition-plan.json 生成

```json
{
  "generated_at": "...",
  "partitions": [
    {
      "name": "<plugin-name>",
      "description": "<1行責務サマリ>",
      "naming_rationale": "<命名根拠 (06章 第n条参照)>",
      "skills": ["<skill-name>", ...],
      "agents": ["<agent-file>", ...],
      "commands": [],
      "hooks": []
    }
  ]
}
```

### Step 7.4 境界検証

```bash
python3 <<'PY'
import json, pathlib
plan = json.loads(pathlib.Path('eval-log/task/phase2-02/partition-plan.json').read_text())
all_skills = []
for p in plan['partitions']:
    all_skills.extend(p['skills'])
assert len(all_skills) == len(set(all_skills)), '重複 partition 配属あり'
inv = json.loads(pathlib.Path('eval-log/task/phase2-01/residual-inventory.json').read_text())
mig_skills = sorted({r['rel'].split('/')[1] for r in inv['records'] if r['verdict']=='migrate-to-plugin' and r['rel'].startswith('skills/')})
assert sorted(set(all_skills)) == mig_skills, f'集合不一致 (skills): missing={set(mig_skills)-set(all_skills)} extra={set(all_skills)-set(mig_skills)}'
# agents / commands / hooks 集合検証
for kind in ('agents', 'commands', 'hooks'):
    assigned = []
    for p in plan['partitions']:
        assigned.extend(p.get(kind, []))
    assert len(assigned) == len(set(assigned)), f'重複 partition 配属あり ({kind})'
    expected = sorted({r['rel'].split('/', 1)[1] for r in inv['records'] if r['verdict']=='migrate-to-plugin' and r['rel'].startswith(f'{kind}/')})
    assert sorted(set(assigned)) == expected, f'集合不一致 ({kind}): missing={set(expected)-set(assigned)} extra={set(assigned)-set(expected)}'
print('partition boundary OK (skills + agents + commands + hooks)')
PY
```

### Step 7.5 境界外参照ゼロ確認

```bash
for s in $(jq -r '.partitions[].skills[]' eval-log/task/phase2-02/partition-plan.json); do
  python3 scripts/lint-external-refs.py --skills-dir "creator-kit/skills/$s" --fail-on-external --json \
    > "eval-log/task/phase2-02/extref-$s.json" || true
done
```

`|| true` はログ採取を継続するためだけに使う。後続集計で各 JSON の `external_refs` を確認し、partition 内参照を allow-list として除外したうえで partition 外参照が 1 件でもあれば DoD-4 は FAIL とする。

### Step 7.6 README 更新

`doc/migration/phase2/README.md` のステータスを「完了 (YYYY-MM-DD)」に更新。partition 一覧表を README 末尾に追記 (参照しやすさのため)。

### Step 7.7 レビュー承認

solo_operator が `review-approval.json` を生成。

## Section 8. 検証手順

| 完了条件 | 検証コマンド |
|---|---|
| DoD-1 | DoD 表の inline |
| DoD-2 | `python3 -c "import json,re;d=json.load(open('eval-log/task/phase2-02/partition-plan.json'));assert all(re.fullmatch(r'[a-z][a-z0-9-]*', p['name']) for p in d['partitions'])"` |
| DoD-3 | Step 7.4 のスクリプト |
| DoD-4 | Step 7.5 の集計 (`jq` で `external_refs` 合計が 0) |
| DoD-5 | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-02/partition-plan.json'));assert all(p.get('description') and p.get('naming_rationale') for p in d['partitions'])"` |
| DoD-6 | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-02/partition-plan.json'));ns={p['name'] for p in d['partitions']};assert 'skill-creator' not in ns"` |
| DoD-7 | `jq '.decision' eval-log/task/phase2-02/review-approval.json` が `"approved"` |

## Section 9. リスクと対策

| 失敗モード | 対策 | INV参照 |
|---|---|---|
| 親類グルーピングが大きすぎて 1 plugin が肥大化 | partition 内 skill 数の上限を solo_operator が指定 (TODO(human)) | - |
| plugin 名が試験移行済 skill-creator と衝突 | DoD-6 で機械検出 | INV-9 |
| 同じ skill を複数 partition に重複配属 | Step 7.4 集合一致検査 | INV-9 |
| plugin 境界を跨ぐ skill 内参照 (`[[other-skill]]` 等) が残る | Step 7.5 lint-external-refs.py で検出。残れば 02 を再策定 | 公式制約 e |
| 命名規約違反 (CamelCase、snake_case 混入) | DoD-2 正規表現 | 06章 |

## Section 10. 成果物一覧

| 成果物 | パス | 責任者 |
|---|---|---|
| partition-plan.json | `eval-log/task/phase2-02/partition-plan.json` | AI 草案 + solo_operator 確定 |
| 親類グルーピング草案 | `eval-log/task/phase2-02/kin-grouping-draft.json` | AI |
| 境界外参照 lint 結果 | `eval-log/task/phase2-02/extref-<skill>.json` | AI |
| レビュー承認 | `eval-log/task/phase2-02/review-approval.json` | solo_operator |

ツール契約 (凍結参照): `scripts/lint-external-refs.py` は Phase 0 タスク 01 で凍結。本タスクで CLI 仕様変更しない。

## Section 11. 参照ドキュメント

- `doc/ClaudeCodeスキルの設計書/05-layering-skill-subagent-hook-mcp-cli.md`
- `doc/ClaudeCodeスキルの設計書/06-classification-and-naming.md`
- `eval-log/task/01/inventory.json` (Phase 0 棚卸し)
- `eval-log/task/phase2-01/residual-inventory.json`

## Section 12. 中学生レベル概念説明

文房具を箱に詰める作業に似ています。01 で「持っていく文房具のリスト」が出来たので、本タスクではそれを「ペン用の箱」「ノート用の箱」「定規用の箱」のように責務別に箱 (= plugin) に分けます。同じ文房具を 2 つの箱に入れてはダメ (重複)、リストにある全文房具がどこかの箱に入っている必要があります (欠落なし)。さらに「ペン用の箱を開けるためにノート用の箱を開ける必要がある」状態 (= plugin 間参照) も禁止です。

## Section 13. チェックリスト

- [ ] phase2-01 DoD 全 PASS 確認
- [ ] Step 7.1 親類グルーピング草案生成
- [ ] Step 7.2 solo_operator が plugin 名と境界を確定 (TODO(human))
- [ ] Step 7.3 partition-plan.json 生成
- [ ] Step 7.4 境界検証 PASS
- [ ] Step 7.5 境界外参照 0 件
- [ ] Step 7.6 README 更新
- [ ] Step 7.7 review-approval.json 生成
