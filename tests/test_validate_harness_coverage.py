"""validate-harness-coverage.py の unit テスト (このスクリプト自体を >=80% 行カバレッジで dogfood)。"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "validate_harness_coverage", ROOT / "scripts" / "validate-harness-coverage.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _setup(tmp_path, *, code_pct=None, llm_avg=None, skill_pass=True):
    m = _load()
    m.PLUGINS_DIR = tmp_path / "plugins"
    m.DOC_DIR = tmp_path / "doc"
    m.EVAL_LOG = tmp_path / "eval-log"
    m.EVAL_LOG.mkdir(parents=True, exist_ok=True)
    # 1 skill 構築
    sd = m.PLUGINS_DIR / "p" / "skills" / "run-x"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "SKILL.md").write_text("---\nname: run-x\nkind: run\n---\n", encoding="utf-8")
    (m.PLUGINS_DIR / "p" / "agents").mkdir(parents=True, exist_ok=True)
    (m.PLUGINS_DIR / "p" / "agents" / "a.md").write_text("agent", encoding="utf-8")
    (m.DOC_DIR).mkdir(parents=True, exist_ok=True)
    (m.DOC_DIR / "x.md").write_text("doc", encoding="utf-8")
    if code_pct is not None:
        (m.EVAL_LOG / "code-coverage.json").write_text(
            json.dumps({"totals": {"percent_covered": code_pct}}), encoding="utf-8"
        )
    if llm_avg is not None:
        (m.EVAL_LOG / "llm-coverage.json").write_text(
            json.dumps({"average_coverage_pct": llm_avg}), encoding="utf-8"
        )
    cr = m.EVAL_LOG / "p" / "run-x" / "content-review"
    cr.mkdir(parents=True, exist_ok=True)
    v = "PASS" if skill_pass else "FAIL"
    for n in ("elegance-verdict.json", "rubric-verdict.json"):
        (cr / n).write_text(json.dumps({"verdict": v, "score": 0.95}), encoding="utf-8")
    return m


def test_pct_helper():
    m = _load()
    assert m._pct(2, 4) == 50.0
    assert m._pct(0, 0) == 0.0


def test_report_fail_when_uninstrumented(tmp_path):
    m = _setup(tmp_path, code_pct=95.0, llm_avg=95.0, skill_pass=True)
    rep = m.build_report(80.0)
    # agents/commands/hooks/docs が未計測 → spec_met False
    assert rep["spec_met"] is False
    assert rep["axes_total"] == 12
    assert rep["axes_instrumented"] >= 3
    scripts = next(s for s in rep["sections"] if s["type"] == "scripts")
    assert scripts["mechanical"]["coverage_pct"] == 95.0
    assert scripts["mechanical"]["met"] is True
    skills = next(s for s in rep["sections"] if s["type"] == "skills")
    assert skills["llm_eval"]["coverage_pct"] == 100.0  # 1/1 PASS
    assert skills["llm_eval"]["met"] is True


def test_skill_failing_verdict_not_counted(tmp_path):
    m = _setup(tmp_path, code_pct=50.0, llm_avg=50.0, skill_pass=False)
    rep = m.build_report(80.0)
    skills = next(s for s in rep["sections"] if s["type"] == "skills")
    assert skills["llm_eval"]["coverage_pct"] == 0.0


def test_missing_coverage_json_marks_uninstrumented(tmp_path):
    m = _setup(tmp_path, code_pct=None, llm_avg=None, skill_pass=True)
    rep = m.build_report(80.0)
    scripts = next(s for s in rep["sections"] if s["type"] == "scripts")
    assert scripts["mechanical"]["instrumented"] is False
    assert scripts["mechanical"]["coverage_pct"] is None


def test_main_writes_json_and_returns_zero(tmp_path, monkeypatch, capsys):
    m = _setup(tmp_path, code_pct=10.0, llm_avg=10.0, skill_pass=True)
    out = tmp_path / "harness.json"
    monkeypatch.setattr("sys.argv", ["x", "--json", str(out)])
    assert m.main() == 0
    printed = capsys.readouterr().out
    assert "FAIL (ハーネス仕様 未達)" in printed
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["spec_met"] is False


def test_main_gate_returns_one_when_unmet(tmp_path, monkeypatch):
    m = _setup(tmp_path, code_pct=10.0, llm_avg=10.0, skill_pass=True)
    monkeypatch.setattr("sys.argv", ["x", "--gate", "--json", str(tmp_path / "h.json")])
    assert m.main() == 1


# --- ratchet-floor (回帰ガード) ---------------------------------------------
# 純関数 (build_floor_from_report / compare_to_floor / merge_floor_up) を
# fixture 無しの軽量 report dict で叩く。main() の 3 経路は _setup の実 fixture で。

def _rep(scripts_llm=62.7, scripts_mech=85.6, scripts_count=100, agents_count=10):
    return {"threshold": 80.0, "sections": [
        {"type": "scripts", "count": scripts_count,
         "mechanical": {"coverage_pct": scripts_mech},
         "llm_eval": {"coverage_pct": scripts_llm}},
        {"type": "agents", "count": agents_count,
         "mechanical": {"coverage_pct": 68.0},
         "llm_eval": {"coverage_pct": 56.0}},
    ]}


def test_build_floor_extracts_each_axis():
    m = _load()
    floor = m.build_floor_from_report(_rep())
    assert floor["floors"]["scripts"]["llm_eval"] == 62.7
    assert floor["floors"]["agents"]["mechanical"] == 68.0
    assert floor["counts"] == {"scripts": 100, "agents": 10}
    assert floor["threshold"] == 80.0


def test_compare_to_floor_same_value_no_violation():
    m = _load()
    rep = _rep()
    assert m.compare_to_floor(rep, m.build_floor_from_report(rep)) == []


def test_compare_to_floor_detects_regression_beyond_tolerance():
    m = _load()
    floor = m.build_floor_from_report(_rep(scripts_llm=62.7))
    v = m.compare_to_floor(_rep(scripts_llm=62.0), floor)  # 0.7pt 低下
    assert any("scripts/llm_eval" in x for x in v)


def test_compare_to_floor_tolerates_rounding_noise():
    m = _load()
    floor = m.build_floor_from_report(_rep(scripts_llm=62.7))
    assert m.compare_to_floor(_rep(scripts_llm=62.65), floor) == []  # 0.05pt は許容


def test_compare_to_floor_ignores_improvement():
    m = _load()
    floor = m.build_floor_from_report(_rep(scripts_llm=62.7))
    assert m.compare_to_floor(_rep(scripts_llm=90.0), floor) == []


def test_compare_to_floor_skips_missing_axis():
    m = _load()
    # floor に無い type / None coverage は skip (KeyError で落ちない)
    rep = {"sections": [{"type": "new", "mechanical": {"coverage_pct": 10.0},
                         "llm_eval": {"coverage_pct": None}}]}
    assert m.compare_to_floor(rep, {"floors": {}}) == []


def test_merge_floor_up_ratchets_up():
    m = _load()
    floor = m.build_floor_from_report(_rep(scripts_llm=62.7))
    up, warns = m.merge_floor_up(floor, _rep(scripts_llm=90.0))
    assert up["floors"]["scripts"]["llm_eval"] == 90.0
    assert warns == []


def test_merge_floor_up_holds_on_regression():
    m = _load()
    floor = m.build_floor_from_report(_rep(scripts_llm=62.7))
    held, warns = m.merge_floor_up(floor, _rep(scripts_llm=50.0))
    assert held["floors"]["scripts"]["llm_eval"] == 62.7  # 回帰は焼かない
    assert any("scripts/llm_eval" in w for w in warns)


def test_merge_floor_up_preserves_count_when_artifacts_were_removed():
    m = _load()
    floor = m.build_floor_from_report(_rep(scripts_count=100))
    held, warns = m.merge_floor_up(floor, _rep(scripts_count=90))
    assert held["counts"]["scripts"] == 100
    assert any("scripts/count" in w for w in warns)


def test_rebase_floor_on_removal_accepts_lower_ratio_for_smaller_population():
    m = _load()
    floor = m.build_floor_from_report(_rep(scripts_llm=62.7, scripts_count=100))
    rebased, notes = m.rebase_floor_on_removal(
        floor,
        _rep(scripts_llm=55.0, scripts_count=90),
        "remove obsolete plugin",
    )
    assert rebased["counts"]["scripts"] == 90
    assert rebased["floors"]["scripts"]["llm_eval"] == 55.0
    assert rebased["last_rebase"] == {
        "mode": "artifact-removal",
        "reason": "remove obsolete plugin",
        "removed_counts": {"scripts": 10},
    }
    assert any("scripts: artifact count 100 -> 90" in n for n in notes)


def test_rebase_floor_on_removal_rejects_regression_without_count_change():
    m = _load()
    floor = m.build_floor_from_report(_rep(scripts_llm=62.7, scripts_count=100))
    try:
        m.rebase_floor_on_removal(
            floor,
            _rep(scripts_llm=55.0, scripts_count=100),
            "not actually a removal",
        )
    except ValueError as exc:
        assert "count 不変" in str(exc)
    else:
        raise AssertionError("count 不変の coverage 回帰を rebase してはならない")


def test_rebase_floor_on_removal_rejects_added_artifacts():
    m = _load()
    floor = m.build_floor_from_report(_rep(scripts_count=100))
    try:
        m.rebase_floor_on_removal(
            floor,
            _rep(scripts_count=101),
            "mixed add and remove",
        )
    except ValueError as exc:
        assert "artifact count が増加" in str(exc)
    else:
        raise AssertionError("artifact 追加を削除専用 rebase で許可してはならない")


def test_rebase_floor_on_removal_requires_reason_and_count_snapshot():
    m = _load()
    floor = m.build_floor_from_report(_rep())
    try:
        m.rebase_floor_on_removal(floor, _rep(scripts_count=90), "")
    except ValueError as exc:
        assert "--rebase-reason" in str(exc)
    else:
        raise AssertionError("reason なしの rebase を許可してはならない")

    floor.pop("counts")
    try:
        m.rebase_floor_on_removal(floor, _rep(scripts_count=90), "remove plugin")
    except ValueError as exc:
        assert "counts がない" in str(exc)
    else:
        raise AssertionError("count snapshot なしの rebase を許可してはならない")


def test_main_self_test_returns_zero(monkeypatch):
    m = _load()
    monkeypatch.setattr("sys.argv", ["x", "--self-test"])
    assert m.main() == 0


def test_main_update_floor_then_ratchet_ok(tmp_path, monkeypatch):
    m = _setup(tmp_path, code_pct=95.0, llm_avg=95.0, skill_pass=True)
    floor = tmp_path / "floor.json"
    hj = str(tmp_path / "h.json")
    monkeypatch.setattr("sys.argv", ["x", "--update-floor", "--json", hj, "--floor", str(floor)])
    assert m.main() == 0
    assert floor.is_file()
    # 同じ現値で ratchet → 回帰なし exit0
    monkeypatch.setattr("sys.argv", ["x", "--ratchet", "--json", hj, "--floor", str(floor)])
    assert m.main() == 0


def test_main_rebase_floor_on_removal_then_ratchet_ok(tmp_path, monkeypatch):
    m = _setup(tmp_path, code_pct=95.0, llm_avg=95.0, skill_pass=True)
    report = m.build_report(80.0)
    floor_data = m.build_floor_from_report(report)
    floor_data["counts"]["agents"] += 1
    floor_data["floors"]["agents"]["mechanical"] = 50.0
    floor_data["floors"]["agents"]["llm_eval"] = 50.0
    floor = tmp_path / "floor.json"
    floor.write_text(json.dumps(floor_data), encoding="utf-8")
    hj = str(tmp_path / "h.json")

    monkeypatch.setattr("sys.argv", [
        "x", "--rebase-floor-on-removal", "--rebase-reason", "remove obsolete plugin",
        "--json", hj, "--floor", str(floor),
    ])
    assert m.main() == 0
    rebased = json.loads(floor.read_text(encoding="utf-8"))
    assert rebased["last_rebase"]["removed_counts"] == {"agents": 1}

    monkeypatch.setattr("sys.argv", ["x", "--ratchet", "--json", hj, "--floor", str(floor)])
    assert m.main() == 0


def test_main_ratchet_without_floor_returns_two(tmp_path, monkeypatch):
    m = _setup(tmp_path, code_pct=95.0, llm_avg=95.0, skill_pass=True)
    monkeypatch.setattr("sys.argv", ["x", "--ratchet", "--json", str(tmp_path / "h.json"),
                                     "--floor", str(tmp_path / "absent.json")])
    assert m.main() == 2  # floor 不在は初期化を促す usage error


def test_main_ratchet_detects_regression(tmp_path, monkeypatch):
    m = _setup(tmp_path, code_pct=95.0, llm_avg=95.0, skill_pass=True)
    floor = tmp_path / "floor.json"
    # 高い floor を人工的に置く (scripts mechanical を 99% に固定) → 現値 95% が回帰
    floor.write_text(json.dumps({"threshold": 80.0, "floors": {
        "scripts": {"mechanical": 99.0, "llm_eval": 0.0}}}), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["x", "--ratchet", "--json", str(tmp_path / "h.json"),
                                     "--floor", str(floor)])
    assert m.main() == 1
