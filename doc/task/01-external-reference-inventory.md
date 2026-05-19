# タスク 01 — 外部参照棚卸し

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| タスク ID | 01 |
| タスク名称 | 外部参照棚卸し (External Reference Inventory) |
| 種別 | 仕様策定 + 実行 |
| 担当 | AI (走査・分類) + 人間レビュー (判定確定) |
| 期限 | 34章 Phase 0 完了の最低条件 (制約 e の PASS) |
| 依存タスク | なし (本タスクが doc/task/ 群の最上流) |
| 後続タスク | 02 (settings merge 仕様策定) |
| ステータス | 完了 (2026-05-20 実行ログ生成済) |
| 改訂履歴 | 2026-05-19 v1 initial / 2026-05-19 v2 ツール契約整合修正 |

## Section 2. 目的と背景

### 目的

`creator-kit/skills/` および `.claude/skills/` 配下の全 SKILL.md について、所属予定 plugin (skill-creator) の境界を越えた外部参照を機械走査し、違反候補を一覧化する。

### 背景

設計書34章「公式制約 5 点照合表」の制約 e (plugin 内 Skill が plugin 外の scripts/adapters/.claude/config/ を参照することを禁ずる) が暫定 FAIL の状態にあり、34章 Phase 2 移行の最大ブロッカーである。

### 根拠

- `doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md` Phase 0 タスク表 4行目
- `doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md` 公式制約 e
- 既存スクリプト `scripts/lint-external-refs.py` (走査ツール実装済)

## Section 3. 用語集 (本タスク固有)

| 用語 | 定義 |
|---|---|
| 外部参照 (external reference) | SKILL.md内のパス参照のうち、所属plugin外を指すもの。lint出力の `refs[].external == true` に相当 |
| 内部参照 | 自plugin内で完結する参照。`refs[].external == false` |
| 違反候補 | 外部参照のうち人間判定が未確定のもの |
| inventory.json | 棚卸し結果の機械可読出力 (本タスクの主成果物) |
| decision-table | 違反候補ごとに `verdict` を記録した表 |
| verdict | 違反候補に対する人間判定。`migrate / allow / deprecate / defer` の4値 |

## Section 4. スコープ

### 含む

- `creator-kit/skills/*/SKILL.md` (1階層直下の SKILL.md)
- `.claude/skills/*/SKILL.md` (1階層直下の SKILL.md)
- 上記 SKILL.md 内で参照されているパス文字列

### 含まない

- `doc/` 配下 (設計書は plugin 対象外)
- 動的に組み立てられるパス参照 (静的解析の限界)
- バイナリファイル
- 1階層を越える深い SKILL.md ネスト (現実装ツールの走査範囲外)

**注**: Section 4 は `scripts/lint-external-refs.py` の実装範囲 (`skills_dir.glob("*/SKILL.md")`) と一致させてある。

## Section 5. 前提条件

| # | 条件 | 確認コマンド |
|---|---|---|
| 1 | `scripts/lint-external-refs.py` が実行可能 | `test -x scripts/lint-external-refs.py` |
| 2 | Python 3.11+ | `python3 --version` |
| 3 | 走査対象ディレクトリ存在 | `test -d creator-kit/skills && test -d .claude/skills` |
| 4 | `eval-log/task/` 作成権限 | `mkdir -p eval-log/task/01` |
| 5 | JSON 検証は Python stdlib で実行可能 | `python3 -c "import json"` |

### 依存ツールCLI契約確認 (必須、README ツール契約凍結原則準拠)

下記が `python3 scripts/lint-external-refs.py --help` の出力と完全一致することを確認する:

```
usage: lint-external-refs.py [-h] [--skills-dir SKILLS_DIR]
                             [--allowed-prefix ALLOWED_PREFIX] [--json]
                             [--fail-on-external]
```

**出力スキーマ (確定済み契約)**:

```json
{
  "skills_dir": "<path>",
  "allowed_prefixes": [...],
  "skills_scanned": <int>,
  "external_ref_count": <int>,
  "reports": [
    {
      "skill": "<name>",
      "path": "<SKILL.md path>",
      "refs": [
        {"ref": "<raw path>", "line": <int>, "external": <bool>}
      ]
    }
  ]
}
```

**この契約と相違する場合、本仕様書は P1_structural として再作業**。

## Section 6. 完了条件 (Definition of Done)

| # | 条件 | 機械検証コマンド |
|---|---|---|
| DoD-1 | `eval-log/task/01/inventory.json` 生成 | `test -f eval-log/task/01/inventory.json` |
| DoD-2 | inventory.json が必須フィールドを持つ | `python3 -c "import json; d=json.load(open('eval-log/task/01/inventory.json')); assert all(k in d for k in ['task_id','scanned_skill_count','violations'])"` |
| DoD-3 | 走査済 SKILL.md 件数が現実と一致 | `python3 -c "import json, pathlib; d=json.load(open('eval-log/task/01/inventory.json')); actual=sum(1 for _ in list(pathlib.Path('creator-kit/skills').glob('*/SKILL.md'))+list(pathlib.Path('.claude/skills').glob('*/SKILL.md'))); assert d['scanned_skill_count']==actual"` |
| DoD-4 | 全違反候補に `verdict` 入力済 | `python3 -c "import json; d=json.load(open('eval-log/task/01/inventory.json')); assert all(v.get('verdict') is not None for v in d.get('violations', []))"` |
| DoD-5 | `decision-table.md` 生成、全候補が表に存在 | `python3 -c "import json; d=json.load(open('eval-log/task/01/inventory.json')); rows=sum(1 for line in open('eval-log/task/01/decision-table.md') if line.startswith('|'))-2; assert rows==len(d.get('violations', []))"` |
| DoD-6 | `summary.md` に「後続タスクへの引き継ぎ」セクション存在 | `grep -q "後続タスクへの引き継ぎ" eval-log/task/01/summary.md` |
| DoD-7 | `review-approval.json` の `approver` 非空 | `python3 -c "import json; assert json.load(open('eval-log/task/01/review-approval.json')).get('approver')"` |
| DoD-8 | `defer` の割合が全違反の30%以下 | `python3 -c "import json; d=json.load(open('eval-log/task/01/inventory.json')); v=d.get('violations', []); assert (sum(1 for x in v if x.get('verdict')=='defer')*100/(len(v) or 1)) <= 30"` |

**全 8 件 PASS で完了**。

## Section 7. 実行手順

### Step 7.1 — 環境準備と前提検証

```bash
mkdir -p eval-log/task/01
test -x scripts/lint-external-refs.py || { echo "FAIL: lint不在"; exit 1; }
python3 --version
test -d creator-kit/skills && test -d .claude/skills || { echo "FAIL: 走査対象不在"; exit 1; }
python3 -c "import json" || { echo "FAIL: python json unavailable"; exit 1; }
```

### Step 7.2 — 走査対象一覧の凍結

```bash
find creator-kit/skills .claude/skills -maxdepth 2 -name "SKILL.md" -type f | sort > eval-log/task/01/scan-target-list.txt
wc -l eval-log/task/01/scan-target-list.txt
```

### Step 7.3 — ツール契約の実機確認

```bash
python3 scripts/lint-external-refs.py --help > eval-log/task/01/cli-contract-actual.txt
diff <(grep -E "^\s+(-h, --help|--)" eval-log/task/01/cli-contract-actual.txt | sed -E 's/[[:space:]]{2,}show this help message and exit$//' | sort) <(printf '  --allowed-prefix ALLOWED_PREFIX\n  --fail-on-external\n  --json\n  --skills-dir SKILLS_DIR\n  -h, --help\n' | sort) && echo "CONTRACT MATCH"
```

**MATCHでなければ本タスクを中断**し、`eval-log/task/01/abort-report.json` に `{reason: "cli-contract-mismatch", details: ...}` を書き、README に proposal セクションを追記してユーザー承認を得る。

### Step 7.4 — 静的走査実行 (2ディレクトリ個別実行→マージ)

ツールは `--skills-dir` 単一指定のみ対応のため、ディレクトリごとに実行する。

```bash
python3 scripts/lint-external-refs.py --skills-dir creator-kit/skills --json > eval-log/task/01/raw-creator-kit.json
python3 scripts/lint-external-refs.py --skills-dir .claude/skills --json > eval-log/task/01/raw-claude.json

python3 -c "import json; [json.load(open(f)) for f in ['eval-log/task/01/raw-creator-kit.json','eval-log/task/01/raw-claude.json']]" && echo "RAW JSON VALID"
```

### Step 7.5 — 違反候補の抽出と inventory.json 生成

```bash
python3 <<'PY'
import json, datetime
raw_files = ['eval-log/task/01/raw-creator-kit.json', 'eval-log/task/01/raw-claude.json']
all_reports = []
total_scanned = 0
for f in raw_files:
    d = json.load(open(f))
    total_scanned += d['skills_scanned']
    all_reports.extend(d['reports'])

violations = []
for r in all_reports:
    for ref in r['refs']:
        if ref['external']:
            violations.append({
                'source': r['path'],
                'skill': r['skill'],
                'raw_target': ref['ref'],
                'line': ref['line'],
                'verdict': None,
                'migration_target': None,
                'reviewer_note': None,
            })

out = {
    'task_id': '01',
    'generated_at': datetime.datetime.now().isoformat(),
    'scanned_skill_count': total_scanned,
    'scanned_files': [r['path'] for r in all_reports],
    'violation_count': len(violations),
    'violations': violations,
}
json.dump(out, open('eval-log/task/01/inventory.json','w'), indent=2, ensure_ascii=False)
print(f"violations={len(violations)} scanned={total_scanned}")
PY
```

### Step 7.6 — 人間レビュー (TODO(human))

`inventory.json` の各 `violations[].verdict` に下記いずれかを入力:

| 値 | 意味 | 追記必須 |
|---|---|---|
| `migrate` | plugin 内に移植 | `migration_target` |
| `allow` | 許容外部参照 | `reviewer_note` |
| `deprecate` | 参照廃止 | `reviewer_note` |
| `defer` | 次 Phase まで保留 | `reviewer_note` |

**TODO(human) 解除条件**: DoD-4 PASS かつ DoD-8 PASS (defer 30%以下)。

### Step 7.7 — decision-table.md 生成

```bash
python3 <<'PY'
import json
data = json.load(open('eval-log/task/01/inventory.json'))
with open('eval-log/task/01/decision-table.md','w') as f:
    f.write('# 違反候補判定表\n\n')
    f.write('| # | source | raw_target | line | verdict | migration_target | note |\n')
    f.write('|---|---|---|---|---|---|---|\n')
    for i, v in enumerate(data['violations'], 1):
        f.write(f"| {i} | {v['source']} | {v['raw_target']} | {v['line']} | {v['verdict']} | {v.get('migration_target') or '-'} | {v.get('reviewer_note') or '-'} |\n")
PY
```

### Step 7.8 — summary.md 生成

`eval-log/task/01/summary.md` を以下の構成で記述:

```
# タスク 01 完了報告

## 走査統計
- 対象 SKILL.md: N 件
- 検出参照: M 件
- 違反候補: K 件

## verdict 内訳
- migrate: A
- allow: B
- deprecate: C
- defer: D (全違反の X%、上限 30%)

## 後続タスクへの引き継ぎ
- タスク 02 settings merge で考慮すべき外部参照: ...
- タスク 03 symlink 構築で考慮すべき外部参照: ...
- defer 案件の次 Phase 持ち越し
```

### Step 7.9 — 承認ログ生成

```bash
cat > eval-log/task/01/review-approval.json <<EOF
{
  "task_id": "01",
  "approver": "solo_operator",
  "approved_at": "$(date -Iseconds)",
  "next_task_unblock": "02"
}
EOF
```

## Section 8. 検証手順

Section 6 の DoD-1 〜 DoD-8 を順に実行し全 PASS を確認する。

## Section 9. リスクと対策

| ID | リスク | 確率 | 影響 | 対策 |
|---|---|---|---|---|
| R-01 | ツール契約が将来変更される | 低 | 大 | Step 7.3 で毎回再確認 |
| R-02 | 動的参照を静的解析で見逃す | 高 | 中 | summary.md で限界明記、Phase 2 で動的確認 |
| R-03 | verdict 主観揺れ | 中 | 中 | 複数人レビュー (将来) |
| R-04 | defer 多発 | 中 | 大 | DoD-8 で上限30%強制 |
| R-05 | 走査中の SKILL.md 変動 | 低 | 中 | Step 7.2 で対象凍結 |
| R-06 | eval-log 誤削除 | 低 | 大 | git add+commit で永続化 |

## Section 10. 成果物一覧

| ファイル | 生成 Step | 責任者 |
|---|---|---|
| `eval-log/task/01/scan-target-list.txt` | 7.2 | AI |
| `eval-log/task/01/cli-contract-actual.txt` | 7.3 | AI |
| `eval-log/task/01/raw-creator-kit.json` | 7.4 | AI |
| `eval-log/task/01/raw-claude.json` | 7.4 | AI |
| `eval-log/task/01/inventory.json` | 7.5+7.6 | AI生成+人間判定 |
| `eval-log/task/01/decision-table.md` | 7.7 | AI |
| `eval-log/task/01/summary.md` | 7.8 | AI |
| `eval-log/task/01/review-approval.json` | 7.9 | 人間 |

### ツール契約 (本タスクが依存する CLI 契約)

- ツール: `scripts/lint-external-refs.py`
- フラグ: `--skills-dir <path>` (単一), `--allowed-prefix`, `--json`, `--fail-on-external`
- 出力キー: `skills_dir`, `allowed_prefixes`, `skills_scanned`, `external_ref_count`, `reports`
- reports 要素: `{skill, path, refs:[{ref, line, external}]}`

## Section 11. 参照ドキュメント

- `doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md` 制約 e
- `scripts/lint-external-refs.py` 本体

## Section 12. 中学生レベル概念説明

引っ越しを想像してください。**段ボール箱 (= plugin) に部屋の中身を詰める前に、どの物にも外に伸びているコード (= 外部参照) がないかを全部書き出す作業**です。

```
   隣の部屋                自分の部屋
   ┌──────┐                ┌──────┐
   │コンセント│ ←━━━━━━━━━━ │ドライヤー│ ← 段ボール(plugin)へ
   └──────┘                └──────┘
                                ↑
              箱を運ぶとコード切れる！
```

機械(`lint-external-refs.py`)に部屋を走査させて、外に伸びているコードのリストを作り、それぞれを「巻き取る (migrate)」「許容 (allow)」「切る (deprecate)」「あとで決める (defer)」に分類します。

## Section 13. 実行者チェックリスト

- [ ] README を最後まで読んだ
- [ ] 本仕様書を最後まで読んだ
- [ ] Section 5 の前提条件 5件 + ツール契約確認 PASS
- [ ] Step 7.1 〜 7.9 を順に実行
- [ ] DoD-1 〜 DoD-8 全 PASS
- [ ] 成果物 8件が `eval-log/task/01/` 配下に揃う
- [ ] README タスク一覧のステータスを「完了」に更新
- [ ] 後続タスク 02 着手可能を宣言

## 改訂履歴

| 日付 | バージョン | 改訂者 | 内容 |
|---|---|---|---|
| 2026-05-19 | v1 | initial | Section 1-13 構成で初版 |
| 2026-05-19 | v2 | elegant-review | Phase 2 アナリスト指摘反映: ツール契約整合、Section 命名、DoD機械検証統一、defer上限追加 |
