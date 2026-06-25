#!/usr/bin/env python3
# /// script
# name: validate-paradigm-coverage
# purpose: Validate that elegant-review outputs cover all 30 paradigms with structured findings.
# inputs:
#   - argv: review.md or findings.json
# outputs:
#   - stdout: OK message
#   - stderr: missing paradigm or schema errors
#   - exit: 0=OK / 1=coverage failure / 2=usage error
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# dependencies: []
# ///
"""Check whether a review output covers all 30 paradigms.

Usage:
  validate-paradigm-coverage.py <review.md | findings.json>

Exit codes:
  0 -> all 30 covered with structured findings or markdown mentions
  1 -> missing paradigms detected
  2 -> usage error
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Each paradigm: id -> list of acceptance tokens (ja + en, lowercased substring match)
PARADIGMS: dict[int, list[str]] = {
    1: ["批判的思考", "critical"],
    2: ["演繹思考", "演繹", "deductive"],
    3: ["帰納的思考", "帰納", "inductive"],
    4: ["アブダクション", "abductive", "abduction"],
    5: ["垂直思考", "vertical"],
    6: ["要素分解", "decomposition"],
    7: ["mece"],
    8: ["2軸思考", "二軸思考", "two-axis", "two axis"],
    9: ["プロセス思考", "process thinking"],
    10: ["メタ思考", "meta thinking"],
    11: ["抽象化思考", "抽象化", "abstraction"],
    12: ["ダブル・ループ", "ダブルループ", "double-loop", "double loop"],
    13: ["ブレインストーミング", "ブレスト", "brainstorm"],
    14: ["水平思考", "lateral"],
    15: ["逆説思考", "paradox"],
    16: ["類推思考", "類推", "analogy"],
    17: ["if思考", "what-if", "what if"],
    18: ["素人思考", "beginner"],
    19: ["システム思考", "systems thinking", "system thinking"],
    20: ["因果関係分析", "causal analysis"],
    21: ["因果ループ", "causal loop"],
    22: ["トレードオン", "trade-on", "trade on"],
    23: ["プラスサム", "positive-sum", "positive sum"],
    24: ["価値提案思考", "価値提案", "value proposition"],
    25: ["戦略的思考", "strategic"],
    26: ["why思考", "why thinking"],
    27: ["改善思考", "improvement"],
    28: ["仮説思考", "hypothesis"],
    29: ["論点思考", "issue thinking"],
    30: ["kj法", "kj method"],
}

EXPECTED_META: dict[int, tuple[str, str, str]] = {
    1: ("critical", "A-logical", "elegant-logical-structural-analyst"),
    2: ("deduction", "A-logical", "elegant-logical-structural-analyst"),
    3: ("induction", "A-logical", "elegant-logical-structural-analyst"),
    4: ("abduction", "A-logical", "elegant-logical-structural-analyst"),
    5: ("vertical", "A-logical", "elegant-logical-structural-analyst"),
    6: ("decomposition", "B-structural", "elegant-logical-structural-analyst"),
    7: ("mece", "B-structural", "elegant-logical-structural-analyst"),
    8: ("two-axis", "B-structural", "elegant-logical-structural-analyst"),
    9: ("process", "B-structural", "elegant-logical-structural-analyst"),
    10: ("meta", "C-meta", "elegant-meta-divergent-analyst"),
    11: ("abstraction", "C-meta", "elegant-meta-divergent-analyst"),
    12: ("double-loop", "C-meta", "elegant-meta-divergent-analyst"),
    13: ("brainstorming", "D-divergent", "elegant-meta-divergent-analyst"),
    14: ("lateral", "D-divergent", "elegant-meta-divergent-analyst"),
    15: ("paradox", "D-divergent", "elegant-meta-divergent-analyst"),
    16: ("analogy", "D-divergent", "elegant-meta-divergent-analyst"),
    17: ("if", "D-divergent", "elegant-meta-divergent-analyst"),
    18: ("naive", "D-divergent", "elegant-meta-divergent-analyst"),
    19: ("systems", "E-system", "elegant-system-strategic-analyst"),
    20: ("causal", "E-system", "elegant-system-strategic-analyst"),
    21: ("causal-loop", "E-system", "elegant-system-strategic-analyst"),
    22: ("trade-on", "F-strategic", "elegant-system-strategic-analyst"),
    23: ("plus-sum", "F-strategic", "elegant-system-strategic-analyst"),
    24: ("value-proposition", "F-strategic", "elegant-system-strategic-analyst"),
    25: ("strategic", "F-strategic", "elegant-system-strategic-analyst"),
    26: ("why", "A-logical", "elegant-logical-structural-analyst"),
    27: ("kaizen", "G-problem", "elegant-system-strategic-analyst"),
    28: ("hypothesis", "G-problem", "elegant-system-strategic-analyst"),
    29: ("issue", "G-problem", "elegant-system-strategic-analyst"),
    30: ("kj", "G-problem", "elegant-system-strategic-analyst"),
}


def validate_structured_json(path: Path) -> tuple[bool, list[str]]:
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False, ["invalid json"]
    findings = data.get("paradigm_findings")
    if not isinstance(findings, list):
        return False, ["missing paradigm_findings"]

    by_id: dict[int, dict] = {}
    errors: list[str] = []
    for idx, item in enumerate(findings):
        if not isinstance(item, dict):
            errors.append(f"paradigm_findings[{idx}] is not an object")
            continue
        pid = item.get("paradigm_id")
        if not isinstance(pid, int):
            errors.append(f"paradigm_findings[{idx}].paradigm_id is not int")
            continue
        by_id[pid] = item

    coverage = data.get("thought_method_coverage")
    skipped_by_method: dict[str, str] = {}
    used_methods: set[str] = set()
    if coverage is None:
        errors.append("missing thought_method_coverage")
    elif not isinstance(coverage, dict):
        errors.append("thought_method_coverage must be an object")
    else:
        if coverage.get("total") != 30:
            errors.append("thought_method_coverage.total must be 30")
        used = coverage.get("used", [])
        if not isinstance(used, list):
            errors.append("thought_method_coverage.used must be a list")
        else:
            used_methods = {str(item).strip() for item in used if str(item).strip()}
        skipped = coverage.get("skipped_with_reason", [])
        if not isinstance(skipped, list):
            errors.append("thought_method_coverage.skipped_with_reason must be a list")
        else:
            for idx, item in enumerate(skipped):
                if not isinstance(item, dict):
                    errors.append(f"skipped_with_reason[{idx}] must be object")
                    continue
                method = str(item.get("method", "")).strip()
                reason = str(item.get("reason", "")).strip()
                if not method or not reason:
                    errors.append(f"skipped_with_reason[{idx}] requires method and reason")
                    continue
                skipped_by_method[method] = reason
        covered_count = len(used_methods) + len(skipped_by_method)
        if covered_count != 30:
            errors.append(
                "thought_method_coverage.used + skipped_with_reason must cover 30 distinct methods"
            )
        overlap = used_methods & set(skipped_by_method)
        if overlap:
            errors.append(f"thought_method_coverage used/skipped overlap: {sorted(overlap)}")

    missing = []
    for pid in PARADIGMS:
        expected_name = EXPECTED_META[pid][0]
        if pid not in by_id and expected_name not in skipped_by_method:
            missing.append(pid)
        if pid in by_id and coverage is not None and expected_name not in used_methods:
            errors.append(f"paradigm {pid}: finding exists but method missing from coverage.used")
    if missing:
        errors.append(f"missing paradigm_findings ids without skip_reason: {missing}")

    valid_conditions = {"C1", "C2", "C3", "C4"}
    valid_severities = {"critical", "high", "medium", "low"}
    for pid in sorted(set(PARADIGMS) & set(by_id)):
        item = by_id[pid]
        expected_name, expected_category, expected_agent = EXPECTED_META[pid]
        if item.get("paradigm_name") != expected_name:
            errors.append(f"paradigm {pid}: expected paradigm_name={expected_name}")
        if item.get("category") != expected_category:
            errors.append(f"paradigm {pid}: expected category={expected_category}")
        if item.get("agent") != expected_agent:
            errors.append(f"paradigm {pid}: expected agent={expected_agent}")
        observations = item.get("observations")
        issues = item.get("issues")
        if not isinstance(observations, list) or not any(str(x).strip() for x in observations):
            errors.append(f"paradigm {pid}: observations must contain non-empty text")
        if not isinstance(issues, list):
            errors.append(f"paradigm {pid}: issues must be a list")
            continue
        for i, issue in enumerate(issues):
            if not isinstance(issue, dict):
                errors.append(f"paradigm {pid} issue {i}: not an object")
                continue
            if issue.get("condition") not in valid_conditions:
                errors.append(f"paradigm {pid} issue {i}: invalid condition")
            if issue.get("severity") not in valid_severities:
                errors.append(f"paradigm {pid} issue {i}: invalid severity")
            signal = issue.get("condition_signal")
            valid_signals = {"contradiction", "omission", "inconsistency", "dependency_break", "smell"}
            if signal is not None and signal not in valid_signals:
                errors.append(f"paradigm {pid} issue {i}: invalid condition_signal")
            if not str(issue.get("description", "")).strip():
                errors.append(f"paradigm {pid} issue {i}: missing description")
            if not str(issue.get("recommended_intervention", "")).strip():
                errors.append(f"paradigm {pid} issue {i}: missing recommended_intervention")

    variable_abstraction = data.get("variable_abstraction")
    if not isinstance(variable_abstraction, list):
        errors.append("variable_abstraction must be a list")
    for idx, var in enumerate(variable_abstraction or []):
        if not isinstance(var, dict):
            errors.append(f"variable_abstraction[{idx}] must be object")
            continue
        for key in ("concrete_value", "variable_name", "source_trace"):
            if key not in var:
                errors.append(f"variable_abstraction[{idx}] missing {key}")
        if not str(var.get("variable_name", "")).startswith("{{"):
            errors.append(f"variable_abstraction[{idx}].variable_name must be template variable")

    return not errors, errors


def extract_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: validate-paradigm-coverage.py <file>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if path.suffix == ".json":
        ok, errors = validate_structured_json(path)
        if not ok:
            for err in errors:
                print(err, file=sys.stderr)
            return 1
        print("OK: all 30 paradigms covered with structured findings")
        return 0

    text = extract_text(path)
    missing = []
    for pid, tokens in PARADIGMS.items():
        if not any(tok.lower() in text for tok in tokens):
            missing.append(pid)
    if missing:
        print(f"MISSING paradigms ({len(missing)}/30): {missing}", file=sys.stderr)
        return 1
    print("OK: all 30 paradigms covered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
