#!/usr/bin/env python3
# /// script
# name: check-build-handoff
# purpose: handoff-run-plugin-dev-plan.json が plan(L3) から build(L4) への実行可能ルーティング契約を満たすか検証する。
# inputs:
#   - argv: <handoff-json>
# outputs:
#   - stdout: OK summary
#   - stderr: schema/routing/top-sort/envelope violation
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""build handoff 契約を検証する。

run-plugin-dev-plan 自体は L4 実 build を行わない。代わりに、後段 build skill が
迷わず消費できる routing artifact を出すことをこの gate で保証する。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

ALLOWED_BUILDERS = {
    "run-skill-create",
    "run-build-skill",
    "parent-skill-build",
    "plugin-scaffold",
    "manual-user-gated",
}
EXPECTED_BUILDER = {
    "skill": "run-skill-create",
    "sub-agent": "run-build-skill",
    "slash-command": "run-build-skill",
    "hook": "run-build-skill",
    "script": "parent-skill-build",
}
EXPECTED_BUILD_KIND = {
    "skill": "skill",
    "sub-agent": "agent",
    "slash-command": "command",
    "hook": "hook",
    "script": "script",
}
ENVELOPE_STATUSES = {"planned", "external_gap", "manual-user-gated", "not_applicable"}
TODO_RE = ("TODO", "TBD", "<TODO", "{{")


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse error: {exc}") from exc


def _require_str(obj: dict, key: str, errors: list[str], prefix: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{prefix}.{key} が非空 string でない")
        return ""
    return value.strip()


def _route_errors(route: dict, idx: int, ids: set[str], plan_dir: Path) -> list[str]:
    prefix = f"routes[{idx}]"
    errors: list[str] = []
    rid = _require_str(route, "id", errors, prefix)
    ck = _require_str(route, "component_kind", errors, prefix)
    _require_str(route, "name", errors, prefix)
    spec_rel = _require_str(route, "spec", errors, prefix)
    builder = _require_str(route, "builder", errors, prefix)
    build_kind = _require_str(route, "build_kind", errors, prefix)
    _require_str(route, "build_target", errors, prefix)

    if ck and ck not in specfm.COMPONENT_KINDS:
        errors.append(f"{prefix}.component_kind={ck!r} が enum 外 {list(specfm.COMPONENT_KINDS)}")
    if builder and builder not in ALLOWED_BUILDERS:
        errors.append(f"{prefix}.builder={builder!r} が enum 外 {sorted(ALLOWED_BUILDERS)}")
    if ck in EXPECTED_BUILDER and builder and builder != EXPECTED_BUILDER[ck]:
        errors.append(f"{prefix}: component_kind={ck} は builder={EXPECTED_BUILDER[ck]} を要求 (現値 {builder})")
    if ck in EXPECTED_BUILD_KIND and build_kind and build_kind != EXPECTED_BUILD_KIND[ck]:
        errors.append(f"{prefix}: component_kind={ck} は build_kind={EXPECTED_BUILD_KIND[ck]} を要求 (現値 {build_kind})")
    build_args = route.get("build_args")
    if not isinstance(build_args, dict) or not build_args:
        errors.append(f"{prefix}.build_args が非空 object でない")
    elif builder == "run-build-skill" and build_args.get("kind") != build_kind:
        errors.append(f"{prefix}.build_args.kind={build_args.get('kind')!r} が build_kind={build_kind!r} と不一致")
    elif builder == "run-skill-create" and not str(build_args.get("skill_name", "")).strip():
        errors.append(f"{prefix}.build_args.skill_name が空")
    elif builder == "parent-skill-build":
        for key in ("parent_skill", "script_path"):
            if not str(build_args.get(key, "")).strip():
                errors.append(f"{prefix}.build_args.{key} が空")

    depends = route.get("depends_on")
    if not isinstance(depends, list):
        errors.append(f"{prefix}.depends_on が list でない")
    else:
        for dep in depends:
            if not isinstance(dep, str) or not dep.strip():
                errors.append(f"{prefix}.depends_on に非空 string でない値がある")
            elif dep not in ids:
                errors.append(f"{prefix}.depends_on={dep!r} は routes 内に存在しない")
    if spec_rel:
        spec_path = plan_dir / spec_rel
        if not spec_path.is_file():
            errors.append(f"{prefix}.spec が plan_dir 配下に存在しない: {spec_path}")
    if rid and not rid.startswith("C"):
        errors.append(f"{prefix}.id={rid!r} は component id (Cxx) 形式でない")
    return errors


def _check_toposort(routes: list[dict]) -> list[str]:
    seen: set[str] = set()
    errors: list[str] = []
    for idx, route in enumerate(routes):
        rid = str(route.get("id", "")).strip()
        for dep in route.get("depends_on", []) if isinstance(route.get("depends_on"), list) else []:
            if dep not in seen:
                errors.append(f"routes[{idx}] {rid}: depends_on={dep} が先行 route に無い (top-sort 違反)")
        if rid:
            seen.add(rid)
    return errors


def _check_manifest_draft(path: Path, target_plugin_slug: str, prefix: str) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"{prefix}.draft_path が存在しない: {path}"]
    text = path.read_text(encoding="utf-8")
    for token in TODO_RE:
        if token in text:
            errors.append(f"{prefix}.draft_path に placeholder {token!r} が残っている")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"{prefix}.draft_path JSON parse error: {exc}")
        return errors
    if data.get("name") != target_plugin_slug:
        errors.append(f"{prefix}.draft_path name={data.get('name')!r} != target_plugin_slug={target_plugin_slug!r}")
    return errors


def _check_envelope(envelope: object, plan_dir: Path, target_plugin_slug: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(envelope, dict) or not envelope:
        return ["envelope が非空 dict でない"]
    for key, item in envelope.items():
        prefix = f"envelope.{key}"
        if not isinstance(item, dict):
            errors.append(f"{prefix} が dict でない")
            continue
        status = item.get("status")
        if status not in ENVELOPE_STATUSES:
            errors.append(f"{prefix}.status={status!r} が enum 外 {sorted(ENVELOPE_STATUSES)}")
        owner = item.get("owner")
        if status not in ("not_applicable",) and not (isinstance(owner, str) and owner.strip()):
            errors.append(f"{prefix}.owner が非空 string でない")
        if status in ("external_gap", "manual-user-gated"):
            reason = item.get("gap_reason") or item.get("approval_reason")
            if not (isinstance(reason, str) and reason.strip()):
                errors.append(f"{prefix}: status={status} は gap_reason/approval_reason が必要")
        if key == "manifest" and status != "not_applicable":
            draft_path = item.get("draft_path")
            if not isinstance(draft_path, str) or not draft_path.strip():
                errors.append(f"{prefix}.draft_path が非空 string でない")
            else:
                errors.extend(_check_manifest_draft(plan_dir / draft_path, target_plugin_slug, prefix))
    return errors


def validate_handoff(data: object, handoff_path: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["handoff root が object でない"]
    plan_dir_raw = _require_str(data, "plan_dir", errors, "handoff")
    _require_str(data, "target_plugin_slug", errors, "handoff")
    target_plugin_slug = str(data.get("target_plugin_slug", "")).strip()
    mode = data.get("mode")
    if mode not in ("create", "update"):
        errors.append(f"handoff.mode={mode!r} は create|update のみ")
    derived = data.get("derived_count")
    if not isinstance(derived, int) or derived < 1:
        errors.append(f"handoff.derived_count={derived!r} は正の int であること")
    requested = data.get("requested_count")
    if requested is not None and (not isinstance(requested, int) or requested < 1):
        errors.append(f"handoff.requested_count={requested!r} は null または正の int")
    force_13 = data.get("force_13")
    if not isinstance(force_13, bool):
        errors.append(f"handoff.force_13={force_13!r} は bool であること")

    # spec / build_target の解決は cwd 非依存にする。handoff は必ず <PLAN_DIR> 直下に
    # 書かれる (handoff_path.parent == PLAN_DIR) ため、相対 plan_dir フィールド (repo-root
    # 相対の metadata) を Path.cwd() で再構成せず handoff ファイルの所在を基準にする。
    # cwd を基準にすると skill dir から実行された CI 等で plan_dir が二重化して spec を
    # 見失う (cwd 依存バグ)。絶対パス plan_dir のみ明示値を尊重する。
    if plan_dir_raw and Path(plan_dir_raw).is_absolute():
        plan_dir = Path(plan_dir_raw)
    else:
        plan_dir = handoff_path.parent

    routes = data.get("routes")
    if not isinstance(routes, list) or not routes:
        errors.append("handoff.routes が非空 list でない")
        routes = []
    ids = {str(r.get("id", "")).strip() for r in routes if isinstance(r, dict) and str(r.get("id", "")).strip()}
    if len(ids) != len(routes):
        errors.append("handoff.routes の id が欠落または重複している")
    if isinstance(derived, int) and routes and len(routes) != derived:
        errors.append(f"handoff.derived_count={derived} と routes 件数 {len(routes)} が不一致")
    if force_13 is True:
        if derived != 13:
            errors.append(f"handoff.force_13=true では derived_count=13 が必要 (現値 {derived})")
        if routes and len(routes) != 13:
            errors.append(f"handoff.force_13=true では routes 件数 13 が必要 (現値 {len(routes)})")
    for idx, route in enumerate(routes):
        if not isinstance(route, dict):
            errors.append(f"routes[{idx}] が object でない")
            continue
        errors.extend(_route_errors(route, idx, ids, plan_dir))
    errors.extend(_check_toposort([r for r in routes if isinstance(r, dict)]))
    errors.extend(_check_envelope(data.get("envelope"), plan_dir, target_plugin_slug))
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="build handoff JSON を検証する")
    ap.add_argument("handoff", help="handoff-run-plugin-dev-plan.json")
    args = ap.parse_args(argv)

    path = Path(args.handoff)
    if not path.is_file():
        sys.stderr.write(f"handoff not found: {path}\n")
        return 2
    try:
        data = _load_json(path)
    except ValueError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2
    errors = validate_handoff(data, path.resolve())
    if not errors:
        routes = data.get("routes", [])
        sys.stdout.write(f"OK: build handoff が {len(routes)} routes と envelope 契約を満たす\n")
        return 0
    for err in errors:
        sys.stderr.write(err + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
