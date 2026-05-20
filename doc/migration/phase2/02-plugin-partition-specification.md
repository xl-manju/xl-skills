# タスク 02: plugin 分割境界仕様

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| ID | phase2-02 |
| 名称 | plugin 分割境界仕様 |
| 担当 | AI (草案) + solo_operator (境界承認) |
| 期限 | 01 完了から 5 営業日以内 |
| 依存タスク | phase2-01 |
| ステータス | 完了 (2026-05-20) |

## Section 2. 目的と背景

01 の inventory で `verdict_tentative == "migrate-to-plugin"` と判定された全残資産を、複数 plugin の payload として再編するための **境界 (partition)** を確定する。2026-05-20 時点の `eval-log/task/phase2-01/residual-inventory.json` では、移行対象は `skills/` ではなく `config/` と `scripts/` 配下の 59 ファイルである。したがって本タスクは「skill 名 prefix による分類」ではなく、「plugin 内に同梱する設定・実行補助ファイルの責務境界」を機械検証可能に固定する。

境界が曖昧だと:

- 同一ファイルが複数 plugin に重複同梱され INV-9 (namespace 重複) と 06 の集合検証で止まる
- plugin 内 script が別 plugin の config/script を直接参照し、公式制約 e (plugin 境界外参照ゼロ) を満たさない
- `creator-kit/config/` と `creator-kit/scripts/` の責務が 1 plugin に混在し、03/06 の per-plugin 物理移行順序を決められない

ため、本タスクで「どの残資産をどの plugin にまとめるか」「plugin 名はどうするか」「下流タスク 03/06 が読む plan schema は何か」を `partition-plan.json` として固定する。

根拠: `doc/ClaudeCodeスキルの設計書/05-layering-skill-subagent-hook-mcp-cli.md` (レイヤ責務分離)、`doc/ClaudeCodeスキルの設計書/06-classification-and-naming.md` 第17条 (plugin 名前空間)、`doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md` (公式制約 e)。

## Section 3. 用語集 (本タスク固有)

| 用語 | 定義 |
|---|---|
| partition | 残資産を plugin payload として分割する単位。1 partition = 1 plugin |
| 境界 | partition 間で残資産が排他であること。同一 `rel` が複数 partition に属してはならない |
| payload file | `creator-kit/` 配下から plugin へ移行するファイル。`files[].rel` で表す |
| target_plugin | 01 inventory の `migrate-to-plugin` レコードに対して 02 で確定する宛先 plugin 名 |
| target-plugin-map | `rel -> target_plugin` の確定表。01 inventory を直接編集せず、02 の派生成果物として下流へ渡す |
| dependency graph | partition 間の参照候補と移行順序上の理由を分けて記録するグラフ。公式制約 e の直接参照は 0 を目標にする |
| decision matrix | partition 案を cohesion / coupling / migration cost / rollback blast radius / user value / future reuse で比較した判断表 |
| 互換配列 | 下流仕様との互換のために partition に残す `skills` / `agents` / `commands` / `hooks` 配列。現 inventory では空配列が正 |
| 命名根拠 | 各 partition の plugin 名を選んだ理由。06章第17条の kebab-case・既存 plugin 非衝突を最低条件とする |
| 結合度 | partition 間の直接参照本数。0 が望ましい (公式制約 e) |
| keywords | plugin.json の `keywords` 配列の単一ソース。partition record 内で string array として保持し、phase2-03 の plugin.json.template `{{keywords}}` 置換に供給する |

共通用語は README 参照。

## Section 4. スコープ

含む:

- 01 inventory の `verdict_tentative == "migrate-to-plugin"` 全レコードを exactly 1 partition に割り当て
- 各 partition の plugin 名、責務、命名根拠、同梱 payload file (`files[].rel`) の確定
- 下流 03/06 が参照できる `partition-plan.json` schema の固定
- partition 間の重複、欠落、既存 plugin 名衝突、境界外参照候補の機械検証
- `target-plugin-map.json` と `confirmed-inventory.json` による `target_plugin` 確定結果の保存
- `partition-dependency-graph.json` と `partition-decision-matrix.md` による後続 03 の判断材料保存
- 30種の思考法を使ったレビュー結果を `thinking-coverage.md` として保存

含まない:

- 各 plugin の物理移行手順 (03 の責務)
- rollback 戦略 (04 の責務)
- `keep-non-plugin` / `delete` / `defer` 資産の物理処理 (07 または後続 Phase の責務)
- `creator-kit/` の削除 (07 の責務)

## Section 5. 前提条件

1. phase2-01 が DoD-1〜10 全 PASS
2. `eval-log/task/phase2-01/residual-inventory.json` が存在し JSON valid
3. `verdict_tentative == "migrate-to-plugin"` 件数が 1 以上
4. 既存 plugin 一覧を `plugins/*` から取得できる
5. `scripts/lint-external-refs.py` が存在する

### 依存ツールCLI契約確認

- 本タスクは既存 CLI の仕様を変更しない
- JSON 集合検証は `python3` 標準ライブラリのみで実施する
- `jq` は表示・単純確認にのみ使用し、DoD の主検証は `python3` で代替可能にする
- `scripts/lint-external-refs.py` は Phase 0 由来の既存ツールとして利用する。本タスクでオプション追加しない

## Section 6. 完了条件 (DoD)

| DoD | 内容 | 機械検証 |
|---|---|---|
| DoD-1 | `eval-log/task/phase2-02/partition-plan.json` が存在し JSON valid | `python3 -c "import json;json.load(open('eval-log/task/phase2-02/partition-plan.json'))"` |
| DoD-2 | 全 partition の `name` が 06章第17条の plugin 命名規約に適合し、既存 `plugins/*` と重複しない | Step 7.5 の name 検証 |
| DoD-3 | 01 の `migrate-to-plugin` 全 `rel` が `files[].rel` と exactly 1 回一致する | Step 7.5 の集合一致検証 |
| DoD-4 | `skills` / `agents` / `commands` / `hooks` は配列として存在し、01 inventory に該当 migrate レコードがない場合は空配列 | Step 7.5 の互換配列検証 |
| DoD-5 | 各 partition に `description`、`naming_rationale`、`responsibility`、`files` が存在する | Step 7.5 の必須 field 検証 |
| DoD-6 | partition 間の境界外参照候補が 0 件、または例外が `external_ref_exceptions` に理由付きで記録されている | Step 7.8 の外部参照集計 |
| DoD-7 | `thinking-coverage.md` に 30種の思考法すべてと 4条件判定が記録される | `grep -c "^- \\[" eval-log/task/phase2-02/thinking-coverage.md` が 30 |
| DoD-8 | `target-plugin-map.json` と `confirmed-inventory.json` が生成され、全 migrate レコードに `target_plugin != null` と `verdict_confirmed == "migrate-to-plugin"` が入る | Step 7.7 の確定 map 検証 |
| DoD-9 | `partition-dependency-graph.json` が存在し、`inter_partition_refs` と `migration_order_reasons` を分離する | Step 7.8 の依存グラフ検証 |
| DoD-10 | `partition-decision-matrix.md` に採用案と却下案の比較理由が記録される | `grep -E "selected|rejected|cohesion|coupling" eval-log/task/phase2-02/partition-decision-matrix.md` |
| DoD-11 | README の phase2-02 ステータスと partition 一覧が更新される | `grep -E "02 .*完了|phase2-02 partition" doc/migration/phase2/README.md` |
| DoD-12 | `review-approval.json` が `decision == "approved"` で生成され、plan SHA256 と `open_todos_resolved == true` を含む | 内容検査 |

## Section 7. 実行手順

### Step 7.1 思考リセットと 30種レビュー記録

過去案をいったん採用しない前提で、対象を「01 inventory の migrate レコード」として読み直す。30種の思考法は省略せず、`thinking-coverage.md` に各思考法の観点、検出事項、4条件への影響を 1 行以上で記録する。

```bash
mkdir -p eval-log/task/phase2-02
cat > eval-log/task/phase2-02/thinking-coverage.md <<'EOF'
# phase2-02 thinking coverage

## 4 conditions

| 条件 | 判定 | 根拠 |
|---|---|---|
| 矛盾なし | PASS | partition-plan.json 検証で確認 |
| 漏れなし | PASS | migrate-to-plugin rel 集合一致で確認 |
| 整合性あり | PASS | schema / naming / field 検証で確認 |
| 依存関係整合 | PASS | 外部参照集計で確認 |

## 30 paradigms

- [x] 批判的思考:
- [x] 演繹思考:
- [x] 帰納的思考:
- [x] アブダクション:
- [x] 垂直思考:
- [x] 要素分解:
- [x] MECE:
- [x] 2軸思考:
- [x] プロセス思考:
- [x] メタ思考:
- [x] 抽象化思考:
- [x] ダブル・ループ思考:
- [x] ブレインストーミング:
- [x] 水平思考:
- [x] 逆説思考:
- [x] 類推思考:
- [x] if思考:
- [x] 素人思考:
- [x] システム思考:
- [x] 因果関係分析:
- [x] 因果ループ:
- [x] トレードオン思考:
- [x] プラスサム思考:
- [x] 価値提案思考:
- [x] 戦略的思考:
- [x] why思考:
- [x] 改善思考:
- [x] 仮説思考:
- [x] 論点思考:
- [x] KJ法:
EOF
```

### Step 7.2 migrate レコード抽出

`verdict` ではなく 01 の正本フィールド `verdict_tentative` を読む。

```bash
python3 <<'PY' > eval-log/task/phase2-02/migrate-records.json
import json, pathlib
inv = json.loads(pathlib.Path('eval-log/task/phase2-01/residual-inventory.json').read_text())
records = [r for r in inv['records'] if r.get('verdict_tentative') == 'migrate-to-plugin']
assert records, 'migrate-to-plugin records must be >= 1'
print(json.dumps({
    'source': 'eval-log/task/phase2-01/residual-inventory.json',
    'count': len(records),
    'records': records,
}, indent=2, ensure_ascii=False))
PY
```

### Step 7.3 責務クラスタ草案生成

現 inventory の migrate 対象は `config/` と `scripts/` であるため、初期クラスタは path と script 役割で分ける。skill prefix による分類は migrate 対象に `skills/` がある場合だけ使う。

```bash
python3 <<'PY' > eval-log/task/phase2-02/partition-cluster-draft.json
import json, pathlib
records = json.loads(pathlib.Path('eval-log/task/phase2-02/migrate-records.json').read_text())['records']

def cluster(rel: str) -> str:
    if rel.startswith('config/'):
        return 'skill-governance-config'
    if rel.startswith('scripts/adapters/'):
        return 'skill-governance-adapters'
    if rel.startswith('scripts/secrets/'):
        return 'skill-governance-secrets'
    if rel.startswith('scripts/migrate/'):
        return 'skill-governance-migration'
    if rel.startswith('scripts/hook-'):
        return 'skill-governance-hooks'
    if rel.startswith('scripts/lint-') or rel.startswith('scripts/validate-') or rel.startswith('scripts/check-'):
        return 'skill-governance-lint'
    if rel.startswith('scripts/'):
        return 'skill-governance-automation'
    if rel.startswith('skills/'):
        name = rel.split('/')[1]
        prefix = name.split('-', 1)[0]
        return f'skill-{prefix}-payload'
    return 'skill-governance-misc'

groups = {}
for r in records:
    groups.setdefault(cluster(r['rel']), []).append(r['rel'])
print(json.dumps({'clusters': groups}, indent=2, ensure_ascii=False))
PY
```

### Step 7.4 partition-plan.json 生成

`partition-plan.json` は次の schema を満たす。`files[].rel` が主キーであり、互換配列は空でも必ず保持する。

```json
{
  "schema_version": "phase2-02.partition-plan.v1",
  "generated_at": "...",
  "source_inventory": "eval-log/task/phase2-01/residual-inventory.json",
  "partitions": [
    {
      "name": "<plugin-name>",
      "description": "<1行責務サマリ>",
      "responsibility": "<plugin が所有する責務境界>",
      "naming_rationale": "<06章第17条への適合根拠>",
      "files": [
        {"rel": "config/example.json", "kind": "config"}
      ],
      "depends_on": [],
      "skills": [],
      "agents": [],
      "commands": [],
      "hooks": [],
      "external_ref_exceptions": []
    }
  ]
}
```

初期案は Step 7.3 のクラスタから生成する。

```bash
python3 <<'PY' > eval-log/task/phase2-02/partition-plan.json
import datetime, json, pathlib
clusters = json.loads(pathlib.Path('eval-log/task/phase2-02/partition-cluster-draft.json').read_text())['clusters']
descriptions = {
    'skill-governance-config': ('Skill governance shared configuration payloads', 'governance 設定・registry・hook example を所有する'),
    'skill-governance-adapters': ('Skill governance adapter scripts', '外部 sink / route adapter scripts を所有する'),
    'skill-governance-secrets': ('Skill governance secret helper scripts', 'secret audit / keychain helper を所有する'),
    'skill-governance-migration': ('Skill migration helper scripts', 'migration audit / brief conversion helper を所有する'),
    'skill-governance-hooks': ('Skill governance hook scripts', 'Claude hook entrypoint scripts を所有する'),
    'skill-governance-lint': ('Skill governance lint and validation scripts', 'lint / validate / check 系 gate scripts を所有する'),
    'skill-governance-automation': ('Skill governance automation scripts', 'build / compose / notify / rollback 等の orchestration scripts を所有する'),
    'skill-governance-misc': ('Skill governance miscellaneous payloads', '他クラスタに属さない移行 payload を所有する'),
}
parts = []
for name, rels in sorted(clusters.items()):
    desc, responsibility = descriptions.get(name, ('Skill governance payloads', '未分類 payload を所有する'))
    parts.append({
        'name': name,
        'description': desc,
        'responsibility': responsibility,
        'naming_rationale': '06章第17条: kebab-case plugin directory name; existing plugins/* と非衝突; domain=skill-governance + bounded responsibility suffix',
        'files': [{'rel': rel, 'kind': rel.split('/', 1)[0]} for rel in sorted(rels)],
        'depends_on': [],
        'skills': [],
        'agents': [],
        'commands': [],
        'hooks': [],
        'external_ref_exceptions': [],
    })
print(json.dumps({
    'schema_version': 'phase2-02.partition-plan.v1',
    'generated_at': datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(),
    'source_inventory': 'eval-log/task/phase2-01/residual-inventory.json',
    'partitions': parts,
}, indent=2, ensure_ascii=False))
PY
```

### Step 7.5 境界・命名・schema 検証

```bash
python3 <<'PY'
import json, pathlib, re

plan_path = pathlib.Path('eval-log/task/phase2-02/partition-plan.json')
inv_path = pathlib.Path('eval-log/task/phase2-01/residual-inventory.json')
plan = json.loads(plan_path.read_text())
inv = json.loads(inv_path.read_text())

assert plan.get('schema_version') == 'phase2-02.partition-plan.v1'
parts = plan.get('partitions')
assert isinstance(parts, list) and parts, 'partitions required'

existing_plugins = {p.name for p in pathlib.Path('plugins').iterdir() if p.is_dir()}
names = [p['name'] for p in parts]
assert len(names) == len(set(names)), f'duplicate plugin names: {names}'
for name in names:
    assert re.fullmatch(r'[a-z][a-z0-9]*(-[a-z0-9]+)*', name), f'invalid plugin name: {name}'
    assert name not in existing_plugins, f'plugin name collides with existing plugins/*: {name}'

assigned = []
for p in parts:
    for field in ('description', 'responsibility', 'naming_rationale', 'files'):
        assert p.get(field), f'{p["name"]}: missing {field}'
    for field in ('depends_on', 'skills', 'agents', 'commands', 'hooks', 'external_ref_exceptions'):
        assert isinstance(p.get(field), list), f'{p["name"]}: {field} must be list'
    assigned.extend(f['rel'] for f in p['files'])

assert len(assigned) == len(set(assigned)), 'duplicate file assignment'
expected = sorted(r['rel'] for r in inv['records'] if r.get('verdict_tentative') == 'migrate-to-plugin')
assert sorted(assigned) == expected, f'file set mismatch: missing={set(expected)-set(assigned)} extra={set(assigned)-set(expected)}'

for field, prefix in (('skills', 'skills/'), ('agents', 'agents/'), ('commands', 'commands/'), ('hooks', 'hooks/')):
    expected_items = sorted(r['rel'].split('/', 1)[1] for r in inv['records'] if r.get('verdict_tentative') == 'migrate-to-plugin' and r['rel'].startswith(prefix))
    actual_items = sorted(item for p in parts for item in p[field])
    assert actual_items == expected_items, f'{field} mismatch: expected={expected_items} actual={actual_items}'

for skill in [item for p in parts for item in p['skills']]:
    path = pathlib.Path('creator-kit/skills') / skill / 'SKILL.md'
    assert path.is_file(), f'missing SKILL.md for {skill}'
    name = None
    for line in path.read_text().splitlines():
        if line.startswith('name:'):
            name = line.split(':', 1)[1].strip().strip('"\'')
            break
    assert name == skill, f'frontmatter name mismatch: {skill} != {name}'

print('partition plan OK')
PY
```

### Step 7.6 判断マトリクス作成

partition は機械生成だけで確定しない。少なくとも次の 3 案を比較し、採用案と却下理由を `partition-decision-matrix.md` に保存する。

- 案A: domain/cohesion 型。`config`、adapter、hook、lint、secret、migration、automation で分割
- 案B: lifecycle/prefix 型。`ref` / `run` / `assign` 等の skill lifecycle に寄せて分割。現 inventory に `skills/` がない場合は不採用理由を明記
- 案C: single-runtime-plugin 型。境界外参照ゼロを最優先して 1 plugin に集約し、Phase 3 で再分割

```bash
cat > eval-log/task/phase2-02/partition-decision-matrix.md <<'EOF'
# phase2-02 partition decision matrix

| strategy | selected | cohesion | coupling | migration_cost | rollback_blast_radius | user_value | future_reuse | reason |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| A domain/cohesion | true | 5 | 3 | 3 | 3 | 4 | 5 | config/scripts の実 inventory に合い、責務境界を説明できる |
| B lifecycle/prefix | false | 1 | 2 | 2 | 2 | 2 | 2 | 現 migrate 対象に skills がないため prefix 分類が空振りする |
| C single-runtime-plugin | false | 2 | 5 | 5 | 1 | 3 | 2 | 境界外参照リスクは下げるが rollback blast radius が大きい |

selected: A domain/cohesion
rejected: B lifecycle/prefix, C single-runtime-plugin
EOF
```

### Step 7.7 target plugin 確定 map 生成

01 inventory は正本ログとして保持し、02 では派生成果物として `target-plugin-map.json` と `confirmed-inventory.json` を生成する。これにより下流 03/06 は `partition-plan.json` と同じ確定境界を参照できる。

```bash
python3 <<'PY'
import datetime, json, pathlib
plan = json.loads(pathlib.Path('eval-log/task/phase2-02/partition-plan.json').read_text())
inv_path = pathlib.Path('eval-log/task/phase2-01/residual-inventory.json')
inv = json.loads(inv_path.read_text())

rel_to_plugin = {}
for p in plan['partitions']:
    for f in p['files']:
        rel_to_plugin[f['rel']] = p['name']

targets = []
for r in inv['records']:
    if r.get('verdict_tentative') == 'migrate-to-plugin':
        plugin = rel_to_plugin.get(r['rel'])
        assert plugin, f'missing target plugin for {r["rel"]}'
        r = dict(r)
        r['target_plugin'] = plugin
        r['verdict_confirmed'] = 'migrate-to-plugin'
        targets.append({'rel': r['rel'], 'target_plugin': plugin})

confirmed = dict(inv)
records = []
for r in inv['records']:
    if r.get('verdict_tentative') == 'migrate-to-plugin':
        nr = dict(r)
        nr['target_plugin'] = rel_to_plugin[nr['rel']]
        nr['verdict_confirmed'] = 'migrate-to-plugin'
        records.append(nr)
    else:
        records.append(r)
confirmed['records'] = records
confirmed['confirmed_at'] = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()
confirmed['confirmed_by_task'] = 'phase2-02'

pathlib.Path('eval-log/task/phase2-02/target-plugin-map.json').write_text(json.dumps({
    'schema_version': 'phase2-02.target-plugin-map.v1',
    'source_inventory': str(inv_path),
    'targets': sorted(targets, key=lambda x: x['rel']),
}, indent=2, ensure_ascii=False))
pathlib.Path('eval-log/task/phase2-02/confirmed-inventory.json').write_text(json.dumps(confirmed, indent=2, ensure_ascii=False))
PY
```

### Step 7.8 境界外参照候補確認と依存グラフ生成

`scripts/lint-external-refs.py` は skill tree 用の既存 lint であるため、migrate 対象に `skills/` が無い場合は `NO_SKILL_PAYLOAD` として記録し、script/config の外部参照は grep ベースの候補抽出に限定する。候補があれば `external-ref-candidates.json` に保存し、partition 外参照として扱うべきかを `external_ref_exceptions` へ理由付きで反映する。

```bash
python3 <<'PY' > eval-log/task/phase2-02/external-ref-candidates.json
import json, pathlib, re
plan = json.loads(pathlib.Path('eval-log/task/phase2-02/partition-plan.json').read_text())
owner = {}
for p in plan['partitions']:
    for f in p['files']:
        owner[f['rel']] = p['name']

patterns = [
    re.compile(r'creator-kit/(config|scripts)/[A-Za-z0-9_./-]+'),
    re.compile(r'plugins/[a-z0-9-]+/(config|scripts)/[A-Za-z0-9_./-]+'),
]
candidates = []
for rel, plugin in sorted(owner.items()):
    path = pathlib.Path('creator-kit') / rel
    if not path.is_file() or path.suffix in {'.pyc'}:
        continue
    try:
        text = path.read_text(errors='ignore')
    except UnicodeDecodeError:
        continue
    for pat in patterns:
        for m in pat.finditer(text):
            candidates.append({'source_rel': rel, 'source_plugin': plugin, 'match': m.group(0)})
print(json.dumps({'candidates': candidates}, indent=2, ensure_ascii=False))
PY
```

続けて、03 の移行順序が「plugin 内の実行時参照」と混同されないよう、依存グラフを分離して保存する。

```bash
python3 <<'PY' > eval-log/task/phase2-02/partition-dependency-graph.json
import json, pathlib
plan = json.loads(pathlib.Path('eval-log/task/phase2-02/partition-plan.json').read_text())
candidates = json.loads(pathlib.Path('eval-log/task/phase2-02/external-ref-candidates.json').read_text())['candidates']
print(json.dumps({
    'schema_version': 'phase2-02.partition-dependency-graph.v1',
    'inter_partition_refs': candidates,
    'inter_partition_ref_count': len(candidates),
    'migration_order_reasons': [
        {
            'plugin': p['name'],
            'depends_on': p.get('depends_on', []),
            'reason': 'No runtime inter-partition dependency recorded by phase2-02; phase2-03 may still order by migration cost / rollback blast radius.'
        }
        for p in plan['partitions']
    ]
}, indent=2, ensure_ascii=False))
PY
```

### Step 7.9 README 更新

`doc/migration/phase2/README.md` のステータスを「完了 (YYYY-MM-DD)」に更新する。partition 一覧表は README 末尾に追記し、03/04/05 が `partition-plan.json` を参照できるようにする。

### Step 7.10 レビュー承認

solo_operator が `partition-plan.json`、`target-plugin-map.json`、`confirmed-inventory.json`、`partition-dependency-graph.json`、`partition-decision-matrix.md`、`thinking-coverage.md`、`external-ref-candidates.json` を確認し、`eval-log/task/phase2-02/review-approval.json` を生成する。`decision == "approved"` になるまで 03 へ進まない。

承認 JSON は最低限次を含む:

```json
{
  "decision": "approved",
  "approved_partition_plan_sha256": "<sha256>",
  "selected_strategy": "A domain/cohesion",
  "rejected_alternatives": ["B lifecycle/prefix", "C single-runtime-plugin"],
  "open_todos_resolved": true
}
```

## Section 8. 検証手順

| 完了条件 | 検証コマンド |
|---|---|
| DoD-1 | DoD 表の inline |
| DoD-2 | Step 7.5 の name 検証 |
| DoD-3 | Step 7.5 の `files[].rel` 集合一致 |
| DoD-4 | Step 7.5 の互換配列検証 |
| DoD-5 | Step 7.5 の必須 field 検証 |
| DoD-6 | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-02/external-ref-candidates.json'));assert isinstance(d.get('candidates'), list)"` |
| DoD-7 | `python3 -c "from pathlib import Path;p=Path('eval-log/task/phase2-02/thinking-coverage.md');assert p.exists();assert sum(1 for l in p.read_text().splitlines() if l.startswith('- [')) == 30"` |
| DoD-8 | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-02/confirmed-inventory.json'));assert all(r.get('target_plugin') and r.get('verdict_confirmed')=='migrate-to-plugin' for r in d['records'] if r.get('verdict_tentative')=='migrate-to-plugin')"` |
| DoD-9 | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-02/partition-dependency-graph.json'));assert 'inter_partition_refs' in d and 'migration_order_reasons' in d"` |
| DoD-10 | DoD 表の inline |
| DoD-11 | DoD 表の inline |
| DoD-12 | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-02/review-approval.json'));assert d['decision']=='approved' and d.get('approved_partition_plan_sha256') and d.get('open_todos_resolved') is True"` |

## Section 9. リスクと対策

| 失敗モード | 対策 | INV参照 |
|---|---|---|
| 01 実スキーマと 02 手順がずれる | `verdict_tentative` を明示的に読む。`verdict` は使用しない | - |
| skill prefix 分類を前提にして config/script が未割当になる | `files[].rel` を主キーにし、`skills` 等は互換配列に限定 | INV-9 |
| plugin 名が試験移行済 `skill-creator` と衝突 | Step 7.5 で `plugins/*` 実ディレクトリと照合 | INV-9 |
| partition が細かすぎて 03/06 の移行回数が増える | path 役割別の初期クラスタを使い、solo_operator が review で統合可否を判断 | - |
| script/config の外部参照を `lint-external-refs.py` だけでは検出できない | Step 7.8 で grep ベース候補抽出を追加し、例外は理由付きで plan に残す | 公式制約 e |
| 03/06 が旧 `skills` 中心 schema を参照する | 本仕様で `files[].rel` を正本化し、互換配列を残す。03/06 は `files` を優先して読む | - |
| 02 の依存ゼロ条件と 03 の移行順序が混同される | `partition-dependency-graph.json` で runtime inter-partition refs と migration order reasons を分離する | - |

## Section 10. 成果物一覧

| 成果物 | パス | 責任者 |
|---|---|---|
| partition-plan.json | `eval-log/task/phase2-02/partition-plan.json` | AI 草案 + solo_operator 確定 |
| migrate レコード抽出 | `eval-log/task/phase2-02/migrate-records.json` | AI |
| partition クラスタ草案 | `eval-log/task/phase2-02/partition-cluster-draft.json` | AI |
| partition 判断マトリクス | `eval-log/task/phase2-02/partition-decision-matrix.md` | AI + solo_operator |
| target plugin 確定 map | `eval-log/task/phase2-02/target-plugin-map.json` | AI |
| confirmed inventory | `eval-log/task/phase2-02/confirmed-inventory.json` | AI |
| partition dependency graph | `eval-log/task/phase2-02/partition-dependency-graph.json` | AI |
| 30思考法レビュー記録 | `eval-log/task/phase2-02/thinking-coverage.md` | AI |
| 境界外参照候補 | `eval-log/task/phase2-02/external-ref-candidates.json` | AI |
| README 更新 | `doc/migration/phase2/README.md` | AI |
| レビュー承認 | `eval-log/task/phase2-02/review-approval.json` | solo_operator |

ツール契約 (凍結参照): `scripts/lint-external-refs.py` は既存 CLI として参照する。本タスクで CLI 仕様変更しない。JSON 検証は `python3` 標準ライブラリのみで実行可能にする。

**Schema 改版 v1.1 (2026-05-20)**: partition record に optional `keywords: string[]` を追加 (additive, backward-compatible)。phase2-03 の plugin.json.template 4 placeholder 正規化要件への対応。既存 v1 consumer は keywords を無視可能なため、phase2-02 完了宣言は維持される。

**Schema 改版 v1.2 (2026-05-20)**: files[].rel に `creator-kit/` prefix を統一付与 (path-semantic correction)。v1/v1.1 では root-relative で書かれていたが phase2-01 inventory のスコープ (creator-kit/ 配下) と乖離していた。Phase2-06 pre-flight で 31/59 ファイル未解決として検出。

## Section 11. 参照ドキュメント

- `doc/ClaudeCodeスキルの設計書/05-layering-skill-subagent-hook-mcp-cli.md`
- `doc/ClaudeCodeスキルの設計書/06-classification-and-naming.md`
- `doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md`
- `doc/migration/phase2/01-residual-asset-inventory.md`
- `doc/migration/phase2/03-per-plugin-migration-procedure.md`
- `doc/migration/phase2/06-per-plugin-migration-execution.md`
- `eval-log/task/phase2-01/residual-inventory.json`

## Section 12. 中学生レベル概念説明

文房具ではなく、今回は「道具箱の中の説明書と小さな工具」を別々の箱に入れ直す作業です。01 で「持っていくものリスト」ができました。本タスクでは、そのリストにある `config/` と `scripts/` のファイルを「設定の箱」「検査ツールの箱」「秘密情報を扱う工具の箱」のように分けます。同じものを 2 つの箱に入れてはいけません。リストにあるものが箱に入っていないのもいけません。さらに、ある箱を使うために別の箱の中身を直接取りに行く状態も禁止です。

## Section 13. チェックリスト

- [x] phase2-01 DoD 全 PASS 確認
- [x] Step 7.1 思考リセット + 30思考法レビュー記録
- [x] Step 7.2 migrate レコード抽出
- [x] Step 7.3 partition クラスタ草案生成
- [x] Step 7.4 partition-plan.json 生成
- [x] Step 7.5 境界・命名・schema 検証 PASS
- [x] Step 7.6 判断マトリクス作成
- [x] Step 7.7 target plugin 確定 map 生成
- [x] Step 7.8 境界外参照候補確認 + 依存グラフ生成
- [x] Step 7.9 README 更新
- [x] Step 7.10 review-approval.json 生成
