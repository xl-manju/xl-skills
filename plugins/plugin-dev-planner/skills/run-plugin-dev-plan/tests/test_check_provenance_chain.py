"""check-provenance-chain.py (C05) の機能テスト。

intake→goal-spec→plan→handoff→改善成果物 の 5 ノード追跡可能性と断裂検出、
--resolve での ref 実在 + 継続性検査、usage error を固定する。
"""
from __future__ import annotations

import json


def _gs(intake=True, improvement=False):
    d = {"purpose": "x", "background": "y", "goal": "z", "checklist": [], "plan_dir": "plugin-plans/sample"}
    if intake:
        d["source_intake"] = {"ref": "intake.json", "schema_version": "2.0.0"}
    if improvement:
        d["source_improvement"] = {"ref": "improvement-handoff.json", "schema_version": "1.0.0"}
    return d


def _write_handoff(tmp_path):
    (tmp_path / "handoff-run-plugin-dev-plan.json").write_text(
        json.dumps({"plan_dir": str(tmp_path), "routes": []}, ensure_ascii=False), encoding="utf-8"
    )


# ─────────────────── check_chain (単体) ───────────────────
def test_clean_chain_no_breaks(tmp_path, provenance_chain):
    _write_handoff(tmp_path)
    breaks = provenance_chain.check_chain(
        _gs(intake=True), plan_dir=tmp_path,
        require_improvement=False, allow_missing_intake=False, resolve=False,
    )
    assert breaks == []


def test_missing_intake_is_break(tmp_path, provenance_chain):
    breaks = provenance_chain.check_chain(
        _gs(intake=False), plan_dir=None,
        require_improvement=False, allow_missing_intake=False, resolve=False,
    )
    assert any("E1 断裂" in b for b in breaks)


def test_missing_intake_allowed_for_greenfield(provenance_chain):
    breaks = provenance_chain.check_chain(
        _gs(intake=False), plan_dir=None,
        require_improvement=False, allow_missing_intake=True, resolve=False,
    )
    assert breaks == []


def test_missing_handoff_is_break(tmp_path, provenance_chain):
    breaks = provenance_chain.check_chain(
        _gs(intake=True), plan_dir=tmp_path,  # handoff 未作成
        require_improvement=False, allow_missing_intake=False, resolve=False,
    )
    assert any("E2 断裂" in b for b in breaks)


def test_require_improvement_missing_is_break(provenance_chain):
    breaks = provenance_chain.check_chain(
        _gs(intake=True, improvement=False), plan_dir=None,
        require_improvement=True, allow_missing_intake=False, resolve=False,
    )
    assert any("E3 断裂" in b for b in breaks)


def test_require_improvement_present_ok(provenance_chain):
    breaks = provenance_chain.check_chain(
        _gs(intake=True, improvement=True), plan_dir=None,
        require_improvement=True, allow_missing_intake=False, resolve=False,
    )
    assert breaks == []


# ─────────────────── --resolve (ref 実在 + 継続性) ───────────────────
def test_resolve_flags_missing_ref_file(tmp_path, provenance_chain):
    breaks = provenance_chain.check_chain(
        _gs(intake=True), plan_dir=tmp_path,
        require_improvement=False, allow_missing_intake=False, resolve=True,
    )
    _write_handoff(tmp_path)  # handoff はあるが intake.json は無い
    breaks = provenance_chain.check_chain(
        _gs(intake=True), plan_dir=tmp_path,
        require_improvement=False, allow_missing_intake=False, resolve=True,
    )
    assert any("実在しない" in b and "source_intake" in b for b in breaks)


def test_resolve_continuity_mismatch_detected(tmp_path, provenance_chain):
    _write_handoff(tmp_path)
    (tmp_path / "intake.json").write_text("{}", encoding="utf-8")
    # improvement-handoff の provenance.source_intake が goal-spec と別 intake を指す。
    (tmp_path / "improvement-handoff.json").write_text(
        json.dumps({"provenance": {"source_intake": "OTHER-intake.json"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    gs = _gs(intake=True, improvement=True)
    breaks = provenance_chain.check_chain(
        gs, plan_dir=tmp_path,
        require_improvement=True, allow_missing_intake=False, resolve=True,
    )
    assert any("継続性断裂" in b for b in breaks)


def test_resolve_continuity_match_ok(tmp_path, provenance_chain):
    _write_handoff(tmp_path)
    (tmp_path / "intake.json").write_text("{}", encoding="utf-8")
    (tmp_path / "improvement-handoff.json").write_text(
        json.dumps({"provenance": {"source_intake": "intake.json"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    gs = _gs(intake=True, improvement=True)
    breaks = provenance_chain.check_chain(
        gs, plan_dir=tmp_path,
        require_improvement=True, allow_missing_intake=False, resolve=True,
    )
    assert breaks == []


# ─────────────────── main / CLI ───────────────────
def test_main_clean_returns_zero(tmp_path, provenance_chain):
    _write_handoff(tmp_path)
    gs = tmp_path / "goal-spec.json"
    gs.write_text(json.dumps(_gs(intake=True), ensure_ascii=False), encoding="utf-8")
    assert provenance_chain.main(["--goal-spec", str(gs), "--plan-dir", str(tmp_path)]) == 0


def test_main_break_returns_one(tmp_path, provenance_chain):
    gs = tmp_path / "goal-spec.json"
    gs.write_text(json.dumps(_gs(intake=False), ensure_ascii=False), encoding="utf-8")
    assert provenance_chain.main(["--goal-spec", str(gs)]) == 1


def test_main_missing_file_returns_two(tmp_path, provenance_chain):
    assert provenance_chain.main(["--goal-spec", str(tmp_path / "nope.json")]) == 2


def test_main_bad_json_returns_two(tmp_path, provenance_chain):
    gs = tmp_path / "goal-spec.json"
    gs.write_text("{ broken", encoding="utf-8")
    assert provenance_chain.main(["--goal-spec", str(gs)]) == 2


# ─────────────────── pass marker (C11 digest pin 契約) ───────────────────
def test_marker_written_on_pass(tmp_path, provenance_chain):
    import hashlib
    _write_handoff(tmp_path)
    gs = tmp_path / "goal-spec.json"
    gs.write_text(json.dumps(_gs(intake=True), ensure_ascii=False), encoding="utf-8")
    rc = provenance_chain.main(
        ["--goal-spec", str(gs), "--plan-dir", str(tmp_path), "--marker-dir", str(tmp_path)]
    )
    assert rc == 0
    marker = tmp_path / ".gate" / "provenance-chain.pass"
    assert marker.is_file()
    assert marker.read_text().strip() == hashlib.sha256(gs.read_bytes()).hexdigest()


def test_marker_not_written_on_break(tmp_path, provenance_chain):
    gs = tmp_path / "goal-spec.json"
    gs.write_text(json.dumps(_gs(intake=False), ensure_ascii=False), encoding="utf-8")
    provenance_chain.main(["--goal-spec", str(gs), "--marker-dir", str(tmp_path)])
    assert not (tmp_path / ".gate" / "provenance-chain.pass").exists()
