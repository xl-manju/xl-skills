"""examples/sample-plan ゴールデン出力が core 5 scripts / 6 invocations + handoff gate を全 exit0 で通ることを固定する。

これにより「マトリクスが精緻でも、その通りに spec を生成し検査を通せるか」という
最大の未実証点を回帰防止する (生成物の実例 = 完全性の可視化)。ゴールデンが drift して
検査に落ちたら本テストが fail する。
"""
from __future__ import annotations

from pathlib import Path

import pytest

PLAN = Path(__file__).resolve().parent.parent / "examples" / "sample-plan"
INVENTORY = PLAN / "component-inventory.json"
HANDOFF = PLAN / "handoff-run-plugin-dev-plan.json"
GOAL_SPEC = PLAN / "goal-spec.json"


def test_example_plan_dir_exists():
    assert PLAN.is_dir(), f"ゴールデン plan ディレクトリが無い: {PLAN}"
    assert (PLAN / "index.md").is_file()
    assert GOAL_SPEC.is_file()
    assert INVENTORY.is_file()
    assert HANDOFF.is_file()
    # 5 component_kind を網羅 (skill 偏重でない実例) + index
    specs = sorted(p.name for p in PLAN.glob("*.md"))
    assert len(specs) == 6, specs  # index + 5 specs


def test_frontmatter_gate(specfm):
    assert specfm.main(["--specs-dir", str(PLAN)]) == 0


def test_plugin_goal_spec_gate(plugin_goal_spec):
    assert plugin_goal_spec.main([str(GOAL_SPEC)]) == 0


def test_gates_gate(gates):
    assert gates.main(["--specs-dir", str(PLAN)]) == 0


def test_topsort_gate(topsort):
    assert topsort.main([str(PLAN)]) == 0


def test_unassigned_gate(unassigned):
    assert unassigned.main(["--inventory", str(INVENTORY), "--specs-dir", str(PLAN)]) == 0


def test_matrix_coverage_gate(matrix):
    assert matrix.main([str(PLAN)]) == 0


def test_build_handoff_gate(handoff):
    assert handoff.main([str(HANDOFF)]) == 0


def test_surface_inventory_gate(surfaces):
    assert surfaces.main([str(INVENTORY)]) == 0


def test_all_five_component_kinds_present(specfm_mod):
    """ゴールデンが 5 種の component_kind を 1 本ずつ持つ (skill 偏重の解消を実証)。"""
    kinds = set()
    for p in PLAN.glob("*.md"):
        fm = specfm_mod.parse_frontmatter(p.read_text(encoding="utf-8"))
        ck = str(fm.get("component_kind", "")).strip()
        if ck:
            kinds.add(ck)
    assert kinds == {"skill", "sub-agent", "slash-command", "hook", "script"}, kinds
