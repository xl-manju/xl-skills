#!/usr/bin/env python3
# /// script
# name: project-task-status
# purpose: task-graph 駆動 build の live 実行状態を plan dir へ read-only 投影する観測ビュー生成器 (TG-C09)。task-graph.json (構造・単一 writer=derive・plugin-plans/ 追跡) は runtime state を焼かず ephemeral な task-state.json (eval-log/ build dir) が真の状態を持つため、両者を merge した派生ビュー (task-graph-status.json + 人間可読 task-progress.md) を plan dir へ書き出し「plugin-plans を見ても status が変わらない」観測性断絶を解消する。task-graph.json/task-state.json は一切書かず単一 writer 不変条件と graph_hash pin を温存する (state を task-graph.json へ焼くと hash が毎遷移で変わり pin が壊れるため投影で解決)。discovered-task inbox を読めば未処理の追加タスク (外ループ待ち) も同一ビューに載る。
# inputs:
#   - argv: --task-graph <task-graph.json> --task-state <task-state.json> [--out-json P] [--out-md P] [--discovered-inbox DIR]
#           (--out-json/--out-md 省略時は task-graph.json の親 dir へ task-graph-status.json / task-progress.md)
# outputs:
#   - stdout: 生成先パス + 進捗サマリ JSON
#   - stderr: 読込/parse/write エラー
#   - exit: 0=OK / 2=usage/IO error
#   - write-scope: <plan_dir>/task-graph-status.json + <plan_dir>/task-progress.md (派生ビューのみ・task-graph.json/task-state.json は不変)
# contexts: [C, E]
# network: false
# write-scope: <plan_dir>/task-graph-status.json + <plan_dir>/task-progress.md
# dependencies: []
# requires-python: ">=3.10"
# ///
"""live 実行状態の plan dir 投影器 (TG-C09・観測性断絶の解消)。

「plugin-plans/<slug>/task-graph.json を見ても status が変わらない」問題の解消。task-graph.json は
構造 SSOT (単一 writer=derive-task-graph・plugin-plans/ 追跡) であり runtime state を焼かない。
真の状態は build 毎に使い捨ての task-state.json (eval-log/<slug>/build dir・gitignore) にあるため、
両者を merge した派生ビューを plan dir へ書き出して可視化する:
  - task-graph.json/task-state.json は read-only (単一 writer 不変条件・graph_hash pin を温存)。
    state を task-graph.json へ焼くと canonical hash が毎遷移で変わり pin (F10) が壊れるため、
    上書きでなく投影で解く。
  - dispatch-ready-set.merge_state (task-state を task-graph へ overlay) と
    summarize-task-progress.summarize (by_state/completion_rate 集計) を sibling import で再利用し
    SSOT を二重実装しない。
  - discovered-task inbox を渡せば未処理 (外ループ待ち) の追加タスクも同一ビューに載る
    (「新しいタスクを追加した」対応が plan dir で見える)。

出力は 2 ファイル: task-graph-status.json (機械可読・overlay 済 node + summary + discovered) と
task-progress.md (人間可読・phase グループの ✓/▶/✗/☐ チェックリスト)。どちらも派生ビューゆえ
手書き編集しない (再生成で上書き)。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

_STATE_ICON = {"done": "✓", "running": "▶", "blocked": "✗", "pending": "☐"}
_TERMINAL_DISCOVERED = {"accepted", "rejected", "superseded"}


def _load_sibling(stem: str):
    """同一 scripts/ 配下のハイフン名 module を importlib で読み込む (TG SSOT 再利用)。"""
    path = Path(__file__).resolve().parent / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_dispatch = _load_sibling("dispatch-ready-set")
_summarize = _load_sibling("summarize-task-progress")
merge_state = _dispatch.merge_state
summarize = _summarize.summarize


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pending_discovered(inbox: Path) -> list[dict]:
    """discovered-task inbox から未処理 (status が terminal でない) の追加タスクを昇順で返す。"""
    if not inbox.is_dir():
        return []
    out: list[dict] = []
    for form_path in sorted(inbox.glob("*.json")):
        try:
            form = _read_json(form_path)
        except (OSError, json.JSONDecodeError):
            continue
        status = form.get("status") or "pending"
        if status in _TERMINAL_DISCOVERED:
            continue
        node = form.get("proposed_node", {}) if isinstance(form.get("proposed_node"), dict) else {}
        out.append({
            "form": form_path.name,
            "proposed_id": node.get("id"),
            "title": node.get("title"),
            "phase_ref": node.get("phase_ref"),
            "change_level": form.get("change_level"),
            "reason": form.get("reason"),
            "status": status,
        })
    return out


def build_status(graph: dict, task_state: dict, build_dir: Path,
                 discovered: list[dict]) -> dict:
    """overlay 済 node + summary + discovered を統合した status ビュー dict を返す (read-only 純関数)。"""
    state_by_id = {n.get("id"): n for n in task_state.get("nodes", []) if isinstance(n, dict)}
    merged = merge_state(graph, state_by_id)
    live_nodes = []
    for n in merged.get("nodes", []):
        if not isinstance(n, dict):
            continue
        st = state_by_id.get(n.get("id"), {})
        entry = {
            "id": n.get("id"),
            "title": n.get("title"),
            "phase_ref": n.get("phase_ref"),
            "entity_ref": n.get("entity_ref"),
            "state": n.get("state", "pending"),
        }
        if st.get("blocked_reason"):
            entry["blocked_reason"] = st.get("blocked_reason")
        if st.get("route_report"):
            entry["route_report"] = st.get("route_report")
        live_nodes.append(entry)
    live_nodes.sort(key=lambda x: str(x.get("id")))
    # summary は **full graph (overlay 済 live_nodes) を母集団**に算出する。task-state.json は
    # build 中 sparse (遷移発生 node のみ on-demand 追加) ゆえ summarize(task_state) の分母を使うと、
    # 未着手 node が分母から欠け「done 1件のみ→完了率100%」と過大表示され、直下の全 graph
    # チェックリスト (未着手=pending 計上) と同一文書で矛盾する。route_report_count のみ
    # summarize (build_dir の route-*.json 実ファイル数) を read-only 流用する。
    by_state = {k: 0 for k in ("pending", "running", "done", "blocked")}
    for n in live_nodes:
        st = n.get("state")
        if st in by_state:
            by_state[st] += 1
    total = len(live_nodes)
    completion_rate = (by_state["done"] / total) if total else 0.0
    blocked_tasks = [n["id"] for n in live_nodes if n.get("state") == "blocked"]
    route_report_count = summarize(task_state, build_dir)["route_report_count"]
    return {
        "_generated": "project-task-status.py (派生ビュー・手書き編集しない・再生成で上書き)",
        "graph_hash": task_state.get("graph_hash"),
        "summary": {
            "total": total,
            "by_state": by_state,
            "completion_rate": completion_rate,
            "blocked_tasks": blocked_tasks,
            "route_report_count": route_report_count,
        },
        "nodes": live_nodes,
        "discovered_pending": discovered,
    }


def render_markdown(status: dict) -> str:
    """status ビューを人間可読な task-progress.md 文字列へ整形する (phase グループ・状態アイコン)。"""
    s = status["summary"]
    pct = round(s["completion_rate"] * 100)
    lines = [
        "# task-progress (live 実行状態・派生ビュー)",
        "",
        "> `project-task-status.py` 生成の派生ビュー。構造の正本は `task-graph.json`、状態の正本は "
        "build dir の `task-state.json`。手書き編集しない (再生成で上書き)。build 異常終了時は最後の "
        "投影時点のスナップショットで stale の可能性がある (最新は再投影で得る)。",
        "",
        "- 凡例: ✓=done / ▶=running / ✗=blocked / ☐=pending / ⏳=未処理の発見タスク (外ループ待ち)",
        f"- 完了率: **{pct}%** ({s['by_state']['done']}/{s['total']})",
        f"- 状態内訳: done={s['by_state']['done']} / running={s['by_state']['running']} "
        f"/ blocked={s['by_state']['blocked']} / pending={s['by_state']['pending']}",
        f"- route-report 数: {s['route_report_count']}",
    ]
    if status.get("graph_hash"):
        lines.append(f"- graph_hash pin: `{status['graph_hash']}`")
    lines.append("")

    # phase グループの node チェックリスト。
    by_phase: dict[str, list[dict]] = {}
    for n in status["nodes"]:
        by_phase.setdefault(str(n.get("phase_ref")), []).append(n)
    for phase in sorted(by_phase):
        lines.append(f"## {phase}")
        for n in by_phase[phase]:
            icon = _STATE_ICON.get(n.get("state"), "?")
            extra = ""
            if n.get("blocked_reason"):
                extra = f" — blocked_reason={n['blocked_reason']}"
            lines.append(f"- {icon} `{n.get('id')}` {n.get('title', '')}{extra}")
        lines.append("")

    disc = status.get("discovered_pending") or []
    if disc:
        lines.append("## 未処理の発見タスク (外ループ待ち・`--mode update --discovered-inbox` で反映)")
        for d in disc:
            lines.append(
                f"- ⏳ `{d.get('proposed_id')}` {d.get('title', '')} "
                f"[{d.get('change_level')}] — {d.get('reason', '')}"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="project-task-status.py",
        description="live 実行状態を plan dir へ read-only 投影する (task-graph-status.json + task-progress.md)。",
    )
    p.add_argument("--task-graph", required=True, help="task-graph.json (構造・plan dir)")
    p.add_argument("--task-state", required=True, help="task-state.json (live 状態・build dir)")
    p.add_argument("--out-json", default=None, help="省略時 <task-graph の親>/task-graph-status.json")
    p.add_argument("--out-md", default=None, help="省略時 <task-graph の親>/task-progress.md")
    p.add_argument("--discovered-inbox", default=None, help="未処理の発見タスクを載せる discovered-task inbox dir")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    graph_path = Path(args.task_graph)
    state_path = Path(args.task_state)
    try:
        graph = _read_json(graph_path)
        task_state = _read_json(state_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"読込/parse 失敗: {exc}", file=sys.stderr)
        return 2

    plan_dir = graph_path.parent
    out_json = Path(args.out_json) if args.out_json else plan_dir / "task-graph-status.json"
    out_md = Path(args.out_md) if args.out_md else plan_dir / "task-progress.md"
    discovered = _pending_discovered(Path(args.discovered_inbox)) if args.discovered_inbox else []

    status = build_status(graph, task_state, state_path.parent, discovered)
    try:
        out_json.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        out_md.write_text(render_markdown(status), encoding="utf-8")
    except OSError as exc:
        print(f"write error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({
        "status_json": str(out_json),
        "progress_md": str(out_md),
        "completion_rate": status["summary"]["completion_rate"],
        "by_state": status["summary"]["by_state"],
        "discovered_pending": len(discovered),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
