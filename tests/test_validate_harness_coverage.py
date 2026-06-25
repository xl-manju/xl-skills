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
