"""C01 ready-set-from-checklist.py の subprocess CLI 実挙動テスト。

ハイフン名かつ conftest fixture 対象外 (skills/.../templates 配下) のため、
plugin-root conftest の importlib fixture を使わず subprocess CLI で実走検証する。
検証済み実挙動 (オーケストレータ smoke test) に対する genuine な回帰固定:
depends_on 未充足除外 / id 昇順決定論 / write_scope 非依存 / fail-closed exit code。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/run-build-skill/templates/task-graph-engine/scripts/ready-set-from-checklist.py"
)


def _run(progress_path: Path | None = None, *, extra: list[str] | None = None):
    argv = [sys.executable, str(SCRIPT)]
    if progress_path is not None:
        argv.append(str(progress_path))
    if extra:
        argv.extend(extra)
    return subprocess.run(argv, capture_output=True, text=True)


def _write(tmp_path: Path, checklist: list[dict]) -> Path:
    p = tmp_path / "progress.json"
    p.write_text(json.dumps({"checklist": checklist}, ensure_ascii=False), encoding="utf-8")
    return p


def test_script_exists():
    assert SCRIPT.is_file()


def test_ready_excludes_unsatisfied_dependency(tmp_path):
    p = _write(
        tmp_path,
        [
            {"id": "C1", "status": "done", "depends_on": []},
            {"id": "C2", "status": "pending", "depends_on": ["C1"]},
            {"id": "C3", "status": "pending", "depends_on": ["C2"]},
            {"id": "C10", "status": "pending", "depends_on": ["C1"]},
        ],
    )
    r = _run(p)
    assert r.returncode == 0, r.stderr
    # C2/C10 は C1(done) 充足で ready、C3 は C2 が pending ゆえ除外。
    assert json.loads(r.stdout) == {"ready": ["C2", "C10"]}


def test_id_ascending_is_numeric_not_lexicographic(tmp_path):
    # 辞書順なら C10 < C2 になるが、数値昇順 (C2 < C10) を要求する決定論。
    p = _write(
        tmp_path,
        [
            {"id": "C1", "status": "done", "depends_on": []},
            {"id": "C10", "status": "pending", "depends_on": ["C1"]},
            {"id": "C2", "status": "pending", "depends_on": ["C1"]},
        ],
    )
    r = _run(p)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["ready"] == ["C2", "C10"]


def test_write_scope_key_does_not_change_ready(tmp_path):
    # H1: tie-break/write_scope 機構を持たない。余分な write_scope キーは無視される。
    without = _write(
        tmp_path / "a" if False else tmp_path,
        [
            {"id": "C1", "status": "done", "depends_on": []},
            {"id": "C2", "status": "pending", "depends_on": ["C1"]},
            {"id": "C10", "status": "pending", "depends_on": ["C1"]},
        ],
    )
    ready_without = json.loads(_run(without).stdout)["ready"]

    with_scope = tmp_path / "with_scope.json"
    with_scope.write_text(
        json.dumps(
            {
                "checklist": [
                    {"id": "C1", "status": "done", "depends_on": [], "write_scope": "x"},
                    {"id": "C2", "status": "pending", "depends_on": ["C1"], "write_scope": "y"},
                    {"id": "C10", "status": "pending", "depends_on": ["C1"], "write_scope": "x"},
                ]
            }
        ),
        encoding="utf-8",
    )
    ready_with = json.loads(_run(with_scope).stdout)["ready"]
    assert ready_without == ready_with == ["C2", "C10"]


def test_all_done_yields_empty_ready_exit0(tmp_path):
    p = _write(
        tmp_path,
        [
            {"id": "C1", "status": "done", "depends_on": []},
            {"id": "C2", "status": "done", "depends_on": ["C1"]},
        ],
    )
    r = _run(p)
    assert r.returncode == 0
    assert json.loads(r.stdout) == {"ready": []}


def test_blocked_and_done_excluded_from_ready(tmp_path):
    p = _write(
        tmp_path,
        [
            {"id": "C1", "status": "done", "depends_on": []},
            {"id": "C2", "status": "blocked", "depends_on": ["C1"]},
            {"id": "C3", "status": "pending", "depends_on": ["C1"]},
        ],
    )
    r = _run(p)
    assert r.returncode == 0
    assert json.loads(r.stdout)["ready"] == ["C3"]


def test_dangling_dependency_not_ready(tmp_path):
    # 依存先が checklist に不在 = 永遠に done にならない → ready にならない (read-only は fail-closed せず not-ready)。
    p = _write(
        tmp_path,
        [{"id": "C2", "status": "pending", "depends_on": ["C1"]}],
    )
    r = _run(p)
    assert r.returncode == 0
    assert json.loads(r.stdout)["ready"] == []


def test_empty_checklist_exit0(tmp_path):
    p = tmp_path / "empty.json"
    p.write_text("{}", encoding="utf-8")
    r = _run(p)
    assert r.returncode == 0
    assert json.loads(r.stdout) == {"ready": []}


def test_usage_no_arg_exit2(tmp_path):
    r = _run(None)
    assert r.returncode == 2
    assert "usage" in r.stderr


def test_help_flag_exit0():
    r = _run(None, extra=["-h"])
    assert r.returncode == 0


def test_missing_file_exit2(tmp_path):
    r = _run(tmp_path / "nope.json")
    assert r.returncode == 2


def test_bad_json_exit2(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json {", encoding="utf-8")
    r = _run(p)
    assert r.returncode == 2


def test_item_without_id_is_data_integrity_exit1(tmp_path):
    p = _write(tmp_path, [{"status": "pending"}])
    r = _run(p)
    assert r.returncode == 1


def test_checklist_not_list_exit1(tmp_path):
    p = tmp_path / "notlist.json"
    p.write_text(json.dumps({"checklist": {"id": "C1"}}), encoding="utf-8")
    r = _run(p)
    assert r.returncode == 1


def test_depends_on_not_list_exit1(tmp_path):
    p = _write(tmp_path, [{"id": "C1", "status": "pending", "depends_on": "C0"}])
    r = _run(p)
    assert r.returncode == 1
