#!/usr/bin/env python3
# /// script
# name: validate-build-trace
# purpose: Validate run-build-skill reproducibility trace including 26/27/28 meta gates.
# inputs:
#   - argv: eval-log/skill-build-trace.json
# outputs:
#   - stdout: ok message
#   - stderr: validation errors
#   - exit: 0=OK / 1=validation failure / 2=usage or JSON error
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
"""Validate run-build-skill reproducibility trace.

Usage:
  validate-build-trace.py eval-log/skill-build-trace.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


LAYER_YAML_PATH_PATTERNS = {
    "skill-local-v1": re.compile(
        r"^plugins/[a-z][a-z0-9-]*/skills/(ref|run|wrap|assign|delegate)-"
        r"[a-z0-9]+(-[a-z0-9]+)*/prompts/R[0-9]+\.yaml$"
    ),
    "agents-legacy": re.compile(
        r"^plugins/[a-z][a-z0-9-]*/agents/prompts/[a-z][a-z0-9-]*\.yaml$"
    ),
}
RESPONSIBILITY_ID_RE = re.compile(r"^R[0-9]+$")
PROMPT_REQUIRED_KINDS = {"run", "assign"}
PROMPT_OPTIONAL_KINDS = {"ref", "wrap"}
PROMPT_SKIP_KINDS = {"delegate"}


REQUIRED_BUILD_STEPS = {
    "problem-definition",
    "execution-layer",
    "classification",
    "naming",
    "frontmatter",
    "body",
    "support-files",
    "permissions-hooks",
    "validation",
    "operation-improvement",
}

REQUIRED_DOC_COVERAGE = {
    "02-skill-structure",
    "03-frontmatter",
    "04-invocation-permissions",
    "05-layering",
    "06-classification-naming",
    "07-progressive-disclosure",
    "08-skill-writing-guidelines",
    "09-evaluation-orchestration",
    "10-subagents-hooks-integration",
    "11-templates",
    "13-checklists",
    "14-dynamic-context-injection",
    "15-official-source-notes",
    "16-official-skills-reference",
    "26-meta-skill-dogfooding",
    "27-rubric-governance-runbook",
    "28-script-execution-model",
    "29-multi-project-rubric-composition",
    "30-paradigm-analogy-map",
    "31-output-routing-adapter-architecture",
    "32-creator-kit-implementation-ledger",
    "33-change-governance",
    "34-plugin-governance-roadmap",
    "35-meta-harness-feedback-loop",
}

REQUIRED_LAYERS = {"Skill", "Subagent", "Hook", "MCP", "CLI", "script"}
REQUIRED_GATES = {"lint", "evaluator", "elegant_review", "governance"}
REQUIRED_SCRIPT_CONTEXTS = {"A", "B", "C", "D", "E"}
REQUIRED_GOVERNANCE_ROLES = {"proposer", "reviewer", "approver", "tooling"}


def _as_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value}


def _items_by_key(value: object, key: str) -> dict[str, dict]:
    if not isinstance(value, list):
        return {}
    out = {}
    for item in value:
        if isinstance(item, dict) and item.get(key):
            out[str(item[key])] = item
    return out


def _status_ok(item: dict) -> bool:
    status = str(item.get("status", "")).upper()
    evidence = str(item.get("evidence", "")).strip()
    reason = str(item.get("reason", "")).strip()
    if status in {"PASS", "FAIL"}:
        return bool(evidence)
    if status == "N/A":
        return bool(reason or evidence)
    return False


def _completion_status_ok(item: dict) -> bool:
    status = str(item.get("status", "")).upper()
    return status in {"PASS", "N/A"} and _status_ok(item)


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _non_empty_list(value: object) -> bool:
    return isinstance(value, list) and bool(value)


def _resolve_brief_kind(data: dict) -> str | None:
    variant = data.get("variant_support")
    if isinstance(variant, dict):
        prefix = str(variant.get("prefix", "")).strip().lower()
        if prefix:
            return prefix
    return None


def _validate_prompt_generation_model(data: dict) -> list[str]:
    """Validate trace.prompt_generation_model against reproducibility-trace-schema.md.

    Enforces rules 1-6 from the schema: policy resolution, regex path match,
    id↔filename consistency, anchor_coverage emptiness, and required-policy
    lint PASS gating. Kind-based optionality follows agent-template.md table.
    """
    errs: list[str] = []
    model = data.get("prompt_generation_model")
    kind = _resolve_brief_kind(data)

    if not isinstance(model, dict):
        if kind in PROMPT_REQUIRED_KINDS:
            errs.append(
                f"prompt_generation_model is required when brief.kind={kind!r} "
                f"(run/assign). Schema: reproducibility-trace-schema.md"
            )
        return errs

    policy = model.get("policy_resolution")
    if not isinstance(policy, dict):
        errs.append("prompt_generation_model.policy_resolution missing")
        resolved = None
    else:
        resolved = str(policy.get("resolved_policy", "")).strip().lower()
        if resolved not in {"required", "optional", "skip"}:
            errs.append(
                f"policy_resolution.resolved_policy invalid: {resolved!r} "
                "(expected required/optional/skip)"
            )
        if not str(policy.get("resolved_via", "")).strip():
            errs.append("policy_resolution.resolved_via must explain derivation")
        if kind in PROMPT_REQUIRED_KINDS and resolved == "skip":
            errs.append(
                f"resolved_policy=skip contradicts brief.kind={kind!r} "
                "(run/assign require prompt generation)"
            )
        if kind in PROMPT_SKIP_KINDS and resolved == "required":
            errs.append(
                f"resolved_policy=required contradicts brief.kind={kind!r} "
                "(delegate skips prompt-creator)"
            )

    per_resp = model.get("per_responsibility")
    if not isinstance(per_resp, list):
        errs.append("prompt_generation_model.per_responsibility must be array")
        per_resp = []

    if resolved == "required" and not per_resp:
        errs.append(
            "per_responsibility must not be empty when resolved_policy=required"
        )
    if resolved == "skip" and per_resp:
        errs.append(
            "per_responsibility must be empty when resolved_policy=skip "
            "(or escalate via policy_resolution.resolved_via)"
        )

    seen_ids: set[str] = set()
    for idx, item in enumerate(per_resp):
        if not isinstance(item, dict):
            errs.append(f"per_responsibility[{idx}] must be object")
            continue
        rid = str(item.get("id", "")).strip()
        if not RESPONSIBILITY_ID_RE.match(rid):
            errs.append(
                f"per_responsibility[{idx}].id={rid!r} must match ^R[0-9]+$"
            )
        if rid in seen_ids:
            errs.append(f"per_responsibility[{idx}].id={rid!r} duplicated")
        seen_ids.add(rid)

        convention = str(item.get("path_convention", "")).strip()
        pattern = LAYER_YAML_PATH_PATTERNS.get(convention)
        layer_path = str(item.get("layer_yaml_path", "")).strip()
        if pattern is None:
            errs.append(
                f"per_responsibility[{idx}].path_convention invalid: "
                f"{convention!r} (expected skill-local-v1 or agents-legacy)"
            )
        elif not pattern.match(layer_path):
            errs.append(
                f"per_responsibility[{idx}].layer_yaml_path={layer_path!r} "
                f"does not match {convention} regex"
            )
        elif convention == "skill-local-v1" and rid:
            stem = Path(layer_path).stem
            if stem != rid:
                errs.append(
                    f"per_responsibility[{idx}] filename {stem!r} != id {rid!r}"
                )

        if resolved == "required":
            lint_status = str(item.get("lint_status", "")).upper()
            if lint_status != "PASS":
                escalation = str(item.get("escalation", "")).strip().lower()
                if not escalation or escalation == "none":
                    errs.append(
                        f"per_responsibility[{idx}] lint_status={lint_status!r} "
                        "requires escalation != none when policy=required"
                    )

    anchor = model.get("anchor_coverage")
    if isinstance(anchor, dict):
        missing = anchor.get("missing_anchors")
        if isinstance(missing, list) and missing:
            errs.append(
                f"anchor_coverage.missing_anchors must be empty: {missing}"
            )
    elif resolved == "required":
        errs.append("anchor_coverage required when resolved_policy=required")

    cross_ref = model.get("cross_ref")
    if isinstance(cross_ref, dict):
        if cross_ref.get("join_key") != "responsibility.id":
            errs.append(
                "cross_ref.join_key must be 'responsibility.id' "
                "(reproducibility-trace-schema.md)"
            )
        if resolved == "required" and not cross_ref.get("prompt_creator_trace_path"):
            errs.append(
                "cross_ref.prompt_creator_trace_path required when policy=required"
            )

    return errs


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate-build-trace.py eval-log/skill-build-trace.json", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    # A-3 強制化: ファイル未存在 or 空は FAIL (exit 1) として扱う
    # run-build-skill Step 3.5 開始前に必ずトレースを記録することを強制する。
    if not path.exists():
        print(f"FAIL: skill-build-trace.json not found: {path}", file=sys.stderr)
        print("run-build-skill Step 3.5 を開始する前に skill-build-trace.json を作成してください。", file=sys.stderr)
        return 1
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        print(f"FAIL: skill-build-trace.json is empty: {path}", file=sys.stderr)
        print("空ファイルは無効です。run-build-skill Step 3.5 の記録内容を投入してください。", file=sys.stderr)
        return 1

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"invalid json: {exc}", file=sys.stderr)
        return 2

    errs: list[str] = []

    source_docs = _as_set(data.get("source_docs"))
    if not source_docs:
        errs.append("source_docs must list the docs actually read")
    context_map = data.get("context_map_decision")
    if not isinstance(context_map, dict):
        errs.append("missing context_map_decision")
    else:
        for key in ("map", "task_category", "selected_docs"):
            if not context_map.get(key):
                errs.append(f"context_map_decision.{key} is empty")
        selected_docs = _as_set(context_map.get("selected_docs"))
        if selected_docs and source_docs and not source_docs.issubset(selected_docs):
            errs.append("source_docs must be a subset of context_map_decision.selected_docs")

    design = data.get("design_model")
    if not isinstance(design, dict):
        errs.append("missing design_model")
    else:
        for key in ("intent", "contract", "boundary", "execution", "feedback"):
            if not design.get(key):
                errs.append(f"design_model.{key} is empty")

    build_steps = _items_by_key(data.get("build_flow_coverage"), "step")
    missing_steps = REQUIRED_BUILD_STEPS - set(build_steps)
    if missing_steps:
        errs.append(f"missing build_flow_coverage steps: {sorted(missing_steps)}")
    for step, item in build_steps.items():
        if step in REQUIRED_BUILD_STEPS and not _completion_status_ok(item):
            errs.append(f"invalid build_flow_coverage item: {step}")

    doc_coverage = _items_by_key(data.get("doc_coverage"), "doc")
    missing_coverage = REQUIRED_DOC_COVERAGE - set(doc_coverage)
    if missing_coverage:
        errs.append(f"missing doc_coverage items: {sorted(missing_coverage)}")
    for doc, item in doc_coverage.items():
        if doc in REQUIRED_DOC_COVERAGE and not _completion_status_ok(item):
            errs.append(f"invalid doc_coverage item: {doc}")

    layer_items = _items_by_key(data.get("layer_decisions"), "layer")
    missing_layers = REQUIRED_LAYERS - set(layer_items)
    if missing_layers:
        errs.append(f"missing layer_decisions: {sorted(missing_layers)}")
    for layer, item in layer_items.items():
        if layer not in REQUIRED_LAYERS:
            continue
        decision = str(item.get("decision", "")).lower()
        if decision not in {"use", "skip"}:
            errs.append(f"layer_decisions.{layer} invalid decision")
        for key in ("reason", "placement_evidence", "fallback"):
            if not str(item.get(key, "")).strip():
                errs.append(f"layer_decisions.{layer} missing {key}")
        for key in ("dependency_direction_ok", "macos_stdlib_ok"):
            if not isinstance(item.get(key), bool):
                errs.append(f"layer_decisions.{layer}.{key} must be boolean")
        if item.get("deterministic") not in {True, False}:
            errs.append(f"layer_decisions.{layer}.deterministic must be boolean")

    variant = data.get("variant_support")
    if not isinstance(variant, dict):
        errs.append("missing variant_support")
    else:
        for key in ("prefix", "role_suffix", "subagent", "hook"):
            if not variant.get(key):
                errs.append(f"variant_support.{key} is empty")
        # 強化 (M3): variant_support.prefix が現行 kind 列挙と整合するか検証
        # （`atomic` などの旧仕様値が trace に紛れ込まないようガード）
        valid_prefixes = {"ref", "run", "wrap", "assign", "delegate"}
        prefix_val = str(variant.get("prefix", "")).strip().lower()
        if prefix_val and prefix_val not in valid_prefixes:
            errs.append(
                f"variant_support.prefix={prefix_val!r} not in {sorted(valid_prefixes)} "
                "(atomic は旧仕様。19章 factory 障害 #6 参照)"
            )
        # variant_support.prefix と生成スキル frontmatter の kind が一致するかクロスチェック
        skill_path = data.get("skill_path") or data.get("target_skill_path")
        if skill_path:
            from pathlib import Path as _P
            skill_md = _P(skill_path) / "SKILL.md"
            if skill_md.exists():
                text = skill_md.read_text(encoding="utf-8")
                # frontmatter 内の kind 行を最小パースで抽出
                for line in text.splitlines():
                    s = line.strip()
                    if s.startswith("kind:"):
                        kind_val = s.split(":", 1)[1].strip().split("#", 1)[0].strip()
                        if prefix_val and kind_val and prefix_val != kind_val:
                            errs.append(
                                f"variant_support.prefix={prefix_val!r} != frontmatter.kind={kind_val!r} in {skill_md}"
                            )
                        break

    # 強化 (M3): context_map_decision.category が resource-map.yaml に列挙された
    # category のいずれかに一致するか検証
    context_decision = data.get("context_map_decision")
    if isinstance(context_decision, dict):
        cats = context_decision.get("category")
        if cats:
            # resource-map.yaml を探索（trace 隣接か run-build-skill 直下）
            from pathlib import Path as _P
            candidate_maps = [
                _P("plugins/skill-creator/skills/run-build-skill/references/resource-map.yaml"),
                _P(".claude/skills/run-build-skill/references/resource-map.yaml"),
            ]
            known_cats: set[str] = set()
            for cm in candidate_maps:
                if cm.exists():
                    try:
                        for ln in cm.read_text(encoding="utf-8").splitlines():
                            stripped = ln.strip()
                            if stripped.startswith("- category:"):
                                known_cats.add(stripped.split(":", 1)[1].strip().strip('"'))
                    except OSError:
                        pass
                    break
            if known_cats:
                cat_list = cats if isinstance(cats, list) else [cats]
                for c in cat_list:
                    if c not in known_cats:
                        errs.append(
                            f"context_map_decision.category={c!r} not in resource-map.yaml "
                            f"({sorted(known_cats)})"
                        )

    patterns = data.get("pattern_decisions")
    if not isinstance(patterns, list) or not patterns:
        errs.append("missing pattern_decisions")
    else:
        for idx, item in enumerate(patterns):
            if not isinstance(item, dict):
                errs.append(f"pattern_decisions[{idx}] must be object")
                continue
            decision = str(item.get("decision", "")).lower()
            if decision not in {"use", "skip"}:
                errs.append(f"pattern_decisions[{idx}].decision invalid")
            for key in ("pattern_ref", "reason", "reuse_target"):
                if not str(item.get(key, "")).strip():
                    errs.append(f"pattern_decisions[{idx}].{key} is empty")

    gates = data.get("reproducibility_gates")
    if not isinstance(gates, dict):
        errs.append("missing reproducibility_gates")
    else:
        missing_gates = REQUIRED_GATES - set(gates)
        if missing_gates:
            errs.append(f"missing reproducibility_gates: {sorted(missing_gates)}")
        for gate in REQUIRED_GATES & set(gates):
            status = str(gates.get(gate, "")).upper()
            if status not in {"PASS", "N/A"}:
                errs.append(f"invalid gate status: {gate}={gates.get(gate)}")

    script_model = data.get("script_execution_model")
    if not isinstance(script_model, dict):
        errs.append("missing script_execution_model")
    else:
        contexts = _as_set(script_model.get("contexts"))
        if missing_contexts := REQUIRED_SCRIPT_CONTEXTS - contexts:
            errs.append(f"script_execution_model.contexts missing: {sorted(missing_contexts)}")
        for key in ("responsibility_matrix", "priority_order", "permission_boundary"):
            if not _non_empty_string(script_model.get(key)):
                errs.append(f"script_execution_model.{key} is empty")
        scripts = script_model.get("scripts")
        if not isinstance(scripts, list) or not scripts:
            errs.append("script_execution_model.scripts must list generated/used scripts")
        else:
            for idx, item in enumerate(scripts):
                if not isinstance(item, dict):
                    errs.append(f"script_execution_model.scripts[{idx}] must be object")
                    continue
                for key in ("path", "type", "allowed_contexts", "frontmatter_status"):
                    if not item.get(key):
                        errs.append(f"script_execution_model.scripts[{idx}].{key} is empty")
                allowed = _as_set(item.get("allowed_contexts"))
                unknown = allowed - REQUIRED_SCRIPT_CONTEXTS
                if unknown:
                    errs.append(f"script_execution_model.scripts[{idx}].allowed_contexts unknown: {sorted(unknown)}")

    governance = data.get("governance_model")
    if not isinstance(governance, dict):
        errs.append("missing governance_model")
    else:
        for key in ("rubric_version", "rubric_hash", "proposal_required", "impact_assessment"):
            if not str(governance.get(key, "")).strip():
                errs.append(f"governance_model.{key} is empty")
        roles = governance.get("roles")
        if not isinstance(roles, dict):
            errs.append("governance_model.roles is missing")
        else:
            missing_roles = REQUIRED_GOVERNANCE_ROLES - set(roles)
            if missing_roles:
                errs.append(f"governance_model.roles missing: {sorted(missing_roles)}")
        if "newly_failing_count" in governance and not isinstance(governance.get("newly_failing_count"), int):
            errs.append("governance_model.newly_failing_count must be integer when present")

    dogfooding = data.get("dogfooding_model")
    if not isinstance(dogfooding, dict):
        errs.append("missing dogfooding_model")
    else:
        for key in ("artifact_type", "adapter", "forked_evaluator", "eval_log_path"):
            if not _non_empty_string(dogfooding.get(key)):
                errs.append(f"dogfooding_model.{key} is empty")
        if not _non_empty_list(dogfooding.get("recursive_checks")):
            errs.append("dogfooding_model.recursive_checks must list rubric checks")

    optional_models = {
        "rubric_composition_model": ("ordered_refs", "merge_strategy", "conflict_policy", "composition_hash_evidence"),
        "paradigm_analogy_model": ("primary_analogy", "matched_skill_concept", "limits", "placement_decision"),
        "output_routing_model": ("task_kind", "payload_schema_version", "route_ref", "adapter_registry_ref", "fallback", "secret_boundary"),
    }
    for model_name, keys in optional_models.items():
        model = data.get(model_name)
        if not isinstance(model, dict):
            errs.append(f"missing {model_name}")
            continue
        status = str(model.get("status", "")).upper()
        if status == "N/A":
            if not str(model.get("reason", "")).strip():
                errs.append(f"{model_name}.reason is required when N/A")
            continue
        if status != "PASS":
            errs.append(f"{model_name}.status must be PASS or N/A")
        for key in keys:
            if not model.get(key):
                errs.append(f"{model_name}.{key} is empty")

    errs.extend(_validate_prompt_generation_model(data))

    variable_contract = data.get("variable_contract")
    if not isinstance(variable_contract, list) or not variable_contract:
        errs.append("variable_contract must list template variables or N/A rationale item")
    else:
        for idx, item in enumerate(variable_contract):
            if not isinstance(item, dict):
                errs.append(f"variable_contract[{idx}] must be object")
                continue
            for key in ("name", "meaning", "default", "required", "not_applicable_when", "source_trace"):
                if key not in item or item.get(key) in ("", None):
                    errs.append(f"variable_contract[{idx}].{key} is empty")

    if errs:
        for err in errs:
            print(err, file=sys.stderr)
        return 1

    print(f"ok: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
