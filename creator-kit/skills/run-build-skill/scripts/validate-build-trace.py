#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Validate run-build-skill reproducibility trace.

Usage:
  validate-build-trace.py eval-log/skill-build-trace.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


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
}

REQUIRED_LAYERS = {"Skill", "Subagent", "Hook", "MCP", "CLI", "script"}
REQUIRED_GATES = {"lint", "evaluator", "elegant_review", "governance"}


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
                _P("creator-kit/skills/run-build-skill/references/resource-map.yaml"),
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

    if errs:
        for err in errs:
            print(err, file=sys.stderr)
        return 1

    print(f"ok: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
