# doc/migration/phase0 — Phase 0 タスク仕様書インデックス

最終更新: 2026-05-20 (doc/task → doc/migration/phase0 リネーム)

## このディレクトリの目的

`doc/migration/phase0/` は、設計書34章の **Phase 0-2 ゲート**に接続する実行可能タスク仕様書を保管する正本ディレクトリ。

本ディレクトリでは、34章の移行段階を **Phase**、各タスク仕様書内の固定構成を **Section** と呼ぶ。両者を混同しない。

### 設計原則

| 原則 | 内容 |
|---|---|
| 単一責務 (SRP) | 1ファイル = 1タスク。複数の責務を1ファイルに混ぜない |
| 100人中100人 | 読み手の前提知識を仮定せず、用語集と中学生レベル説明を必須 |
| 好き勝手禁止 | 仕様書に書かれた手順以外の改変・追加・省略は禁止。逸脱は proposal を作成 |
| Section 1-13 厳守 | 全タスク仕様書は本 README 末尾の Section 1-13 構成テンプレに従う |
| 仕様凍結 | レビュー PASS 後の仕様変更は P0_breaking (33章) 扱い。再合意必須 |

## 34章 Phase 対応

| 34章 Phase | 本ディレクトリで扱うタスク | 実行ゲート |
|---|---|---|
| Phase 0 | 01、および 02〜07 の準備仕様・CLI実装 | 公式制約 c/e、settings 生成、symlink 派生の前提を閉じる |
| Phase 1 | 02〜07 のレビュー結果を使った設計・評価 | 34章 Phase 1 → Phase 2 ゲートが PASS するまで物理移行しない |
| Phase 2 | 08 | skill-creator 1件のみの試験 plugin 物理移行。Phase 0/1 完了と公式制約5点 PASS が前提 |
| Phase 完了宣言 | 09 | 対象 Phase の実行結果、残課題、承認を記録する |

**重要**: 08 は Phase 2 の試験移行タスクであり、Phase 0 完了だけで実行してはならない。

## タスク一覧と依存関係

```
                    [01] 外部参照棚卸し
                          │
                          ▼
   [02] settings.json マージ仕様策定 (34a章新設)
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
[03] symlink構築      [04] settings    [05] 3層モデル
  仕様策定           マージCLI仕様      文書化(CONVENTIONS)
        │                 │                 │
        ▼                 ▼                 │
[06] build-claude-     [07] build-claude-   │
   symlinks.py 実装     settings.py 実装    │
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼
                   [08] 試験移行
                  (creator-kit → plugins/skill-creator/)
                          │
                          ▼
                  [09] 結果ドキュメント化
                     (eval-log + Phase gate完了宣言)
```

### タスク一覧表

| ID | ファイル | 責務 | 種別 | 依存 | ステータス |
|---|---|---|---|---|---|
| 01 | `01-external-reference-inventory.md` | 全 SKILL.md の plugin 外参照棚卸し | 仕様+実行 | なし | 完了 (2026-05-20) |
| 02 | `02-settings-merge-specification.md` | settings.json マージ仕様確定 (34a章執筆) | 仕様 | 01 | 完了 (2026-05-20) |
| 03 | `03-symlink-build-specification.md` | build-claude-symlinks.py 仕様 | 仕様 | 02 | 完了 (2026-05-20) |
| 04 | `04-settings-merge-cli-specification.md` | build-claude-settings.py 仕様 | 仕様 | 02 | 完了 (2026-05-20) |
| 05 | `05-three-layer-model-documentation.md` | 層A/B/C 責務境界の CONVENTIONS.md 追記 | 仕様+実行 | 02 | 完了 (2026-05-20) |
| 06 | `06-build-claude-symlinks-implementation.md` | build-claude-symlinks.py 実装 | 実装 | 03 | 完了 (2026-05-20) |
| 07 | `07-build-claude-settings-implementation.md` | build-claude-settings.py 実装 | 実装 | 04 | 完了 (2026-05-20) |
| 08 | `08-trial-migration-skill-creator.md` | creator-kit/ → plugins/skill-creator/ 試験移行 | 実行 | 05, 06, 07 + 34章 Phase 1→2 gate PASS | 完了 (2026-05-20) |
| 09 | `09-phase0-completion-report.md` | Phase gate 完了報告書 + eval-log | 文書 | 対象 Phase の全タスク | 完了 (2026-05-20) |

**作成順序**: 01 → 02 → 03/04/05 並列可 → 06/07 並列可 → 09 (Phase 0/1 close) → 08 (Phase 2 gate PASS 後) → 09 (Phase 2 close)

**実装系タスク (06, 07) は仕様系タスク (02, 03, 04) が全て PASS してから着手**。08 は 05/06/07 と 34章 Phase 1→2 gate が全て PASS してから着手する。

## 用語集 (全タスク共通)

| 用語 | 定義 |
|---|---|
| plugin | Claude Code 公式の配布単位。`plugins/<name>/` 配下に skills/agents/commands/hooks/scripts/references を持つ |
| Phase 0 | 設計書34章で定義された準備フェーズ。plugin 物理移行の前提条件を整える期間 |
| Phase 1 | plugin 物理移行前の設計+評価フェーズ |
| Phase 2 | 試験 plugin (skill-creator) 1件のみの物理移行フェーズ |
| 正本 (source of truth) | 全変更を行う唯一の場所。`plugins/<name>/` を指す |
| 派生 (derivative) | 正本から自動生成される副本。`.claude/agents,skills,commands/` の symlink 群 |
| 三層モデル | 層A=配布対象、層B=プロジェクト固有運用、層C=移行中 drift の責務分類 |
| INV-* | settings merge の不変条件識別子 (INV-1〜INV-12) |
| TODO(human) | 機械では決められない人間判断箇所のマーカー。勝手に埋めない (34章 第4更新ルール) |
| P0/P1/P2/P3 | 変更影響度分類 (33章)。P0=破壊的、P3=軽微 |
| build-claude-symlinks.py | plugins/*/{agents,skills,commands}/ から .claude/ への symlink を冪等に再構築する CLI |
| build-claude-settings.py | plugins/*/.claude-plugin/plugin.json から .claude/settings.json を冪等に再生成する CLI |
| マーカー区間 | settings.json 内の `_generated_section_start` と `_generated_section_end` で挟まれた自動生成領域 |
| user セクション | マーカー区間外の手編集領域。build CLI 実行で 1byte も変更されてはならない |

## 参照ドキュメント (全タスク共通)

| 参照先 | 役割 |
|---|---|
| `doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md` | plugin 移行ロードマップ正本 |
| `doc/ClaudeCodeスキルの設計書/33-change-governance.md` | 変更分類 MECE と P0/P1/P2/P3 規約 |
| `doc/ClaudeCodeスキルの設計書/06-classification-and-naming.md` | 命名規約 (第1〜17条) |
| `doc/ClaudeCodeスキルの設計書/05-layering-skill-subagent-hook-mcp-cli.md` | レイヤ責務分離 |
| `doc/ClaudeCodeスキルの設計書/10-subagents-hooks-integration.md` | SubAgent / Hook 統合 |
| `doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook.md` | eval-log パス規約 |
| `creator-kit/skills/ref-skill-naming-convention/SKILL.md` | 命名規約サマリ |
| `creator-kit/manifest.json` | 現 kit 構成正本 |
| `references/governance-params.json.example` | 運用パラメータ例。実体は承認済みコピーまたは `creator-kit/config/governance-params.json.example` を確認 |

## 横断不安要素チェック表

plugin 由来の設定・Skill・Agent・Command を `.claude/` 配下へ派生生成する際は、下記をすべて gate として扱う。1件でも FAIL の場合、08 の試験移行へ進まない。

| 不安要素 | 対応仕様 | Gate |
|---|---|---|
| 同名 skill / agent / command が別 plugin から生成される | 03 の名前衝突検出、34a の INV-9 | `build-claude-symlinks.py --check` と `build-claude-settings.py --dry-run --json` が conflict 0 |
| `SKILL.md name` とディレクトリ名のズレで短名が衝突する | 03 Step 7.4 | frontmatter name と directory name を同一 namespace で検査 |
| hooks が重複して二重発動する | 34a INV-5 | event + matcher + command の重複は exit 2 |
| permissions が plugin 間で矛盾する | 34a INV-11 | 同一 rule の deny/ask 競合は exit 2 |
| `.claude/settings.json` の構造が壊れる | 34a INV-10 | permissions/hooks の型検査 PASS |
| user 管理領域が壊れる | 34a INV-1 | user 管理領域 hash が実行前後で一致 |
| 生成計画が不完全でレビューできない | 34a INV-12 / 04 plan JSON | plan に namespace/settings/conflicts/invariants_checked を含む |
| rollback 不能な物理移行になる | 08 DoD-8 | rollback.sh 事前生成 + `bash -n` PASS |
| 未確定 TODO が実装へ流れる | 本 README 実行ルール | TODO(human) が残る対象は次タスク着手不可 |

## Section 1-13 構成テンプレート (全タスク仕様書必須)

**注意**: タスク仕様書内のセクション番号は `Section N` を使う。34章の `Phase 0〜4` と名前空間が衝突するため、`Phase` の語をセクション見出しに使ってはならない (Phase 2 アナリスト合意による命名規約)。

```
Section  1. メタ情報            (ID, 名称, 担当, 期限, 依存タスク, ステータス)
Section  2. 目的と背景          (なぜこのタスクが必要か、根拠ドキュメント参照)
Section  3. 用語集              (本タスク固有用語のみ。共通用語は README 参照)
Section  4. スコープ            (含む / 含まない を明示)
Section  5. 前提条件            (実行前に満たすべき条件、依存タスク完了状況)
                              **Section 5 末尾に「依存ツールCLI契約確認」を必須項目として含めること**
Section  6. 完了条件 (DoD)      (Definition of Done。機械検証可能な形で列挙)
Section  7. 実行手順            (ステップバイステップ、各ステップに通し番号)
Section  8. 検証手順            (各完了条件をどう確認するか、コマンド・ログ等)
Section  9. リスクと対策        (想定失敗モード×対策、INV-* 参照)
Section 10. 成果物一覧          (生成するファイル+パス+責任者。**依存ツールのCLI仕様も成果物として列挙**)
Section 11. 参照ドキュメント    (本タスク固有の参照。共通は README 参照)
Section 12. 中学生レベル概念説明 (専門用語を使わず、例え話で説明)
Section 13. チェックリスト      (実行者がチェックしながら進める箇条書き)
```

## ツール契約凍結原則 (Phase 2 アナリスト発見、必須遵守)

タスク仕様書を書き始める前に、依存する CLI ツール (Python/shell スクリプト) について以下を確定する:

1. `<tool> --help` を実行し、実在する引数・フラグを記録
2. ツールが出力する JSON/テキストの実フィールド名を1回試走で確認
3. 期待スキーマが実装と乖離する場合は、**仕様書執筆前にどちらを正本とするかを決定**する
4. 確定したCLI契約をタスク仕様書 Section 10 に「ツール契約」として明記
5. 仕様書の機械検証コマンドは、必ずこの確定済み契約のみを使う

**この原則を踏まずに仕様書を書いた場合、当該仕様書は P1_structural (33章) として再作業対象になる**。

## 実行ルール (好き勝手禁止)

1. **タスクは ID 順に着手する**。並列可と明記されたタスクのみ並列実行可能
2. **仕様凍結後の改変は禁止**。逸脱が必要な場合は本 README に proposal セクションを追加し、ユーザー承認後に該当仕様書を更新
3. **Section 1-13 のいずれかを省略しない**。該当しない場合は `N/A — 理由:` を明記
4. **TODO(human) は実装者が埋めない**。レビュアー (solo_operator もしくは指名された人間) が埋める
5. **完了条件 (Section 6) を1つでも満たさない状態でステータスを「完了」にしない**
6. **検証ログは `eval-log/task/<task-id>/` に保存**。改竄禁止

## Proposal: 01 Step 7.3 CLI契約確認コマンド修正

ステータス: 適用済み (2026-05-19) / 再検証で CONTRACT MATCH 確認 (2026-05-20)。タスク 01 全 DoD PASS、abort 条件は解消。v1 期の `eval-log/task/01/abort-report.json` は `eval-log/task/01/_archive/` に移動済 (成果物外)。

### 背景

タスク 01 Step 7.3 の契約確認で、`python3 scripts/lint-external-refs.py --help` の実出力は仕様書 Section 5 の usage と一致している。一方、検証コマンドは `grep -E "^\s+--"` で実出力のオプション行を抽出するため、`argparse` が出す `  -h, --help` 行を除外する。

期待リストには `  -h, --help` が含まれているため、実装と契約が一致していても diff は必ず以下を出して FAIL する。

```diff
4a5
>   -h, --help
```

### 提案

タスク 01 Step 7.3 の抽出条件を、短縮オプション付きの help 行も拾う形へ修正する。

```bash
diff <(grep -E "^\s+(-h, --help|--)" eval-log/task/01/cli-contract-actual.txt | sed -E 's/[[:space:]]{2,}show this help message and exit$//' | sort) <(printf '  --allowed-prefix ALLOWED_PREFIX\n  --fail-on-external\n  --json\n  --skills-dir SKILLS_DIR\n  -h, --help\n' | sort) && echo "CONTRACT MATCH"
```

### 影響

- 分類: P1_structural
- 対象: `doc/migration/phase0/01-external-reference-inventory.md` Step 7.3
- 実装スクリプト `scripts/lint-external-refs.py` の CLI 契約変更は不要
- 承認後、タスク 01 を Step 7.3 から再開可能

## 改訂履歴

| 日付 | 改訂者 | 内容 |
|---|---|---|
| 2026-05-19 | initial | doc/migration/phase0/ 新設、タスク 01〜09 をインデックス化 |
| 2026-05-19 | v2 | Section 1-13 命名規約導入、ツール契約凍結原則追加、01 を v2 化 |
| 2026-05-19 | v3 | タスク 02〜09 仕様書を全件生成 (各 Section 1-13 完備、ツール契約節含む) |
| 2026-05-19 | v4 | 34章 Phase とタスク Section の名前空間を分離し、08/09 の Phase gate 依存を明確化 |
| 2026-05-20 | v5 | Phase gate closed。01〜09 の完了状態、closure JSON、完了報告書を反映 |
| 2026-05-20 | v6 | Task 08 DoD-7 を実行可能性証跡で PASS 化し、全タスク完了状態へ同期 |
