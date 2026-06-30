"""check-spec-frontmatter.py の機能テスト (component_kind 別分岐)。"""
from __future__ import annotations

from conftest import write_component_spec


def test_clean_skill_run(tmp_path, specfm):
    p = write_component_spec(tmp_path, "C01", "skill", skill_kind="run")
    assert specfm.check_spec(p.read_text(encoding="utf-8")) == []


def test_clean_each_component_kind(tmp_path, specfm):
    for ck in ("sub-agent", "slash-command", "hook", "script"):
        p = write_component_spec(tmp_path, "C01", ck)
        assert specfm.check_spec(p.read_text(encoding="utf-8")) == [], ck


def test_clean_skill_ref_no_criteria_required(tmp_path, specfm):
    p = write_component_spec(tmp_path, "C01", "skill", skill_kind="ref")
    assert specfm.check_spec(p.read_text(encoding="utf-8")) == []


def test_no_frontmatter(specfm):
    assert specfm.check_spec("plain text") == ["frontmatter (--- ブロック) が無い"]


def test_missing_component_kind(specfm):
    text = "---\nid: C01\nkind: run\n---\n"
    errs = specfm.check_spec(text)
    assert any("component_kind が未宣言" in e for e in errs)


def test_bad_component_kind(specfm):
    text = "---\nid: C01\ncomponent_kind: widget\n---\n"
    errs = specfm.check_spec(text)
    assert any("enum 外" in e for e in errs)


def test_skill_missing_brief_field(tmp_path, specfm):
    p = write_component_spec(tmp_path, "C01", "skill", drop=["boundary"])
    errs = specfm.check_spec(p.read_text(encoding="utf-8"))
    assert any("構造的必須フィールド欠落: boundary" in e for e in errs)


def test_hook_missing_fail_closed(tmp_path, specfm):
    p = write_component_spec(tmp_path, "C01", "hook", drop=["fail_closed"])
    errs = specfm.check_spec(p.read_text(encoding="utf-8"))
    assert any("fail_closed" in e for e in errs)


def test_non_skill_does_not_require_brief_fields(tmp_path, specfm):
    # hook spec に skill-brief 形状 (goal 等) が無くても通る
    p = write_component_spec(tmp_path, "C01", "hook")
    txt = p.read_text(encoding="utf-8")
    assert "goal:" not in txt.split("---")[1]
    assert specfm.check_spec(txt) == []


def test_missing_quality_gates(tmp_path, specfm):
    p = write_component_spec(tmp_path, "C01", "skill", drop=["quality_gates"])
    errs = specfm.check_spec(p.read_text(encoding="utf-8"))
    assert any("quality_gates ブロックが無い" in e for e in errs)


def test_missing_harness(tmp_path, specfm):
    p = write_component_spec(tmp_path, "C01", "skill", drop=["harness_coverage"])
    errs = specfm.check_spec(p.read_text(encoding="utf-8"))
    assert any("harness_coverage ブロックが無い" in e for e in errs)


def test_skill_loop_missing_criteria(tmp_path, specfm):
    p = write_component_spec(tmp_path, "C01", "skill", skill_kind="run", drop=["feedback_contract"])
    errs = specfm.check_spec(p.read_text(encoding="utf-8"))
    assert any("loop kind は feedback_contract.criteria 必須" in e for e in errs)


def test_skill_loop_criteria_must_be_purpose_derived(tmp_path, specfm):
    # goal「観測可能な完了状態」と語彙が重ならない汎用 fallback criteria は弾く (R3 §2.2 機械化)
    p = write_component_spec(
        tmp_path, "C01", "skill", skill_kind="run",
        overrides={"feedback_contract": {"criteria": [
            {"id": "IN1", "loop_scope": "inner", "text": "lint exit0", "verify_by": "lint"},
            {"id": "OUT1", "loop_scope": "outer", "text": "4 条件 PASS", "verify_by": "elegant-review"},
        ]}},
    )
    errs = specfm.check_spec(p.read_text(encoding="utf-8"))
    assert any("purpose 由来でない" in e for e in errs)


def test_skill_loop_purpose_derived_criteria_pass(tmp_path, specfm):
    # 既定 fixture は goal 由来 criteria を携帯し purpose-traceability を満たす
    p = write_component_spec(tmp_path, "C01", "skill", skill_kind="run")
    assert not any("purpose 由来でない" in e for e in specfm.check_spec(p.read_text(encoding="utf-8")))


def test_skill_bad_kind(tmp_path, specfm):
    p = write_component_spec(tmp_path, "C01", "skill", overrides={"kind": "weird"})
    errs = specfm.check_spec(p.read_text(encoding="utf-8"))
    assert any("skill kind enum 外" in e for e in errs)


def test_skill_assign_needs_skip_or_criteria(tmp_path, specfm):
    p = write_component_spec(
        tmp_path, "C01", "skill", skill_kind="assign",
        overrides={"feedback_contract": {"max_iterations": 3}},
    )
    errs = specfm.check_spec(p.read_text(encoding="utf-8"))
    assert any("skip_reason か criteria" in e for e in errs)


def test_collect_skips_index(tmp_path, specfm):
    write_component_spec(tmp_path, "C01", "skill")
    (tmp_path / "index.md").write_text("---\nid: I\n---", encoding="utf-8")
    assert "index" not in [p.stem for p in specfm.collect_specs(tmp_path)]


def test_main_ok(tmp_path, specfm, capsys):
    write_component_spec(tmp_path, "C01", "skill")
    assert specfm.main(["--specs-dir", str(tmp_path)]) == 0
    assert "OK" in capsys.readouterr().out


def test_main_violation(tmp_path, specfm, capsys):
    write_component_spec(tmp_path, "C01", "skill", drop=["quality_gates"])
    assert specfm.main(["--specs-dir", str(tmp_path)]) == 1
    assert "quality_gates" in capsys.readouterr().err


def test_main_explicit_file(tmp_path, specfm):
    p = write_component_spec(tmp_path, "C01", "script")
    assert specfm.main([str(p)]) == 0


def test_main_no_args(specfm):
    assert specfm.main([]) == 2


def test_main_specs_dir_not_dir(tmp_path, specfm):
    assert specfm.main(["--specs-dir", str(tmp_path / "nope")]) == 2


def test_main_file_not_found(tmp_path, specfm):
    assert specfm.main([str(tmp_path / "ghost.md")]) == 2
