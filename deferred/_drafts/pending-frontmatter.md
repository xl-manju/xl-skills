# PENDING_FRONTMATTER 移行計画

28章§7 規格に従い PEP 723 inline frontmatter を全 Python script に必須化する過程の途中状態を記録する。

## 完了済み（frontmatter 完全準拠）

| script | contexts | 完了日 |
|---|---|---|
| `creator-kit/scripts/lint-script-frontmatter.py` | E, C | 2026-05-19 |
| `creator-kit/scripts/lint-rubric-violation.py` | E, C | 2026-05-19 |
| `creator-kit/scripts/compute-rubric-hash.py` | E, B | 2026-05-19 |
| `creator-kit/scripts/doc-to-skill-adapter.py` | B, E | 2026-05-19 |
| `creator-kit/scripts/notify-if-governance-trigger.py` | D | 2026-05-19 |
| `creator-kit/scripts/rollback-to-stable.py` | E, C | 2026-05-19 |
| `creator-kit/scripts/hook-*.py` (6本) | C / D | 2026-05-19 |
| `creator-kit/_bootstrap/test-self-regenerate.py` | E, B | 2026-05-19 |

## PENDING（次サイクルで補完予定）

`lint-script-frontmatter.py` の `--exemption-list` で当面 `EXCEPTION` 扱いとする。28章§4.7 の `PENDING_RENAME` ステータスと同様の扱い。

### Tier 1: scripts/直下 既存ブロックあり / キー欠落（最優先）

完全な frontmatter ブロックは存在し、`name` `purpose` `contexts` `network` `write-scope` `dependencies` までは記載済み。`inputs:` `outputs:` を追記すれば完了。

- `lint-skill-name.py`
- `lint-skill-tree.py`
- `lint-path-canonical.py`
- `lint-skill-dep-step7.py`
- `lint-dependency-direction.py`
- `validate-frontmatter.py`

### Tier 2: scripts/直下 ブロック完全欠落

```
# /// script ... # ///
```
ブロックを冒頭から追加する必要あり。

- `lint-skill-description.py`
- `lint-forbidden-deps.py`
- `lint-manifest-contents.py`
- `build-manifest-registration-plan.py`
- `check-rubric-sync.py`
- `re-evaluate-on-rubric-bump.py`
- `write-eval-log.py`

### Tier 3: サブディレクトリ（adapters/ secrets/ migrate/）

サブディレクトリの命名規則例外（28章§4.4 / §4.6）は適用済み。frontmatter は補完が必要。

- `adapters/dispatch.py`（contexts: B, E）
- `adapters/resolve_route.py`（contexts: B, E）
- `adapters/sink_local.py` / `sink_http.py` / `sink_notion.py` / `sink_sheets.py` / `sink_slack.py`（contexts: B、network: true、31章 Sink Contract 例外）
- `secrets/keychain_helper.py` / `audit_secret_leak.py`（contexts: B）
- `migrate/audit.py` / `to-brief.py` / `backfill-source-tier.py`（contexts: B, E）

### Tier 4: 命名 PENDING_RENAME

- `cross_platform_secret.py` → `scripts/secrets/cross-platform-secret.py` へ移動＋改名（28章§4.4 例外節非該当のため）

## 完了の機械判定

```bash
python3 creator-kit/scripts/lint-script-frontmatter.py creator-kit/scripts \
  | wc -l   # 0 になれば Tier 1-3 完了
```

## 段階移行スケジュール

bootstrap フェーズ（eval-log < 20 件）の間に Tier 1 → Tier 2 → Tier 3 → Tier 4 の順で補完する。governance-policy.json の `P2_content`（auto_apply）で進められる範囲。命名変更（Tier 4）は `P1_structural` のため proposal を起票する。
