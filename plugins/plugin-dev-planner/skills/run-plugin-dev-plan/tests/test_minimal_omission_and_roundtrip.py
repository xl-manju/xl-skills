"""DEF-3 / DEF-2 回帰固定 (2026-06-30 elegant-review)。

DEF-3 (minimal-omission golden): 現 examples/sample-plan は 5 component_kind 全 present の
ゴールデンのみで、「正しく省略した最小 plan も合格する」中心仮説が end-to-end で未実証だった。
本テストは単一 skill + 非 skill surface を omitted_reason 付きで正当省略した最小 plan が
決定論ゲート (surface-inventory / detect-unassigned / matrix-coverage / spec-frontmatter /
spec-gates) を全 exit0 で通ることを固定する (omission without reason の負例は
test_check_surface_inventory.py が単体で担保する二層)。

DEF-2 (OUT2 round-trip readiness): test_schema_parity.py はフィールド集合 parity のみで、
生成済み skill spec の frontmatter が skill-brief instance へ無加工で写せる (= 必須フィールド
欠落 0) かの instance-level 検証が無かった。jsonschema 非依存 (本 plugin は stdlib 正本) で、
sample-plan の skill spec が skill-brief base required + kind 別 conditional required を
漏れなく携帯することを specfm 正本に照らして固定する。
"""
from __future__ import annotations

import json
from pathlib import Path

from conftest import write_component_spec, write_index

_PLAN = Path(__file__).resolve().parent.parent / "examples" / "sample-plan"


def _minimal_inventory() -> dict:
    """単一 skill + 全 kind 検討済 + 非 skill surface を理由付き省略した最小 inventory。"""
    return {
        "considered_component_kinds": ["skill", "sub-agent", "slash-command", "hook", "script"],
        "force_13": False,
        "components": [
            {
                "id": "C01",
                "component_kind": "skill",
                "kind": "run",
                "name": "run-minimal",
                "depends_on": [],
                "build_target": "plugins/minimal/skills/run-minimal/",
            }
        ],
        "plugin_level_surfaces": {
            "manifest": {"required": True, "path": ".claude-plugin/plugin.json"},
            "composition": {"required": True, "path": "plugin-composition.yaml"},
            "harness_eval": {"required": True, "path": "EVALS.json"},
            "references_config_assets": {"required": False, "omitted_reason": "共有 references 不要 (単一 skill)"},
            "mcp_app_connector": {"required": False, "omitted_reason": "MCP/app connector 不要"},
        },
    }


def _write_minimal_plan(tmp_path) -> tuple[Path, Path]:
    """tmp_path に最小 plan (inventory + 1 skill spec + index) を生成する。"""
    inventory = tmp_path / "component-inventory.json"
    inventory.write_text(json.dumps(_minimal_inventory(), ensure_ascii=False), encoding="utf-8")
    write_component_spec(tmp_path, "C01", "skill", skill_kind="run")
    write_index(tmp_path, ["C01"])
    return tmp_path, inventory


def test_minimal_omission_plan_passes_all_deterministic_gates(
    tmp_path, surfaces, unassigned, matrix, gates, specfm
):
    """単一 skill + 理由付き surface 省略の最小 plan が全決定論ゲートを exit0 で通る (DEF-3)。"""
    plan_dir, inventory = _write_minimal_plan(tmp_path)
    assert surfaces.main([str(inventory)]) == 0, "surface-inventory が正当な最小省略を拒否"
    assert unassigned.main(["--inventory", str(inventory), "--specs-dir", str(plan_dir)]) == 0
    assert matrix.main([str(plan_dir)]) == 0, "matrix-coverage が最小 plan を拒否"
    assert gates.main(["--specs-dir", str(plan_dir)]) == 0
    assert specfm.main(["--specs-dir", str(plan_dir)]) == 0


def test_sample_skill_specs_roundtrip_to_skill_brief_required(specfm_mod):
    """sample-plan の skill spec frontmatter が skill-brief 必須フィールドを欠落 0 で携帯する (DEF-2)。

    skill-brief instance へ無加工で写せる = base required (specfm.SKILL_BRIEF_FIELDS) +
    kind 別 conditional required (specfm.skill_conditional_required) を全充足。
    """
    skill_specs = []
    for p in _PLAN.glob("*.md"):
        if p.stem in {"index", "main"}:
            continue
        fm = specfm_mod.parse_frontmatter(p.read_text(encoding="utf-8"))
        if str(fm.get("component_kind", "")).strip() == "skill":
            skill_specs.append((p, fm))
    assert skill_specs, "sample-plan に skill component_kind の spec が無い"
    for p, fm in skill_specs:
        kind = str(fm.get("kind", "")).strip()
        required = set(specfm_mod.SKILL_BRIEF_FIELDS) | set(specfm_mod.skill_conditional_required(kind))
        missing = sorted(f for f in required if f not in fm)
        assert not missing, f"{p.name}: skill-brief 必須フィールド欠落 (round-trip 不可): {missing}"
