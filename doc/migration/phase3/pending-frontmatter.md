# script frontmatter backlog

Phase 2 carry-over から移管。旧 `creator-kit/` パスは Phase 2 後の plugin 正本パスへ置換済み。本ファイルは Phase 2 未完了リストではなく、lint exemption 下の Phase 3 backlog である。

## 完了済み

| script | contexts | 完了日 |
|---|---|---|
| `plugins/skill-governance-lint/scripts/lint-script-frontmatter.py` | E, C | 2026-05-19 |
| `plugins/skill-governance-lint/scripts/lint-rubric-violation.py` | E, C | 2026-05-19 |
| `plugins/skill-governance-automation/scripts/compute-rubric-hash.py` | E, B | 2026-05-19 |
| `plugins/skill-governance-automation/scripts/doc-to-skill-adapter.py` | B, E | 2026-05-19 |
| `plugins/skill-governance-automation/scripts/notify-if-governance-trigger.py` | D | 2026-05-19 |
| `plugins/skill-governance-automation/scripts/rollback-to-stable.py` | E, C | 2026-05-19 |
| `plugins/skill-governance-hooks/scripts/hook-*.py` | C / D | 2026-05-19 |
| `installers/bootstrap/test-self-regenerate.py` | E, B | 2026-05-19 |

## PENDING

`plugins/skill-governance-lint/scripts/lint-script-frontmatter.py` の `--exemption-list` で当面 `EXCEPTION` 扱いとする。命名変更を伴うものは `P1_structural` として proposal を必須にする。

### Tier 1: 既存ブロックあり / キー欠落

- `plugins/skill-governance-lint/scripts/lint-skill-name.py`
- `plugins/skill-governance-lint/scripts/lint-skill-tree.py`
- `plugins/skill-governance-lint/scripts/lint-path-canonical.py`
- `plugins/skill-governance-lint/scripts/lint-skill-dep-step7.py`
- `plugins/skill-governance-lint/scripts/lint-dependency-direction.py`
- `plugins/skill-governance-lint/scripts/validate-frontmatter.py`

### Tier 2: ブロック完全欠落

- `plugins/skill-governance-lint/scripts/lint-skill-description.py`
- `plugins/skill-governance-lint/scripts/lint-forbidden-deps.py`
- `plugins/skill-governance-lint/scripts/lint-manifest-contents.py`
- `plugins/skill-governance-automation/scripts/build-manifest-registration-plan.py`
- `plugins/skill-governance-lint/scripts/check-rubric-sync.py`
- `plugins/skill-governance-automation/scripts/re-evaluate-on-rubric-bump.py`
- `plugins/skill-governance-automation/scripts/write-eval-log.py`

### Tier 3: サブディレクトリ

- `plugins/skill-governance-adapters/scripts/adapters/dispatch.py`
- `plugins/skill-governance-adapters/scripts/adapters/resolve_route.py`
- `plugins/skill-governance-adapters/scripts/adapters/sink_local.py`
- `plugins/skill-governance-adapters/scripts/adapters/sink_http.py`
- `plugins/skill-governance-adapters/scripts/adapters/sink_notion.py`
- `plugins/skill-governance-adapters/scripts/adapters/sink_sheets.py`
- `plugins/skill-governance-adapters/scripts/adapters/sink_slack.py`
- `plugins/skill-governance-secrets/scripts/secrets/keychain_helper.py`
- `plugins/skill-governance-secrets/scripts/secrets/audit_secret_leak.py`
- `plugins/skill-governance-migration/scripts/migrate/audit.py`
- `plugins/skill-governance-migration/scripts/migrate/to-brief.py`
- `plugins/skill-governance-migration/scripts/migrate/backfill-source-tier.py`

### Tier 4: 命名 PENDING_RENAME

- `plugins/skill-governance-automation/scripts/cross_platform_secret.py` -> `plugins/skill-governance-secrets/scripts/secrets/cross-platform-secret.py`

### Tier 5: Phase 2 後に検出された plugin skill 内スクリプト

- `plugins/skill-creator/skills/assign-skill-design-evaluator/scripts/render-findings-score.py`
- `plugins/skill-creator/skills/run-skill-create/scripts/resolve-brief-to-category.py`
- `plugins/skill-creator/skills/run-skill-rubric-governance/scripts/diff-rubric-impact.py`
- `plugins/skill-creator/skills/run-skill-rubric-governance/scripts/lint-rubric-violation.py`
- `plugins/skill-creator/skills/wrap-git-commit-safe/scripts/pre-commit-secret-scan.py`
- `plugins/skill-governance-automation/scripts/guard-change-category.py`

## 機械判定

```bash
python3 plugins/skill-governance-lint/scripts/lint-script-frontmatter.py plugins
```
