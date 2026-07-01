from __future__ import annotations

import json

from conftest import component_entry


def _valid_inventory() -> dict:
    return {
        "considered_component_kinds": ["skill", "sub-agent", "slash-command", "hook", "script"],
        "components": [component_entry("C01", "skill", skill_kind="run")],
        "plugin_level_surfaces": {
            "manifest": {"required": True, "path": ".claude-plugin/plugin.json"},
            "composition": {"required": True, "path": "plugin-composition.yaml"},
            "harness_eval": {"required": True, "path": "EVALS.json"},
            "references_config_assets": {"required": False, "omitted_reason": "No shared references needed"},
            "schemas": {"required": False, "omitted_reason": "No standalone JSON schema needed"},
            "vendor": {"required": False, "omitted_reason": "No cross-plugin SSOT to vendor"},
            "mcp_app_connector": {"required": False, "omitted_reason": "No MCP/app connector needed"},
        },
    }


def test_surface_inventory_accepts_considered_all_and_minimal_components(tmp_path, surfaces):
    inventory = tmp_path / "component-inventory.json"
    inventory.write_text(json.dumps(_valid_inventory(), ensure_ascii=False), encoding="utf-8")

    assert surfaces.main([str(inventory)]) == 0


def test_surface_inventory_rejects_missing_considered_kind(tmp_path, surfaces):
    data = _valid_inventory()
    data["considered_component_kinds"] = ["skill"]
    inventory = tmp_path / "component-inventory.json"
    inventory.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    assert surfaces.main([str(inventory)]) == 1


def test_surface_inventory_rejects_omission_without_reason(tmp_path, surfaces):
    data = _valid_inventory()
    data["plugin_level_surfaces"]["mcp_app_connector"] = {"required": False}
    inventory = tmp_path / "component-inventory.json"
    inventory.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    assert surfaces.main([str(inventory)]) == 1


def test_surface_inventory_rejects_invalid_component(tmp_path, surfaces):
    """per-phase 転換: 各 component は validate_inventory_component で検証される
    (build_target 欠落など shape 不備を surface-inventory も弾く)。"""
    data = _valid_inventory()
    data["components"] = [component_entry("C01", "skill", drop=["build_target"])]
    inventory = tmp_path / "component-inventory.json"
    inventory.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    assert surfaces.main([str(inventory)]) == 1
