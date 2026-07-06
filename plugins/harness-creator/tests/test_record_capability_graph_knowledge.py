"""C07 record-capability-graph-knowledge.py の subprocess CLI 実挙動テスト。

検証済み実挙動: knowledge-capability-graph.json + knowledge-index.json への append/merge、
各 entry の source_ref、二度実行しても既存 entry 非破壊 (単一truち/冪等)、--dry-run は書かない。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/run-build-skill/templates/task-graph-engine/scripts/record-capability-graph-knowledge.py"
)


def _run(graph: Path, *args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(graph), *args], capture_output=True, text=True
    )


def _graph(tmp_path: Path, *, with_gap: bool = True) -> Path:
    g = {
        "nodes": [
            {"id": "skill:a", "kind": "skill", "path": "skills/a/SKILL.md"},
            {"id": "skill:b", "kind": "skill", "path": "skills/b/SKILL.md"},
        ],
        "edges": [
            {"from": "skill:a", "to": "skill:b", "type": "skill-invoke", "source_ref": "skills/a/SKILL.md"}
        ],
        "gaps": (
            [{"from": "skill:a", "ref": "skill:ghost", "type": "skill-invoke", "source_ref": "skills/a/SKILL.md"}]
            if with_gap
            else []
        ),
    }
    p = tmp_path / "graph.json"
    p.write_text(json.dumps(g), encoding="utf-8")
    return p


def test_script_exists():
    assert SCRIPT.is_file()


def test_first_run_records_entries_exit0(tmp_path):
    g = _graph(tmp_path)
    kdir = tmp_path / "knowledge"
    r = _run(g, "--target-knowledge-dir", str(kdir))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["loop_a_status"]["added"]
    store = json.loads((kdir / "knowledge-capability-graph.json").read_text(encoding="utf-8"))
    # summary + gap の 2 entry。
    ids = {it["id"] for it in store["items"]}
    assert "cdg-summary" in ids
    assert any(i.startswith("cdg-gap-") for i in ids)


def test_every_entry_has_source_ref(tmp_path):
    g = _graph(tmp_path)
    kdir = tmp_path / "knowledge"
    _run(g, "--target-knowledge-dir", str(kdir))
    store = json.loads((kdir / "knowledge-capability-graph.json").read_text(encoding="utf-8"))
    for item in store["items"]:
        assert item.get("source_ref"), item


def test_idempotent_second_run_skips_existing(tmp_path):
    g = _graph(tmp_path)
    kdir = tmp_path / "knowledge"
    _run(g, "--target-knowledge-dir", str(kdir))
    first = json.loads((kdir / "knowledge-capability-graph.json").read_text(encoding="utf-8"))
    r2 = _run(g, "--target-knowledge-dir", str(kdir))
    assert r2.returncode == 0, r2.stderr
    out2 = json.loads(r2.stdout)
    assert out2["loop_a_status"]["added"] == []
    assert out2["loop_a_status"]["skipped"]
    second = json.loads((kdir / "knowledge-capability-graph.json").read_text(encoding="utf-8"))
    # 二度目でも item 集合は非破壊 (単一truち)。
    assert first["items"] == second["items"]


def test_category_registered_in_index(tmp_path):
    g = _graph(tmp_path)
    kdir = tmp_path / "knowledge"
    _run(g, "--target-knowledge-dir", str(kdir))
    index = json.loads((kdir / "knowledge-index.json").read_text(encoding="utf-8"))
    assert any(c["id"] == "capability-graph" for c in index["categories"])


def test_dry_run_writes_nothing(tmp_path):
    g = _graph(tmp_path)
    kdir = tmp_path / "knowledge"
    r = _run(g, "--target-knowledge-dir", str(kdir), "--dry-run")
    assert r.returncode == 0
    assert not kdir.exists() or not any(kdir.iterdir())


def test_loop_b_records_second_store(tmp_path):
    g = _graph(tmp_path)
    ka = tmp_path / "ka"
    kb = tmp_path / "kb"
    r = _run(g, "--target-knowledge-dir", str(ka), "--harness-knowledge-dir", str(kb))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["loop_b_status"] is not None
    assert (kb / "knowledge-capability-graph.json").is_file()


def test_discovered_json_adds_task_entries(tmp_path):
    g = _graph(tmp_path, with_gap=False)
    disc = tmp_path / "disc.json"
    disc.write_text(json.dumps([{"id": "C5", "text": "discovered"}]), encoding="utf-8")
    kdir = tmp_path / "knowledge"
    r = _run(g, "--target-knowledge-dir", str(kdir), "--discovered-json", str(disc))
    assert r.returncode == 0, r.stderr
    ids = {e["id"] for e in json.loads(r.stdout)["entries"]}
    assert "cdg-task-c5" in ids


def test_bad_graph_path_exit2(tmp_path):
    r = _run(tmp_path / "nope.json", "--target-knowledge-dir", str(tmp_path / "k"))
    assert r.returncode == 2


def test_bad_discovered_json_not_list_exit2(tmp_path):
    g = _graph(tmp_path, with_gap=False)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"not": "list"}), encoding="utf-8")
    r = _run(g, "--target-knowledge-dir", str(tmp_path / "k"), "--discovered-json", str(bad))
    assert r.returncode == 2


def test_missing_required_target_dir_exit2(tmp_path):
    g = _graph(tmp_path)
    r = _run(g)
    assert r.returncode == 2
