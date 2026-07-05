from __future__ import annotations

import json
from pathlib import Path


SLUG = "demo-plugin"


def _route(route_id: str, name: str, target: str, *, depends_on=None, builder="plugin-scaffold"):
    route = {
        "id": route_id,
        "component_kind": "script",
        "name": name,
        "depends_on": depends_on or [],
        "placement_scope": "plugin-root" if builder == "plugin-scaffold" else "skill",
        "builder": builder,
        "builder_status": "contract-only",
        "gap_ref": "GAP-SCRIPT-BUILDER",
        "build_kind": "script",
        "build_args": {"script_path": target.removeprefix(f"plugins/{SLUG}/")},
        "build_target": target,
        "status": "planned",
    }
    if builder == "parent-skill-build":
        route["requires_parent_scaffold"] = "C01"
    return route


def _write_plan(tmp_path: Path, routes: list[dict]) -> Path:
    plan = tmp_path / "plugin-plans" / SLUG
    plan.mkdir(parents=True)
    handoff = {"target_plugin_slug": SLUG, "plan_dir": str(plan), "routes": routes}
    inventory = {"components": routes}
    handoff_path = plan / "handoff-run-plugin-dev-plan.json"
    handoff_path.write_text(json.dumps(handoff, ensure_ascii=False), encoding="utf-8")
    (plan / "component-inventory.json").write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    return handoff_path


def _read_report(tmp_path: Path, route_id: str) -> dict:
    return json.loads((tmp_path / "eval-log" / SLUG / "build" / f"route-{route_id}.json").read_text(encoding="utf-8"))


def test_build_script_route_creates_missing_script_and_report(tmp_path, monkeypatch, script_route_builder):
    monkeypatch.chdir(tmp_path)
    route = _route("C01", "lint-a", f"plugins/{SLUG}/scripts/lint-a.py")
    handoff = _write_plan(tmp_path, [route])

    rc, payload = script_route_builder.build_script_route(handoff_path=handoff, route_id="C01")

    assert rc == 0, payload
    target = tmp_path / route["build_target"]
    assert target.is_file()
    assert "source-route-id: C01" in target.read_text(encoding="utf-8")
    report = _read_report(tmp_path, "C01")
    assert report["status"] == "skipped"
    assert "minimal scaffold generated" in report["skip_reason"]
    assert report["build_target"] == route["build_target"]
    assert report["deviations"] == [
        "minimal scaffold generated; domain implementation still required before dependent routes may proceed"
    ]


def test_build_script_route_existing_file_is_not_overwritten(tmp_path, monkeypatch, script_route_builder):
    monkeypatch.chdir(tmp_path)
    route = _route("C01", "lint-a", f"plugins/{SLUG}/scripts/lint-a.py")
    handoff = _write_plan(tmp_path, [route])
    target = tmp_path / route["build_target"]
    target.parent.mkdir(parents=True)
    original = "print('kept')\n"
    target.write_text(original, encoding="utf-8")

    rc, payload = script_route_builder.build_script_route(handoff_path=handoff, route_id="C01")

    assert rc == 0, payload
    assert target.read_text(encoding="utf-8") == original
    report = _read_report(tmp_path, "C01")
    assert "exists sha256=" in report["evidence"][0]
    assert report["deviations"] == []


def test_build_script_route_blocks_when_dependency_report_missing(tmp_path, monkeypatch, script_route_builder):
    monkeypatch.chdir(tmp_path)
    r1 = _route("C01", "lint-a", f"plugins/{SLUG}/scripts/lint-a.py")
    r2 = _route("C02", "lint-b", f"plugins/{SLUG}/scripts/lint-b.py", depends_on=["C01"])
    handoff = _write_plan(tmp_path, [r1, r2])

    rc, payload = script_route_builder.build_script_route(handoff_path=handoff, route_id="C02")

    assert rc == 1
    assert any("dependency C01" in err for err in payload["errors"])
    assert not (tmp_path / r2["build_target"]).exists()


def test_build_script_route_consumes_dependency_report(tmp_path, monkeypatch, script_route_builder):
    monkeypatch.chdir(tmp_path)
    r1 = _route("C01", "lint-a", f"plugins/{SLUG}/scripts/lint-a.py")
    r2 = _route("C02", "lint-b", f"plugins/{SLUG}/scripts/lint-b.py", depends_on=["C01"])
    handoff = _write_plan(tmp_path, [r1, r2])
    first_target = tmp_path / r1["build_target"]
    first_target.parent.mkdir(parents=True)
    first_target.write_text("# existing implementation\n", encoding="utf-8")

    assert script_route_builder.build_script_route(handoff_path=handoff, route_id="C01")[0] == 0
    rc, payload = script_route_builder.build_script_route(handoff_path=handoff, route_id="C02")

    assert rc == 0, payload
    report = _read_report(tmp_path, "C02")
    assert report["inputs_consumed"] == [f"eval-log/{SLUG}/build/route-C01.json"]


def test_build_script_route_rejects_non_script_route(tmp_path, monkeypatch, script_route_builder):
    monkeypatch.chdir(tmp_path)
    route = {
        "id": "C01",
        "component_kind": "skill",
        "name": "run-a",
        "depends_on": [],
        "builder": "run-skill-create",
        "build_kind": "skill",
        "build_target": f"plugins/{SLUG}/skills/run-a/",
    }
    handoff = _write_plan(tmp_path, [route])

    rc, payload = script_route_builder.build_script_route(handoff_path=handoff, route_id="C01")

    assert rc == 1
    assert "route is not a script route" in payload["errors"]


def test_build_script_route_blocks_dependency_that_was_only_scaffolded(tmp_path, monkeypatch, script_route_builder):
    monkeypatch.chdir(tmp_path)
    r1 = _route("C01", "lint-a", f"plugins/{SLUG}/scripts/lint-a.py")
    r2 = _route("C02", "lint-b", f"plugins/{SLUG}/scripts/lint-b.py", depends_on=["C01"])
    handoff = _write_plan(tmp_path, [r1, r2])

    assert script_route_builder.build_script_route(handoff_path=handoff, route_id="C01")[0] == 0
    rc, payload = script_route_builder.build_script_route(handoff_path=handoff, route_id="C02")

    assert rc == 1
    assert any("dependency C01" in err and "status=skipped" in err for err in payload["errors"])


def test_build_script_route_resolves_repo_root_from_handoff_not_cwd(tmp_path, monkeypatch, script_route_builder):
    route = _route("C01", "lint-a", f"plugins/{SLUG}/scripts/lint-a.py")
    handoff = _write_plan(tmp_path, [route])
    target = tmp_path / route["build_target"]
    target.parent.mkdir(parents=True)
    target.write_text("# existing implementation\n", encoding="utf-8")
    cwd = tmp_path / "plugins" / "harness-creator"
    cwd.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(cwd)

    rc, payload = script_route_builder.build_script_route(handoff_path=handoff, route_id="C01", dry_run=True)

    assert rc == 0, payload
    assert payload["repo_root"] == tmp_path.as_posix()
    assert payload["would_create"] is False


def test_build_script_route_validates_parent_skill_contract(tmp_path, monkeypatch, script_route_builder):
    monkeypatch.chdir(tmp_path)
    parent = {
        "id": "C01",
        "component_kind": "skill",
        "name": "run-a",
        "depends_on": [],
        "builder": "run-skill-create",
        "build_kind": "skill",
        "build_target": f"plugins/{SLUG}/skills/run-a/",
    }
    child = _route(
        "C02",
        "lint-a",
        f"plugins/{SLUG}/skills/run-a/scripts/lint-a.py",
        builder="parent-skill-build",
    )
    child["build_args"]["parent_skill"] = "run-a"
    child["build_args"]["script_path"] = "scripts/lint-a.py"
    handoff = _write_plan(tmp_path, [parent, child])

    rc, payload = script_route_builder.build_script_route(handoff_path=handoff, route_id="C02")

    assert rc == 0, payload
    assert (tmp_path / parent["build_target"]).is_dir()
    report = _read_report(tmp_path, "C02")
    assert "created parent skill scaffold directory" in report["deviations"][0]


def test_build_script_route_rejects_script_path_build_target_mismatch(tmp_path, monkeypatch, script_route_builder):
    monkeypatch.chdir(tmp_path)
    route = _route("C01", "lint-a", f"plugins/{SLUG}/scripts/not-lint-a.py")
    route["build_args"]["script_path"] = "scripts/lint-a.py"
    handoff = _write_plan(tmp_path, [route])

    rc, payload = script_route_builder.build_script_route(handoff_path=handoff, route_id="C01")

    assert rc == 1
    assert any("script_path does not match build_target" in err for err in payload["errors"])
