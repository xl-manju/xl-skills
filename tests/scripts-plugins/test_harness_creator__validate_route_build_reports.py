"""validate-route-build-reports.py (route 実行レポート契約) を genuine に検証する。

対象契約: plugins/harness-creator/skills/run-build-skill/references/route-build-report.md
  - validate_report_shape: schema 相当の形状 + cross-field (skip_reason/evidence)
  - validate_against_route: handoff route との同値性 (route が SSOT)
  - validate_dependency_chain: 依存レポート実在/非 failure + inputs_consumed 被覆
  - validate_complete: 全 route 実在 + failure ゼロ + orphan 検出
  - main の CLI 契約: --route / --complete / --self-test / usage の returncode と stdout JSON

副作用なし (network/keychain 不使用)。tmp_path のみ書き込み。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "harness-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "validate-route-build-reports.py"
)

_SPEC = importlib.util.spec_from_file_location("vrbr_under_test", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)

SLUG = "demo-plugin"


def _routes():
    return [
        {"id": "C1", "component_kind": "script", "name": "lint-a", "depends_on": [],
         "builder": "plugin-scaffold", "build_target": f"plugins/{SLUG}/scripts/lint-a.py"},
        {"id": "C2", "component_kind": "skill", "name": "run-b", "depends_on": ["C1"],
         "builder": "run-skill-create", "build_target": f"plugins/{SLUG}/skills/run-b/"},
    ]


def _handoff():
    return {"target_plugin_slug": SLUG, "routes": _routes()}


def _report(rid, route, **over):
    rep = {
        "schema_version": "1.0.0", "plugin_slug": SLUG, "route_id": rid,
        "component_kind": route["component_kind"], "name": route["name"],
        "builder": route["builder"], "build_target": route["build_target"],
        "status": "success", "summary": "build 完了。lint exit0 を確認。",
        "deviations": [], "evidence": ["lint exit0"],
        "inputs_consumed": [], "handover": None,
    }
    rep.update(over)
    return rep


@pytest.fixture()
def reports_dir(tmp_path):
    d = tmp_path / "eval-log" / SLUG / "build"
    d.mkdir(parents=True)
    return d


def _write(reports_dir, rid, data):
    (reports_dir / f"route-{rid}.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------
# validate_report_shape
# --------------------------------------------------------------------------

def test_shape_valid_report_has_no_findings():
    assert MOD.validate_report_shape(_report("C1", _routes()[0])) == []


def test_shape_rejects_non_dict():
    assert MOD.validate_report_shape(["x"])


def test_shape_missing_required_key():
    rep = _report("C1", _routes()[0])
    del rep["summary"]
    assert any("summary" in f for f in MOD.validate_report_shape(rep))


def test_shape_rejects_unknown_key():
    rep = _report("C1", _routes()[0], extra_field="x")
    assert any("未知キー" in f for f in MOD.validate_report_shape(rep))


def test_shape_success_requires_evidence():
    rep = _report("C1", _routes()[0], evidence=[])
    assert any("evidence" in f for f in MOD.validate_report_shape(rep))


def test_shape_skipped_requires_skip_reason():
    rep = _report("C1", _routes()[0], status="skipped", evidence=[])
    assert any("skip_reason" in f for f in MOD.validate_report_shape(rep))


def test_shape_skipped_with_reason_passes_and_allows_empty_evidence():
    rep = _report("C1", _routes()[0], status="skipped",
                  skip_reason="既存実体を維持", evidence=[])
    assert MOD.validate_report_shape(rep) == []


def test_shape_skip_reason_forbidden_on_success():
    rep = _report("C1", _routes()[0], skip_reason="不要な理由")
    assert any("skip_reason" in f for f in MOD.validate_report_shape(rep))


def test_shape_rejects_bad_enums():
    rep = _report("C1", _routes()[0], status="done", builder="make",
                  component_kind="widget")
    findings = MOD.validate_report_shape(rep)
    assert any("status" in f for f in findings)
    assert any("builder" in f for f in findings)
    assert any("component_kind" in f for f in findings)


# --------------------------------------------------------------------------
# validate_against_route / validate_dependency_chain
# --------------------------------------------------------------------------

def test_against_route_detects_build_target_drift():
    route = _routes()[0]
    rep = _report("C1", route, build_target="plugins/other/x.py")
    assert any("build_target" in f for f in MOD.validate_against_route(rep, route, SLUG))


def test_against_route_detects_slug_mismatch():
    route = _routes()[0]
    rep = _report("C1", route, plugin_slug="other-plugin")
    assert any("plugin_slug" in f for f in MOD.validate_against_route(rep, route, SLUG))


def test_chain_missing_dependency_report_fails(reports_dir):
    handoff = _handoff()
    _write(reports_dir, "C2", _report("C2", _routes()[1],
                                      inputs_consumed=[MOD.report_path(SLUG, "C1")]))
    assert any("未作成" in f for f in MOD.validate_route(handoff, reports_dir, "C2"))


def test_chain_satisfied_passes(reports_dir):
    handoff = _handoff()
    _write(reports_dir, "C1", _report("C1", _routes()[0], handover="申し送り"))
    _write(reports_dir, "C2", _report("C2", _routes()[1],
                                      inputs_consumed=[MOD.report_path(SLUG, "C1")]))
    assert MOD.validate_route(handoff, reports_dir, "C1") == []
    assert MOD.validate_route(handoff, reports_dir, "C2") == []


def test_chain_requires_inputs_consumed_declaration(reports_dir):
    handoff = _handoff()
    _write(reports_dir, "C1", _report("C1", _routes()[0]))
    _write(reports_dir, "C2", _report("C2", _routes()[1], inputs_consumed=[]))
    assert any("inputs_consumed" in f for f in MOD.validate_route(handoff, reports_dir, "C2"))


def test_chain_dependency_failure_blocks_successor(reports_dir):
    handoff = _handoff()
    _write(reports_dir, "C1", _report("C1", _routes()[0], status="failure"))
    _write(reports_dir, "C2", _report("C2", _routes()[1],
                                      inputs_consumed=[MOD.report_path(SLUG, "C1")]))
    assert any("failure" in f for f in MOD.validate_route(handoff, reports_dir, "C2"))


def test_route_unknown_id_fails(reports_dir):
    assert any("存在しない" in f
               for f in MOD.validate_route(_handoff(), reports_dir, "C99"))


def test_route_id_filename_mismatch_fails(reports_dir):
    _write(reports_dir, "C1", _report("C2", _routes()[0]))
    assert any("route_id" in f for f in MOD.validate_route(_handoff(), reports_dir, "C1"))


# --------------------------------------------------------------------------
# validate_complete
# --------------------------------------------------------------------------

def test_complete_all_green_passes(reports_dir):
    _write(reports_dir, "C1", _report("C1", _routes()[0]))
    _write(reports_dir, "C2", _report("C2", _routes()[1],
                                      inputs_consumed=[MOD.report_path(SLUG, "C1")]))
    assert MOD.validate_complete(_handoff(), reports_dir) == []


def test_complete_missing_report_fails(reports_dir):
    _write(reports_dir, "C1", _report("C1", _routes()[0]))
    assert any("C2" in f for f in MOD.validate_complete(_handoff(), reports_dir))


def test_complete_detects_orphan_report(reports_dir):
    _write(reports_dir, "C1", _report("C1", _routes()[0]))
    _write(reports_dir, "C2", _report("C2", _routes()[1],
                                      inputs_consumed=[MOD.report_path(SLUG, "C1")]))
    _write(reports_dir, "C9", _report("C9", _routes()[0], route_id="C9"))
    assert any("orphan" in f for f in MOD.validate_complete(_handoff(), reports_dir))


# --------------------------------------------------------------------------
# CLI 契約
# --------------------------------------------------------------------------

def _run(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd)


def _setup_repo(tmp_path):
    handoff_path = tmp_path / "handoff.json"
    handoff_path.write_text(json.dumps(_handoff()), encoding="utf-8")
    reports = tmp_path / "eval-log" / SLUG / "build"
    reports.mkdir(parents=True)
    _write(reports, "C1", _report("C1", _routes()[0]))
    _write(reports, "C2", _report("C2", _routes()[1],
                                  inputs_consumed=[MOD.report_path(SLUG, "C1")]))
    # success レポートは build_target の現物存在を要求する (repo_root=tmp_path)。
    # C1=script (ファイル) / C2=skill (ディレクトリ) の実体を用意する。
    c1_target = tmp_path / _routes()[0]["build_target"]
    c1_target.parent.mkdir(parents=True, exist_ok=True)
    c1_target.write_text("# lint-a\n", encoding="utf-8")
    (tmp_path / _routes()[1]["build_target"]).mkdir(parents=True, exist_ok=True)
    return handoff_path


def test_cli_self_test_passes():
    proc = _run("--self-test")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["valid"] is True


def test_cli_route_and_complete_pass(tmp_path):
    handoff_path = _setup_repo(tmp_path)
    for args in (["--route", "C2"], ["--complete"]):
        proc = _run("--handoff", str(handoff_path), *args, cwd=tmp_path)
        out = json.loads(proc.stdout)
        assert proc.returncode == 0, proc.stdout
        assert out["valid"] is True and out["findings"] == []


def test_cli_route_failure_exit1(tmp_path):
    handoff_path = _setup_repo(tmp_path)
    (tmp_path / "eval-log" / SLUG / "build" / "route-C1.json").unlink()
    proc = _run("--handoff", str(handoff_path), "--route", "C2", cwd=tmp_path)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["findings"]


def test_cli_usage_errors_exit2(tmp_path):
    handoff_path = _setup_repo(tmp_path)
    # --route と --complete の同時指定 / 両方欠落 / handoff 欠落
    assert _run("--handoff", str(handoff_path), cwd=tmp_path).returncode == 2
    assert _run("--handoff", str(handoff_path), "--route", "C1", "--complete",
                cwd=tmp_path).returncode == 2
    assert _run("--handoff", str(tmp_path / "nope.json"), "--complete",
                cwd=tmp_path).returncode == 2


def test_cli_reports_dir_override(tmp_path):
    handoff_path = _setup_repo(tmp_path)
    # cwd=tmp_path で repo_root を tmp_path に固定し build_target 現物存在検査を成立させる。
    proc = _run("--handoff", str(handoff_path), "--complete",
                "--reports-dir", str(tmp_path / "eval-log" / SLUG / "build"),
                cwd=tmp_path)
    assert proc.returncode == 0, proc.stdout
