# doc/migration/phase2 — Phase 2 本番 タスク仕様書インデックス

最終更新: 2026-05-20

## このディレクトリの目的

`doc/migration/phase2/` は、設計書34章の **Phase 2 本番(残り plugin 全件移行 + creator-kit 廃止)**に接続する実行可能タスク仕様書を保管する正本ディレクトリ。

Phase 0 (準備) と Phase 1 (設計+評価)、および Phase 2 試験移行 (skill-creator 1件、`doc/migration/phase0/08-trial-migration-skill-creator.md`) は既に closure 済み。本ディレクトリは「試験 → 本番」への昇格、すなわち **creator-kit/ 残資産の plugin 物理移行と creator-kit/ ディレクトリの正本剥奪** を扱う。

本ディレクトリでは、34章の移行段階を **Phase**、各タスク仕様書内の固定構成を **Section** と呼ぶ。両者を混同しない。

### 設計原則

| 原則 | 内容 |
|---|---|
| 単一責務 (SRP) | 1ファイル = 1タスク。複数の責務を1ファイルに混ぜない |
| 100人中100人 | 読み手の前提知識を仮定せず、用語集と中学生レベル説明を必須 |
| 好き勝手禁止 | 仕様書に書かれた手順以外の改変・追加・省略は禁止。逸脱は proposal を作成 |
| Section 1-13 厳守 | 全タスク仕様書は本 README 末尾の Section 1-13 構成テンプレに従う |
| 仕様凍結 | レビュー PASS 後の仕様変更は P0_breaking (33章) 扱い。再合意必須 |
| Phase 0 資産再利用 | `scripts/build-claude-symlinks.py` と `build-claude-settings.py` は本 Phase で**新規実装しない**。CLI 契約は phase0 タスク 03/04 で凍結済 |

## 34章 Phase 対応

| 34章 Phase | 本ディレクトリで扱うタスク | 実行ゲート |
|---|---|---|
| Phase 2 本番 | 01〜08 | Phase 0 closure (`eval-log/phase/0/closure.json`)、Phase 1 closure (`eval-log/phase/1/closure.json`)、試験移行 (phase0 タスク 08) が PASS 済 |
| Phase 完了宣言 | 09 | 対象 Phase の実行結果、残課題、承認を記録する |

**重要**: 本 Phase は試験移行 (skill-creator 1件) の延長線上で **複数 plugin の量産** を扱う。Phase 0 の build CLI と settings merge 仕様の上に成立しており、CLI 仕様の変更を含めない。CLI 変更が必要な場合は P0_breaking として 33章ガバナンス手続きへ戻る。

## タスク一覧と依存関係

```
                    [01] 残資産棚卸し
                          │
                          ▼
                  [02] plugin 分割境界仕様
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
[03] 物理移行手順    [04] rollback/      [05] CONVENTIONS
   仕様 (per-plugin)    drift 検証仕様      更新仕様
        │                 │                 │
        └─────────────────┼─────────────────┘
                          ▼
                   [06] 各 plugin 物理移行
                       (実行)
                          │
                          ▼
                   [07] creator-kit/
                     物理削除 (実行)
                          │
                          ▼
                   [08] 全 plugin 統合検証
                          │
                          ▼
                  [09] Phase 2 本番 完了報告
```

### タスク一覧表

| ID | ファイル | 責務 | 種別 | 依存 | ステータス |
|---|---|---|---|---|---|
| 01 | `01-residual-asset-inventory.md` | creator-kit 残資産 (skills/agents/非plugin資産) の棚卸し | 仕様+実行 | phase0 Phase 0 closure | 完了 (2026-05-20) |
| 02 | `02-plugin-partition-specification.md` | 残資産を複数 plugin に分割する境界仕様 (どの skill をどの plugin へ) | 仕様 | 01 | 完了 (2026-05-20) |
| 03 | `03-per-plugin-migration-procedure.md` | plugin 毎の物理移行手順仕様 (移行順序、依存解決、namespace 検査) | 仕様 | 02 | 完了 (2026-05-20) |
| 04 | `04-rollback-and-drift-specification.md` | rollback.sh 生成と drift 検証 (build CLI --check) の本番運用仕様 | 仕様 | 02 | 完了 (2026-05-20) |
| 05 | `05-conventions-phase2-update.md` | 三層モデル CONVENTIONS.md の Phase 2 本番化追記 (層C 退役、層B 縮退) | 仕様+実行 | 02 | 完了 (2026-05-20) |
| 06 | `06-per-plugin-migration-execution.md` | 各 plugin を `plugins/<name>/` へ物理移行する実行タスク | 実行 | 03, 04, 05 | 完了 (2026-05-20) |
| 07 | `07-creator-kit-removal.md` | `creator-kit/` 配下の正本剥奪と物理削除 | 実行 | 06 | 完了 (2026-05-20) |
| 08 | `08-phase2-integration-verification.md` | 全 plugin 統合検証 (build CLI --check、INV-1〜12、namespace conflict 0) | 実行 | 07 | 完了 (2026-05-20) |
| 09 | `09-phase2-completion-report.md` | Phase 2 本番完了報告 + closure.json | 文書 | 08 | 完了 (2026-05-20) |

**作成順序**: 01 → 02 → 03/04/05 並列可 → 06 → 07 → 08 → 09

**実装系タスク (06, 07) は仕様系タスク (02, 03, 04, 05) が全て PASS してから着手**。08 は 06/07 が完了し、Phase 0 で凍結済の build CLI が `--check` exit 0 を返すまで着手しない。

## 用語集 (本 Phase 固有)

| 用語 | 定義 |
|---|---|
| 残資産 | `creator-kit/` 配下に存在し、`plugins/skill-creator/` への試験移行 (phase0 タスク 08) 完了後も creator-kit 側に残っている全資産 |
| plugin 分割境界 | 残資産を複数 plugin へ再編する際の責務境界。同一 plugin 内には責務が単一の skill/agent/command 群のみを置く |
| 量産 | 試験 1件 (skill-creator) から複数 plugin へのスケール過程 |
| 正本剥奪 | あるディレクトリが「変更を行う唯一の場所」でなくなる状態への遷移。本 Phase では `creator-kit/` から正本性を取り除く |
| Phase 2 試験 | phase0 タスク 08 を指す。skill-creator 1件のみの物理移行 |
| Phase 2 本番 | 本ディレクトリが扱う作業。試験移行で立証された手順を量産展開する |
| INV-* | settings merge の不変条件 (INV-1〜INV-12)。phase0 タスク 02 と 34a 章で定義済。本 Phase では新規追加しない |

共通用語 (plugin、正本、派生、三層モデル、TODO(human)、P0〜P3、build-claude-*.py、マーカー区間、user セクション) は `doc/migration/phase0/README.md` の用語集を参照する。

## 参照ドキュメント (本 Phase 固有)

| 参照先 | 役割 |
|---|---|
| `doc/migration/phase0/README.md` | Phase 0 タスク仕様インデックス。CLI 契約と用語集の上流 |
| `doc/migration/phase0/08-trial-migration-skill-creator.md` | 試験移行手順の正本。本 Phase は本仕様の量産版 |
| `doc/migration/phase0/PHASE-GATE-COMPLETION.md` | Phase 0 完了報告。本 Phase の前提 |
| `eval-log/phase/0/closure.json` | Phase 0 closure 証跡 |
| `eval-log/phase/1/closure.json` | Phase 1 (設計+評価) closure 証跡。本 Phase の実行ゲート条件 (上表「Phase 2 本番」行) として参照する。Phase 1 が PASS でなければ 01 に着手しない |
| `doc/ClaudeCodeスキルの設計書/34-plugin-governance-roadmap.md` | plugin 移行ロードマップ正本 |
| `doc/ClaudeCodeスキルの設計書/34a-settings-merge-spec.md` | settings merge 不変条件 (INV-1〜12) |
| `doc/ClaudeCodeスキルの設計書/33-change-governance.md` | 変更分類 MECE と P0〜P3 |
| `scripts/build-claude-symlinks.py` | Phase 0 凍結済 CLI。本 Phase で再利用 (新規実装不可) |
| `scripts/build-claude-settings.py` | Phase 0 凍結済 CLI。本 Phase で再利用 |
| `CONVENTIONS.md` | 三層モデル定義。本 Phase 05 で追記 |
| `creator-kit/manifest.json` | 現 kit 構成正本 (Phase 2 本番完了で正本剥奪) |

## 横断不安要素チェック表 (Phase 2 本番)

plugin 量産時は、下記をすべて gate として扱う。1件でも FAIL の場合、07 (creator-kit 削除) へ進まない。

| 不安要素 | 対応仕様 | Gate |
|---|---|---|
| 同名 skill / agent / command が複数 plugin に重複定義される | 02 namespace 仕様、34a INV-9 | `build-claude-symlinks.py --check` と `build-claude-settings.py --dry-run --json` が conflict 0 |
| `SKILL.md name` とディレクトリ名のズレが残資産から持ち込まれる | 02 Step 7.x | frontmatter name と directory name を全 plugin で同一 namespace 検査 |
| hooks が複数 plugin から重複登録される | 34a INV-5 | event + matcher + command の重複は exit 2 |
| permissions が plugin 間で deny/ask 競合する | 34a INV-11 | 同一 rule の deny/ask 競合は exit 2 |
| `.claude/settings.json` user セクションが変更される | 34a INV-1 | user セクション hash が全実行前後で一致 |
| 試験移行 plugin (skill-creator) との二重生成が発生する | 02、03 | 同一 skill 名の plugin 由来が複数になった場合 exit 2 |
| 移行途中で .claude/skills が一時的に壊れる | 06、04 rollback | 各 plugin 投入後に build CLI --check が exit 0 |
| creator-kit 残資産のうち plugin 化されない資産の扱いが不明 | 01、02 verdict 集計 | 全資産が `migrate-to-plugin` / `keep-non-plugin` / `delete` / `defer` のいずれかに分類済。`defer` は `defer_reason`、削除前退避先、Phase 3 carry-over を必須とする |
| rollback 不能な物理移行になる | 04、06 | 各 plugin 投入毎に rollback.sh を事前生成 + `bash -n` PASS |
| Phase 0 で凍結した CLI 契約に依存変更が混入する | 設計原則 | `scripts/build-claude-*.py --help` 出力 hash が phase0 frozen と一致 |

## Section 1-13 構成テンプレート (全タスク仕様書必須)

**注意**: タスク仕様書内のセクション番号は `Section N` を使う。34章の `Phase 0〜4` と名前空間が衝突するため、`Phase` の語をセクション見出しに使ってはならない。

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

## ツール契約凍結原則 (Phase 0 から継承、必須遵守)

Phase 0 で凍結された CLI 契約は本 Phase で変更しない。タスク仕様書を書き始める前に:

1. `<tool> --help` の出力が phase0 frozen ファイル (`eval-log/task/06/cli-contract-frozen.txt`、`eval-log/task/07/cli-contract-frozen.txt`) と一致することを確認
2. 一致しない場合は、本 Phase 着手の前に phase0 タスク 06/07 のレビュー再開と P1_structural (33章) 手続きへ戻る
3. 確定した CLI 契約をタスク仕様書 Section 10 に「ツール契約 (凍結参照)」として明記
4. 仕様書の機械検証コマンドは、必ず Phase 0 凍結済契約のみを使う

## 実行ルール (好き勝手禁止)

1. **タスクは ID 順に着手する**。並列可と明記されたタスクのみ並列実行可能
2. **仕様凍結後の改変は禁止**。逸脱が必要な場合は本 README に proposal セクションを追加し、ユーザー承認後に該当仕様書を更新
3. **Section 1-13 のいずれかを省略しない**。該当しない場合は `N/A — 理由:` を明記
4. **TODO(human) は実装者が埋めない**。レビュアー (solo_operator もしくは指名された人間) が埋める
5. **完了条件 (Section 6) を1つでも満たさない状態でステータスを「完了」にしない**
6. **検証ログは `eval-log/task/phase2-<task-id>/` に保存**。<task-id> は **2桁ゼロパディング必須** (例: `phase2-01`、`phase2-09`)。Phase 0 と log path を分離 (phase0 と衝突回避)
7. **plugin の物理移行 (06) と creator-kit 削除 (07) は不可逆性が高い**。各ステップで `git status -s` を残し、ロールバック手段が `eval-log/task/phase2-06/rollback-<plugin>.sh` に揃っているまで着手しない

## phase2-02 partition 一覧

正本成果物: `eval-log/task/phase2-02/partition-plan.json`

| partition | files | 責務 |
|---|---:|---|
| `skill-governance-adapters` | 7 | 外部 sink / route adapter scripts |
| `skill-governance-automation` | 13 | build / compose / notify / rollback 等の orchestration scripts |
| `skill-governance-config` | 12 | governance 設定・registry・hook example |
| `skill-governance-hooks` | 6 | Claude hook entrypoint scripts |
| `skill-governance-lint` | 15 | lint / validate / check 系 gate scripts |
| `skill-governance-migration` | 3 | migration audit / brief conversion helper |
| `skill-governance-secrets` | 3 | secret audit / keychain helper |

phase2-02 partition では `eval-log/task/phase2-01/residual-inventory.json` の `verdict_tentative == "migrate-to-plugin"` 59件を `files[].rel` として exactly 1 partition に割り当てた。`target-plugin-map.json` と `confirmed-inventory.json` は下流 03/06 の入力として使用する。`partition-dependency-graph.json` の `inter_partition_refs` は post-migration runtime dependency ではなく、03/06 で rewrite または例外処理が必要な legacy path 候補として扱う。

## 改訂履歴

| 日付 | 改訂者 | 内容 |
|---|---|---|
| 2026-05-20 | AI | Phase 2 closed。phase2-01〜08 の完了状態、closure JSON、完了報告書を反映 |
| 2026-05-20 | AI | phase2-08 完了。全 plugin 統合検証、和集合一致、user section hash、revert dry-run、Claude CLI plugin validate を PASS として記録 |
| 2026-05-20 | AI | phase2-05 完了。CONVENTIONS.md に Phase 2 本番 (発効待ち: 層C 退役) を追記し、README ステータスを更新 |
| 2026-05-20 | AI | phase2-03 / 04 / 06 完了。7 partition を `plugins/<name>/` へ物理移行し、phase2-06 証跡と承認ログを更新 |
| 2026-05-20 | AI | phase2-02 完了。7 partition / 59 migrate files / target-plugin-map / dependency graph を登録 |
| 2026-05-20 | initial | doc/migration/phase2/ 新設、タスク 01〜09 をインデックス化 |
