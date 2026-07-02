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
    / "harness-creator"
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


def test_loop_kind_skip_reason_does_not_escape_empty_criteria():
    # loop 実行系の skip_reason escape は封鎖 (FEEDBACK_SKIP_KINDS=ref/assign 限定。
    # lint-feedback-contract.py と対称)。
    data = {
        "skill_kind": "wrap",
        "feedback_contract": {"skip_reason": "委譲先で評価するため本体は N/A", "criteria": []},
    }
    errs = MOD._validate_feedback_contract(data)
    assert errs and any("skip_reason escape は" in e for e in errs)


def test_assign_kind_skip_reason_with_empty_criteria_is_na_escape():
    # ref/assign は kind 自体が escape 対象: skip_reason + 空 criteria でもエラーなし。
    data = {
        "skill_kind": "assign",
        "feedback_contract": {"skip_reason": "read-only 評価器のため N/A", "criteria": []},
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


# --- requirement_coverage (RTM): 要望被覆の機械検査 ---
#
# doc_coverage(参照知識)と対になる「ユーザー要望の被覆」。brief の非空要求フィールド
# 全てが mapped / not_applicable+reason で被覆されることを exit 1 検査する。
# 旧 trace は skip、brief 参照があるのに coverage 無しは WARN (段階導入)。

import json


def _brief_dict():
    """最小・現実的な brief。被覆対象は trigger_conditions / output_contract /
    key_constraints / goal / boundary の5フィールド (識別系は除外セット)。"""
    return {
        "skill_name": "run-x",
        "prefix": "run",
        "kind": "run",
        "hierarchy_level": "L1",
        "trigger_conditions": ["契約書を作りたいとき", "台帳から量産したいとき"],
        "output_contract": "生成物が黄色二系統で出力される",
        "key_constraints": ["トークンは Keychain のみ", "誤値より空欄優先"],
        "goal": "G を達成する",
        "boundary": "同定と補完のみ。与信判断は対象外",
    }


def _full_coverage():
    return [
        {"requirement_id": "trigger_conditions", "disposition": "mapped",
         "mapped_to": "SKILL.md description trigger句"},
        {"requirement_id": "output_contract", "disposition": "mapped",
         "mapped_to": "OUT1"},
        {"requirement_id": "key_constraints[0]", "disposition": "mapped",
         "mapped_to": "IN1"},
        {"requirement_id": "key_constraints[1]", "disposition": "not_applicable",
         "reason": "本 build では Notion 書込を行わないため対象外"},
        {"requirement_id": "goal", "disposition": "mapped",
         "mapped_to": "SKILL.md ゴールシーク実行節"},
        {"requirement_id": "boundary", "disposition": "mapped",
         "mapped_to": "SKILL.md 境界節"},
    ]


def _rtm_trace(tmp_path, coverage):
    """brief を tmp に書き、それを参照する trace dict と trace_path を返す。"""
    brief_p = tmp_path / "skill-brief.json"
    brief_p.write_text(json.dumps(_brief_dict()), encoding="utf-8")
    trace = {"brief_path": "skill-brief.json"}
    if coverage is not None:
        trace["requirement_coverage"] = coverage
    return trace, tmp_path / "skill-build-trace.json"


def test_requirement_coverage_full_passes(tmp_path):
    trace, tp = _rtm_trace(tmp_path, _full_coverage())
    assert MOD._validate_requirement_coverage(trace, tp) == []


def test_requirement_coverage_missing_field_fails(tmp_path):
    # boundary の被覆を落とす → 欠落フィールドとして検出すべき。
    cov = [c for c in _full_coverage() if c["requirement_id"] != "boundary"]
    trace, tp = _rtm_trace(tmp_path, cov)
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert errs and any("missing=['boundary']" in e for e in errs)


def test_requirement_coverage_absent_old_trace_skips(tmp_path, capsys):
    # brief 参照も coverage も無い旧 trace: 検査せず WARN も出さない。
    errs = MOD._validate_requirement_coverage({}, tmp_path / "t.json")
    assert errs == []
    assert "WARN" not in capsys.readouterr().err


def test_requirement_coverage_absent_with_brief_ref_warns(tmp_path, capsys):
    # brief 情報 (source_docs) があるのに coverage 無し → WARN のみ (FAIL しない)。
    trace = {"source_docs": ["eval-log/skill-brief.json"]}
    errs = MOD._validate_requirement_coverage(trace, tmp_path / "t.json")
    assert errs == []
    assert "requirement_coverage" in capsys.readouterr().err


def test_requirement_coverage_unknown_field_fails(tmp_path):
    cov = _full_coverage() + [
        {"requirement_id": "nonexistent_field", "disposition": "mapped",
         "mapped_to": "x"}
    ]
    trace, tp = _rtm_trace(tmp_path, cov)
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert any("not found in brief" in e and "nonexistent_field" in e for e in errs)


def test_requirement_coverage_index_out_of_range_fails(tmp_path):
    cov = _full_coverage() + [
        {"requirement_id": "key_constraints[9]", "disposition": "mapped",
         "mapped_to": "x"}
    ]
    trace, tp = _rtm_trace(tmp_path, cov)
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert any("key_constraints[9]" in e and "not found" in e for e in errs)


def test_requirement_coverage_mapped_requires_mapped_to(tmp_path):
    cov = _full_coverage()
    del cov[1]["mapped_to"]
    trace, tp = _rtm_trace(tmp_path, cov)
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert any("mapped_to is required" in e for e in errs)


def test_requirement_coverage_na_requires_reason(tmp_path):
    cov = _full_coverage()
    del cov[3]["reason"]
    trace, tp = _rtm_trace(tmp_path, cov)
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert any("reason is required" in e for e in errs)


def test_requirement_coverage_bad_disposition_fails(tmp_path):
    cov = _full_coverage()
    cov[0]["disposition"] = "deferred"
    trace, tp = _rtm_trace(tmp_path, cov)
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert any("disposition='deferred'" in e for e in errs)


def test_requirement_coverage_duplicate_id_fails(tmp_path):
    cov = _full_coverage() + [_full_coverage()[0]]
    trace, tp = _rtm_trace(tmp_path, cov)
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert any("duplicated" in e for e in errs)


def test_requirement_coverage_unresolvable_brief_warns_structural_only(tmp_path, capsys):
    # brief ファイルが無い場合は構造検査のみ (WARN)。cwd 依存で trace 資産を壊さない。
    trace = {
        "brief_path": "no-such-brief.json",
        "requirement_coverage": _full_coverage(),
    }
    errs = MOD._validate_requirement_coverage(trace, tmp_path / "t.json")
    assert errs == []
    assert "brief を解決できない" in capsys.readouterr().err


def test_requirement_coverage_brief_detected_from_source_docs(tmp_path):
    # brief_path 無しでも source_docs の skill-brief*.json から突合先を推定する。
    brief_p = tmp_path / "skill-brief.json"
    brief_p.write_text(json.dumps(_brief_dict()), encoding="utf-8")
    trace = {
        "source_docs": ["skill-brief.json"],
        "requirement_coverage": _full_coverage(),
    }
    assert MOD._validate_requirement_coverage(trace, tmp_path / "t.json") == []


def test_requirement_coverage_non_array_fails(tmp_path):
    trace, tp = _rtm_trace(tmp_path, None)
    trace["requirement_coverage"] = {"oops": True}
    errs = MOD._validate_requirement_coverage(trace, tp)
    assert errs == ["requirement_coverage must be array"]


# --- manifest 検証経路 (--self-test) が緑であること ---

def test_self_test_exits_zero():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
