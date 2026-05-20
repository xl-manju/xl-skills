# タスク 03 — build-claude-symlinks.py 仕様策定

## Section 1. メタ情報

| 項目 | 値 |
|---|---|
| タスク ID | 03 |
| タスク名称 | build-claude-symlinks.py CLI 仕様策定 |
| 種別 | 仕様策定 |
| 担当 | AI 起案 + 人間承認 |
| 期限 | Phase 0 完了の最低条件 |
| 依存タスク | 02 (settings merge 仕様) |
| 後続タスク | 06 (本仕様に基づく実装) |
| ステータス | 完了 |
| 改訂履歴 | 2026-05-20 v4 task execution complete |

## Section 2. 目的と背景

### 目的

`plugins/<name>/{agents,skills,commands}/` を **正本 (source of truth)** とし、`.claude/{agents,skills,commands}/` 配下に **派生 (derivative) symlink** を冪等に再構築する CLI ツールの仕様を確定する。

### 背景

- 設計書 34 章は plugin → .claude/ の symlink 派生モデルを採用するが、**再構築アルゴリズムが未定義**。
- 既存 `creator-kit/install.sh` は kit 単位の installer であり、複数 plugin 対応・冪等性保証・drift 検出に欠ける。

### 根拠

- `doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md` §4「symlink 派生モデル」
- 既存 `creator-kit/install.sh` (参考実装)

## Section 3. 用語集

| 用語 | 定義 |
|---|---|
| 正本 | `plugins/<name>/{agents,skills,commands}/<item>/` の実体ディレクトリ |
| 派生 symlink | `.claude/{agents,skills,commands}/<item>` から正本への相対 symlink |
| drift | 派生が正本と乖離した状態 (絶対パス symlink, ファイル混在等) |
| 冪等 | N 回実行しても結果が等しい性質 |
| --check モード | drift 検出のみ行い書き換えしない (CI 用) |

## Section 4. スコープ

### 含む

- `plugins/*/agents/*.md` → `.claude/agents/*.md`
- `plugins/*/skills/*/SKILL.md` → `.claude/skills/<skill>/` ディレクトリ symlink
- `plugins/*/commands/*.md` → `.claude/commands/*.md`
- 冪等再構築、drift 検出、`--dry-run`/`--check` モード
- 複数 plugin の名前衝突検出

### 含まない

- settings.json マージ (タスク 04)
- `scripts/`, `references/` の symlink (Layer A/B 三層モデルでの扱いはタスク 05)
- Windows ジャンクションサポート (`creator-kit/install.ps1` は別系統)

## Section 5. 前提条件

| # | 条件 |
|---|---|
| 1 | タスク 02 完了 |
| 2 | `plugins/` ディレクトリが将来的に出現する前提 |
| 3 | OS は POSIX (macOS/Linux)。Windows は別タスク |

### 依存ツールCLI契約確認

本仕様は将来実装する `scripts/build-claude-symlinks.py` の CLI 契約正本を本書 Section 10 で定義する。実装 (タスク 06) は本契約に従う。

## Section 6. 完了条件 (DoD)

| # | 条件 | 検証 |
|---|---|---|
| DoD-1 | CLI 契約 (フラグ・終了コード・出力スキーマ) が Section 10 に明記 | レビュアー確認 |
| DoD-2 | 冪等性アルゴリズム擬似コードあり | `grep -q "冪等" doc/migration/phase0/03-symlink-build-specification.md` |
| DoD-3 | 名前衝突 (同名 skill が複数 plugin に存在) の検出規約あり | レビュアー確認 |
| DoD-4 | `--check` 終了コード規約 (0=clean, 1=drift, 2/3/4=error subclasses) | レビュアー確認 |
| DoD-5 | symlink target の相対パス規約あり (絶対パス禁止) | `grep -q "symlink target は必ず .dst.parent. からの相対パス" doc/migration/phase0/03-symlink-build-specification.md` |
| DoD-6 | `eval-log/task/03/review-approval.json` 生成 | `python3 -c "import json; assert json.load(open('eval-log/task/03/review-approval.json')).get('approver')"` |

## Section 7. 実行手順

### Step 7.1 — CLI 契約案

```
usage: build-claude-symlinks.py [-h]
                                [--plugins-dir PLUGINS_DIR]
                                [--target-dir TARGET_DIR]
                                [--kinds KINDS]
                                [--dry-run]
                                [--check]
                                [--prune]
                                [--json]
```

| フラグ | 既定値 | 役割 |
|---|---|---|
| `--plugins-dir` | `plugins` | 正本ルート |
| `--target-dir` | `.claude` | 派生ルート |
| `--kinds` | `agents,skills,commands` | 対象種別 (カンマ区切り) |
| `--dry-run` | false | 実行計画を JSON 出力し書き換えない |
| `--check` | false | drift 検出のみ。差分あれば exit 1 |
| `--prune` | false | どの plugin にも対応しない orphan symlink を削除対象に含める |
| `--json` | false | レポートを JSON で stdout 出力 |

終了コード: 0=success, 1=drift detected (check モード) / 2=name conflict / 3=invalid plugin layout / 4=fs error。

### Step 7.2 — 出力スキーマ案

```json
{
  "plugins_dir": "<path>",
  "target_dir": "<path>",
  "kinds": ["agents","skills","commands"],
  "plan": [
    {"action": "create|update|noop|conflict", "src": "...", "dst": "...", "reason": "..."}
  ],
  "summary": {"created": N, "updated": N, "noop": N, "conflict": N}
}
```

### Step 7.3 — 冪等アルゴリズム擬似コード

**規約 (DoD-5 正本):** symlink target は必ず `dst.parent` からの相対パスで生成する。絶対パス symlink は禁止 (リポジトリ可搬性のため)。下記擬似コード中の `src_rel = relative(item, dst.parent)` がこの規約の唯一の実装規範である。

```
for kind in kinds:
    for plugin in sorted(plugins_dir.iterdir()):
        for item in sorted((plugin / kind).iterdir()):
            dst = target_dir / kind / item.name
            src_rel = relative(item, dst.parent)
            if dst is symlink and readlink(dst) == src_rel:
                action = noop
            elif dst exists:
                if dst is symlink and readlink(dst) != src_rel:
                    action = update (unlink + symlink)
                else:
                    action = conflict (real file/dir found)
            else:
                action = create
            apply(action) unless dry_run
```

### Step 7.4 — 名前衝突検出

同一 `kind` 配下で複数 plugin が同名 item を提供した場合、**先勝ち禁止**で `conflict` を返し exit 2。回避策はリネームまたは plugin 統合。

skill の場合は、ディレクトリ名だけでなく `SKILL.md` frontmatter の `name` も同じ名前空間として扱う。たとえば `plugins/a/skills/foo/SKILL.md` と `plugins/b/skills/bar/SKILL.md` の frontmatter `name: foo` が衝突する場合も exit 2。これは公式 plugin の namespaced invocation と、開発用 `.claude/skills/<short-name>` symlink の混同を防ぐための dev-mode 制約である。

### Step 7.5 — orphan / broken symlink 掃除

| 状態 | 定義 | 既定動作 | `--check` | `--prune` |
|---|---|---|---|---|
| broken | symlink target が存在しない | report のみ | exit 1 | 削除 |
| orphan | symlink target は存在するが、現 plugin inventory に対応しない | report のみ | exit 1 | 削除 |
| wrong-target | 同名 item があるが target が違う | update | exit 1 | update |
| real-file-conflict | dst が symlink ではない実ファイル/実ディレクトリ | conflict | exit 2 | conflict |

`--prune` の既定値は false に固定する。既定変更は P1_structural proposal を必要とする。

### Step 7.6 — レビュー記録

`eval-log/task/03/review-approval.json` 生成。

## Section 8. 検証手順

DoD-1〜DoD-6 を順に検査。

## Section 9. リスクと対策

| ID | リスク | 対策 |
|---|---|---|
| R-01 | 絶対パス symlink を作って不可搬になる | INV「target は dst からの相対パス」を必須化 |
| R-02 | 名前衝突を silent merge する | exit 2 で必ず失敗、CI で再現 |
| R-03 | 既存 real file を上書き | `dst exists and not symlink` を conflict 扱い |
| R-04 | `.claude/<kind>/` の孤児が残る | `--prune` で明示的に掃除可 |
| R-05 | 実装と仕様の乖離 | 06 の DoD で本仕様の CLI を逐条検査 |

## Section 10. 成果物一覧

| ファイル | 責任者 |
|---|---|
| `doc/migration/phase0/03-symlink-build-specification.md` (本書) | AI |
| `eval-log/task/03/cli-contract.txt` (Section 7.1 をコピー) | AI |
| `eval-log/task/03/review-approval.json` | 人間 |

### ツール契約 (タスク 06 への引き継ぎ正本)

タスク 06 は以下の契約に従って実装する。

```
usage: build-claude-symlinks.py [-h]
                                [--plugins-dir PLUGINS_DIR]
                                [--target-dir TARGET_DIR]
                                [--kinds KINDS]
                                [--dry-run]
                                [--check]
                                [--prune]
                                [--json]
```

| フラグ | 既定値 | 役割 |
|---|---|---|
| `--plugins-dir` | `plugins` | 正本ルート |
| `--target-dir` | `.claude` | 派生ルート |
| `--kinds` | `agents,skills,commands` | 対象種別 (カンマ区切り) |
| `--dry-run` | false | 実行計画を JSON 出力し書き換えない |
| `--check` | false | drift 検出のみ。差分あれば exit 1 |
| `--prune` | false | どの plugin にも対応しない orphan symlink を削除対象に含める |
| `--json` | false | レポートを JSON で stdout 出力 |

終了コード: 0=success, 1=drift detected (check モード), 2=name conflict, 3=invalid plugin layout, 4=fs error。

```json
{
  "plugins_dir": "<path>",
  "target_dir": "<path>",
  "kinds": ["agents","skills","commands"],
  "plan": [
    {"action": "create|update|noop|conflict", "src": "...", "dst": "...", "reason": "..."}
  ],
  "summary": {"created": N, "updated": N, "noop": N, "conflict": N}
}
```

## Section 11. 参照ドキュメント

- `doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md`
- `creator-kit/install.sh` (参考)

## Section 12. 中学生レベル概念説明

学校の教室の **掃除当番表** を想像してください。教室 (= `.claude/`) には日替わりで担当が書かれた札 (= symlink) があり、札は職員室の元名簿 (= `plugins/`) を指しています。

```
職員室 plugins/skill-creator/skills/run-build-skill/   ← 元名簿 (実体)
       │
       └─→ symlink (相対参照)
              │
教室 .claude/skills/run-build-skill   ← 札 (派生)
```

CLI は **札を毎回作り直して、職員室と矛盾しない状態に戻す**役割。同名の札が 2 つ違う名簿を指していたら「衝突」としてエラーを返します。

## Section 13. 実行者チェックリスト

- [x] タスク 02 完了確認
- [x] CLI 契約 (フラグ・終了コード) 確定
- [x] 冪等アルゴリズム擬似コードレビュー
- [x] 名前衝突規約を承認
- [x] `--prune` 既定値 false を確認
- [x] DoD-1〜DoD-6 全 PASS

## 改訂履歴

| 日付 | バージョン | 改訂者 | 内容 |
|---|---|---|---|
| 2026-05-19 | v1 | initial | Section 1-13 構成で初版 |
| 2026-05-19 | v2 | elegant-review | `--prune` をCLI契約へ追加し、broken/orphan/wrong-target/real-file-conflictをMECE化 |
| 2026-05-19 | v3 | elegant-review | skill directory名とSKILL.md frontmatter nameの両方をdev短名名前空間として衝突検出対象化 |
| 2026-05-20 | v4 | Codex | Section 10 に CLI 契約正本を明記し、DoD 検証を完了 |
| 2026-05-20 | v4.1 | step-by-step audit | DoD-5 を独立規範文化し、検証手段を grep に格上げ |
