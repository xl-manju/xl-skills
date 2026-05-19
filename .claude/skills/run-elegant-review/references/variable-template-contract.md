# 変数テンプレート契約

`run-elegant-review` は、対象固有の改善をそのまま再利用成果物へ埋め込まない。必ず次の順序で抽象化する。

1. 具体値を観察する。
2. 具体値をテンプレート変数へ写像する。
3. 変数の意味、既定値、必須性、適用しない条件を記録する。
4. 由来は `source_trace` に残す。
5. Skill / SubAgent / script / config へ反映する時は変数名を使う。

## 標準変数

| 変数 | 意味 | 既定値 |
|---|---|---|
| `{{PROJECT_ROOT}}` | 対象プロジェクトのルート | 実行時 cwd |
| `{{KIT_ROOT}}` | creator-kit のルート | `{{PROJECT_ROOT}}/creator-kit` |
| `{{target_type}}` | 対象種別 | `custom` |
| `{{target_path}}` | 対象パス | 入力値 |
| `{{review_workspace}}` | レビュー作業領域 | OS別一時ディレクトリ |
| `{{owner}}` | 所有者 | 利用プロジェクトで指定 |
| `{{os_kind}}` | 実行OS | `unknown` |
| `{{external_executor}}` | 外部実行環境 | `none` |

## findings で使う分類

| フィールド | 用途 |
|---|---|
| `finding_scope` | 一回限りの指摘か、横展開する設計知かを分ける |
| `source_tier` | 根拠の強さを示す |
| `trace_evidence` | 具体的な由来を示す |
| `migration_bucket` | `doc/20` の移行先分類へ接続する |
| `reuse_surface` | template / rubric / lint / hook / reference / manifest / runbook のどこへ昇格するかを示す |
| `runtime_variant` | `doc/22` のOS差分へ接続する |
| `dependency_assumption` | stdlib-only / optional-cli などの前提を示す |
| `negative_case` | 適用しない条件を明示する |
| `re_audit_trigger` | 再監査する契機を示す |

## 禁止

- 実プロジェクト名、個人名、固定絶対パス、固定API URL、固定ownerを reusable な成果物へ直書きしない。
- 具体値を消さない。`source_trace` に証跡として残す。
- `{{...}}` をパラメーター名として使う場合、本文説明は日本語で書く。
