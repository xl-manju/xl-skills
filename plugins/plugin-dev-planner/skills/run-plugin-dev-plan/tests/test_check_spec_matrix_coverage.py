"""check-spec-matrix-coverage.py の機能テスト (43行 operationalize 被覆)。"""
from __future__ import annotations

from conftest import write_component_spec, write_index


def test_classify_counts(matrix):
    counts = matrix.classify_counts()
    assert counts == {"OP": 10, "conditional": 16, "N-A": 17}
    assert sum(counts.values()) == 43


def test_classify_membership(matrix):
    # 件数でなく行 ID 集合を完全一致で固定 (分類すり替えを検出)
    c = matrix.current_classification()
    op = {r for r, k in c.items() if k == "OP"}
    cond = {r for r, k in c.items() if k == "conditional"}
    na = {r for r, k in c.items() if k == "N-A"}
    assert op == {"A1", "A5", "A8", "C1", "C2", "F1", "F2", "F3", "F4", "F6"}
    assert cond == {"A7", "A10", "F5", "F7", "D6", "B1", "D1", "D2", "D5",
                    "A11", "E5", "E6", "E1", "E2", "G1", "G2"}
    assert na == {"A2", "A3", "A4", "A6", "A9", "B2", "B3", "C3", "C4",
                  "D3", "D4", "E3", "E4", "G3", "G4", "G5", "G6"}
    assert matrix.membership_drift() == []  # 現行 ROWS は固定集合と一致


def test_membership_drift_detects_count_neutral_swap(matrix):
    # OP の A1 を N-A へ、N-A の A2 を OP へ 1:1 入替 → 件数 {10,16,17} 不変だが集合 drift
    c = matrix.current_classification()
    c["A1"], c["A2"] = "N-A", "OP"
    counts = {"OP": sum(v == "OP" for v in c.values()),
              "conditional": sum(v == "conditional" for v in c.values()),
              "N-A": sum(v == "N-A" for v in c.values())}
    assert counts == {"OP": 10, "conditional": 16, "N-A": 17}  # 件数は不変
    drift = matrix.membership_drift(c)
    assert drift  # 集合ガードは入替を検出する
    assert any("OP" in d for d in drift) and any("N-A" in d for d in drift)


def test_self_test_includes_membership(matrix):
    code, msgs = matrix.self_test(matrix._DEFAULT_MATRIX)
    assert code == 0 and msgs == []  # 43 行一致 + 集合一致


def test_rows_table_has_43(matrix):
    assert len(matrix.ROWS) == 43


def test_self_test_against_reflection(matrix):
    code, msgs = matrix.self_test(matrix._DEFAULT_MATRIX)
    assert code == 0, msgs


def test_self_test_drift(tmp_path, matrix):
    bad = tmp_path / "m.md"
    bad.write_text("| A1 | x |\n| ZZ9 | y |\n", encoding="utf-8")
    code, msgs = matrix.self_test(bad)
    assert code == 1 and msgs


def test_parse_matrix_ids(matrix):
    ids = matrix.parse_matrix_ids("| A1 | x |\n| B2 | y |\nnoise\n| g | z |\n")
    assert ids == ["A1", "B2"]


def test_has_dotted(matrix):
    d = {"quality_gates": {"evaluator": {"threshold": 80}}}
    assert matrix._has(d, "quality_gates.evaluator")
    assert matrix._has(d, "quality_gates.evaluator.threshold")
    assert not matrix._has(d, "quality_gates.missing")
    assert not matrix._has({"k": ""}, "k")  # 空文字は不在扱い
    assert not matrix._has({"k": None}, "k")  # None も不在
    # 明示的に置かれた空コンテナは addressed (値域の正否は gates の責務)
    assert matrix._has({"k": []}, "k")
    assert matrix._has({"k": {}}, "k")


def test_check_spec_coverage_skill_clean(tmp_path, matrix, specfm_mod):
    p = write_component_spec(tmp_path, "C01", "skill", skill_kind="run")
    fm = specfm_mod.parse_frontmatter(p.read_text(encoding="utf-8"))
    assert matrix.check_spec_coverage(fm) == []


def test_check_spec_coverage_hook_only_op(tmp_path, matrix, specfm_mod):
    # hook は OP-ALWAYS アンカーのみ要求 (skill 専用行は適用されない)
    p = write_component_spec(tmp_path, "C01", "hook")
    fm = specfm_mod.parse_frontmatter(p.read_text(encoding="utf-8"))
    assert matrix.check_spec_coverage(fm) == []


def test_check_spec_coverage_skill_missing_goal_seek(tmp_path, matrix, specfm_mod):
    p = write_component_spec(tmp_path, "C01", "skill", skill_kind="run", drop=["goal_seek"])
    fm = specfm_mod.parse_frontmatter(p.read_text(encoding="utf-8"))
    missing = matrix.check_spec_coverage(fm)
    # D1/D2/D5 が goal_seek 欠落で未反映になる
    assert any(m.startswith("D1") for m in missing)
    assert any("goal_seek" in m for m in missing)


def test_check_spec_coverage_prompt_layer_required_for_run(tmp_path, matrix, specfm_mod):
    p = write_component_spec(tmp_path, "C01", "skill", skill_kind="run", drop=["prompt_layer"])
    fm = specfm_mod.parse_frontmatter(p.read_text(encoding="utf-8"))
    assert any("prompt_layer" in m for m in matrix.check_spec_coverage(fm))


def test_knowledge_loop_only_when_feature(tmp_path, matrix, specfm_mod):
    # 通常 (feature なし) は G1 非適用
    p1 = write_component_spec(tmp_path, "C01", "skill")
    fm1 = specfm_mod.parse_frontmatter(p1.read_text(encoding="utf-8"))
    assert not any(m.startswith("G1") for m in matrix.check_spec_coverage(fm1))
    # feature opt-in だが knowledge_loop キー欠落 → G1 未反映
    p2 = write_component_spec(tmp_path, "C02", "skill", features=["knowledge_loop"])
    fm2 = specfm_mod.parse_frontmatter(p2.read_text(encoding="utf-8"))
    assert any(m.startswith("G1") for m in matrix.check_spec_coverage(fm2))


def test_check_plugin_coverage_clean_and_missing(matrix):
    full = {"distribution": {"distributable": False, "bundles": ["none"]},
            "pkg_contract": {"x": 1}, "governance": {"x": 1}, "ci": {"x": 1},
            "ssot_dedup": {"x": 1}, "feedback_deploy": {"x": 1}}
    assert matrix.check_plugin_coverage(full) == []
    missing = matrix.check_plugin_coverage({})
    ids = {m.split()[0] for m in missing}
    assert {"F3", "F4", "F6", "A7", "A10", "F5", "F7", "D6"} <= ids


def test_run_clean(tmp_path, matrix, capsys):
    write_component_spec(tmp_path, "C01", "skill", skill_kind="run")
    write_component_spec(tmp_path, "C02", "hook")
    write_index(tmp_path, ["C01", "C02"], plugin_meta=True)
    code, findings, counts = matrix.run(tmp_path, "index.md")
    assert code == 0, findings
    assert counts["OP"] == 10


def test_run_plugin_meta_missing(tmp_path, matrix):
    write_component_spec(tmp_path, "C01", "skill")
    write_index(tmp_path, ["C01"], plugin_meta=False)
    code, findings, counts = matrix.run(tmp_path, "index.md")
    assert code == 1
    assert any("plugin-level" in f for f in findings)


def test_run_missing_index(tmp_path, matrix):
    write_component_spec(tmp_path, "C01", "skill")
    code, findings, counts = matrix.run(tmp_path, "index.md")
    assert code == 2


def test_run_no_specs(tmp_path, matrix):
    write_index(tmp_path, [])
    code, findings, counts = matrix.run(tmp_path, "index.md")
    assert code == 2


def test_main_self_test(matrix, capsys):
    assert matrix.main(["--self-test"]) == 0
    assert "drift なし" in capsys.readouterr().out


def test_main_self_test_fail(tmp_path, matrix):
    bad = tmp_path / "m.md"
    bad.write_text("| ZZ9 | y |\n", encoding="utf-8")
    assert matrix.main(["--self-test", "--matrix", str(bad)]) == 1


def test_main_clean(tmp_path, matrix, capsys):
    write_component_spec(tmp_path, "C01", "skill", skill_kind="run")
    write_index(tmp_path, ["C01"], plugin_meta=True)
    assert matrix.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "OP=10" in out and "conditional=16" in out and "N-A=17" in out


def test_main_violation(tmp_path, matrix, capsys):
    write_component_spec(tmp_path, "C01", "skill")
    write_index(tmp_path, ["C01"], plugin_meta=False)
    assert matrix.main([str(tmp_path)]) == 1


def test_main_no_plan_dir(matrix):
    assert matrix.main([]) == 2


def test_main_not_a_dir(tmp_path, matrix):
    f = tmp_path / "x.txt"
    f.write_text("x", encoding="utf-8")
    assert matrix.main([str(f)]) == 2


def test_main_missing_index_exit2(tmp_path, matrix):
    write_component_spec(tmp_path, "C01", "skill")
    assert matrix.main([str(tmp_path)]) == 2
