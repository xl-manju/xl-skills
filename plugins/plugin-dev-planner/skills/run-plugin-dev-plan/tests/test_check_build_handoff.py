"""check-build-handoff.py の機能テスト (per-phase 転換)。

routes は component-inventory.json 由来。route.spec は参照する phase ファイル (任意・推奨は
phase-05-implementation.md)。旧 本数固定/derived_count/force_13 ブロックは削除された。
"""
from __future__ import annotations

import json

from conftest import component_entry, write_inventory, write_phase_spec


def _write_plan(tmp_path, overrides: dict | None = None):
    # route.spec が参照する phase ファイル (実装フェーズ) を用意する (spec 実在検査用)。
    write_phase_spec(tmp_path, 5)
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
        "routes": [
            {
                "id": "C01",
                "component_kind": "skill",
                "name": "run-sample",
                "spec": "phase-05-implementation.md",
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
                "spec": "phase-05-implementation.md",
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


def _write_inventory_for_handoff(tmp_path):
    c01 = component_entry(
        "C01", "skill",
        overrides={
            "name": "run-sample",
            "build_target": "plugins/sample-plugin/skills/run-sample/",
            "build_args": {"skill_name": "run-sample", "kind": "run"},
        },
    )
    c02 = component_entry(
        "C02", "sub-agent",
        depends_on=["C01"],
        overrides={
            "name": "sample-verifier",
            "build_target": "plugins/sample-plugin/agents/sample-verifier.md",
            "build_args": {"kind": "agent", "name": "sample-verifier"},
        },
    )
    write_inventory(tmp_path, [c01, c02])


def test_clean_handoff(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    assert handoff.validate_handoff(data, path) == []
    assert handoff.main([str(path)]) == 0


def test_inventory_provenance_compares_depends_on(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    _write_inventory_for_handoff(tmp_path)
    data["routes"][1]["depends_on"] = []
    errs = handoff.validate_handoff(data, path)
    assert any("depends_on" in e and "inventory" in e for e in errs)


def test_inventory_provenance_compares_build_args(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    _write_inventory_for_handoff(tmp_path)
    data["routes"][1]["build_args"] = {"kind": "agent", "name": "other"}
    errs = handoff.validate_handoff(data, path)
    assert any("build_args" in e and "inventory" in e for e in errs)


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


def _plugin_root_script_route() -> dict:
    return {
        "id": "C09",
        "component_kind": "script",
        "name": "validate-payload.py",
        "spec": "phase-05-implementation.md",
        "depends_on": [],
        "placement_scope": "plugin-root",
        "builder": "plugin-scaffold",
        "build_kind": "script",
        "build_args": {"script_path": "scripts/validate-payload.py"},
        "build_target": "plugins/sample-plugin/scripts/validate-payload.py",
        "status": "planned",
    }


def test_plugin_root_script_route_clean(tmp_path, handoff):
    """plugin-root script route (builder=plugin-scaffold・build_args.script_path) が通る。"""
    route = _plugin_root_script_route()
    path, data = _write_plan(tmp_path, {"routes": [route]})
    assert handoff.validate_handoff(data, path) == []
    assert handoff.main([str(path)]) == 0


def test_plugin_root_script_wrong_builder_fails(tmp_path, handoff):
    """plugin-root script が parent-skill-build のままだと builder 不整合で弾かれる。"""
    route = _plugin_root_script_route()
    route["builder"] = "parent-skill-build"
    path, data = _write_plan(tmp_path, {"routes": [route]})
    errs = handoff.validate_handoff(data, path)
    assert any("builder=plugin-scaffold" in e for e in errs)


def test_plugin_scaffold_route_needs_script_path(tmp_path, handoff):
    """plugin-scaffold route は build_args.script_path 必須。"""
    route = _plugin_root_script_route()
    route["build_args"] = {"parent_skill": "run-x"}  # script_path 欠落
    path, data = _write_plan(tmp_path, {"routes": [route]})
    errs = handoff.validate_handoff(data, path)
    assert any("script_path" in e for e in errs)


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


def test_manifest_draft_name_mismatch_fails(tmp_path, handoff):
    path, data = _write_plan(tmp_path)
    (tmp_path / "envelope-draft" / "plugin.json").write_text(
        json.dumps({"name": "other-plugin", "version": "0.1.0", "description": "sample"}, ensure_ascii=False),
        encoding="utf-8",
    )
    errs = handoff.validate_handoff(data, path)
    assert any("target_plugin_slug" in e for e in errs)


def test_main_missing_file_returns_usage_error(tmp_path, handoff):
    """存在しない handoff パスは usage error (exit 2) を返す。"""
    assert handoff.main([str(tmp_path / "does-not-exist.json")]) == 2


def test_main_invalid_json_returns_usage_error(tmp_path, handoff):
    """壊れた JSON は _load_json の ValueError 経由で usage error (exit 2) になる。"""
    bad = tmp_path / "handoff-run-plugin-dev-plan.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    assert handoff.main([str(bad)]) == 2


def test_main_validation_error_returns_one(tmp_path, handoff):
    """検証エラーを持つ handoff は main が stderr へ出力し exit 1 を返す。"""
    path, data = _write_plan(tmp_path)
    data["routes"][0]["builder"] = "run-build-skill"  # skill は run-skill-create であるべき
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    assert handoff.main([str(path)]) == 1


def test_relative_plan_dir_is_cwd_independent(monkeypatch, tmp_path, handoff):
    """相対 plan_dir フィールド (repo-root 相対 metadata) を持つ handoff でも、cwd に依存せず
    handoff ファイルの所在 (= PLAN_DIR) を基準に spec を解決する。

    回帰防止: 旧実装は相対 plan_dir を Path.cwd() で再構成していたため、skill dir cwd の CI
    から実行すると plan_dir が二重化して spec を見失っていた (creator-kit-ci の nested-test
    収集で露呈)。本テストは無関係な cwd から実行しても exit0 になることを固定する。
    """
    # 参照 phase ファイル (phase-05-implementation.md) は handoff と同じ tmp_path に在るが、
    # plan_dir フィールドは repo-root 相対の metadata 値にする。
    path, data = _write_plan(tmp_path, {"plan_dir": "eval-log/some-plugin/plan"})
    monkeypatch.chdir(tmp_path.parent)  # repo-root でも skill dir でもない無関係 cwd
    assert handoff.main([str(path)]) == 0
    assert handoff.validate_handoff(data, path) == []
