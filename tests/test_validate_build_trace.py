"""validate-build-trace.py の feedback_contract 検査と manifest self-test を実証する。

評価フィードバックループ配線で追加された _validate_feedback_contract の核契約を固める:
  - loop 実行系 (run/wrap/delegate) は criteria を必須とし inner+outer を各1件以上課す
  - ref/assign は N/A escape (feedback_contract 不要、あっても配列形式のみ確認)
  - id は ^(IN|OUT|C)[0-9]+$ / verify_by は固定 enum に強制 (build-flags と同型)
これらは「per-skill 評価基準の漏れ防止」というユーザー要望の機械的担保点。
"""
import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "skill-creator"
    / "skills"
    / "run-build-skill"
    / "scripts"
    / "validate-build-trace.py"
)
SPEC = importlib.util.spec_from_file_location("validate_build_trace", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _valid_run_contract():
    """run kind の最小・正しい feedback_contract (inner+outer を含む)。"""
    return {
        "skill_kind": "run",
        "feedback_contract": {
            "criteria": [
                {
                    "id": "IN1",
                    "loop_scope": "inner",
                    "text": "ゴールシーク内ループで checklist を満たす",
                    "verify_by": "lint",
                },
                {
                    "id": "OUT1",
                    "loop_scope": "outer",
                    "text": "ハーネス全体で4条件 PASS",
                    "verify_by": "elegant-review",
                },
            ]
        },
    }


# --- 正常系 ---

def test_run_kind_valid_contract_has_no_errors():
    assert MOD._validate_feedback_contract(_valid_run_contract()) == []


def test_ref_kind_without_contract_is_na_escape():
    # ref は read-only 評価器: feedback_contract が無くてもエラーにしない。
    assert MOD._validate_feedback_contract({"skill_kind": "ref"}) == []


def test_run_kind_skip_reason_escapes_empty_criteria():
    data = {
        "skill_kind": "wrap",
        "feedback_contract": {"skip_reason": "委譲先で評価するため本体は N/A", "criteria": []},
    }
    assert MOD._validate_feedback_contract(data) == []


def test_unknown_kind_legacy_trace_is_not_checked():
    # kind 不明の旧トレースは破壊回避のため検査しない。
    assert MOD._validate_feedback_contract({}) == []


# --- 異常系: 漏れ / 形式違反を確実に検出する ---

def test_run_kind_missing_contract_is_error():
    errs = MOD._validate_feedback_contract({"skill_kind": "run"})
    assert errs and any("feedback_contract is required" in e for e in errs)


def test_run_kind_missing_outer_scope_is_error():
    data = _valid_run_contract()
    # outer を削って inner のみにする → outer 欠落を検出すべき。
    data["feedback_contract"]["criteria"] = [
        data["feedback_contract"]["criteria"][0]
    ]
    errs = MOD._validate_feedback_contract(data)
    assert any("outer" in e for e in errs)


def test_run_kind_bad_id_pattern_is_error():
    data = _valid_run_contract()
    data["feedback_contract"]["criteria"][0]["id"] = "X9"  # IN|OUT|C 以外
    errs = MOD._validate_feedback_contract(data)
    assert any("must match" in e and "X9" in e for e in errs)


def test_run_kind_bad_verify_by_enum_is_error():
    data = _valid_run_contract()
    data["feedback_contract"]["criteria"][0]["verify_by"] = "magic"
    errs = MOD._validate_feedback_contract(data)
    assert any("verify_by" in e and "magic" in e for e in errs)


def test_run_kind_duplicate_id_is_error():
    data = _valid_run_contract()
    data["feedback_contract"]["criteria"][1]["id"] = "IN1"  # 重複
    errs = MOD._validate_feedback_contract(data)
    assert any("duplicated" in e for e in errs)


def test_ref_kind_non_list_criteria_is_error():
    data = {"skill_kind": "ref", "feedback_contract": {"criteria": "oops"}}
    errs = MOD._validate_feedback_contract(data)
    assert any("must be array" in e for e in errs)


# --- manifest 検証経路 (--self-test) が緑であること ---

def test_self_test_exits_zero():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
