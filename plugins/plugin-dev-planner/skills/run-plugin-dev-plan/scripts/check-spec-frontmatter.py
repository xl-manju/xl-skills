#!/usr/bin/env python3
# /// script
# name: check-spec-frontmatter
# purpose: 各タスク仕様書 frontmatter が component_kind を宣言し、その kind 別の構造契約(skill偏重を解消)と core 規律(quality_gates/harness_coverage/feedback criteria)を携帯しているかを検証する決定論ゲート。
# inputs:
#   - argv: <spec.md ...> | --specs-dir DIR
# outputs:
#   - stdout: OK サマリ
#   - stderr: component_kind / 構造キー / criteria / harness violation
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""タスク仕様書 frontmatter を component_kind 別に検証する。

判定 (run-plugin-dev-plan の C2/C3 / PART1 skill偏重解消):
  - `component_kind` ∈ {skill,sub-agent,slash-command,hook,script} を宣言 (必須)
  - component_kind 別の構造的必須キー (specfm.STRUCTURAL_REQUIRED)。skill 以外に
    skill-brief 形状を強制しない
  - core 規律 (全 buildable): `quality_gates` / `harness_coverage` ブロックの存在
  - 条件付き: skill かつ skill kind∈{run,wrap,delegate} は feedback_contract.criteria 必須
    (skill kind∈{ref,assign} は feedback_contract.skip_reason 可)

quality_gates の中身 (p0_lint 網羅/elegant_review/evaluator 等) と harness 数値は
check-spec-gates.py が深掘り検証する (本 lint は構造と criteria を担う)。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402


def check_spec(text: str) -> list[str]:
    """タスク仕様書 1 件の frontmatter を検査し errors を返す。"""
    if specfm.split_frontmatter(text) is None:
        return ["frontmatter (--- ブロック) が無い"]
    fm = specfm.parse_frontmatter(text)
    errs: list[str] = []

    ck = str(fm.get("component_kind", "")).strip()
    if not ck:
        return ["component_kind が未宣言 (skill/sub-agent/slash-command/hook/script のいずれか)"]
    if ck not in specfm.COMPONENT_KINDS:
        return [f"component_kind={ck!r} が enum 外 {list(specfm.COMPONENT_KINDS)}"]

    # 1. component_kind 別の構造的必須キー
    #    presence-only フィールド (実 schema で minItems 無し) は空配列/false も存在として許容。
    for field in specfm.STRUCTURAL_REQUIRED[ck]:
        if field in getattr(specfm, "SKILL_BRIEF_PRESENCE_ONLY", frozenset()):
            if field not in fm or fm[field] is None:
                errs.append(f"[{ck}] 構造的必須フィールド欠落: {field}")
        elif field not in fm or fm[field] in (None, "", []):
            errs.append(f"[{ck}] 構造的必須フィールド欠落: {field}")

    # 2. core 規律 (全 buildable): quality_gates / harness_coverage ブロックの存在
    if not isinstance(fm.get("quality_gates"), dict):
        errs.append(f"[{ck}] quality_gates ブロックが無い (全 buildable spec の core 規律)")
    if not isinstance(fm.get("harness_coverage"), dict):
        errs.append(f"[{ck}] harness_coverage ブロックが無い (min/kind_pass を持つこと)")

    # 3. 条件付き: skill kind∈{run,wrap,delegate} は feedback_contract.criteria 必須
    if ck == "skill":
        skill_kind = str(fm.get("kind", "")).strip()
        if skill_kind not in specfm.SKILL_KINDS:
            errs.append(f"[skill] kind={skill_kind!r} が skill kind enum 外 {list(specfm.SKILL_KINDS)}")
        # skill-brief.schema allOf の条件付き required (prefix/kind 依存)
        for field in specfm.skill_conditional_required(skill_kind):
            if field not in fm or fm[field] in (None, "", []):
                errs.append(f"[skill] kind={skill_kind} の条件付き必須フィールド欠落: {field}")
        fc = fm.get("feedback_contract")
        if skill_kind in specfm.FEEDBACK_LOOP_SKILL_KINDS:
            if not isinstance(fc, dict):
                errs.append("[skill] loop kind は feedback_contract.criteria 必須")
            else:
                errs.extend(specfm.validate_criteria(fc.get("criteria")))
                # 成果物評価の operationalize: criteria が当該 spec の goal/checklist 由来か
                # (汎用品質ゲートの言い換えへ退化していないか) を機械検証する (R3 §2.2)。
                errs.extend(specfm.criteria_purpose_traceability_errors(
                    fc.get("criteria"), goal=fm.get("goal"), checklist=fm.get("checklist")))
        else:
            # ref/assign: criteria か skip_reason のいずれか
            if isinstance(fc, dict) and not fc.get("skip_reason") and not fc.get("criteria"):
                errs.append("[skill] ref/assign は feedback_contract.skip_reason か criteria のいずれかが必要")
    return errs


def collect_specs(specs_dir: Path) -> list[Path]:
    return [p for p in sorted(specs_dir.glob("*.md")) if p.stem not in {"index", "main"}]


def run(paths: list[Path]) -> tuple[int, list[str]]:
    errors: list[str] = []
    for p in paths:
        for e in check_spec(p.read_text(encoding="utf-8")):
            errors.append(f"{p.name}: {e}")
    return (1 if errors else 0), errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="タスク仕様書 frontmatter を component_kind 別に検証する")
    ap.add_argument("specs", nargs="*", help="タスク仕様書 .md")
    ap.add_argument("--specs-dir", default=None, help="タスク仕様書ディレクトリ")
    args = ap.parse_args(argv)

    paths: list[Path] = [Path(s) for s in args.specs]
    if args.specs_dir:
        d = Path(args.specs_dir)
        if not d.is_dir():
            sys.stderr.write(f"not a directory: {d}\n")
            return 2
        paths.extend(collect_specs(d))
    if not paths:
        sys.stderr.write("usage: check-spec-frontmatter.py <spec.md ...> | --specs-dir DIR\n")
        return 2
    missing = [p for p in paths if not p.is_file()]
    if missing:
        for p in missing:
            sys.stderr.write(f"not found: {p}\n")
        return 2
    code, errors = run(paths)
    if code == 0:
        sys.stdout.write(f"OK: {len(paths)} 仕様書が component_kind 別契約 + core 規律を携帯\n")
        return 0
    for e in errors:
        sys.stderr.write(e + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
