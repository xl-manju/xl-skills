#!/usr/bin/env python3
# /// script
# name: validate-route-build-reports
# purpose: Validate per-route build reports under eval-log/<slug>/build/ against handoff routes (L4 execution handover chain).
# inputs:
#   - argv: --handoff plugin-plans/<slug>/handoff-run-plugin-dev-plan.json [--reports-dir DIR] (--route ID | --complete)
# outputs:
#   - stdout: JSON {"valid": bool, "mode": str, "findings": [str, ...]}
#   - exit: 0=PASS / 1=validation failure / 2=usage or JSON error
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
"""plugin 一括 build の route 実行レポート (route-build-report) を検証する。

契約正本: references/route-build-report.md / schemas/route-build-report.schema.json

Usage:
  # route 1 本の完了直後: レポート形状 + handoff 整合 + 依存チェーンを検証
  validate-route-build-reports.py --handoff plugin-plans/<slug>/handoff-run-plugin-dev-plan.json --route C01

  # 全 route 終端: 全レポート実在 + failure ゼロ + orphan ゼロを検証
  validate-route-build-reports.py --handoff plugin-plans/<slug>/handoff-run-plugin-dev-plan.json --complete

  # 内蔵 self-test (一時ディレクトリ上で代表シナリオを検査)
  validate-route-build-reports.py --self-test

CLI 出力契約:
  stdout: JSON {"valid": bool, "mode": "route:<id>"|"complete"|"self-test", "findings": [str, ...]}
  exit:   0=PASS, 1=FAIL, 2=usage/parse error
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = "1.0.0"
COMPONENT_KINDS = {"skill", "sub-agent", "slash-command", "hook", "script"}
BUILDERS = {"run-skill-create", "run-build-skill", "plugin-scaffold", "parent-skill-build"}
STATUSES = {"success", "failure", "skipped"}
ROUTE_ID_RE = re.compile(r"^C[0-9]+$")
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
REQUIRED_KEYS = (
    "schema_version", "plugin_slug", "route_id", "component_kind", "name",
    "builder", "build_target", "status", "summary", "deviations",
    "evidence", "inputs_consumed", "handover",
)
OPTIONAL_KEYS = ("skip_reason",)


def report_path(slug: str, route_id: str) -> str:
    """レポートの repo-root 相対パス規約 (inputs_consumed の照合にも使う)。"""
    return f"eval-log/{slug}/build/route-{route_id}.json"


def _is_str_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(x, str) and x for x in value)


def validate_report_shape(report: object) -> list[str]:
    """schema (route-build-report.schema.json) 相当の形状検査。findings を返す。"""
    if not isinstance(report, dict):
        return ["report: JSON object でない"]
    findings: list[str] = []
    for key in REQUIRED_KEYS:
        if key not in report:
            findings.append(f"report: 必須キー {key} 欠落")
    unknown = set(report) - set(REQUIRED_KEYS) - set(OPTIONAL_KEYS)
    if unknown:
        findings.append(f"report: 未知キー {sorted(unknown)} (additionalProperties=false)")
    if report.get("schema_version") != SCHEMA_VERSION:
        findings.append(f"schema_version: {SCHEMA_VERSION} でない")
    slug = report.get("plugin_slug")
    if not (isinstance(slug, str) and SLUG_RE.match(slug)):
        findings.append("plugin_slug: ^[a-z][a-z0-9-]*$ に不一致")
    rid = report.get("route_id")
    if not (isinstance(rid, str) and ROUTE_ID_RE.match(rid)):
        findings.append("route_id: ^C[0-9]+$ に不一致")
    if report.get("component_kind") not in COMPONENT_KINDS:
        findings.append(f"component_kind: enum 外 ({report.get('component_kind')!r})")
    if not (isinstance(report.get("name"), str) and report.get("name")):
        findings.append("name: 非空文字列でない")
    if report.get("builder") not in BUILDERS:
        findings.append(f"builder: enum 外 ({report.get('builder')!r})")
    if not (isinstance(report.get("build_target"), str) and report.get("build_target")):
        findings.append("build_target: 非空文字列でない")
    status = report.get("status")
    if status not in STATUSES:
        findings.append(f"status: enum 外 ({status!r})")
    if not (isinstance(report.get("summary"), str) and report.get("summary")):
        findings.append("summary: 非空文字列でない")
    for key in ("deviations", "evidence", "inputs_consumed"):
        if key in report and not _is_str_list(report[key]):
            findings.append(f"{key}: 非空文字列の配列でない")
    if "handover" in report and not (report["handover"] is None or isinstance(report["handover"], str)):
        findings.append("handover: string か null でない")
    # cross-field
    if status == "skipped" and not (isinstance(report.get("skip_reason"), str) and report.get("skip_reason")):
        findings.append("skip_reason: status=skipped なのに非空 skip_reason が無い")
    if status != "skipped" and "skip_reason" in report:
        findings.append("skip_reason: status=skipped 以外では書かない")
    if status == "success" and _is_str_list(report.get("evidence")) and not report["evidence"]:
        findings.append("evidence: status=success は 1 件以上必須")
    return findings


def _repo_root_from_handoff_path(path: Path) -> Path:
    resolved = path.resolve()
    if "plugin-plans" in resolved.parts:
        idx = resolved.parts.index("plugin-plans")
        return Path(*resolved.parts[:idx]) if idx else Path("/")
    return Path.cwd()


def validate_against_route(report: dict, route: dict, slug: str, repo_root: Path | None = None) -> list[str]:
    """レポートと handoff route の同値性 (route が SSOT・レポートは写し)。"""
    findings: list[str] = []
    if report.get("plugin_slug") != slug:
        findings.append(f"plugin_slug: handoff target_plugin_slug ({slug}) と不一致")
    for key in ("component_kind", "name", "builder", "build_target"):
        if report.get(key) != route.get(key):
            findings.append(f"{key}: handoff route と不一致 (report={report.get(key)!r} route={route.get(key)!r})")
    if repo_root is not None and report.get("status") == "success":
        target = repo_root / str(report.get("build_target", ""))
        if not target.exists():
            findings.append(f"build_target: success report だが現物が存在しない ({report.get('build_target')})")
    return findings


def _load_report(reports_dir: Path, slug: str, route_id: str) -> tuple[dict | None, list[str]]:
    path = reports_dir / f"route-{route_id}.json"
    if not path.is_file():
        return None, [f"route {route_id}: レポート未作成 ({report_path(slug, route_id)})"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [f"route {route_id}: レポートが JSON として読めない ({exc})"]
    if not isinstance(data, dict):
        return None, [f"route {route_id}: レポートが JSON object でない"]
    return data, []


def validate_dependency_chain(report: dict, route: dict, reports_dir: Path, slug: str) -> list[str]:
    """依存 route のレポート実在/非 failure と inputs_consumed 被覆 (fail-closed の本体)。"""
    findings: list[str] = []
    consumed = {str(PurePosixPath(p)) for p in report.get("inputs_consumed", []) if isinstance(p, str)}
    for dep_id in route.get("depends_on", []) or []:
        dep_report, errs = _load_report(reports_dir, slug, dep_id)
        if errs:
            findings.extend(f"依存 {e}" for e in errs)
            continue
        dep_status = dep_report.get("status")
        if dep_status not in STATUSES:
            findings.append(f"依存 route {dep_id}: status 不正 ({dep_status!r})")
        elif dep_status != "success":
            findings.append(f"依存 route {dep_id}: status={dep_status} のまま後続を build している")
        expected = report_path(slug, dep_id)
        if expected not in consumed:
            findings.append(f"inputs_consumed: 依存レポート {expected} の読取宣言が無い")
    return findings


def validate_route(handoff: dict, reports_dir: Path, route_id: str, repo_root: Path | None = None) -> list[str]:
    slug = handoff.get("target_plugin_slug", "")
    routes = {r.get("id"): r for r in handoff.get("routes", []) if isinstance(r, dict)}
    route = routes.get(route_id)
    if route is None:
        return [f"route {route_id}: handoff routes に存在しない"]
    report, errs = _load_report(reports_dir, slug, route_id)
    if errs:
        return errs
    findings = validate_report_shape(report)
    if report.get("route_id") not in (None, route_id):
        findings.append(f"route_id: ファイル名 route-{route_id}.json と不一致 ({report.get('route_id')!r})")
    findings.extend(validate_against_route(report, route, slug, repo_root))
    findings.extend(validate_dependency_chain(report, route, reports_dir, slug))
    return findings


def validate_complete(handoff: dict, reports_dir: Path, repo_root: Path | None = None) -> list[str]:
    slug = handoff.get("target_plugin_slug", "")
    routes = [r for r in handoff.get("routes", []) if isinstance(r, dict)]
    findings: list[str] = []
    for route in routes:
        rid = route.get("id", "?")
        route_findings = validate_route(handoff, reports_dir, rid, repo_root)
        findings.extend(route_findings)
        if not route_findings:
            report, _ = _load_report(reports_dir, slug, rid)
            if report and report.get("status") == "failure":
                findings.append(f"route {rid}: status=failure が残っている (build 未完了)")
    known_ids = {r.get("id") for r in routes}
    if reports_dir.is_dir():
        for path in sorted(reports_dir.glob("route-*.json")):
            rid = path.stem.removeprefix("route-")
            if rid not in known_ids:
                findings.append(f"orphan レポート: {path.name} は handoff routes に無い route (計画 drift)")
    return findings


def _load_handoff(path: Path) -> tuple[dict | None, str | None]:
    if not path.is_file():
        return None, f"handoff が見つからない: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, f"handoff が JSON として読めない: {exc}"
    if not isinstance(data, dict) or not isinstance(data.get("routes"), list):
        return None, "handoff に routes 配列が無い"
    slug = data.get("target_plugin_slug")
    if not (isinstance(slug, str) and SLUG_RE.match(slug)):
        return None, "handoff の target_plugin_slug が不正"
    return data, None


def _emit(valid: bool, mode: str, findings: list[str]) -> int:
    print(json.dumps({"valid": valid, "mode": mode, "findings": findings}, ensure_ascii=False, indent=2))
    return 0 if valid else 1


def _self_test() -> int:
    import tempfile

    findings: list[str] = []

    def check(label: str, cond: bool) -> None:
        if not cond:
            findings.append(f"self-test: {label}")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        slug = "demo-plugin"
        handoff = {
            "target_plugin_slug": slug,
            "routes": [
                {"id": "C1", "component_kind": "script", "name": "lint-a", "depends_on": [],
                 "builder": "plugin-scaffold", "build_target": f"plugins/{slug}/scripts/lint-a.py"},
                {"id": "C2", "component_kind": "skill", "name": "run-b", "depends_on": ["C1"],
                 "builder": "run-skill-create", "build_target": f"plugins/{slug}/skills/run-b/"},
            ],
        }
        reports_dir = root / "eval-log" / slug / "build"
        reports_dir.mkdir(parents=True)

        def base_report(rid: str, route: dict, **over: object) -> dict:
            rep = {
                "schema_version": SCHEMA_VERSION, "plugin_slug": slug, "route_id": rid,
                "component_kind": route["component_kind"], "name": route["name"],
                "builder": route["builder"], "build_target": route["build_target"],
                "status": "success", "summary": "build 完了。lint exit0 を確認。",
                "deviations": [], "evidence": ["lint exit0"],
                "inputs_consumed": [], "handover": None,
            }
            rep.update(over)
            return rep

        r1, r2 = handoff["routes"]
        (root / r1["build_target"]).parent.mkdir(parents=True, exist_ok=True)
        (root / r1["build_target"]).write_text("# lint-a\n", encoding="utf-8")
        (root / r2["build_target"]).mkdir(parents=True, exist_ok=True)
        # (1) 依存レポート欠落: C2 は C1 レポートが無いと FAIL
        (reports_dir / "route-C2.json").write_text(json.dumps(
            base_report("C2", r2, inputs_consumed=[report_path(slug, "C1")])), encoding="utf-8")
        check("C1 欠落で C2 が FAIL", validate_route(handoff, reports_dir, "C2", root))
        # (2) チェーン充足で PASS
        (reports_dir / "route-C1.json").write_text(json.dumps(
            base_report("C1", r1, handover="run-b は lint-a の exit code 契約に依存")), encoding="utf-8")
        check("C1 単体 PASS", not validate_route(handoff, reports_dir, "C1", root))
        check("チェーン充足で C2 PASS", not validate_route(handoff, reports_dir, "C2", root))
        # (3) inputs_consumed 未宣言は FAIL
        (reports_dir / "route-C2.json").write_text(json.dumps(
            base_report("C2", r2, inputs_consumed=[])), encoding="utf-8")
        check("読取宣言なしで C2 FAIL",
              any("inputs_consumed" in f for f in validate_route(handoff, reports_dir, "C2", root)))
        (reports_dir / "route-C2.json").write_text(json.dumps(
            base_report("C2", r2, inputs_consumed=[report_path(slug, "C1")])), encoding="utf-8")
        # (4) success なのに evidence 空は FAIL
        bad = base_report("C1", r1, evidence=[])
        check("success+evidence 空 FAIL", any("evidence" in f for f in validate_report_shape(bad)))
        # (5) skipped は skip_reason 必須
        bad = base_report("C1", r1, status="skipped")
        check("skipped+skip_reason 無し FAIL", any("skip_reason" in f for f in validate_report_shape(bad)))
        ok = base_report("C1", r1, status="skipped", skip_reason="既存実体を維持", evidence=[])
        check("skipped+reason PASS", not validate_report_shape(ok))
        # (6) handoff との不一致は FAIL
        drift = base_report("C1", r1, build_target="plugins/other/x.py")
        check("build_target drift FAIL", validate_against_route(drift, r1, slug))
        missing_target = base_report("C1", r1)
        (root / r1["build_target"]).unlink()
        check("success target missing FAIL",
              any("現物が存在しない" in f for f in validate_against_route(missing_target, r1, slug, root)))
        (root / r1["build_target"]).write_text("# lint-a\n", encoding="utf-8")
        # (7) 依存 failure / skipped で後続 FAIL
        (reports_dir / "route-C1.json").write_text(json.dumps(
            base_report("C1", r1, status="failure")), encoding="utf-8")
        check("依存 failure で C2 FAIL",
              any("failure" in f for f in validate_route(handoff, reports_dir, "C2", root)))
        (reports_dir / "route-C1.json").write_text(json.dumps(
            base_report("C1", r1, status="skipped", skip_reason="domain implementation pending", evidence=[])), encoding="utf-8")
        check("依存 skipped で C2 FAIL",
              any("status=skipped" in f for f in validate_route(handoff, reports_dir, "C2", root)))
        (reports_dir / "route-C1.json").write_text(json.dumps(base_report("C1", r1)), encoding="utf-8")
        # (8) complete: 全 route 緑で PASS / orphan で FAIL
        check("complete PASS", not validate_complete(handoff, reports_dir, root))
        (reports_dir / "route-C9.json").write_text(json.dumps(base_report("C9", r1)), encoding="utf-8")
        check("orphan で complete FAIL",
              any("orphan" in f for f in validate_complete(handoff, reports_dir, root)))

    return _emit(not findings, "self-test", findings)


def main(argv: list[str]) -> int:
    args = list(argv)
    if "--self-test" in args:
        return _self_test()

    def _opt(name: str) -> str | None:
        if name in args:
            i = args.index(name)
            if i + 1 >= len(args):
                return None
            return args[i + 1]
        return None

    handoff_arg = _opt("--handoff")
    route_id = _opt("--route")
    complete = "--complete" in args
    if not handoff_arg or (route_id is None) == (not complete):
        print(json.dumps({"valid": False, "mode": "usage", "findings": [
            "usage: validate-route-build-reports.py --handoff <handoff.json> (--route <id> | --complete) [--reports-dir DIR]",
        ]}, ensure_ascii=False))
        return 2
    handoff_path = Path(handoff_arg)
    handoff, err = _load_handoff(handoff_path)
    if err:
        print(json.dumps({"valid": False, "mode": "usage", "findings": [err]}, ensure_ascii=False))
        return 2
    reports_dir_arg = _opt("--reports-dir")
    reports_dir = Path(reports_dir_arg) if reports_dir_arg else Path(
        report_path(handoff["target_plugin_slug"], "C0")).parent
    repo_root = _repo_root_from_handoff_path(handoff_path)
    if route_id is not None:
        return _emit(not (findings := validate_route(handoff, reports_dir, route_id, repo_root)),
                     f"route:{route_id}", findings)
    return _emit(not (findings := validate_complete(handoff, reports_dir, repo_root)), "complete", findings)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
