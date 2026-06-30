"""check-spec-gates.py の機能テスト (quality_gates / harness 深掘り検証)。"""
from __future__ import annotations

from conftest import (
    write_component_spec,
    write_index,
    valid_quality_gates,
    valid_plugin_meta,
)


def test_clean_skill(tmp_path, gates):
    p = write_component_spec(tmp_path, "C01", "skill")
    assert gates.check_gates(p.read_text(encoding="utf-8")) == []


def test_clean_each_kind(tmp_path, gates):
    for ck in ("sub-agent", "slash-command", "hook", "script"):
        p = write_component_spec(tmp_path, "C01", ck)
        assert gates.check_gates(p.read_text(encoding="utf-8")) == [], ck


def test_no_frontmatter(gates):
    assert gates.check_gates("plain") == ["frontmatter (--- ブロック) が無い"]


def test_missing_component_kind(gates):
    assert any("未宣言" in e for e in gates.check_gates("---\nid: C01\n---\n"))


def test_missing_quality_gates(tmp_path, gates):
    p = write_component_spec(tmp_path, "C01", "skill", drop=["quality_gates"])
    assert any("quality_gates ブロックが無い" in e for e in gates.check_gates(p.read_text(encoding="utf-8")))


def test_p0_lint_incomplete(tmp_path, gates):
    qg = valid_quality_gates("skill")
    qg["p0_lint"] = ["lint-skill-name"]  # 8 本に満たない
    p = write_component_spec(tmp_path, "C01", "skill", overrides={"quality_gates": qg})
    assert any("p0_lint が必須 lint を欠く" in e for e in gates.check_gates(p.read_text(encoding="utf-8")))


def test_build_trace_not_required(tmp_path, gates):
    qg = valid_quality_gates("skill")
    qg["build_trace"] = "optional"
    p = write_component_spec(tmp_path, "C01", "skill", overrides={"quality_gates": qg})
    assert any("build_trace は 'required'" in e for e in gates.check_gates(p.read_text(encoding="utf-8")))


def test_elegant_review_bad(tmp_path, gates):
    qg = valid_quality_gates("skill")
    qg["elegant_review"] = {"conditions": ["C1", "C2"], "all_pass": False}
    p = write_component_spec(tmp_path, "C01", "skill", overrides={"quality_gates": qg})
    errs = gates.check_gates(p.read_text(encoding="utf-8"))
    assert any("conditions は" in e for e in errs)
    assert any("all_pass は true" in e for e in errs)


def test_elegant_review_missing(tmp_path, gates):
    qg = valid_quality_gates("skill")
    del qg["elegant_review"]
    p = write_component_spec(tmp_path, "C01", "skill", overrides={"quality_gates": qg})
    assert any("elegant_review ブロックが無い" in e for e in gates.check_gates(p.read_text(encoding="utf-8")))


def test_content_review_bad(tmp_path, gates):
    qg = valid_quality_gates("skill")
    qg["content_review"] = {"verdict": "FAIL", "sha_match": False}
    p = write_component_spec(tmp_path, "C01", "skill", overrides={"quality_gates": qg})
    errs = gates.check_gates(p.read_text(encoding="utf-8"))
    assert any("verdict は PASS" in e for e in errs)
    assert any("sha_match は true" in e for e in errs)


def test_content_review_missing(tmp_path, gates):
    qg = valid_quality_gates("skill")
    del qg["content_review"]
    p = write_component_spec(tmp_path, "C01", "skill", overrides={"quality_gates": qg})
    assert any("content_review ブロックが無い" in e for e in gates.check_gates(p.read_text(encoding="utf-8")))


def test_evaluator_bad(tmp_path, gates):
    qg = valid_quality_gates("skill")
    qg["evaluator"] = {"threshold": 70, "high_max": 2}
    p = write_component_spec(tmp_path, "C01", "skill", overrides={"quality_gates": qg})
    errs = gates.check_gates(p.read_text(encoding="utf-8"))
    assert any("threshold は >=80" in e for e in errs)
    assert any("high_max は 0" in e for e in errs)


def test_evaluator_missing(tmp_path, gates):
    qg = valid_quality_gates("skill")
    del qg["evaluator"]
    p = write_component_spec(tmp_path, "C01", "skill", overrides={"quality_gates": qg})
    assert any("evaluator ブロックが無い" in e for e in gates.check_gates(p.read_text(encoding="utf-8")))


def test_harness_low(tmp_path, gates):
    p = write_component_spec(tmp_path, "C01", "skill", overrides={"harness_coverage": {"min": 50, "kind_pass": "x"}})
    assert any("harness_coverage.min は >=80" in e for e in gates.check_gates(p.read_text(encoding="utf-8")))


def test_harness_no_kind_pass(tmp_path, gates):
    p = write_component_spec(tmp_path, "C01", "skill", overrides={"harness_coverage": {"min": 90}})
    assert any("kind_pass が空" in e for e in gates.check_gates(p.read_text(encoding="utf-8")))


def test_harness_missing(tmp_path, gates):
    p = write_component_spec(tmp_path, "C01", "skill", drop=["harness_coverage"])
    assert any("harness_coverage ブロックが無い" in e for e in gates.check_gates(p.read_text(encoding="utf-8")))


def test_main_ok(tmp_path, gates, capsys):
    write_component_spec(tmp_path, "C01", "skill")
    write_component_spec(tmp_path, "C02", "hook")
    assert gates.main(["--specs-dir", str(tmp_path)]) == 0
    assert "OK" in capsys.readouterr().out


def test_main_violation(tmp_path, gates, capsys):
    write_component_spec(tmp_path, "C01", "skill", drop=["quality_gates"])
    assert gates.main(["--specs-dir", str(tmp_path)]) == 1
    assert "quality_gates" in capsys.readouterr().err


def test_main_explicit_file(tmp_path, gates):
    p = write_component_spec(tmp_path, "C01", "script")
    assert gates.main([str(p)]) == 0


def test_main_no_args(gates):
    assert gates.main([]) == 2


def test_main_specs_dir_not_dir(tmp_path, gates):
    assert gates.main(["--specs-dir", str(tmp_path / "nope")]) == 2


def test_main_file_not_found(tmp_path, gates):
    assert gates.main([str(tmp_path / "ghost.md")]) == 2


# ── 項目2: 構造キーの値検証 ──────────────────────────────────────────
def test_script_tests_min_too_low(tmp_path, gates):
    p = write_component_spec(tmp_path, "C01", "script", overrides={"tests_min": 50})
    assert any("tests_min は >=80" in e for e in gates.check_gates(p.read_text(encoding="utf-8")))


def test_harness_kind_pass_mismatch(tmp_path, gates):
    # skill run なのに kind_pass が ref 用語だけ → kind と無関係で弾く
    p = write_component_spec(
        tmp_path, "C01", "skill", skill_kind="run",
        overrides={"harness_coverage": {"min": 80, "kind_pass": "source-traceability-only"}},
    )
    assert any("kind と無関係" in e for e in gates.check_gates(p.read_text(encoding="utf-8")))


def test_harness_kind_pass_ref_ok(tmp_path, gates):
    p = write_component_spec(tmp_path, "C01", "skill", skill_kind="ref")
    # ref の clean spec (kind_pass=source-traceability+ref-review) は kind_pass 整合 OK
    errs = [e for e in gates.check_gates(p.read_text(encoding="utf-8")) if "kind_pass" in e]
    assert errs == []


# ── 項目1: plugin_meta 値域検証 ──────────────────────────────────────
def test_plugin_meta_clean(gates):
    assert gates.check_plugin_meta(valid_plugin_meta(distributable=False)) == []
    assert gates.check_plugin_meta(valid_plugin_meta(distributable=True)) == []


def test_plugin_meta_conditional_na_with_reason_ok(gates):
    """条件付きキーは {applicable: false, reason: <非空>} で明示 N/A 可 (A7 整合)。"""
    pm = valid_plugin_meta(distributable=False)
    pm["pkg_contract"] = {"applicable": False, "reason": "単一 skill・PKG packaging 不要"}
    pm["governance"] = {"applicable": False, "reason": "rubric 改訂を伴わない"}
    pm["feedback_deploy"] = {"applicable": False, "reason": "loop-kind skill 不在"}
    assert gates.check_plugin_meta(pm) == []


def test_plugin_meta_conditional_na_without_reason_fails(gates):
    """applicable:false で reason 欠落/空は N/A 根拠不足としてエラー。"""
    pm = valid_plugin_meta(distributable=False)
    pm["pkg_contract"] = {"applicable": False}  # reason なし
    pm["governance"] = {"applicable": False, "reason": "  "}  # 空白のみ
    errs = gates.check_plugin_meta(pm)
    assert any("pkg_contract が applicable:false だが reason が空" in e for e in errs)
    assert any("governance が applicable:false だが reason が空" in e for e in errs)


def test_plugin_meta_core_na_not_allowed(gates):
    """コアキー (ci) は applicable:false を許さず非空 dict 必須のまま。"""
    pm = valid_plugin_meta(distributable=False)
    pm["ci"] = {"applicable": False, "reason": "x"}  # core は N/A 不可だが非空 dict ではある
    # ci は core ゆえ applicable:false でも「非空 dict」判定は通る (N/A 概念を持たない)。
    # 設計意図: core は常に実体を要求。ここでは非空 dict なのでエラーにはならないが、
    # conditional と違い reason ゲートも N/A 緩和も適用されないことを確認する。
    errs = gates.check_plugin_meta(pm)
    assert not any("ci" in e for e in errs)
    pm["ci"] = {}  # 空 dict は core でエラー
    assert any("plugin_meta.ci が非空 dict でない" in e for e in gates.check_plugin_meta(pm))


def test_plugin_meta_conditional_missing_fails(gates):
    """条件付きキーの欠落/空は (N/A 明示でないため) エラー。"""
    pm = valid_plugin_meta(distributable=False)
    del pm["pkg_contract"]
    assert any("pkg_contract が非空 dict でない" in e for e in gates.check_plugin_meta(pm))


def test_plugin_meta_distributable_not_bool(gates):
    pm = valid_plugin_meta()
    pm["distribution"]["distributable"] = "false"  # 文字列
    assert any("distributable は bool" in e for e in gates.check_plugin_meta(pm))


def test_plugin_meta_false_but_bundles_nonempty(gates):
    pm = valid_plugin_meta(distributable=False)
    pm["distribution"]["bundles"] = ["xl-skills-full"]
    errs = gates.check_plugin_meta(pm)
    assert any("bundles 非空" in e for e in errs)


def test_plugin_meta_false_but_marketplace_true(gates):
    pm = valid_plugin_meta(distributable=False)
    pm["distribution"]["marketplace"] = True
    assert any("marketplace" in e for e in gates.check_plugin_meta(pm))


def test_plugin_meta_true_but_empty_bundles(gates):
    pm = valid_plugin_meta(distributable=True)
    pm["distribution"]["bundles"] = []
    assert any("bundles が空" in e for e in gates.check_plugin_meta(pm))


def test_plugin_meta_distribution_not_dict(gates):
    assert any("distribution が dict でない" in e for e in gates.check_plugin_meta({"distribution": "x"}))


def test_plugin_meta_manifest_contract(gates):
    pm = valid_plugin_meta()
    pm["manifest"]["path"] = "plugin.json"
    pm["manifest"]["validate_plugin"] = False
    errs = gates.check_plugin_meta(pm)
    assert any("manifest.path" in e for e in errs)
    assert any("manifest.validate_plugin" in e for e in errs)


def test_plugin_meta_marketplace_policy_contract(gates):
    pm = valid_plugin_meta()
    pm["marketplace"]["policy"]["installation"] = "MAYBE"
    pm["marketplace"]["policy"]["authentication"] = "LATER"
    pm["marketplace"]["policy"]["category"] = ""
    pm["marketplace"]["cachebuster_for_update"] = False
    errs = gates.check_plugin_meta(pm)
    assert any("policy.installation" in e for e in errs)
    assert any("policy.authentication" in e for e in errs)
    assert any("policy.category" in e for e in errs)
    assert any("cachebuster_for_update" in e for e in errs)


def test_plugin_meta_missing_required_dict(gates):
    pm = valid_plugin_meta()
    del pm["ci"]
    pm["governance"] = {}  # 空 dict も不可
    errs = gates.check_plugin_meta(pm)
    assert any("plugin_meta.ci" in e for e in errs)
    assert any("plugin_meta.governance" in e for e in errs)


def test_run_validates_index_plugin_meta_clean(tmp_path, gates):
    write_component_spec(tmp_path, "C01", "skill")
    write_index(tmp_path, ["C01"], plugin_meta=True)  # 非配布 (bundles 空) airtight
    assert gates.main(["--specs-dir", str(tmp_path)]) == 0


def test_run_validates_index_plugin_meta_violation(tmp_path, gates, capsys):
    write_component_spec(tmp_path, "C01", "skill")
    write_index(tmp_path, ["C01"], plugin_meta=True, distributable=False)
    # index を改竄: 非配布なのに bundles を足す
    idx = tmp_path / "index.md"
    idx.write_text(idx.read_text(encoding="utf-8").replace("bundles: []", "bundles: [xl-skills-full]"), encoding="utf-8")
    assert gates.main(["--specs-dir", str(tmp_path)]) == 1
    assert "bundles 非空" in capsys.readouterr().err
