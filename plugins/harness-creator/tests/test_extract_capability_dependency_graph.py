"""C06 extract-capability-dependency-graph.py の subprocess CLI 実挙動テスト。

検証済み実挙動: node/edge/gaps 抽出 (id 昇順) / fail-closed exit1 (空 graph・循環・dangling) /
usage exit2 / 失敗時も stdout に JSON。F-M04 回帰固定: 相互 pair は循環検出から除外 (exit0)、
真の skill-invoke 循環 (A->B->A) は exit1。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/run-build-skill/templates/task-graph-engine/scripts/extract-capability-dependency-graph.py"
)


def _run(target: Path | str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(target)], capture_output=True, text=True
    )


def _skill(root: Path, name: str, body: str, *, extra_fm: str = "") -> None:
    d = root / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    fm = f"---\nname: {name}\n{extra_fm}---\n{body}\n"
    (d / "SKILL.md").write_text(fm, encoding="utf-8")


def test_script_exists():
    assert SCRIPT.is_file()


def test_mutual_pair_is_not_a_cycle_exit0(tmp_path):
    # F-M04: generator<->evaluator の双方向 pair バインドは runtime 依存でなく循環検出から除外。
    _skill(tmp_path, "a", "body a", extra_fm="pair: b\n")
    _skill(tmp_path, "b", "body b", extra_fm="pair: a\n")
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    graph = json.loads(r.stdout)
    assert graph["gaps"] == []
    types = {(e["from"], e["to"], e["type"]) for e in graph["edges"]}
    assert ("skill:a", "skill:b", "pair") in types
    assert ("skill:b", "skill:a", "pair") in types


def test_true_skill_invoke_cycle_exit1(tmp_path):
    _skill(tmp_path, "a", "uses Skill(b)")
    _skill(tmp_path, "b", "uses Skill(a)")
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "循環依存" in r.stderr
    # 失敗時も stdout に JSON graph を出す (C07/C08 が読めるように)。
    assert json.loads(r.stdout)["nodes"]


def test_dangling_reference_gaps_nonempty_exit1(tmp_path):
    _skill(tmp_path, "a", "uses Skill(ghost)")
    r = _run(tmp_path)
    assert r.returncode == 1
    graph = json.loads(r.stdout)
    assert graph["gaps"]
    assert graph["gaps"][0]["ref"] == "skill:ghost"


def test_empty_graph_exit1(tmp_path):
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "空 graph" in r.stderr
    assert json.loads(r.stdout)["nodes"] == []


def test_nonexistent_dir_exit2(tmp_path):
    r = _run(tmp_path / "nope")
    assert r.returncode == 2


def test_healthy_skill_invoke_edge_exit0(tmp_path):
    _skill(tmp_path, "a", "uses Skill(b)")
    _skill(tmp_path, "b", "leaf")
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    edges = {(e["from"], e["to"], e["type"]) for e in json.loads(r.stdout)["edges"]}
    assert ("skill:a", "skill:b", "skill-invoke") in edges


def test_node_id_kind_name_format_and_sorted(tmp_path):
    _skill(tmp_path, "zeta", "leaf")
    _skill(tmp_path, "alpha", "leaf")
    r = _run(tmp_path)
    node_ids = [n["id"] for n in json.loads(r.stdout)["nodes"]]
    assert node_ids == ["skill:alpha", "skill:zeta"]  # id 昇順で正準化


def test_builtin_agent_excluded_and_script_surface(tmp_path):
    _skill(tmp_path, "a", "uses Agent(general-purpose) and scripts/tool.py")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "tool.py").write_text("print(1)\n", encoding="utf-8")
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    graph = json.loads(r.stdout)
    node_ids = {n["id"] for n in graph["nodes"]}
    assert "script:tool.py" in node_ids
    # builtin agent は gap にも edge にもならない。
    assert graph["gaps"] == []
    edges = {(e["from"], e["to"], e["type"]) for e in graph["edges"]}
    assert ("skill:a", "script:tool.py", "script-call") in edges
    assert not any(e["type"] == "agent-invoke" for e in graph["edges"])
