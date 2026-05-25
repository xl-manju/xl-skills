#!/usr/bin/env python3
"""lint-script-naming.py

28章 §4.1-§4.6 のscript命名規約を機械強制する。
- 動詞リスト: lint/validate/format/render/extract/diff/guard/build
- 例外節 (§4.4): sink_*.py / *_helper.py / audit_*.py
- 例外節 (§4.6): adapters/*.py (Hexagonal Architecture adapter固有名)
- 禁止: アンダースコア(例外節を除く), check/run/main/utils/helper のみ命名

usage:
  python3 scripts/lint-script-naming.py [path...]
  python3 scripts/lint-script-naming.py --report

exit code:
  0 違反なし
  1 違反検出
  2 設定エラー

CONVENTIONS: stdlib only.
"""
import json
import pathlib
import re
import sys

ALLOWED_VERBS = {
    "lint", "validate", "format", "render",
    "extract", "diff", "guard", "build",
}
BANNED_NAMES = {"check.py", "run.py", "main.py", "utils.py", "helper.py"}

# §4.4 例外節
EXCEPTION_PATTERNS = [
    (re.compile(r"^sink_[a-z0-9]+\.py$"), "Sink Contract adapter (§4.4)"),
    (re.compile(r"^[a-z0-9]+_helper\.py$"), "secret helper (§4.4)"),
    (re.compile(r"^audit_[a-z0-9_]+\.py$"), "audit helper (§4.4)"),
]

# 暫定例外 (Change Governance 経由でリネーム予定)
PENDING_RENAME_PATTERNS = [
    re.compile(r"^hook-[a-z0-9-]+\.py$"),
]

# 暫定例外: 個別パス (初回投入時の既存スクリプト群、33章 Change Governance 管理下)
# リネーム計画は .claude/changelog/governance-log.jsonl 参照
PENDING_RENAME_PATHS = {
    "scripts/detect-repeated-rubric-violations.py",
    "scripts/inventory-skill-references.py",
    "scripts/skill-fixture-runner.py",
    "scripts/re-evaluate-on-rubric-bump.py",
    "scripts/gate-phase0.py",
    "plugins/skill-governance-lint/scripts/check-rubric-sync.py",
    "plugins/skill-governance-automation/scripts/cross_platform_secret.py",
    "plugins/skill-governance-automation/scripts/rollback-to-stable.py",
    "plugins/skill-governance-automation/scripts/compute-rubric-hash.py",
    "plugins/skill-governance-automation/scripts/doc-to-skill-adapter.py",
    "plugins/skill-governance-automation/scripts/compose-rubrics.py",
    "plugins/skill-governance-automation/scripts/notify-if-governance-trigger.py",
    "plugins/skill-governance-automation/scripts/write-eval-log.py",
    "plugins/skill-governance-automation/scripts/re-evaluate-on-rubric-bump.py",
    "plugins/skill-governance-migration/scripts/migrate/audit.py",
    "plugins/skill-governance-migration/scripts/migrate/to-brief.py",
    "plugins/skill-governance-migration/scripts/migrate/backfill-source-tier.py",
    "plugins/skill-creator/skills/wrap-git-commit-safe/scripts/pre-commit-secret-scan.py",
    "plugins/skill-creator/skills/run-skill-create/scripts/resolve-brief-to-category.py",
    "plugins/skill-creator/skills/run-build-skill/scripts/set-frontmatter-field.py",
    "scripts/phase2/gen-rollback.py",
    # skill-intake js→py migration (PR #4): keep snake_case until kebab-case rename PR
    "plugins/skill-intake/scripts/append_eval_log.py",
    "plugins/skill-intake/scripts/apply_section_template.py",
    "plugins/skill-intake/scripts/check_completeness.py",
    "plugins/skill-intake/scripts/compose_diagram.py",
    "plugins/skill-intake/scripts/convert_md_to_json.py",
    "plugins/skill-intake/scripts/create_notion_database.py",
    "plugins/skill-intake/scripts/cross_check.py",
    "plugins/skill-intake/scripts/detect_contradictions.py",
    "plugins/skill-intake/scripts/enforce_visualization_rules.py",
    "plugins/skill-intake/scripts/extract_open_questions.py",
    "plugins/skill-intake/scripts/intake_publish_pipeline.py",
    "plugins/skill-intake/scripts/keychain_get_secret.py",
    "plugins/skill-intake/scripts/measure_value_realized.py",
    "plugins/skill-intake/scripts/notion_http.py",
    "plugins/skill-intake/scripts/optimize_layout.py",
    "plugins/skill-intake/scripts/prepare_notion_assets.py",
    "plugins/skill-intake/scripts/publish_notion_page.py",
    "plugins/skill-intake/scripts/quality_gate.py",
    "plugins/skill-intake/scripts/render_notion_page.py",
    "plugins/skill-intake/scripts/render_to_image.py",
    "plugins/skill-intake/scripts/render_to_svg.py",
    "plugins/skill-intake/scripts/section_quality_check.py",
    "plugins/skill-intake/scripts/select_diagram_type.py",
    "plugins/skill-intake/scripts/select_diagrams_per_section.py",
    "plugins/skill-intake/scripts/update_question_bank.py",
    "plugins/skill-intake/scripts/validate_intake.py",
    "plugins/skill-intake/scripts/validate_mermaid.py",
    "plugins/skill-intake/scripts/verify_notion_assets.py",
    "plugins/skill-intake/scripts/verify_notion_schema.py",
    "plugins/skill-intake/scripts/ci_dogfooding_retest.py",
    "plugins/skill-intake/scripts/render_v2_adapter.py",
    "plugins/skill-intake/scripts/m3_deprecation_reverse_index.py",
    "plugins/skill-intake/scripts/dry_render_notion.py",
    "plugins/skill-intake/scripts/dogfooding_regression.py",
    "plugins/skill-intake/scripts/validate_intake_schema.py",
    # prompt-creator scaffold (PR #4): non-standard verb until renamed
    "plugins/skill-creator/skills/run-build-skill/scripts/resolve-skill-dirs.py",
    "plugins/skill-creator/skills/run-skill-create/scripts/evaluate-create-gates.py",
    "plugins/skill-creator/skills/delegate-codex-skill-review/scripts/check-codex-installed.py",
    # PR #12: skill-intake / prompt-creator / skill-creator 拡張に伴う暫定 PENDING (Change Governance で rename 予定)
    "plugins/prompt-creator/skills/run-prompt-create/scripts/evaluate-create-gates.py",
    "plugins/skill-intake/scripts/analyze_user_intent.py",
    "plugins/skill-intake/scripts/convert_v1_to_v2_context.py",
    "plugins/skill-intake/scripts/lint_subagent_seven_layer.py",
    "plugins/skill-intake/skills/run-intake-next-action/scripts/decide-mode.py",
    "plugins/skill-intake/skills/run-intake-interview/scripts/check-five-axes-coverage.py",
    "plugins/skill-intake/skills/run-intake-visualize/scripts/verify-visuals.py",
    "plugins/skill-creator/scripts/compute-dogfooding-metrics.py",
    "plugins/skill-creator/skills/run-build-skill/scripts/auto-record-lesson.py",
    "plugins/skill-creator/skills/run-elegant-review/scripts/check-review-trigger.py",
    "plugins/skill-creator/skills/wrap-git-commit-safe/scripts/preflight-git-commit.py",
    "plugins/skill-creator/skills/run-skill-rubric-governance/scripts/aggregate-evals.py",
    "plugins/skill-creator/skills/ref-task-context-map/scripts/preload-context-map.py",
    # run-skill-update-notifier (PR #8): notifier verb pending allowed-list extension
    "plugins/skill-creator/skills/run-skill-update-notifier/scripts/notifier-check.py",
    # PR #13: elegant-review v2 / plugin-package-check の新規 verb (emit/aggregate) pending rename
    "plugins/skill-creator/skills/run-elegant-review/scripts/emit-observable.py",
    "plugins/skill-creator/skills/run-plugin-package-check/scripts/aggregate-pkg-findings.py",
    # PR #15: run-build-skill knowledge-skeleton template scripts (生成後 rename)
    "plugins/skill-creator/skills/run-build-skill/templates/knowledge-skeleton/scripts/add_entry.py",
    "plugins/skill-creator/skills/run-build-skill/templates/knowledge-skeleton/scripts/build_index.py",
    "plugins/skill-creator/skills/run-build-skill/templates/knowledge-skeleton/scripts/record_usage.py",
    "plugins/skill-creator/skills/run-build-skill/templates/knowledge-skeleton/scripts/search_knowledge.py",
    # prompt-creator js→py 移行 (PR: spec-reflection): 旧 JS 名 (merge/verify/scaffold/generate/convert/log)
    # を踏襲。許可動詞へのリネームは後続 Change Governance PR で SKILL.md/agent/manifest 参照と同時実施。
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/merge-layers.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/verify-completeness.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/scaffold-prompt.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/generate-sheet.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/convert-format.py",
    "plugins/prompt-creator/skills/run-prompt-creator-7layer/scripts/log-usage.py",
    # PR #16: notion 3DB schema-as-code / skill-creator 連動 (notion-/sync- verb pending allowed-list extension)
    "scripts/notion-submit-improvement.py",
    "scripts/notion-upsert-plugin.py",
    "scripts/sync-notion-schema.py",
    # PR #16: build-trace SSOT shim (Python import がハイフン不可のため underscore 許容、§4.3 例外)
    "plugins/skill-creator/skills/run-build-skill/scripts/validate_build_trace_shim.py",
}

VALID_NAME = re.compile(r"^([a-z]+)-[a-z0-9-]+\.py$")

SCAN_ROOTS = ["scripts", "plugins"]
SKIP_PARTS = {"_lib", "__pycache__", "node_modules", ".git"}


def find_scripts(roots):
    for root in roots:
        rp = pathlib.Path(root)
        if not rp.exists():
            continue
        for p in rp.rglob("*.py"):
            if any(part in SKIP_PARTS for part in p.parts):
                continue
            if "/scripts/" in str(p) or str(p.parent).endswith("scripts"):
                yield p
            elif rp.name == "scripts":
                yield p


def classify(path: pathlib.Path):
    name = path.name
    posix = path.as_posix()
    if name in BANNED_NAMES:
        return ("VIOLATION", f"banned name: {name}")
    if path.parent.name == "adapters":
        return ("EXCEPTION", "Hexagonal adapter (§4.6)")
    for pat, reason in EXCEPTION_PATTERNS:
        if pat.match(name):
            return ("EXCEPTION", reason)
    if posix in PENDING_RENAME_PATHS:
        return ("PENDING_RENAME", "legacy path scheduled for rename (33章 Change Governance)")
    for pat in PENDING_RENAME_PATTERNS:
        if pat.match(name):
            return ("PENDING_RENAME", "hook-* prefix scheduled for rename (33章 Change Governance)")
    m = VALID_NAME.match(name)
    if not m:
        if "_" in name:
            return ("VIOLATION", "underscore not allowed (§4.3)")
        return ("VIOLATION", "does not match <verb>-<target>[-<scope>].py")
    verb = m.group(1)
    if verb not in ALLOWED_VERBS:
        return ("VIOLATION", f"verb '{verb}' not in allowed list {sorted(ALLOWED_VERBS)}")
    return ("OK", None)


def main(argv):
    report_mode = "--report" in argv
    paths = [a for a in argv[1:] if not a.startswith("--")]
    scripts = list(find_scripts(paths or SCAN_ROOTS))
    results = {"OK": [], "EXCEPTION": [], "PENDING_RENAME": [], "VIOLATION": []}
    for p in scripts:
        status, reason = classify(p)
        results[status].append({"path": str(p), "reason": reason})
    if report_mode:
        print(json.dumps({
            "summary": {k: len(v) for k, v in results.items()},
            "violations": results["VIOLATION"],
            "pending_rename": results["PENDING_RENAME"],
        }, indent=2, ensure_ascii=False))
    else:
        for item in results["VIOLATION"]:
            print(f"VIOLATION {item['path']}: {item['reason']}", file=sys.stderr)
        for item in results["PENDING_RENAME"]:
            print(f"PENDING  {item['path']}: {item['reason']}", file=sys.stderr)
        print(
            f"summary: OK={len(results['OK'])} "
            f"EXCEPTION={len(results['EXCEPTION'])} "
            f"PENDING={len(results['PENDING_RENAME'])} "
            f"VIOLATION={len(results['VIOLATION'])}"
        )
    return 1 if results["VIOLATION"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
