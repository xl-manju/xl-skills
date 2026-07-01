"""DEF-3 / DEF-2 回帰固定 (per-phase 転換版)。

DEF-3 (minimal-omission golden): 単一 skill + 非 skill surface を omitted_reason 付きで
正当省略した最小 plan (inventory + 13 phase + index) が決定論ゲート (surface-inventory /
detect-unassigned / matrix-coverage / spec-frontmatter / spec-gates) を全 exit0 で通ることを固定する。

DEF-2 (OUT2 round-trip readiness): sample-plan の inventory の skill component が skill-brief
base required + kind 別 conditional required を漏れなく携帯する (無加工で skill-brief instance へ
写せる) ことを specfm 正本に照らして固定する。
"""
from __future__ import annotations

import json
from pathlib import Path

from conftest import component_entry, write_all_phases, write_inventory, write_phase_index

_PLAN = Path(__file__).resolve().parent.parent / "examples" / "sample-plan"


def _write_minimal_plan(tmp_path):
    """tmp_path に最小 plan (inventory + 13 phase + index) を生成する。"""
    inventory = write_inventory(tmp_path, [component_entry("C01", "skill", skill_kind="run")])
    write_all_phases(tmp_path, entities_by_phase={2: ["C01"], 5: ["C01"]})
    write_phase_index(tmp_path, plugin_meta=True)
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


def test_sample_skill_components_roundtrip_to_skill_brief_required(specfm_mod):
    """sample-plan の inventory skill component が skill-brief 必須フィールドを欠落 0 で携帯する (DEF-2)。

    skill-brief instance へ無加工で写せる = base required (specfm.SKILL_BRIEF_FIELDS) +
    kind 別 conditional required (specfm.skill_conditional_required) を全充足。
    """
    data = json.loads((_PLAN / "component-inventory.json").read_text(encoding="utf-8"))
    skills = [c for c in data.get("components", [])
              if isinstance(c, dict) and str(c.get("component_kind", "")).strip() == "skill"]
    assert skills, "sample-plan inventory に skill component が無い"
    for c in skills:
        kind = specfm_mod._skill_kind_of(c)
        required = set(specfm_mod.SKILL_BRIEF_FIELDS) | set(specfm_mod.skill_conditional_required(kind))
        missing = sorted(f for f in required if f not in c)
        assert not missing, f"{c.get('id')}: skill-brief 必須フィールド欠落 (round-trip 不可): {missing}"
