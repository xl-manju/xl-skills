"""C02 self-reflect-append.py の subprocess CLI 実挙動テスト。

パイプで exit code がマスクされるため subprocess.run(...).returncode で直接確認する。
検証済み実挙動: 追記後既存 item 不変 (単一truth) / id 重複 exit1 / 未知 depends_on exit1 /
サイクル exit1 / fail-closed 分岐。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/run-build-skill/templates/task-graph-engine/scripts/self-reflect-append.py"
)


def _run(progress_path: Path, *args: str):
    argv = [sys.executable, str(SCRIPT), str(progress_path), *args]
    return subprocess.run(argv, capture_output=True, text=True)


def _write(tmp_path: Path, checklist: list[dict]) -> Path:
    p = tmp_path / "progress.json"
    p.write_text(json.dumps({"checklist": checklist}, ensure_ascii=False), encoding="utf-8")
    return p


def _base(tmp_path: Path) -> Path:
    return _write(
        tmp_path,
        [
            {"id": "C1", "text": "a", "status": "done", "depends_on": []},
            {"id": "C2", "text": "b", "status": "pending", "depends_on": ["C1"]},
        ],
    )


def test_script_exists():
    assert SCRIPT.is_file()


def test_normal_append_exit0_and_appended_at_end(tmp_path):
    p = _base(tmp_path)
    r = _run(p, "--id", "C3", "--text", "new task", "--depends-on", "C1")
    assert r.returncode == 0, r.stderr
    data = json.loads(p.read_text(encoding="utf-8"))
    ids = [it["id"] for it in data["checklist"]]
    assert ids == ["C1", "C2", "C3"]
    c3 = data["checklist"][-1]
    assert c3["status"] == "pending"
    assert c3["depends_on"] == ["C1"]


def test_existing_items_unchanged(tmp_path):
    p = _base(tmp_path)
    before = json.loads(p.read_text(encoding="utf-8"))["checklist"]
    _run(p, "--id", "C3", "--text", "x", "--depends-on", "C2")
    after = json.loads(p.read_text(encoding="utf-8"))["checklist"]
    # 既存 2 item は id/text/status/depends_on ともに不変。
    assert after[:2] == before


def test_duplicate_id_exit1(tmp_path):
    p = _base(tmp_path)
    r = _run(p, "--id", "C2", "--text", "dup")
    assert r.returncode == 1
    assert "重複" in r.stderr


def test_unknown_depends_on_exit1(tmp_path):
    p = _base(tmp_path)
    r = _run(p, "--id", "C9", "--text", "x", "--depends-on", "C99")
    assert r.returncode == 1
    assert "未知" in r.stderr


def test_self_reference_exit1(tmp_path):
    p = _base(tmp_path)
    r = _run(p, "--id", "C9", "--text", "x", "--depends-on", "C9")
    assert r.returncode == 1


def test_preexisting_cycle_append_triggers_cycle_exit1(tmp_path):
    # checklist が既に C1<->C2 循環を持つ状態で新 sink を追記 → _has_cycle が検出 exit1。
    p = _write(
        tmp_path,
        [
            {"id": "C1", "text": "a", "status": "pending", "depends_on": ["C2"]},
            {"id": "C2", "text": "b", "status": "pending", "depends_on": ["C1"]},
        ],
    )
    r = _run(p, "--id", "C3", "--text", "x", "--depends-on", "C1")
    assert r.returncode == 1
    assert "サイクル" in r.stderr


def test_bad_id_pattern_exit1(tmp_path):
    p = _base(tmp_path)
    r = _run(p, "--id", "XX", "--text", "x")
    assert r.returncode == 1
    assert "pattern" in r.stderr


def test_verify_by_added(tmp_path):
    p = _base(tmp_path)
    r = _run(p, "--id", "C7", "--text", "x", "--verify-by", "script")
    assert r.returncode == 0
    c7 = json.loads(p.read_text(encoding="utf-8"))["checklist"][-1]
    assert c7["verify_by"] == "script"


def test_append_without_depends_on_omits_key(tmp_path):
    p = _write(tmp_path, [{"id": "C1", "text": "a", "status": "done"}])
    r = _run(p, "--id", "C2", "--text", "x")
    assert r.returncode == 0
    c2 = json.loads(p.read_text(encoding="utf-8"))["checklist"][-1]
    assert "depends_on" not in c2


def test_missing_required_text_exit2(tmp_path):
    p = _base(tmp_path)
    r = _run(p, "--id", "C3")
    assert r.returncode == 2


def test_bad_json_exit2(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json {", encoding="utf-8")
    r = _run(p, "--id", "C3", "--text", "x")
    assert r.returncode == 2


def test_checklist_not_list_exit2(tmp_path):
    p = tmp_path / "notlist.json"
    p.write_text(json.dumps({"checklist": "oops"}), encoding="utf-8")
    r = _run(p, "--id", "C3", "--text", "x")
    assert r.returncode == 2


def test_verify_by_invalid_choice_exit2(tmp_path):
    p = _base(tmp_path)
    r = _run(p, "--id", "C3", "--text", "x", "--verify-by", "bogus")
    assert r.returncode == 2
