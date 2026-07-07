"""derive-task-graph.py の canonicalize/graph_hash/derive/--print-graph-hash 契約 (C2/C11/C16)。

canonicalize の冪等性・byte一致再現性・graph_hash 安定性・read-only CLI 契約を固定する。
"""
import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(stem):
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), SCRIPTS / f"{stem}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


DTG = _load("derive-task-graph")


def _sample_graph():
    return {
        "schema_version": "1.0",
        "nodes": [
            {"id": "T2", "title": "b", "phase_ref": "P05", "entity_ref": "C01", "state": "pending", "write_scope": "s2"},
            {"id": "T1", "title": "a", "phase_ref": "P02", "entity_ref": "C01", "state": "done", "write_scope": "s1"},
        ],
        "edges": [
            {"type": "depends_on", "from": "T2", "to": "T1"},
            {"type": "parent_of", "from": "P05", "to": "T2"},
        ],
    }


# ─────────── canonicalize ───────────
def test_canonicalize_sorts_nodes_by_id():
    c = DTG.canonicalize(_sample_graph())
    assert [n["id"] for n in c["nodes"]] == ["T1", "T2"]


def test_canonicalize_sorts_edges():
    c = DTG.canonicalize(_sample_graph())
    # (type, from, to) 昇順: depends_on < parent_of
    assert [e["type"] for e in c["edges"]] == ["depends_on", "parent_of"]


def test_canonicalize_idempotent():
    once = DTG.canonicalize(_sample_graph())
    twice = DTG.canonicalize(once)
    assert once == twice


def test_canonicalize_fixed_key_order():
    c = DTG.canonicalize(_sample_graph())
    assert list(c.keys()) == ["schema_version", "nodes", "edges"]
    assert list(c["nodes"][0].keys()) == ["id", "title", "phase_ref", "entity_ref", "state", "write_scope"]


def test_canonicalize_acceptance_criterion_optional():
    g = _sample_graph()
    g["nodes"][0]["acceptance_criterion"] = "検証可能な受入基準"
    c = DTG.canonicalize(g)
    node = next(n for n in c["nodes"] if n["id"] == "T2")
    assert node["acceptance_criterion"] == "検証可能な受入基準"
    # 持たない node には付与されない
    node1 = next(n for n in c["nodes"] if n["id"] == "T1")
    assert "acceptance_criterion" not in node1


# ─────────── graph_hash / canonical_json ───────────
def test_graph_hash_format():
    import re
    h = DTG.graph_hash(_sample_graph())
    assert re.match(r"^sha256:[0-9a-f]{64}$", h)


def test_graph_hash_stable():
    assert DTG.graph_hash(_sample_graph()) == DTG.graph_hash(_sample_graph())


def test_graph_hash_invariant_to_input_order():
    g1 = _sample_graph()
    g2 = {"schema_version": "1.0", "nodes": list(reversed(g1["nodes"])), "edges": list(reversed(g1["edges"]))}
    assert DTG.graph_hash(g1) == DTG.graph_hash(g2)


def test_canonical_json_byte_match():
    assert DTG.canonical_json(_sample_graph()) == DTG.canonical_json(_sample_graph())


# ─────────── derive (fixture phase から) ───────────
def _write_phase(d: Path, name: str, fm_lines: str, checklist: str):
    d.joinpath(name).write_text(f"---\n{fm_lines}\n---\n# phase\n\n## 完了チェックリスト\n{checklist}\n", encoding="utf-8")


def _fixture_plan(tmp_path: Path):
    _write_phase(
        tmp_path, "phase-01-requirements.md",
        "id: P01\nphase_name: requirements\nentities_covered: [C01]",
        "- [ ] X を実装する\n- [ ] Y を検証する\n\n### 受入例\n- 満たす例: これは拾わない\n",
    )
    tmp_path.joinpath("component-inventory.json").write_text(
        json.dumps({"components": [{"id": "C01", "depends_on": [], "build_target": "plugins/x/scripts/a.py"}]}),
        encoding="utf-8",
    )


def test_derive_checkbox_items_only(tmp_path):
    _fixture_plan(tmp_path)
    g = DTG.derive(tmp_path)
    ids = {n["id"] for n in g["nodes"]}
    # root P01 + 2 checklist node。'### 受入例' の `- ` は拾わない。
    assert "P01" in ids
    checklist_nodes = [n for n in g["nodes"] if n["id"].startswith("P01-C01-")]
    assert len(checklist_nodes) == 2


def test_derive_entity_ref_from_frontmatter(tmp_path):
    _fixture_plan(tmp_path)
    g = DTG.derive(tmp_path)
    cn = next(n for n in g["nodes"] if n["id"] == "P01-C01-01")
    assert cn["entity_ref"] == "C01"
    assert cn["state"] == "pending"


def test_derive_reproducible_byte_match(tmp_path):
    _fixture_plan(tmp_path)
    a = DTG.canonical_json(DTG.derive(tmp_path))
    b = DTG.canonical_json(DTG.derive(tmp_path))
    assert a == b


def test_derive_parent_of_edges(tmp_path):
    _fixture_plan(tmp_path)
    g = DTG.derive(tmp_path)
    parent_edges = [e for e in g["edges"] if e["type"] == "parent_of" and e["from"] == "P01"]
    assert len(parent_edges) == 2


def test_derive_produces_build_target_once_per_component(tmp_path):
    _fixture_plan(tmp_path)
    _write_phase(
        tmp_path, "phase-02-design.md",
        "id: P02\nphase_name: design\nentities_covered: [C01]",
        "- [ ] Z を設計する\n",
    )
    g = DTG.derive(tmp_path)
    produces = [e for e in g["edges"] if e["type"] == "produces"]
    assert produces == [
        {"type": "produces", "from": "P01-C01-01", "to": "plugins/x/scripts/a.py"}
    ]


def test_derive_component_dependency_does_not_target_future_phase(tmp_path):
    _write_phase(
        tmp_path, "phase-01-requirements.md",
        "id: P01\nphase_name: requirements\nentities_covered: [C01]",
        "- [ ] C01 の要件を決める\n",
    )
    _write_phase(
        tmp_path, "phase-02-design.md",
        "id: P02\nphase_name: design\nentities_covered: [C02]",
        "- [ ] C02 を設計する\n",
    )
    _write_phase(
        tmp_path, "phase-03-design-review.md",
        "id: P03\nphase_name: review\nentities_covered: [C01]",
        "- [ ] C01 の後続レビューをする\n",
    )
    tmp_path.joinpath("component-inventory.json").write_text(
        json.dumps({
            "components": [
                {"id": "C01", "depends_on": [], "build_target": "plugins/x/scripts/a.py"},
                {"id": "C02", "depends_on": ["C01"], "build_target": "plugins/x/scripts/b.py"},
            ]
        }),
        encoding="utf-8",
    )
    g = DTG.derive(tmp_path)
    deps = [e for e in g["edges"] if e["type"] == "depends_on" and e["from"] == "P02-C02-01"]
    assert {"type": "depends_on", "from": "P02-C02-01", "to": "P01-C01-01"} in deps
    assert {"type": "depends_on", "from": "P02-C02-01", "to": "P03-C01-01"} not in deps


# ─────────── phase 順序 edge (event 駆動チェーン・M-01/L-09) ───────────
def _two_phase_plan(tmp_path: Path):
    """P01 (leaf 1) → P02 (leaf 1) の 2 phase plan。phase 順序 edge の検証用。"""
    _write_phase(
        tmp_path, "phase-01-requirements.md",
        "id: P01\nphase_name: requirements\nentities_covered: [C01]",
        "- [ ] C01 の要件を決める\n",
    )
    _write_phase(
        tmp_path, "phase-02-design.md",
        "id: P02\nphase_name: design\nentities_covered: [C01]",
        "- [ ] C01 を設計する\n",
    )
    tmp_path.joinpath("component-inventory.json").write_text(
        json.dumps({"components": [
            {"id": "C01", "depends_on": [], "build_target": "plugins/x/scripts/a.py"},
        ]}),
        encoding="utf-8",
    )


def test_phase_marker_depends_on_own_leaves(tmp_path):
    # (1) phase marker は自 phase の全 leaf に depends_on (marker done = phase 完了集約)。
    _two_phase_plan(tmp_path)
    g = DTG.derive(tmp_path)
    assert {"type": "depends_on", "from": "P01", "to": "P01-C01-01"} in g["edges"]
    assert {"type": "depends_on", "from": "P02", "to": "P02-C01-01"} in g["edges"]


def test_phase_leaf_depends_on_previous_marker(tmp_path):
    # (2) 各 phase の leaf は直前 phase marker に depends_on (前 phase 完了記述が発火条件)。
    _two_phase_plan(tmp_path)
    g = DTG.derive(tmp_path)
    assert {"type": "depends_on", "from": "P02-C01-01", "to": "P01"} in g["edges"]
    # 先頭 phase の leaf は前 marker を持たない。
    assert not any(
        e["type"] == "depends_on" and e["from"] == "P01-C01-01" and e["to"] == "P01"
        for e in g["edges"]
    )


def test_phase_order_edges_form_dag_and_gate_ready_set(tmp_path):
    # 順序保証: 全 pending の初期 ready-set は先頭 phase の leaf のみ (後段 phase は非 ready)。
    CRS = _load("compute-ready-set")
    _two_phase_plan(tmp_path)
    g = DTG.derive(tmp_path)
    for n in g["nodes"]:
        n["state"] = "pending"
    ready, _ = CRS.ready_set(g)
    assert "P01-C01-01" in ready              # 先頭 phase leaf は発火可能
    assert "P02-C01-01" not in ready          # 後段 phase leaf は前 phase 完了まで非 ready
    assert "P02" not in ready                 # 後段 marker も非 ready


# ─────────── main / --print-graph-hash CLI ───────────
def test_main_derive_writes_file(tmp_path, capsys):
    _fixture_plan(tmp_path)
    rc = DTG.main([str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "task-graph.json").is_file()


def test_main_print_graph_hash(tmp_path, capsys):
    _fixture_plan(tmp_path)
    DTG.main([str(tmp_path)])
    capsys.readouterr()
    rc = DTG.main(["--print-graph-hash", str(tmp_path / "task-graph.json")])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.startswith("sha256:") and len(out) == len("sha256:") + 64


def test_main_print_graph_hash_bad_json(tmp_path, capsys):
    (tmp_path / "bad.json").write_text("{bad", encoding="utf-8")
    rc = DTG.main(["--print-graph-hash", str(tmp_path / "bad.json")])
    assert rc == 2


def test_main_no_args_usage():
    assert DTG.main([]) == 2


def test_main_print_graph_hash_missing_arg():
    assert DTG.main(["--print-graph-hash"]) == 2


def test_main_not_a_directory(tmp_path):
    assert DTG.main([str(tmp_path / "nope")]) == 2
