"""check-build-handoff.py の機能テスト。"""
from __future__ import annotations

import json

from conftest import write_component_spec


def _write_plan(tmp_path, overrides: dict | None = None):
    write_component_spec(tmp_path, "C01", "skill")
    write_component_spec(tmp_path, "C02", "sub-agent", depends_on=["C01"])
    draft_dir = tmp_path / "envelope-draft"
    draft_dir.mkdir()
    (draft_dir / "plugin.json").write_text(
        json.dumps({"name": "sample-plugin", "version": "0.1.0", "description": "sample"}, ensure_ascii=False),
        encoding="utf-8",
    )
    data = {
        "plan_dir": str(tmp_path),
        "target_plugin_slug": "sample-plugin",
        "mode": "create",
        "requested_count": None,
        "force_13": False,
        "derived_count": 2,
        "routes": [
            {
                "id": "C01",
                "component_kind": "skill",
                "name": "run-sample",
                "spec": "C01-skill.md",
                "depends_on": [],
                "builder": "run-skill-create",
                "build_kind": "skill",
                "build_args": {"skill_name": "run-sample", "kind": "run"},
                "build_target": "plugins/sample-plugin/skills/run-sample/",
                "status": "planned",
            },
            {
                "id": "C02",
                "component_kind": "sub-agent",
                "name": "sample-verifier",
                "spec": "C02-sub-agent.md",
                "depends_on": ["C01"],
                "builder": "run-build-skill",
                "build_kind": "agent",
                "build_args": {"kind": "agent", "name": "sample-verifier"},
                "build_target": "plugins/sample-plugin/agents/sample-verifier.md",
                "status": "planned",
            },
        ],
        "envelope": {
            "manifest": {
                "owner": "plugin-scaffold",
                "status": "external_gap",
                "build_target": "plugins/sample-plugin/.claude-plugin/plugin.json",
                "draft_path": "envelope-draft/plugin.json",
                "gap_reason": "scaffold executor is external",
            }
        },
    }
    if overrides:
        data.update(overrides)
    path = tmp_path / "handoff-run-plugin-dev-plan.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, data


def test_clean_handoff(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    assert handoff.validate_handoff(data, path) == []
    assert handoff.main([str(path)]) == 0


def test_builder_mismatch_fails(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    data["routes"][0]["builder"] = "run-build-skill"
    errs = handoff.validate_handoff(data, path)
    assert any("builder=run-skill-create" in e for e in errs)


def test_build_kind_mismatch_fails(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    data["routes"][1]["build_kind"] = "sub-agent"
    errs = handoff.validate_handoff(data, path)
    assert any("build_kind=agent" in e for e in errs)


def test_run_build_skill_args_kind_mismatch_fails(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    data["routes"][1]["build_args"]["kind"] = "command"
    errs = handoff.validate_handoff(data, path)
    assert any("build_args.kind" in e for e in errs)


def test_toposort_violation_fails(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    data["routes"] = [data["routes"][1], data["routes"][0]]
    errs = handoff.validate_handoff(data, path)
    assert any("top-sort 違反" in e for e in errs)


def test_missing_spec_fails(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    data["routes"][1]["spec"] = "missing.md"
    errs = handoff.validate_handoff(data, path)
    assert any("plan_dir 配下に存在しない" in e for e in errs)


def test_external_gap_requires_reason(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    del data["envelope"]["manifest"]["gap_reason"]
    errs = handoff.validate_handoff(data, path)
    assert any("gap_reason/approval_reason" in e for e in errs)


def test_count_mismatch_fails(tmp_path, handoff):
    path, data = _write_plan(tmp_path, {"derived_count": 13})
    errs = handoff.validate_handoff(data, path)
    assert any("derived_count=13" in e for e in errs)


def test_force_13_requires_13_routes(tmp_path, handoff):
    path, data = _write_plan(tmp_path, {"force_13": True})
    errs = handoff.validate_handoff(data, path)
    assert any("force_13=true" in e for e in errs)


def test_manifest_draft_name_mismatch_fails(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    (tmp_path / "envelope-draft" / "plugin.json").write_text(
        json.dumps({"name": "other-plugin", "version": "0.1.0", "description": "sample"}, ensure_ascii=False),
        encoding="utf-8",
    )
    errs = handoff.validate_handoff(data, path)
    assert any("target_plugin_slug" in e for e in errs)


def test_relative_plan_dir_is_cwd_independent(monkeypatch, tmp_path, handoff):
    """相対 plan_dir フィールド (repo-root 相対 metadata) を持つ handoff でも、cwd に依存せず
    handoff ファイルの所在 (= PLAN_DIR) を基準に spec を解決する。

    回帰防止: 旧実装は相対 plan_dir を Path.cwd() で再構成していたため、skill dir cwd の CI
    から実行すると plan_dir が二重化して spec を見失っていた (creator-kit-ci の nested-test
    収集で露呈)。本テストは無関係な cwd から実行しても exit0 になることを固定する。
    """
    # specs (C01-skill.md / C02-sub-agent.md) は handoff と同じ tmp_path に在るが、
    # plan_dir フィールドは repo-root 相対の metadata 値にする。
    path, data = _write_plan(tmp_path, {"plan_dir": "eval-log/some-plugin/plan"})
    monkeypatch.chdir(tmp_path.parent)  # repo-root でも skill dir でもない無関係 cwd
    assert handoff.main([str(path)]) == 0
    assert handoff.validate_handoff(data, path) == []
