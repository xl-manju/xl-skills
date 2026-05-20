# タスク 01: creator-kit 残資産棚卸し

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| ID | phase2-01 |
| 名称 | creator-kit 残資産棚卸し |
| 担当 | AI (実行) + solo_operator (verdict 承認) |
| 期限 | Phase 2 本番 開始から 3 営業日以内 |
| 依存タスク | なし (Phase 2 本番 の最上流。Phase 0/1 closure と試験移行 PASS に依存) |
| ステータス | 完了 (DoD PASS + CI green, 2026-05-20) |

> **「完了」の真理条件**: (a) Section 6 DoD-1〜10 がすべて機械検証 PASS、かつ (b) `governance-check` + `Creator Kit CI` のローカル相当チェックが PASS、かつ (c) `review-approval.json` の `decision == "approved"` の3条件 AND を満たす状態。phase2-01 自体は creator-kit 残資産棚卸しの責務のみ担い、`manifest.json` 整合性 / `governance-log.jsonl` への承認記録 / plugin 配下への試験移行品質 は **out-of-scope** で phase0 governance および phase2-02 の責務とする。

## Section 2. 目的と背景

`plugins/skill-creator/` への試験移行 (phase0 タスク 08) は完了したが、`creator-kit/` ディレクトリは依然として並存している (現状: skills 20件・agents 6件は plugin と完全一致、その他に `_bootstrap/`、`_drafts/`、`config/`、`install.{sh,ps1}`、`manifest.json`、`migrate-from-project.sh`、`migrate-log/`、`CONVENTIONS.md` 等が残存)。

Phase 2 本番 では `creator-kit/` の正本性を剥奪し、内容を:

- **migrate-to-plugin**: 別 plugin として再編すべき資産
- **keep-non-plugin**: plugin 化しないがリポジトリに保持する資産 (例: `_bootstrap/` のインストーラ)
- **delete**: 移行先が `plugins/skill-creator/` にすでに存在し重複している資産
- **defer**: Phase 2 本番 では扱わず後続 Phase へ送る資産

の 4 verdict に網羅的に分類する。本タスクの inventory がなければ 02 (plugin 分割境界) は着手できない。

根拠: `doc/migration/phase0/README.md` (Phase 0 引き継ぎ事項#1「creator-kit/ 物理削除タイミング」、#2「skill-creator 1 件以外の plugin 移行」)、`doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md` (Phase 4 全面移行ゲート)。

## Section 3. 用語集 (本タスク固有)

| 用語 | 定義 |
|---|---|
| 残資産 | `creator-kit/` 配下の全ファイル・ディレクトリ。`plugins/skill-creator/` への試験移行で複製されたものも含む |
| verdict | 各資産に対する分類: `migrate-to-plugin` / `keep-non-plugin` / `delete` / `defer` の 4 値 MECE |
| 重複資産 | `creator-kit/<path>` と `plugins/skill-creator/<path>` が SHA256 一致するファイル |
| 非 plugin 資産 | `skills/`、`agents/`、`commands/`、`hooks/`、`.claude-plugin/` のいずれにも該当しないファイル |
| `verdict_tentative` | 本タスク内で確定する暫定 verdict。本フェーズで決定可能な分類 (`delete` / `keep-non-plugin` / `defer`) と、宛先未確定の `migrate-to-plugin` を含む |
| `verdict_confirmed` | phase2-02 (plugin 境界決定) を経て確定する最終 verdict。`migrate-to-plugin` レコードには `target_plugin != null` が必須化される |
| `target_plugin` | `migrate-to-plugin` レコードの宛先 plugin 名 (文字列)。phase2-01 では `null` 許容、phase2-02 で確定 |
| `pyc/cache 系資産` | `__pycache__/` 配下 / `*.pyc` 拡張子のファイル。Python bytecode キャッシュ。`verdict_tentative='delete'` 確定 (再生成可能のため安全削除可) |

共通用語は `doc/migration/phase2/README.md` 参照。

## Section 4. スコープ

含む:

- `creator-kit/` 配下の全ファイル列挙 (`find creator-kit -type f`)
- 各ファイルに対する SHA256 と `plugins/skill-creator/` 相当パスとの一致判定
- 各ファイルに対する verdict 付与 (4分類 MECE)
- `eval-log/task/phase2-01/residual-inventory.json` の生成
- verdict 集計表の README 反映

含まない:

- 別 plugin への物理移動 (タスク 06 の責務)
- `creator-kit/` の物理削除 (タスク 07 の責務)
- skill 単位の責務再評価 (タスク 02 の責務)
- `manifest.json` 整合性検査 (phase0 governance / phase2-02 の責務)
- `plugins/skill-creator/` 配下への試験移行品質検査 (phase0-08 試験移行 review の責務)
- `governance-log.jsonl` への P0_breaking 承認記録 (`.github/workflows/governance-check.yml` の責務)

## Section 5. 前提条件

1. Phase 0 closure (`eval-log/phase/0/closure.json`) が PASS で存在する
2. Phase 1 closure (`eval-log/phase/1/closure.json`) が PASS で存在する (Phase 1 = 設計+評価 Phase。README 実行ゲート表参照)
3. `plugins/skill-creator/` が試験移行完了状態にある (`eval-log/task/08/review-approval.json` の `decision == "approved"`)
4. `creator-kit/` ディレクトリが物理的に存在する
5. `python3 >= 3.11` と `sha256sum` (もしくは `shasum -a 256`) が利用可能

### 依存ツールCLI契約確認

- `find --help` の `-type` `-name` `-print` フラグが本タスクの呼び出し形式と一致すること
- `python3 -c "import hashlib,json,pathlib"` が import エラーを返さないこと
- 本タスクは新規 CLI を導入しない (Phase 0 凍結原則)

## Section 6. 完了条件 (DoD)

| DoD | 内容 | 機械検証 |
|---|---|---|
| DoD-1 | `eval-log/task/phase2-01/residual-inventory.json` が存在し、JSON として valid | `python3 -c "import json; json.load(open('eval-log/task/phase2-01/residual-inventory.json'))"` |
| DoD-2 | inventory の全レコードに `verdict_tentative` が付与され、`migrate-to-plugin` / `keep-non-plugin` / `delete` / `defer` のいずれか | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-01/residual-inventory.json'));rs=d['records'];assert all(r.get('verdict_tentative') in {'migrate-to-plugin','keep-non-plugin','delete','defer'} for r in rs)"` |
| DoD-3 | `verdict_tentative == 'delete'` のレコードは (a) `duplicate_of_plugin == true` または (b) `rel` が `__pycache__/` 配下 / `*.pyc` 拡張子 のいずれかを満たす | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-01/residual-inventory.json'));bad=[r for r in d['records'] if r['verdict_tentative']=='delete' and not (r.get('duplicate_of_plugin') or '__pycache__' in r['rel'] or r['rel'].endswith('.pyc'))];assert not bad, bad"` |
| DoD-4 | `_bootstrap/`、`install.sh`、`install.ps1` は `verdict_tentative == "keep-non-plugin"` (理由: 配布用インストーラは plugin 配下に置かない) | inventory.json 該当レコードを確認 |
| DoD-5 | `verdict_tentative == "defer"` のレコードには `defer_reason` フィールドが必須 | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-01/residual-inventory.json'));assert all('defer_reason' in r for r in d['records'] if r['verdict_tentative']=='defer')"` |
| DoD-6 | README タスク一覧表のステータスが「完了 (YYYY-MM-DD)」に更新される | `grep -E "phase2-01.*完了" doc/migration/phase2/README.md` |
| DoD-7 | `review-approval.json` が `eval-log/task/phase2-01/` に生成され、`decision == "approved"` | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-01/review-approval.json'));assert d['decision']=='approved'"` |
| DoD-8 | `verdict_tentative == 'migrate-to-plugin'` の全レコードに `target_plugin` フィールドが存在 (値は `null` 許容、phase2-02 で確定) | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-01/residual-inventory.json'));assert all('target_plugin' in r for r in d['records'] if r['verdict_tentative']=='migrate-to-plugin')"` |
| DoD-9 | `verdict_tentative == 'keep-non-plugin'` レコードの根拠 (`reason`) が明示されている | inventory.json 該当レコードを確認 |
| DoD-10 | Section 4 の「含まない」リストに `manifest.json` 整合性 / `governance-log.jsonl` / plugin 試験移行品質 の 3 項目が明記されている | `grep -E "manifest\.json 整合性\|governance-log" doc/migration/phase2/01-residual-asset-inventory.md` |

## Section 7. 実行手順

### Step 7.1 残資産列挙

```bash
mkdir -p eval-log/task/phase2-01
find creator-kit -type f ! -path '*/.git/*' -print > eval-log/task/phase2-01/residual-files.txt
wc -l eval-log/task/phase2-01/residual-files.txt
```

### Step 7.2 SHA256 計算と plugin 側との一致判定

```bash
python3 scripts/phase2/residual-inventory-builder.py \
  --creator-kit creator-kit \
  --plugin-root plugins/skill-creator \
  --out eval-log/task/phase2-01/residual-inventory.json
```

スクリプトは本タスクで新規実装する必要は無い。代替として以下のインライン Python を使う (Phase 0 凍結 CLI には触らない):

```bash
python3 <<'PY'
import hashlib, json, pathlib
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
ck = pathlib.Path('creator-kit')
pl = pathlib.Path('plugins/skill-creator')
records = []
for f in sorted(ck.rglob('*')):
    if not f.is_file(): continue
    rel = f.relative_to(ck)
    rec = {'path': str(f), 'rel': str(rel), 'sha256': sha(f), 'duplicate_of_plugin': False, 'verdict': None}
    cand = pl / rel
    if cand.is_file() and sha(cand) == rec['sha256']:
        rec['duplicate_of_plugin'] = True
    records.append(rec)
out = {'generated_at': __import__('datetime').datetime.now().astimezone().isoformat(), 'records': records}
pathlib.Path('eval-log/task/phase2-01/residual-inventory.json').write_text(json.dumps(out, indent=2, ensure_ascii=False))
PY
```

### Step 7.3 verdict 自動付与 (機械判定可能な部分)

```bash
python3 <<'PY'
import json, pathlib
p = pathlib.Path('eval-log/task/phase2-01/residual-inventory.json')
d = json.loads(p.read_text())
KEEP_PREFIXES = (
    '_bootstrap/', 'install.sh', 'install.ps1', 'CONVENTIONS.md',
    'manifest.json', 'uninstall.sh', 'migrate-from-project.sh',
    'migrate-log/', 'config/', 'scripts/', 'README.md',
)
for r in d['records']:
    rel = r['rel']
    # 第1分岐: plugin 側との完全重複は delete
    if r['duplicate_of_plugin']:
        r['verdict_tentative'] = 'delete'
        r['reason'] = 'duplicate of plugins/skill-creator'
    # 第2分岐: Python bytecode キャッシュは delete (再生成可能)
    elif '__pycache__' in rel or rel.endswith('.pyc'):
        r['verdict_tentative'] = 'delete'
        r['reason'] = 'python bytecode cache (regenerable)'
    # 第3分岐: 配布物 / installer / repo-level docs は keep-non-plugin
    elif any(rel.startswith(k) or rel == k for k in KEEP_PREFIXES):
        r['verdict_tentative'] = 'keep-non-plugin'
        r['reason'] = 'installer / manifest / repo-level asset stays outside plugin tree'
    else:
        r['verdict_tentative'] = None  # TODO(human) for solo_operator
    # 案A: target_plugin フィールドを必須化 (migrate-to-plugin で後段確定、それ以外は null 固定)
    r.setdefault('target_plugin', None)
p.write_text(json.dumps(d, indent=2, ensure_ascii=False))
PY
```

### Step 7.4 TODO(human) verdict 決定

verdict が `None` のレコードは solo_operator が判定する。判定基準:

- 別 plugin に分割すべき責務がある → `migrate-to-plugin`
- 後続 Phase で別途扱う (例: marketplace 連携前提) → `defer` + `defer_reason`

実装者は判定しない (本 README 実行ルール#4)。

### Step 7.5 集計とサマリ生成

```bash
python3 <<'PY' | tee eval-log/task/phase2-01/verdict-summary.txt
import json, pathlib
from collections import Counter
d = json.loads(pathlib.Path('eval-log/task/phase2-01/residual-inventory.json').read_text())
c = Counter(r['verdict'] for r in d['records'])
print('verdict counts:', dict(c))
PY
```

### Step 7.6 README 更新

`doc/migration/phase2/README.md` のタスク一覧表 phase2-01 行ステータスを「完了 (YYYY-MM-DD)」に更新。

### Step 7.7 レビュー承認

solo_operator がレビューし `eval-log/task/phase2-01/review-approval.json` を生成。

## Section 8. 検証手順

| 完了条件 | 検証コマンド |
|---|---|
| DoD-1 | `python3 -c "import json; json.load(open('eval-log/task/phase2-01/residual-inventory.json'))" && echo PASS` |
| DoD-2 | Step 7.3 末尾の verdict_tentative 集計が None 0 件 |
| DoD-3 | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-01/residual-inventory.json'));bad=[r for r in d['records'] if r['verdict_tentative']=='delete' and not (r.get('duplicate_of_plugin') or '__pycache__' in r['rel'] or r['rel'].endswith('.pyc'))];assert not bad, bad"` |
| DoD-4 | `grep -E '"rel":\s*"(_bootstrap\|install)' eval-log/task/phase2-01/residual-inventory.json` の `verdict_tentative` が `keep-non-plugin` |
| DoD-5 | DoD 表の inline コマンド |
| DoD-6 | `grep -E "phase2-01.*完了" doc/migration/phase2/README.md` |
| DoD-7 | `jq '.decision' eval-log/task/phase2-01/review-approval.json` が `"approved"` |
| DoD-8 | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-01/residual-inventory.json'));assert all('target_plugin' in r for r in d['records'] if r['verdict_tentative']=='migrate-to-plugin')"` |
| DoD-9 | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-01/residual-inventory.json'));assert all(r.get('reason') for r in d['records'] if r['verdict_tentative']=='keep-non-plugin')"` |
| DoD-10 | `grep -E "manifest\.json 整合性\|governance-log" doc/migration/phase2/01-residual-asset-inventory.md` |

## Section 9. リスクと対策

| 失敗モード | 対策 | INV参照 |
|---|---|---|
| `find` 出力に空白を含むパスがあり集計が壊れる | Python `pathlib.rglob` を使用 (Step 7.2) | - |
| verdict が偏り `migrate-to-plugin` が肥大化する | 02 で plugin 境界を精緻化することで吸収 | - |
| 重複判定が SHA256 のみで意味的差を見逃す | 02 で frontmatter `name` も比較する gate を追加 | INV-9 |
| `creator-kit/_drafts/` のような実験的資産を誤って migrate に分類 | TODO(human) で solo_operator 判断 | - |
| `governance-log.jsonl` への承認記録漏れにより plugins/ 配下追加が CI で P0_breaking ブロックされる | phase2-01 完了時に `target_path` に `plugins/` を含む承認 entry を追加することを Section 7.7 の必須手順とする | - |
| `has_recent_changelog` の `target_path.split("/")[0]` 単一要素 substring match 仕様により approval 範囲が不明瞭 | 33章 governance runbook で entry の `target_path` 表記規約 (文字列形式 + 明示的パス列挙) を別途整備 | - |

## Section 10. 成果物一覧

| 成果物 | パス | 責任者 |
|---|---|---|
| 残資産インベントリ JSON | `eval-log/task/phase2-01/residual-inventory.json` | AI |
| 残資産ファイル一覧 | `eval-log/task/phase2-01/residual-files.txt` | AI |
| verdict 集計 | `eval-log/task/phase2-01/verdict-summary.txt` | AI |
| レビュー承認 | `eval-log/task/phase2-01/review-approval.json` | solo_operator |
| README ステータス更新 | `doc/migration/phase2/README.md` | AI |

ツール契約 (凍結参照): 本タスクは新規 CLI を導入しない。Phase 0 `scripts/build-claude-*.py` を変更しない。

## Section 11. 参照ドキュメント

- `doc/migration/phase0/01-external-reference-inventory.md` (棚卸し手順の上流テンプレート)
- `eval-log/task/01/inventory.json` (Phase 0 棚卸し成果物。verdict 4分類の運用先例)
- `doc/migration/phase2/README.md` (本 Phase 用語集と横断 gate 表)

## Section 12. 中学生レベル概念説明

引っ越しの準備に例えると、`creator-kit/` は古い家、`plugins/` は新しい家です。すでに新しい家に運び込んだもの (skill-creator 1 件) は OK。残った荷物 (棚や工具など) を、新しい家に持ち込む (migrate)、屋外の物置に置く (keep-non-plugin)、捨てる (delete)、まだ判断しない (defer) の 4 つに分けます。本タスクはこの仕分け表を作る作業です。仕分けが終わらないと、その後の引っ越し本番には進めません。

## Section 13. チェックリスト

- [x] Phase 0 closure 確認 (`cat eval-log/phase/0/closure.json | grep task_pass_count`)
- [x] `creator-kit/` 物理存在確認
- [x] Step 7.1 `residual-files.txt` 生成
- [x] Step 7.2 inventory.json 生成 (records 数 = residual-files.txt 行数)
- [x] Step 7.3 自動 verdict 付与
- [x] Step 7.4 solo_operator が TODO(human) verdict を全件埋める
- [x] Step 7.5 verdict 集計 None 件数 0
- [x] DoD-1〜7 検証コマンド全 PASS
- [x] README ステータス更新
- [x] review-approval.json 生成
