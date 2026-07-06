"""C03 回帰: build-flags / goal-seek-loop schema の task-graph additive 拡張と
render-combinators の task-graph 配線テキストを固定する。

加えて F-M02 の回帰固定: render-combinators GOAL_SEEK_TASK_GRAPH_SECTION の emitted
verifier (PY heredoc) を抽出し、正当依存順トレース=exit0 / 捏造順序破りトレース=exit1 /
absence-as-violation=exit1 を実走検証する。emitted verifier のロジックがトレースを『助言』でなく
『拘束』として検査し続けることを機械固定する。
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
BUILD_SCRIPTS = HARNESS / "skills/run-build-skill/scripts"
SCHEMAS = HARNESS / "skills/run-build-skill/schemas"
RENDER = BUILD_SCRIPTS / "render-combinators.py"


def _load_render():
    spec = importlib.util.spec_from_file_location("render_combinators_under_test", RENDER)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _extract_verifier() -> str:
    section = _load_render().GOAL_SEEK_TASK_GRAPH_SECTION
    m = re.search(r"<<'PY'\n(.*?)\nPY\n", section, re.DOTALL)
    assert m, "task-graph emitted verifier (PY heredoc) が抽出できない"
    return m.group(1)


def _run_verifier(verifier: str, prog: dict, inter_lines, tmp_path: Path):
    v = tmp_path / "verify.py"
    v.write_text(verifier, encoding="utf-8")
    pp = tmp_path / "progress.json"
    pp.write_text(json.dumps(prog, ensure_ascii=False), encoding="utf-8")
    ip = tmp_path / "intermediate.jsonl"
    if inter_lines is not None:
        ip.write_text(
            "\n".join(json.dumps(l, ensure_ascii=False) for l in inter_lines) + "\n",
            encoding="utf-8",
        )
    return subprocess.run(
        [sys.executable, str(v), str(pp), str(ip)], capture_output=True, text=True
    )


# --- schema additive 拡張 (後方互換) ---


def test_build_flags_engine_enum_includes_task_graph():
    bf = json.loads((SCHEMAS / "build-flags.schema.json").read_text(encoding="utf-8"))
    engine = bf["properties"]["with_goal_seek"]["properties"]["engine"]
    assert "task-graph" in engine["enum"]
    # 既定 inline 不変 = 後方互換。
    assert engine["default"] == "inline"


def test_goal_seek_loop_checklist_depends_on_additive():
    ls = json.loads((SCHEMAS / "goal-seek-loop.schema.json").read_text(encoding="utf-8"))
    item = ls["properties"]["checklist"]["items"]["properties"]
    assert "depends_on" in item
    dep = item["depends_on"]
    assert dep["type"] == "array"
    assert dep["default"] == []  # additive/後方互換 (engine:inline では無視)


def test_goal_seek_loop_engine_enum_includes_task_graph():
    ls = json.loads((SCHEMAS / "goal-seek-loop.schema.json").read_text(encoding="utf-8"))
    assert "task-graph" in ls["properties"]["engine"]["enum"]


# --- render-combinators task-graph 配線テキスト ---


def test_render_has_task_graph_wiring_text():
    section = _load_render().GOAL_SEEK_TASK_GRAPH_SECTION
    assert "ready-set-from-checklist.py" in section
    assert "self-reflect-append.py" in section
    assert "extract-capability-dependency-graph.py" in section
    assert "record-capability-graph-knowledge.py" in section
    assert "dependency graph knowledge" in section


# --- F-M02: emitted verifier の依存順消費検査 ---


def test_emitted_verifier_valid_trace_exit0(tmp_path):
    verifier = _extract_verifier()
    checklist = [
        {"id": "C1", "status": "done", "depends_on": []},
        {"id": "C2", "status": "done", "depends_on": ["C1"]},
    ]
    prog = {"engine": "task-graph", "status": "in_progress", "checklist": checklist, "iteration": 1}
    lines = [
        {"ready_set": ["C1"], "selected_item": "C1"},
        {"ready_set": ["C2"], "selected_item": "C2"},
    ]
    r = _run_verifier(verifier, prog, lines, tmp_path)
    assert r.returncode == 0, r.stderr


def test_emitted_verifier_fabricated_order_break_exit1(tmp_path):
    # C2 (dep C1) を C1 選択前に選択。自己申告 ready_set=["C2"] で min-id 検査は通るが、
    # 位相順序の独立検証 (depends_on が前周回で未選択) が exit1 で弾く (捏造耐性)。
    verifier = _extract_verifier()
    checklist = [
        {"id": "C1", "status": "done", "depends_on": []},
        {"id": "C2", "status": "done", "depends_on": ["C1"]},
    ]
    prog = {"engine": "task-graph", "status": "in_progress", "checklist": checklist, "iteration": 0}
    lines = [{"ready_set": ["C2"], "selected_item": "C2"}]
    r = _run_verifier(verifier, prog, lines, tmp_path)
    assert r.returncode == 1


def test_emitted_verifier_absence_is_violation_exit1(tmp_path):
    # engine:task-graph だが intermediate.jsonl 未生成 = 依存順消費の証跡なし → 拘束違反 exit1。
    verifier = _extract_verifier()
    prog = {
        "engine": "task-graph",
        "status": "in_progress",
        "checklist": [{"id": "C1", "status": "pending", "depends_on": []}],
    }
    r = _run_verifier(verifier, prog, None, tmp_path)  # intermediate.jsonl を書かない
    assert r.returncode == 1


def test_emitted_verifier_inline_engine_not_applicable_exit0(tmp_path):
    verifier = _extract_verifier()
    prog = {
        "engine": "inline",
        "status": "in_progress",
        "checklist": [{"id": "C1", "status": "done", "depends_on": []}],
    }
    r = _run_verifier(verifier, prog, [{"ready_set": ["C1"], "selected_item": "C1"}], tmp_path)
    assert r.returncode == 0
    assert "非適用" in r.stdout


def test_emitted_verifier_dangling_closure_exit1(tmp_path):
    # depends_on closure: 依存先が checklist 内に不在 (dangling) → exit1。
    verifier = _extract_verifier()
    prog = {
        "engine": "task-graph",
        "status": "in_progress",
        "checklist": [{"id": "C2", "status": "pending", "depends_on": ["C1"]}],
    }
    r = _run_verifier(verifier, prog, [{"ready_set": [], "selected_item": None}], tmp_path)
    assert r.returncode == 1
