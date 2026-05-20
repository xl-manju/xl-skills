# タスク 08: Phase 2 統合検証

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| ID | phase2-08 |
| 名称 | Phase 2 統合検証 |
| 担当 | AI (実行) + solo_operator (gate 承認) |
| 期限 | 07 完了から 3 営業日以内 |
| 依存タスク | phase2-07 |
| ステータス | 未着手 |

## Section 2. 目的と背景

06 で各 plugin 個別に build CLI --check PASS を確認したが、全 plugin が `plugins/` に並んだ最終状態での **統合検証** は別途必要。試験移行 (phase0 タスク 08) の DoD-7 では Claude Code CLI 認識まで確認していた。本タスクは:

- 全 plugin 統合状態での namespace conflict 0
- 全 plugin 統合状態での INV-1〜INV-12 PASS
- `.claude/{skills,agents,commands}/` 派生が全 plugin の和集合と一致
- Claude Code CLI による plugin 認識 (利用可能なら)
- creator-kit 削除後の不可逆性確認

を Phase 2 本番完了の最終 gate として実行する。

根拠: `doc/migration/phase0/08-trial-migration-skill-creator.md` DoD-7 (CLI 認識証跡)、横断不安要素チェック表全項目。

## Section 3. 用語集 (本タスク固有)

| 用語 | 定義 |
|---|---|
| 統合状態 | 全 plugin が `plugins/` 配下に存在し、creator-kit/ が削除済の最終状態 |
| 和集合一致 | `.claude/skills/` の symlink 群が `plugins/*/skills/` の和集合と全件一致すること |
| CLI 認識 | Claude Code CLI (利用可能な場合) が plugin を検出・利用できる状態 |
| 不可逆性確認 | revert dry-run で 07 削除 commit を巻き戻せることを確認 |

共通用語は README 参照。

## Section 4. スコープ

含む:

- 全 plugin 統合状態での build CLI --check 再実行
- namespace conflict 0、INV-1〜12 PASS の最終確認
- `.claude/` 派生と plugins/ の和集合一致検証
- Claude Code CLI の `plugin validate` (利用可能な場合) 実行
- 統合検証レポート生成

含まない:

- 個別 plugin の検証 (06 の責務)
- 完了報告 (09 の責務)

## Section 5. 前提条件

1. phase2-07 が DoD 全 PASS、`creator-kit/` 削除済
2. `git status -s` が clean
3. Phase 0 frozen CLI と現状 help が一致

### 依存ツールCLI契約確認

- `scripts/build-claude-symlinks.py --check --json` と `--help` が phase0 frozen と一致
- `scripts/build-claude-settings.py --check --json` と `--help` が phase0 frozen と一致
- `claude` CLI が利用可能なら `claude plugin validate <name>` (試験移行時の運用形式)

## Section 6. 完了条件 (DoD)

| DoD | 内容 | 機械検証 |
|---|---|---|
| DoD-1 | `build-claude-symlinks.py --check --json` の plan 全件 noop & conflicts 0 | inline jq |
| DoD-2 | `build-claude-settings.py --check --json` conflicts 0 & invariants_checked length >= 12 | inline jq |
| DoD-3 | `.claude/skills/` の symlink 群が `plugins/*/skills/` の和集合と一致 | 集合比較 |
| DoD-4 | `.claude/agents/` の symlink 群が `plugins/*/agents/` の和集合と一致 | 集合比較 |
| DoD-5 | `.claude/commands/` の symlink 群が `plugins/*/commands/` の和集合と一致 | 集合比較 |
| DoD-6 | Phase 2 開始 snapshot と最終 snapshot の user セクション hash 一致 | diff |
| DoD-7 | 07 削除 commit の `git revert --no-commit --no-edit && git revert --abort` 成功 | inline |
| DoD-8 | `claude` CLI 利用可能な場合は plugin validate 全 plugin PASS / 利用不可なら recognition snapshot と `waived_by_solo_operator` 記録 | log + waiver |
| DoD-9 | `creator-kit/` 関連の dangling symlink が `.claude/` 配下にゼロ | `find .claude -lname '*creator-kit*' | wc -l` = 0 |
| DoD-10 | 統合検証レポート `eval-log/task/phase2-08/integration-report.md` 生成 | `test -f` |
| DoD-11 | review-approval.json が `decision == "approved"` | 内容検査 |

## Section 7. 実行手順

### Step 7.1 統合 build CLI --check

```bash
mkdir -p eval-log/task/phase2-08
python3 scripts/build-claude-symlinks.py --check --json > eval-log/task/phase2-08/symlinks-final.json
python3 scripts/build-claude-settings.py --check --json > eval-log/task/phase2-08/settings-final.json
echo "exit codes:"
python3 scripts/build-claude-symlinks.py --check; echo "symlinks=$?"
python3 scripts/build-claude-settings.py --check; echo "settings=$?"
```

### Step 7.2 和集合一致検証

```bash
python3 <<'PY' | tee eval-log/task/phase2-08/union-match.log
import pathlib
plugin_skills = sorted({p.name for p in pathlib.Path('plugins').glob('*/skills/*') if p.is_dir()})
claude_skills = sorted({p.name for p in pathlib.Path('.claude/skills').iterdir() if p.is_symlink()})
assert plugin_skills == claude_skills, f'mismatch:\n  plugins: {plugin_skills}\n  .claude: {claude_skills}'
# agents: ファイル名 (.md) で比較 (粒度を skills に揃え: どちらもエントリ名で比較)
plugin_agents = sorted({p.name for p in pathlib.Path('plugins').glob('*/agents/*') if p.is_file() and p.suffix == '.md'})
claude_agents = sorted({p.name for p in pathlib.Path('.claude/agents').iterdir() if p.is_symlink()})
assert plugin_agents == claude_agents, f'mismatch (agents):\n  plugins: {plugin_agents}\n  .claude: {claude_agents}'
plugin_commands = sorted({str(p.relative_to(p.parents[1] / 'commands')) for p in pathlib.Path('plugins').glob('*/commands/**/*') if p.is_file()})
claude_commands_dir = pathlib.Path('.claude/commands')
claude_commands = sorted({str(p.relative_to(claude_commands_dir)) for p in claude_commands_dir.rglob('*') if p.is_symlink()}) if claude_commands_dir.exists() else []
assert plugin_commands == claude_commands, f'mismatch (commands):\n  plugins: {plugin_commands}\n  .claude: {claude_commands}'
print('union match OK (skills + agents + commands)')
PY
```

### Step 7.3 dangling symlink 検出

```bash
find .claude -type l ! -exec test -e {} \; -print > eval-log/task/phase2-08/dangling.txt
test ! -s eval-log/task/phase2-08/dangling.txt
find .claude -lname '*creator-kit*' -print > eval-log/task/phase2-08/creator-kit-refs.txt
test ! -s eval-log/task/phase2-08/creator-kit-refs.txt
```

### Step 7.4 user セクション SHA256 比較

```bash
python3 scripts/build-claude-settings.py --print-user-section-hash > eval-log/task/phase2-08/user-section-final.sha256
# 06 Step 7.1 で保存した user section hash 専用 snapshot (同種比較)
diff eval-log/task/phase2-06/user-section-start.sha256 eval-log/task/phase2-08/user-section-final.sha256 || {
  echo "user セクション差分検出"; exit 1;
}
```

(注: 比較対象はどちらも `build-claude-settings.py --print-user-section-hash` の出力であり、同種比較を保証する。)

### Step 7.5 git revert dry-run

```bash
sha=$(git log --oneline --grep="remove creator-kit" -1 --pretty=%H)
git revert --no-commit --no-edit "$sha" && git revert --abort
echo "revert dry-run OK"
```

### Step 7.6 Claude Code CLI 認識 (利用可能な場合)

```bash
if command -v claude > /dev/null; then
  for p in $(ls plugins); do
    claude plugin validate "$p" 2>&1 | tee "eval-log/task/phase2-08/plugin-validate-$p.txt"
  done
else
  echo "claude CLI not available; recording recognition snapshot only; requires solo_operator waiver" \
    | tee eval-log/task/phase2-08/cli-recognition-note.txt
  ls -la .claude/skills | tee eval-log/task/phase2-08/claude-skills-final.txt
fi
```

### Step 7.7 統合レポート生成

```bash
python3 <<'PY' > eval-log/task/phase2-08/integration-report.md
import json, pathlib, datetime
syms = json.loads(pathlib.Path('eval-log/task/phase2-08/symlinks-final.json').read_text())
sets = json.loads(pathlib.Path('eval-log/task/phase2-08/settings-final.json').read_text())
print(f"# Phase 2 統合検証レポート\n\n生成: {datetime.datetime.now().isoformat()}\n")
print(f"- symlinks plan 件数: {len(syms['plan'])} (全 noop)")
print(f"- symlinks conflicts: {len(syms.get('conflicts', []))}")
print(f"- settings conflicts: {len(sets.get('conflicts', []))}")
print(f"- invariants_checked: {sets.get('invariants_checked')}")
PY
```

### Step 7.8 README ステータス更新 + レビュー承認

`doc/migration/phase2/README.md` を更新、`review-approval.json` 生成。

## Section 8. 検証手順

| 完了条件 | 検証コマンド |
|---|---|
| DoD-1 | `jq -e '.summary.conflict == 0 and ([.plan[] | select(.action!="noop")] | length == 0)' eval-log/task/phase2-08/symlinks-final.json` |
| DoD-2 | `jq '.conflicts | length, (.invariants_checked | length)' eval-log/task/phase2-08/settings-final.json` で 0, >=12 |
| DoD-3, DoD-4, DoD-5 | Step 7.2 のスクリプト exit 0 |
| DoD-6 | Step 7.4 diff exit 0 |
| DoD-7 | Step 7.5 |
| DoD-8 | log と waiver の確認 |
| DoD-9 | `test ! -s eval-log/task/phase2-08/dangling.txt && test ! -s eval-log/task/phase2-08/creator-kit-refs.txt` |
| DoD-10 | `test -f eval-log/task/phase2-08/integration-report.md` |
| DoD-11 | review-approval.json |

## Section 9. リスクと対策

| 失敗モード | 対策 | INV |
|---|---|---|
| 個別 plugin 検証では PASS だが統合時に namespace conflict 検出 | 02 partition 境界の見直しタスクへ戻す (P0_breaking) | INV-9 |
| symlink が一部の plugin について生成されていない | build-claude-symlinks.py を `--apply` で再実行し再検証 | - |
| user セクション hash の比較対象が不揃い (全体 sha vs user-section hash) | Step 7.4 および 06 Step 7.1 で `--print-user-section-hash` 専用 snapshot を取得し同種比較 (解消済) | INV-1 |
| claude CLI が無く DoD-7 を満たせない | snapshot を取得し、`waived_by_solo_operator` を review-approval.json または closure に明記する | - |
| revert dry-run が失敗 (commit が分散) | 07 Step 7.5 の「単一 commit ポリシー」を強制 | - |

## Section 10. 成果物一覧

| 成果物 | パス | 責任者 |
|---|---|---|
| symlinks-final.json / settings-final.json | `eval-log/task/phase2-08/{symlinks,settings}-final.json` | AI |
| union-match.log | `eval-log/task/phase2-08/union-match.log` | AI |
| dangling.txt / creator-kit-refs.txt | `eval-log/task/phase2-08/{dangling,creator-kit-refs}.txt` | AI |
| user-section-final.sha256 | `eval-log/task/phase2-08/user-section-final.sha256` | AI |
| plugin-validate-<name>.txt or claude-skills-final.txt | `eval-log/task/phase2-08/` | AI |
| integration-report.md | `eval-log/task/phase2-08/integration-report.md` | AI |
| review-approval.json | `eval-log/task/phase2-08/review-approval.json` | solo_operator |

ツール契約 (凍結参照): Phase 0 build CLI と `claude plugin validate` (試験移行で運用実証済)。

## Section 11. 参照ドキュメント

- `doc/migration/phase0/08-trial-migration-skill-creator.md` DoD-7 (CLI 認識証跡)
- `eval-log/task/08/dod-verification.md` (試験移行 DoD 表)
- `doc/migration/phase2/04-rollback-and-drift-specification.md` (drift-check.sh)

## Section 12. 中学生レベル概念説明

引っ越しが全部終わった後の最終チェックです。全部屋を見回って「家具が置きたい場所に置かれているか」「電気はちゃんとつくか」「鍵が全部閉まるか」を確認します。1 部屋ずつのチェック (= タスク 06) は終わっているので、本タスクは「全部屋まとめて見たときに不整合がないか」「もし引っ越しを巻き戻したくなったらできるか」を確認します。

## Section 13. チェックリスト

- [ ] phase2-07 DoD 全 PASS
- [ ] Step 7.1 build CLI --check exit 0
- [ ] Step 7.2 和集合一致 PASS
- [ ] Step 7.3 dangling / creator-kit 参照 0 件
- [ ] Step 7.4 user セクション hash 不変
- [ ] Step 7.5 revert dry-run PASS
- [ ] Step 7.6 CLI 認識 or snapshot 取得
- [ ] Step 7.7 integration-report.md 生成
- [ ] DoD 全 PASS
- [ ] solo_operator 承認
