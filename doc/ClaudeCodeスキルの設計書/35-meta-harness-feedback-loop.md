# 35. Meta-Harness Feedback Loop

最終更新: 2026-05-18

## 目的

セッションログを根拠に `ref-*` Skill（および全 Skill）の `description` / 本文 / `gotchas` / `examples` を**統制ある形で**改善するパイプラインを定義する。

Stanford IRIS Lab の Meta-Harness（execution traces → harness end-to-end 最適化）と Hermes Agent（経験から Skill 自己生成）の問題意識に応えるが、**自己採点罠と Goodhart 罠の予防を最優先**とする。本章はそのための構造設計を提示する。

## 正本の分担

| 領域 | 正本 |
|---|---|
| 観測対象 failure mode の閉じた列挙 | `creator-kit/config/meta-harness-observables.json`（配布正本） / `.claude/config/meta-harness-observables.json`（導入先コピー） |
| ガバナンス境界（log由来改善のカテゴリ） | `33-change-governance.md` § log-driven ref-* 改善 |
| 改善の周回ロジック（既存の elegant-review 周回） | `creator-kit/skills/run-elegant-review/references/{amplified-patterns,convergence-policy}.json` |
| 本章で扱うこと | パイプライン全体（収集 → 分類 → 起票 → ガバナンス接続） |

## 中核原則

| 原則 | 意味 |
|---|---|
| **観測軸は閉じた列挙** | failure_modes は observables.json に列挙されたものに限る。追加は P0_breaking |
| **再現性しきい値** | 単一セッション観測で恒久ルール化しない（gotchas は最低3回横断） |
| **改善は P1_structural** | log 由来の ref-* 改善は P2 ではなく P1（自己採点罠予防） |
| **rationale に観測根拠** | log 由来改善の changelog は failure_mode ID と session_id を必須記載 |
| **観測スキーマの不変性** | スキーマ変更は P0_breaking（改善履歴の比較性が失われるため） |

## パイプライン全体図

```
[session logs (.claude/logs/*.jsonl)]
        │
        ▼
[1. collect]   ── 機械収集（hook or 後処理）
        │
        ▼
[2. classify]  ── observables.json の failure_modes と照合
        │
        ▼
[3. accumulate] ── min_recurrence_for_action しきい値判定
        │
        ▼
[4. propose]   ── ref-* 改善 PR 起票（人間レビュー前提）
        │
        ▼
[5. govern]    ── 33章 P1_structural ワークフローに接続
        │
        ▼
[changelog 記録 + Skill 更新]
```

## Phase 別ロードマップ

| Phase | スコープ | 入口ゲート | 出口ゲート |
|---|---|---|---|
| **Phase 0** | observables 列挙確定 + ガバナンス境界定義 | （前提なし） | `.claude/config/meta-harness-observables.json` 初版完成 + 33章 § log-driven 節 |
| **Phase 1** | ログ収集機構（.claude/logs/ スキーマ + collect hook） | Phase 0 完了 | creator-kit manifest 登録 + スキーマ v1.0 確定 + 収集スクリプト配置 + **実ログ蓄積 ≥ 1 セッション** |
| **Phase 2** | classify + accumulate（observables との突合・カウント蓄積） | Phase 1 実装完了 + 実ログ蓄積 ≥ 1 セッション + 7日以上のログ蓄積 | failure_mode 別に閾値超え検出が機械実行できる |
| **Phase 3** | propose（改善 PR 自動起票） | Phase 2 完了 + 誤検出率 < 20% の検証 | ref-* 改善 PR が drafts として自動生成される |
| **Phase 4** | govern 接続（33章 P1_structural ワークフロー自動連結） | Phase 3 完了 + 3件以上の手動 PR 経験 | classify_change が log 起源 PR を P1 として自動分類 |

**現在地**: Phase 1 実装完了・実ログ蓄積待機中（スキーマ v1.0 確定 + `creator-kit/scripts/extract-session-events.py` 配置 + hook example + manifest 登録 + .gitignore）。Phase 2 開始ゲート: 実ログ蓄積 ≥ 1 セッション（未達）。Phase 2 (classify + accumulate) は実ログ蓄積達成後に着手。

## ログスキーマ v1.0（Phase 1 確定）

配布正本: `creator-kit/config/meta-harness-log-schema-v1.0.json`。導入先コピー: `.claude/logs/schema-v1.0.json`。スキーマ変更は P0_breaking（33章 § log-driven ref-* 改善）。

### 構成

| field | type | event 共通/個別 | 用途 |
|---|---|---|---|
| `schema_version` | string | 共通（const "1.0"） | スキーマ互換性 |
| `ts` | ISO8601 string | 共通 | turn 内/turn 間判定 |
| `session_id` | string | 共通 | cross-session 集計の主キー |
| `event` | enum: user_prompt/tool_use/stop | 共通 | event 種別 |
| `text` | string (≤2000) | user_prompt | 発動語/follow-up/境界条件の照合対象 |
| `tool_name`, `skill_invoked`, `skill`, `success` | string/bool | tool_use | 発動有無・誤発動判定 |
| `reason` | string | stop | 中断要因の付帯情報 |

### 収集機構（opt-in）

- スクリプト: `creator-kit/scripts/extract-session-events.py`（install後は `scripts/extract-session-events.py`。28章 §4 動詞 `extract` 準拠）
- hook 登録例: `creator-kit/config/meta-harness-hooks.json.example`（install後は `.claude/settings.meta-harness-hooks.json.example`。UserPromptSubmit / PostToolUse / Stop の3点）
- 出力先: `.claude/logs/<YYYY-MM-DD>.jsonl`（`.claude/logs/.gitignore` で git 追跡除外）

### observables との対応

`.claude/logs/schema-v1.0.json` の `observable_mapping` を正本とする。各 failure mode の `observable_signal` は本スキーマ上で**全て機械観測可能**であることを保証する（Phase 1 出口ゲートの達成条件）。

### Phase 1 出口判定

- [x] スキーマ v1.0 確定（本節）
- [x] 収集スクリプト動作確認（stdin JSON → jsonl 追記）
- [x] hook 登録 example 配置（opt-in）
- [x] creator-kit manifest 登録
- [x] gitignore でログ実体を git から除外
- [ ] 1セッション以上の実ログ蓄積（運用フェーズで達成）

## Goodhart 罠の予防（再強調）

ログを観測対象に組み込むと、以下のいずれかが必然的に発生する。本章はこれらを構造で予防する:

| 罠 | 予防策 |
|---|---|
| ログ映えする発動の最適化 | observables を**閉じた列挙**に固定。追加は P0_breaking |
| 偶発事象の恒久ルール化 | `min_recurrence_for_action` を性質ごとに設定（gotchas≥3） |
| 自己採点罠（自分のログで自分を採点） | log 由来改善は P1_structural（27章の自己採点禁則と同型） |
| 観測軸の振動 | スキーマ変更を P0_breaking 化。改善履歴の比較性を保護 |

## 既存メカニズムとの関係

| 既存 | 本章との関係 |
|---|---|
| `run-elegant-review/references/amplified-patterns.json` (P001-P004) | **elegant-review 周回内の正FB**。本章は**周回を跨ぐ（cross-session）正負FB** |
| `run-elegant-review/references/convergence-policy.json` (C1-C4) | elegant-review の収束ポリシー。本章 propose 段階で参照可能 |
| 24章 SKILL.md テンプレの `gotchas` セクション | 静的記述。本章は gotchas を**観測根拠付きで動的更新**する経路 |
| 27章 rubric-governance | Skill 品質を rubric で評価。本章は rubric では捉えにくい**発動条件と判断材料**を補完 |
| 33章 change-governance | 本章は 33章のワークフローを**log 起源変更にも適用**する経路 |

## 反パターン

| 反パターン | リスク | 予防 |
|---|---|---|
| ログ収集を先に作って observables 未確定運用 | 観測軸が振動、改善方向が定まらない | Phase 0 ゲートで遮断 |
| observables を無制限に追加 | Goodhart 罠 | 追加を P0_breaking 化 |
| 単一セッション観測で description 即変更 | 偶発事象の恒久化 | `min_recurrence_for_action` 必須参照 |
| log 由来改善を P2_content として処理 | 自己採点罠 | 33章ルールで P1_structural 固定 |
| ログを KPI 化して数値最適化 | Skill本来の目的が侵食される | rationale で改善の質的根拠を必須化 |
| 観測スキーマを軽率に変更 | 改善履歴の比較性喪失 | スキーマ変更を P0_breaking 化 |

## 更新ルール

1. observables.json の `failure_modes` を変更する場合、本章「現在地」と 33章 § log-driven 節を同時更新する
2. Phase 進捗があった場合、本章「Phase 別ロードマップ」の出口ゲート判定と「現在地」を更新する
3. ログスキーマを変更する場合、本章「ログスキーマ」セクションを正本確定版に書き換え、changelog に P0_breaking として記録する
4. 本章を変更する場合、自分自身が P1_structural になる（33章自己適用ルール）
