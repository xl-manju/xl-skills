# タスク 03: per-plugin 物理移行手順仕様

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| ID | phase2-03 |
| 名称 | per-plugin 物理移行手順仕様 |
| 担当 | AI (草案) + solo_operator (承認) |
| 期限 | 02 完了から 5 営業日以内 |
| 依存タスク | phase2-02 |
| ステータス | 完了 (2026-05-20) |

## Section 2. 目的と背景

02 で確定した partition (= plugin) 群を、`plugins/<name>/` 配下に物理移行するための **per-plugin 手順テンプレート** を仕様として固定する。試験移行 (phase0 タスク 08) は skill-creator 1 件で完結したが、本 Phase は複数 plugin の量産であり、各 plugin に対し再現性ある手順がないと:

- 移行順序のミスで build CLI --check が一時的に exit !=0 になる
- plugin.json schema 違反が混入する
- 既存 `plugins/skill-creator/` の symlink が壊れる

ため、08 の手順を量産化したテンプレを本タスクで固定する。

根拠: `doc/migration/phase0/08-trial-migration-skill-creator.md` (試験版手順)、`doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md`。

## Section 3. 用語集 (本タスク固有)

| 用語 | 定義 |
|---|---|
| 移行順序 | partition の plugin 化を実施する順番。依存の少ない plugin から先に投入する |
| per-plugin プレイブック | 1 plugin あたりの移行手順を Step 単位で定義したテンプレート |
| 中間状態 | ある plugin を投入し終わり、次の plugin 未投入の状態。build CLI --check が exit 0 を維持すべき状態 |
| plugin.json schema | `plugins/skill-creator/.claude-plugin/plugin.json` で実証済の Claude CLI 認識スキーマ |
| 責務クラス | adapter / hook / lint / migration / secrets / config / automation。partition の plugin を分類する 7 軸。`eval-log/task/phase2-03/migration-order.json` の `responsibility_class` フィールドの値域 |
| executable spec | DoD 検証が「ファイル存在」ではなく「契約 CLI の dry-run 実行」を要求する仕様レベル |

共通用語は README 参照。

## Section 4. スコープ

含む:

- 移行順序の決定基準 (依存数の昇順、責務クラス順 など) の明文化
- per-plugin プレイブックの Step 1-N 定義
- `plugin.json` テンプレートの確定 (skill-creator 実装からの抽出)
- 各 plugin 投入後の検証コマンド列 (build CLI --check + namespace lint)
- 中間状態の不変条件 (INV-Mid-1〜) の定義

含まない:

- 実際の物理移行実行 (06 の責務)
- rollback.sh の自動生成ロジック (04 の責務)
- 削除 (07 の責務)

## Section 5. 前提条件

1. phase2-02 が DoD 全 PASS
2. `eval-log/task/phase2-02/partition-plan.json` が確定済
3. `plugins/skill-creator/.claude-plugin/plugin.json` が valid (試験移行成果物)
4. `scripts/build-claude-symlinks.py --check` と `scripts/build-claude-settings.py --check` が現状 exit 0

### 依存ツールCLI契約確認

- `eval-log/task/06/cli-contract-frozen.txt` と `eval-log/task/07/cli-contract-frozen.txt` は **semantic 契約 (Markdown)** として運用される
- `eval-log/task/06/cli-help-frozen.txt` と `eval-log/task/07/cli-help-frozen.txt` は **syntactic スナップショット (raw --help)** として運用され、`diff -u` の完全一致検査に使用する
- `scripts/build-claude-symlinks.py --help` が `cli-help-frozen.txt` と一致
- `scripts/build-claude-settings.py --help` が `cli-help-frozen.txt` と一致
- raw help snapshot と一致しない場合は本タスク着手不可

## Section 6. 完了条件 (DoD)

| DoD | 内容 | 機械検証 |
|---|---|---|
| DoD-1 | `eval-log/task/phase2-03/migration-procedure.md` が存在し、Step 1-N が明記される | `grep -c "^### Step " eval-log/task/phase2-03/migration-procedure.md` ≥ 5 |
| DoD-2 | 移行順序が partition-plan.json に基づき決定される `migration-order.json` 生成 | `python3 -c "import json;d=json.load(open('eval-log/task/phase2-03/migration-order.json'));assert d['order'] and all('rank' in o for o in d['order'])"` |
| DoD-3 | plugin.json テンプレートが存在 | `test -f eval-log/task/phase2-03/plugin.json.template` |
| DoD-4 | 中間状態の不変条件 (INV-Mid-*) が >= 3 件定義 | `grep -c "^| INV-Mid-[0-9]" eval-log/task/phase2-03/migration-procedure.md` ≥ 3 |
| DoD-5 | 各 Step に検証コマンドが付随 | `grep -A 2 "^### Step " eval-log/task/phase2-03/migration-procedure.md` で `verify:` の出現を確認 |
| DoD-6 | `review-approval.json` が `approved` | 内容検査 |
| DoD-7 | `eval-log/task/phase2-03/deploy-plugin-spec.md` が存在し `scripts/phase2/deploy-plugin.sh` の CLI 契約が明記される、かつ `scripts/phase2/deploy-plugin.sh --dry-run <plugin-name>` が exit 0 で stdout に `[P-1]`〜`[P-9]` の 9 行を出力する | `bash scripts/phase2/deploy-plugin.sh --dry-run skill-governance-adapters \| grep -c '^\[P-[1-9]\]'` == 9 |
| DoD-8 | `eval-log/task/phase2-03/dod-verification.md` と `eval-log/task/phase2-03/cli-contract-verification.md` が存在し、両者の判定結果が `PASS` または `RESOLVED` である | `test -f eval-log/task/phase2-03/dod-verification.md && test -f eval-log/task/phase2-03/cli-contract-verification.md` |

## Section 7. 実行手順

### Step 7.1 移行順序の決定基準策定

基準:

1. 依存される側を先に: `partition-plan.json` の `depends_on` ターゲットが先順位
2. 責務クラス昇順: `adapter` → `hook` → `lint` → `migration` → `secrets` → `config` → `automation` (実装の `responsibility_class` 値域に整合)
3. アルファベット昇順 (上記同点時)

solo_operator 承認: `eval-log/task/phase2-03/review-approval.json` に記録済 (2026-05-20)。

### Step 7.2 migration-order.json 生成

```json
{
  "generated_at": "...",
  "criteria": ["depended-first", "responsibility-class", "alphabetical"],
  "order": [
    {"rank": 1, "plugin": "<name>", "depends_on": []},
    {"rank": 2, "plugin": "<name>", "depends_on": ["<rank-1-plugin>"]}
  ]
}
```

### Step 7.3 per-plugin プレイブックテンプレート策定

各 plugin に対し以下の Step を実行する (テンプレート):

```
Step P-1. plugins/<name>/ ディレクトリ作成
Step P-2. partition-plan.json の対応 skills を creator-kit/skills から git mv
Step P-3. 対応 agents を git mv
Step P-4. .claude-plugin/plugin.json をテンプレートから生成 (name 置換)
Step P-5. build-claude-symlinks.py --check で conflict 0 確認
Step P-6. build-claude-settings.py --check で INV-1〜12 PASS 確認
Step P-7. plugin.json の Claude Code CLI plugin validate (利用可能なら)
Step P-8. rollback-<plugin>.sh 生成 (04 仕様に従う)
Step P-9. 各 Step 結果を eval-log/task/phase2-06/<plugin>/ に保存
```

### Step 7.4 plugin.json テンプレート抽出

```bash
# 4 プレースホルダ ({{plugin_name}}, {{description}}, {{version}}, {{keywords}}) に正規化
python3 -c "
import json, pathlib
p = pathlib.Path('eval-log/task/phase2-03/plugin.json.template')
d = {
  'name': '{{plugin_name}}',
  'version': '{{version}}',
  'description': '{{description}}',
  'keywords': '{{keywords}}'
}
p.write_text(json.dumps(d, indent=2, ensure_ascii=False))
"
```

Step P-6 では partition record から `name`/`version`/`description`/`keywords` を取得して 4 プレースホルダを全置換する。description 固定文の流用は禁止。

### Step 7.5 中間状態の不変条件定義

| 不変条件 | 内容 | 確認タイミング |
|---|---|---|
| INV-Mid-1 | 任意の plugin 投入後、`scripts/build-claude-symlinks.py --check` が exit 0 | 各 Step P-7 後 |
| INV-Mid-2 | 任意の plugin 投入後、`scripts/build-claude-settings.py --check` が INV-1〜12 PASS | 各 Step P-8 後 |
| INV-Mid-3 | 投入済 plugin 以外の SKILL.md は creator-kit に残ったまま不変 | 各 Step P-9 で moved-files.txt と partition-plan.json を突合 |
| INV-Mid-4 | `.claude/settings.json` user セクション hash が一切変動しない | `scripts/build-claude-settings.py --print-user-section-hash` を before/after で diff |
| INV-Mid-5 | `plugins/skill-creator/` が完全保持され `.claude-plugin/plugin.json` が valid | `jq . plugins/skill-creator/.claude-plugin/plugin.json` |

### Step 7.6 migration-procedure.md 執筆

上記 Step P-1〜P-9 と INV-Mid-* を含む完成版を `eval-log/task/phase2-03/migration-procedure.md` に書き出し。

### Step 7.7 レビュー承認

solo_operator が `review-approval.json` 生成。

## Section 8. 検証手順

| 完了条件 | 検証コマンド |
|---|---|
| DoD-1 | `grep -c "^### Step " eval-log/task/phase2-03/migration-procedure.md` ≥ 5 |
| DoD-2 | DoD 表 inline |
| DoD-3 | `test -f eval-log/task/phase2-03/plugin.json.template && jq . eval-log/task/phase2-03/plugin.json.template > /dev/null` |
| DoD-4 | `grep -c "^| INV-Mid-[0-9]" eval-log/task/phase2-03/migration-procedure.md` ≥ 3 |
| DoD-5 | プレイブックの各 Step に `verify:` 行が存在 |
| DoD-6 | review-approval.json |
| DoD-7 | `test -f eval-log/task/phase2-03/deploy-plugin-spec.md && grep -q "scripts/phase2/deploy-plugin.sh" eval-log/task/phase2-03/deploy-plugin-spec.md` |

## Section 9. リスクと対策

| 失敗モード | 対策 | INV |
|---|---|---|
| 移行順序ミスで中間状態が壊れる | INV-Mid-1/2 を各 Step P-9 で確認 | INV-Mid-1, INV-Mid-2 |
| plugin.json schema が CLI 認識と乖離 | テンプレート抽出元は試験移行で認識実証済 | - |
| `git mv` が試験移行済 skill-creator のファイルを誤って動かす | partition-plan.json と整合確認 | INV-9 |
| 移行中に .claude/settings.json user セクションが揺らぐ | INV-Mid-4 + Phase 0 INV-1 | INV-1 |
| (D) plugin.json.template の固定 description を他 plugin 流用 → INV-9 違反 | Step 7.4 placeholder 化と Step P-6 で全 placeholder 置換チェック | INV-9 |

## Section 10. 成果物一覧

| 成果物 | パス | 責任者 |
|---|---|---|
| migration-procedure.md | `eval-log/task/phase2-03/migration-procedure.md` | AI |
| migration-order.json | `eval-log/task/phase2-03/migration-order.json` | AI + solo_operator |
| plugin.json テンプレ | `eval-log/task/phase2-03/plugin.json.template` | AI |
| deploy-plugin-spec.md | `eval-log/task/phase2-03/deploy-plugin-spec.md` | AI |
| review-approval.json | `eval-log/task/phase2-03/review-approval.json` | solo_operator |
| dod-verification.md | `eval-log/task/phase2-03/dod-verification.md` | AI |
| cli-contract-verification.md | `eval-log/task/phase2-03/cli-contract-verification.md` | AI |

`deploy-plugin-spec.md` には `scripts/phase2/deploy-plugin.sh` の CLI 仕様 (引数: `$1 = plugin-name`、exit コード: 0=成功/1=検証失敗/2=設定不整合、stdout: 各 Step 進捗ログ) を明記する。06 はこの仕様を「凍結済」として参照する。

`scripts/phase2/deploy-plugin.sh` 本体は phase2-06 で本実装、本タスクでは `--dry-run` 経路のみを凍結契約として最小実装する。

ツール契約 (凍結参照): `scripts/build-claude-symlinks.py`, `scripts/build-claude-settings.py` を Phase 0 frozen のまま使用。

## Section 11. 参照ドキュメント

- `doc/migration/phase0/08-trial-migration-skill-creator.md` (試験版手順)
- `plugins/skill-creator/.claude-plugin/plugin.json` (実証済テンプレ元)
- `eval-log/task/06/cli-contract-frozen.txt`
- `eval-log/task/07/cli-contract-frozen.txt`
- `eval-log/task/06/cli-help-frozen.txt`
- `eval-log/task/07/cli-help-frozen.txt`
- `eval-log/task/phase2-03/deploy-plugin-spec.md`
- `eval-log/task/phase2-03/dod-verification.md`
- `eval-log/task/phase2-03/cli-contract-verification.md`

## Section 12. 中学生レベル概念説明

引っ越し本番の前に、引越し業者に渡す「箱ごとの運び方マニュアル」を作る作業です。「どの箱から先に運ぶか」「箱を開けたあと何を確認するか」「途中で家具が傾いていないか」のチェックリストを各箱ごとに作るので、本番で迷わずに済みます。試験で 1 箱だけ運んだ経験 (skill-creator) を活かして、量産時にも使える型を作ります。さらに本タスクではマニュアルが「読めばわかる」だけでなく「dry-run コマンドが実際に動く」ところまで踏み込む executable spec 化を行います。

## Section 13. チェックリスト

- [x] phase2-02 DoD 全 PASS 確認
- [x] Phase 0 凍結 CLI 契約と現状の help 出力確認
- [x] Step 7.1〜7.6 完了
- [x] DoD-1〜7 全 PASS
- [x] DoD-8 PASS確認
- [x] solo_operator 承認
