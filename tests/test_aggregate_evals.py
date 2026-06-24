"""aggregate-evals.py の正規化・異常検出・3ソース合流を実証する。

外ループの負フィードバック検知 (連続 FAIL / スコア低下) と、
sink 断線解消で追加された score.jsonl + content-review verdict の合流が要点。
"""
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "skill-creator"
    / "skills"
    / "run-skill-rubric-governance"
    / "scripts"
    / "aggregate-evals.py"
)
SPEC = importlib.util.spec_from_file_location("aggregate_evals", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- 正規化: 各 sink を共通形へ ---

def test_normalize_score_record_passed_true_is_pass():
    rec = {
        "skill_name": "run-z",
        "passed": True,
        "score": 0.9,
        "timestamp": "2026-06-10T00:00:00Z",
        "findings": [],
    }
    n = MOD._normalize_score_record(rec)
    assert n["skill"] == "run-z"
    assert n["verdict"] == "PASS"
    assert n["date"] == "2026-06-10"


def test_normalize_score_record_passed_false_is_fail():
    rec = {"skill_name": "run-z", "passed": False, "timestamp": "2026-06-10T00:00:00Z"}
    assert MOD._normalize_score_record(rec)["verdict"] == "FAIL"


def test_normalize_score_record_without_skill_is_dropped():
    assert MOD._normalize_score_record({"passed": True}) is None


def test_normalize_verdict_record_reads_target_skill():
    rec = {
        "target": {"plugin": "p", "skill": "run-z"},
        "verdict": "FAIL",
        "reviewed_at": "2026-06-11T09:00:00+0900",
    }
    n = MOD._normalize_verdict_record(rec)
    assert n["skill"] == "run-z"
    assert n["verdict"] == "FAIL"
    assert n["date"] == "2026-06-11"


# --- 異常検出: 外ループの負フィードバック ---

def test_detect_consecutive_fail():
    evals = [
        {"skill": "run-x", "date": f"2026-06-0{i}", "verdict": "FAIL", "findings": []}
        for i in (1, 2, 3)
    ]
    anomalies = MOD._detect_anomalies(evals)
    assert any(a["kind"] == "consecutive_fail" and a["rubric_id"] == "run-x" for a in anomalies)


def test_two_fails_do_not_trigger_consecutive_fail():
    evals = [
        {"skill": "run-x", "date": f"2026-06-0{i}", "verdict": "FAIL", "findings": []}
        for i in (1, 2)
    ]
    assert not any(a["kind"] == "consecutive_fail" for a in MOD._detect_anomalies(evals))


def test_detect_score_drop():
    # 6 件: prior=最古1件(高スコア) vs recent=直近5件(低スコア) で 0.1 以上低下。
    scores = [1.0, 0.5, 0.5, 0.5, 0.5, 0.5]
    evals = [
        {"skill": "run-y", "date": f"2026-06-{i + 1:02d}", "verdict": "PASS", "score": s}
        for i, s in enumerate(scores)
    ]
    anomalies = MOD._detect_anomalies(evals)
    assert any(a["kind"] == "score_drop" and a["rubric_id"] == "run-y" for a in anomalies)


# --- 3 ソース合流 (sink 断線解消) ---

def test_load_evals_merges_score_jsonl_and_verdict(monkeypatch, tmp_path):
    eval_log = tmp_path / "eval-log"
    # score.jsonl sink
    score_dir = eval_log / "demo"
    score_dir.mkdir(parents=True)
    (score_dir / "2026-06-10-score.jsonl").write_text(
        json.dumps({
            "skill_name": "run-x", "passed": True, "score": 0.8,
            "timestamp": "2026-06-10T00:00:00Z", "findings": [],
        }) + "\n",
        encoding="utf-8",
    )
    # content-review verdict sink
    cr_dir = eval_log / "demo" / "run-y" / "content-review"
    cr_dir.mkdir(parents=True)
    (cr_dir / "elegance-verdict.json").write_text(
        json.dumps({
            "target": {"plugin": "demo", "skill": "run-y"},
            "verdict": "FAIL", "reviewed_at": "2026-06-11T00:00:00Z",
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: eval_log)
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "EVALS.json")

    evals = MOD._load_evals()["evaluations"]
    skills = {e["skill"] for e in evals}
    assert {"run-x", "run-y"}.issubset(skills)


def test_load_evals_empty_when_no_sources(monkeypatch, tmp_path):
    monkeypatch.setattr(MOD, "_eval_log_dir", lambda: tmp_path / "missing")
    monkeypatch.setattr(MOD, "_evals_path", lambda: tmp_path / "EVALS.json")
    assert MOD._load_evals()["evaluations"] == []
