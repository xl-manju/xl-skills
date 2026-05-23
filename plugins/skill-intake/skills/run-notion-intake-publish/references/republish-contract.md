# Republish Contract — run-notion-intake-publish

## 入力前提 (precondition)

呼び出し元 (人間 or 上位 skill) は次を満たした状態で本 skill を起動する。

| 前提 | 検査方法 | 不成立時 |
|---|---|---|
| `output/<hint>/intake.json` 存在 | `test -f` | exit 2 (hard-fail) |
| `output/<hint>/notion-manifest.json` 存在 | `test -f` | exit 2 |
| Keychain にトークン登録済み | `keychain_get_secret.py --check` | exit 2 (Secret-Out-of-Repo 違反防止) |
| Notion DB スキーマ整合 | `verify_notion_schema.py --on-conflict skip-warn` | exit 1 (skip) or 2 (fail) |
| アセット (PNG/SVG) 全数揃い | `verify_notion_assets.py` (All-or-Nothing) | exit 2 |

## exit code 規約

| code | 意味 | 呼び出し元の期待挙動 |
|---|---|---|
| 0 | publish 成功 | `notion-url.txt` を読み次工程へ |
| 1 | safe-skip (schema 差分など軽微) | warn ログ残し、人間に判断委譲 |
| 2 | hard-fail | 即停止。retry せず原因解析 |

## 不変条件 (invariants)

1. 本 skill 内で `intake.json` を **書き換えない**。読み取り専用。
2. publish 順序は必ず `render → quality_gate → publish`。pipeline 内で固定済み。
3. トークンを環境変数や CLI 引数に **載せない**。Keychain helper 経由のみ。
4. 失敗時も `notion-log.json` は書き出す (silent-fail 禁止)。

## TODO(human): 再公開拒否ルールの追加

下記に「再公開を拒否すべきケース」を 3〜5 条件で列挙してください。
書式: `- <条件> → exit <code> (<理由>)`。

例えば canonical-page-snapshot 更新後で fidelity-guard が pass していない、
manifest と intake の updated_at が逆転している、前回 publish から N 分以内、
など運用で踏みやすい事故ケースを想定してください。

<!-- TODO(human): start -->
- 
- 
- 
<!-- TODO(human): end -->
