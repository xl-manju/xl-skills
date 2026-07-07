"""validate-task-graph.py の機能テスト (C2/C3/C11・conftest 非依存)。

8 検査 (a)DAG非循環 / (b)orphan0 / (c)producer一意 / (d)inventory矛盾0 /
(e)consumes producer実在 / (f)非正準拒否 / (g)node.state永続4値 / (h)dangling edge端点0 を、P04 C2
受入例 (満たす例=exit0 / 満たさない例=inventory矛盾 exit1) を含めて網羅する。
"""
from __future__ import annotations

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


vtg = _load("validate-task-graph")
dtg = _load("derive-task-graph")


# ─────────────────── fixtures ───────────────────
INVENTORY = {"components": [{"id": "C01", "depends_on": []}, {"id": "C02", "depends_on": ["C01"]}]}


def _node(nid, entity, phase="P05", state="pending"):
    return {
        "id": nid,
        "title": f"{nid} title",
        "phase_ref": phase,
        "entity_ref": entity,
        "state": state,
        "write_scope": nid,
    }


def _c2_graph():
    """P04 C2 受入例: 4 node + depends_on/produces/consumes 各 4 本 (canonical 化して返す)。"""
    nodes = [
        _node("T1", "C01", phase="P02"),
        _node("T2", "C01"),
        _node("T3", "C02"),
        _node("T4", "C01"),
    ]
    edges = []
    # depends_on: from=dependent, to=dependency
    for f, t in [("T2", "T1"), ("T3", "T1"), ("T4", "T2"), ("T4", "T3")]:
        edges.append({"type": "depends_on", "from": f, "to": t})
    # produces: from=node, to=artifact
    for f, t in [("T1", "A1"), ("T2", "A2"), ("T3", "A3"), ("T4", "A4")]:
        edges.append({"type": "produces", "from": f, "to": t})
    # consumes: from=artifact, to=node (検査 (e) は consumes.from を artifact とみなす)
    for f, t in [("A1", "T2"), ("A1", "T3"), ("A2", "T4"), ("A3", "T4")]:
        edges.append({"type": "consumes", "from": f, "to": t})
    return dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})


# ─────────────────── 満たす例 (exit0) ───────────────────
def test_c2_accept_example_no_violations():
    assert vtg.validate(_c2_graph(), INVENTORY) == []


def test_c2_graph_is_canonical_idempotent():
    g = _c2_graph()
    assert dtg.canonicalize(g) == g  # (f) を踏まないこと


# ─────────────────── (a) DAG 非循環 ───────────────────
def test_a_cycle_detected_depends_on():
    nodes = [_node("X", "C01"), _node("Y", "C01")]
    edges = [
        {"type": "depends_on", "from": "X", "to": "Y"},
        {"type": "depends_on", "from": "Y", "to": "X"},
    ]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    v = vtg.validate(g, {})
    assert any(msg.startswith("(a)") for msg in v)


def test_a_cycle_via_parent_of():
    nodes = [_node("X", None), _node("Y", None)]
    edges = [
        {"type": "parent_of", "from": "X", "to": "Y"},
        {"type": "parent_of", "from": "Y", "to": "X"},
    ]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    assert any(msg.startswith("(a)") for msg in vtg.validate(g, {}))


# ─────────────────── (h) dangling edge 端点実在 (F5) ───────────────────
def test_h_dangling_depends_on_endpoint_is_violation():
    """depends_on の to が nodes に不在 (dangling) → (h) violation で plan-time 拒否。"""
    nodes = [_node("X", "C01")]
    edges = [{"type": "depends_on", "from": "X", "to": "MISSING"}]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    v = vtg.validate(g, {})
    assert any(msg.startswith("(h)") and "MISSING" in msg for msg in v)


def test_h_produces_consumes_artifact_endpoints_not_flagged():
    """produces/consumes は artifact 端点ゆえ (h) の対象外 (誤検出しない)。"""
    assert not any(msg.startswith("(h)") for msg in vtg.validate(_c2_graph(), INVENTORY))


# ─────────────────── (i) phase 依存方向 ───────────────────
def test_i_future_phase_dependency_is_violation():
    nodes = [_node("EARLY", "C02", phase="P02"), _node("LATE", "C01", phase="P10")]
    edges = [{"type": "depends_on", "from": "EARLY", "to": "LATE"}]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    v = vtg.validate(g, {"components": []})
    assert any(msg.startswith("(i)") and "EARLY" in msg and "LATE" in msg for msg in v)


def test_i_same_or_past_phase_dependency_is_allowed():
    nodes = [_node("EARLY", "C01", phase="P02"), _node("LATE", "C02", phase="P10")]
    edges = [{"type": "depends_on", "from": "LATE", "to": "EARLY"}]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    assert not any(msg.startswith("(i)") for msg in vtg.validate(g, {"components": []}))


# ─────────────────── (b) orphan ───────────────────
def test_b_orphan_node_detected():
    nodes = [_node("T1", "C01"), _node("ORPH", "C01")]
    edges = [{"type": "depends_on", "from": "T1", "to": "T1"}]  # ORPH がどの edge にも現れない
    # cycle を避けるため self-loop は使わず、別 node へ。
    edges = [
        {"type": "produces", "from": "T1", "to": "A1"},
    ]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    v = vtg.validate(g, {})
    assert any(msg.startswith("(b)") and "ORPH" in msg for msg in v)
    assert not any("T1" in msg and msg.startswith("(b)") for msg in v)


# ─────────────────── (c) producer 一意 ───────────────────
def test_c_duplicate_producer_detected():
    nodes = [_node("T1", "C01"), _node("T2", "C01")]
    edges = [
        {"type": "produces", "from": "T1", "to": "A1"},
        {"type": "produces", "from": "T2", "to": "A1"},  # 同一 artifact を 2 node が produce
    ]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    v = vtg.validate(g, {})
    assert any(msg.startswith("(c)") and "A1" in msg for msg in v)


# ─────────────────── (d) inventory 矛盾 ───────────────────
def test_d_inventory_contradiction_when_realizing_edge_removed():
    """P04 満たさない例: T3→T1 (C02 depends C01 の実現) を削除すると inventory 矛盾 1 件で exit1。"""
    g = _c2_graph()
    edges = [e for e in g["edges"] if not (e["type"] == "depends_on" and e["from"] == "T3" and e["to"] == "T1")]
    g2 = dtg.canonicalize({"schema_version": "1.0", "nodes": g["nodes"], "edges": edges})
    v = vtg.validate(g2, INVENTORY)
    dviol = [msg for msg in v if msg.startswith("(d)")]
    assert len(dviol) == 1
    assert v == dviol  # inventory 矛盾のみ (他検査は緑)


def test_d_reversed_only_edge_detected():
    """逆向き edge のみ (正方向欠落) も (d) で捕捉する。"""
    nodes = [_node("A", "C01"), _node("B", "C02")]
    # inventory: C02 depends_on C01 だが edge は C01(A)→C02(B) の逆向きのみ
    edges = [{"type": "depends_on", "from": "A", "to": "B"}]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    v = vtg.validate(g, INVENTORY)
    assert any(msg.startswith("(d)") for msg in v)


def test_d_no_nodes_for_component_skips():
    """component の node が graph に無ければ (d) は発火しない。"""
    nodes = [_node("A", "C01")]  # C02 の node なし
    edges = [{"type": "produces", "from": "A", "to": "X1"}]
    g = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": edges})
    v = vtg.validate(g, INVENTORY)
    assert not any(msg.startswith("(d)") for msg in v)


# ─────────────────── (e) consumes producer 不在 ───────────────────
def test_e_consumes_missing_producer():
    g = _c2_graph()
    edges = list(g["edges"]) + [{"type": "consumes", "from": "A99", "to": "T4"}]
    g2 = dtg.canonicalize({"schema_version": "1.0", "nodes": g["nodes"], "edges": edges})
    v = vtg.validate(g2, INVENTORY)
    assert any(msg.startswith("(e)") and "A99" in msg for msg in v)


# ─────────────────── (f) 非正準拒否 ───────────────────
def test_f_non_canonical_rejected():
    g = _c2_graph()
    # nodes を id 降順に並べ替え (非正準)
    scrambled = {"schema_version": "1.0", "nodes": list(reversed(g["nodes"])), "edges": g["edges"]}
    v = vtg.validate(scrambled, INVENTORY)
    assert any(msg.startswith("(f)") for msg in v)


def test_f_extra_toplevel_key_rejected():
    g = _c2_graph()
    g2 = dict(g)
    g2["extra"] = "hand-added"
    assert any(msg.startswith("(f)") for msg in vtg.validate(g2, INVENTORY))


# ─────────────────── (g) node.state 永続4値 ───────────────────
def test_g_ready_state_rejected():
    g = _c2_graph()
    nodes = [dict(n) for n in g["nodes"]]
    nodes[0]["state"] = "ready"
    g2 = dtg.canonicalize({"schema_version": "1.0", "nodes": nodes, "edges": g["edges"]})
    v = vtg.validate(g2, INVENTORY)
    assert any(msg.startswith("(g)") and "ready" in msg for msg in v)


# ─────────────────── main() CLI ───────────────────
def _write_plan(tmp_path, graph, inventory=None):
    (tmp_path / "task-graph.json").write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    if inventory is not None:
        (tmp_path / "component-inventory.json").write_text(
            json.dumps(inventory, ensure_ascii=False), encoding="utf-8"
        )


def test_main_exit0_on_valid_graph(tmp_path):
    _write_plan(tmp_path, _c2_graph(), INVENTORY)
    assert vtg.main([str(tmp_path)]) == 0


def test_main_exit1_on_violation(tmp_path, capsys):
    g = _c2_graph()
    edges = [e for e in g["edges"] if not (e["type"] == "depends_on" and e["from"] == "T3" and e["to"] == "T1")]
    g2 = dtg.canonicalize({"schema_version": "1.0", "nodes": g["nodes"], "edges": edges})
    _write_plan(tmp_path, g2, INVENTORY)
    assert vtg.main([str(tmp_path)]) == 1
    assert "(d)" in capsys.readouterr().out


def test_main_exit0_without_inventory(tmp_path):
    """component-inventory.json 欠落時は inventory 空扱いで (d) をスキップ。"""
    _write_plan(tmp_path, _c2_graph(), inventory=None)
    assert vtg.main([str(tmp_path)]) == 0


def test_main_usage_error_no_args():
    assert vtg.main([]) == 2


def test_main_usage_error_too_many_args():
    assert vtg.main(["a", "b"]) == 2


def test_main_not_a_directory(tmp_path):
    assert vtg.main([str(tmp_path / "missing")]) == 2


def test_main_bad_graph_json(tmp_path):
    (tmp_path / "task-graph.json").write_text("{ not json", encoding="utf-8")
    assert vtg.main([str(tmp_path)]) == 2


def test_main_bad_inventory_json(tmp_path):
    _write_plan(tmp_path, _c2_graph(), inventory=None)
    (tmp_path / "component-inventory.json").write_text("{ bad", encoding="utf-8")
    assert vtg.main([str(tmp_path)]) == 2
