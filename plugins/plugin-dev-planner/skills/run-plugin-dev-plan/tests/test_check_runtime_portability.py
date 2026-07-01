"""check-runtime-portability.py の機能テスト (F8 install 携帯性)。

(P) >=2 skill から共有される script は placement_scope=plugin-root 必須。
(Q) 全 component の build_target が plugin 内自己完結 (plugins/ 始まり・.. 不在)。
"""
from __future__ import annotations

from conftest import component_entry, write_inventory


# ─────────────────── skill_consumers / check_inventory (単体) ───────────────────
def test_skill_consumers_counts_distinct_skills(runtime):
    comps = [
        component_entry("C09", "script"),
        component_entry("C01", "skill", depends_on=["C09"]),
        component_entry("C02", "skill", depends_on=["C09"]),
        component_entry("C03", "sub-agent", depends_on=["C09"]),  # skill でない=数えない
    ]
    consumers = runtime.skill_consumers(comps)
    assert consumers["C09"] == {"C01", "C02"}


def test_check_inventory_empty(runtime):
    assert any("components" in e for e in runtime.check_inventory({"components": []}))
    assert any("components" in e for e in runtime.check_inventory({}))


def test_shared_script_must_be_plugin_root(runtime):
    """>=2 skill consumer の script が skill placement のままだと violation。"""
    comps = [
        component_entry("C09", "script"),  # 既定 skill placement
        component_entry("C01", "skill", depends_on=["C09"]),
        component_entry("C02", "skill", depends_on=["C09"]),
    ]
    errs = runtime.check_inventory({"components": comps})
    assert any("C09" in e and "plugin-root" in e for e in errs)


def test_shared_script_plugin_root_ok(runtime):
    """plugin-root へ hoist 済みなら通る (偽陽性なし)。"""
    comps = [
        component_entry("C09", "script", overrides={
            "placement_scope": "plugin-root",
            "build_target": "plugins/sample/scripts/do.py",
        }),
        component_entry("C01", "skill", depends_on=["C09"]),
        component_entry("C02", "skill", depends_on=["C09"]),
    ]
    assert runtime.check_inventory({"components": comps}) == []


def test_single_consumer_script_may_stay_skill(runtime):
    """単一 skill consumer の script は skill placement のまま許容 (畳み込み)。"""
    comps = [
        component_entry("C09", "script"),  # skill placement
        component_entry("C01", "skill", depends_on=["C09"]),
    ]
    assert runtime.check_inventory({"components": comps}) == []


def test_build_target_must_be_self_contained(runtime):
    """build_target が plugins/ で始まらない / .. を含むと violation (Q)。"""
    comps = [component_entry("C01", "skill", overrides={"build_target": "elsewhere/skills/run-x/"})]
    assert any("plugins/" in e for e in runtime.check_inventory({"components": comps}))

    comps2 = [component_entry("C09", "script", overrides={
        "placement_scope": "plugin-root",
        "build_target": "plugins/../secret/scripts/s.py",
    })]
    assert any("自己完結" in e for e in runtime.check_inventory({"components": comps2}))


# ─────────────────── self-test ───────────────────
def test_self_test_passes(runtime):
    code, msgs = runtime._self_test()
    assert code == 0, msgs


def test_main_self_test(runtime, capsys):
    assert runtime.main(["--self-test"]) == 0
    assert "P/Q" in capsys.readouterr().out


# ─────────────────── run / main 統合 ───────────────────
def test_run_clean(tmp_path, runtime):
    comps = [
        component_entry("C09", "script", overrides={
            "placement_scope": "plugin-root", "build_target": "plugins/sample/scripts/do.py"}),
        component_entry("C01", "skill", depends_on=["C09"]),
        component_entry("C02", "skill", depends_on=["C09"]),
    ]
    write_inventory(tmp_path, comps)
    code, errs = runtime.run(tmp_path, None)
    assert code == 0, errs


def test_main_clean(tmp_path, runtime, capsys):
    write_inventory(tmp_path, [component_entry("C01", "skill")])
    assert runtime.main([str(tmp_path)]) == 0
    assert "OK" in capsys.readouterr().out


def test_main_violation(tmp_path, runtime):
    comps = [
        component_entry("C09", "script"),
        component_entry("C01", "skill", depends_on=["C09"]),
        component_entry("C02", "skill", depends_on=["C09"]),
    ]
    write_inventory(tmp_path, comps)
    assert runtime.main([str(tmp_path)]) == 1


def test_main_no_plan_dir(runtime):
    assert runtime.main([]) == 2


def test_main_not_a_dir(tmp_path, runtime):
    f = tmp_path / "x.txt"
    f.write_text("x", encoding="utf-8")
    assert runtime.main([str(f)]) == 2


def test_main_missing_inventory(tmp_path, runtime):
    assert runtime.main([str(tmp_path)]) == 2


def test_run_bad_json(tmp_path, runtime):
    (tmp_path / "component-inventory.json").write_text("{not json", encoding="utf-8")
    code, errs = runtime.run(tmp_path, None)
    assert code == 2 and any("parse error" in e for e in errs)
