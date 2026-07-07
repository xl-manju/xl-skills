#!/usr/bin/env python3
# /// script
# name: check-shape-non-regression
# purpose: 新shape (task-graph 駆動) の acceptance_criterion 携帯率が旧shape (13 phase §5) 基準線を下回らず、derive-task-graph の2回実行が byte 一致するかを検査する非劣化ゲート (C14 a,c)。
# inputs:
#   - argv: <PLAN_DIR> [--recommend-fallback]
# outputs:
#   - stdout: violations or OK / fallback 推奨
#   - exit: 0=OK / 1=劣化検出 / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""新旧shape 非劣化ゲート (C14 (a) 精度携帯率 / (c) 再現性)。

(a) acceptance_attachment_rate(nodes, edges): 新shape task node のうち検証可能な
    acceptance_criterion (検証不能自然文は除外) を携帯し、かつ検証可能成果物 (produces) を
    指す node の割合。legacy_baseline_rate(phase_files): 旧shape §5 項目のうち検証可能な
    outcome を文中携帯する率 (散文アクション項目は 0)。前者が後者を下回れば劣化。
(c) check_reproducibility(plan_dir): derive-task-graph.derive() を同一入力に 2 回適用し
    canonical_json() の byte 一致 + node id 集合一致を検証する。
(b) 品質 A/B genuine 判定は本 script の責務外 (C02 R1-evaluate.md 側)。C10⇔C14 相互参照:
    本ゲートが劣化検出した場合は shape_marker を fixed-13-phase へ fallback する
    (--recommend-fallback 指定時に推奨値を追加出力)。
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

# acceptance_criterion が「検証可能」であることの簡易素片 (具体語シグナル)。
_CONCRETE_RE = re.compile(r"[A-Za-z]{3,}|[0-9]|[≥≤=]|一致|検証|テスト|exit")
# 旧shape §5 項目が「検証可能な outcome を携帯する」ことの簡易素片。散文アクション
# (「〜を実装する」等) を 0 とみなすため、期待結果を表す語のみを signal にする
# (「検証する」等のアクション動詞は含めない=二層分離のヒューリスティック層)。
_LEGACY_OUTCOME_RE = re.compile(r"一致|exit\s*0|を満たす|以上|≥|≤|等しい|expected")

_DTG_CACHE = None


def _load_derive_task_graph():
    """同梱 derive-task-graph.py を file-path import する (derive/canonicalize/checklist 共有)。"""
    global _DTG_CACHE
    if _DTG_CACHE is None:
        path = Path(__file__).resolve().parent / "derive-task-graph.py"
        spec = importlib.util.spec_from_file_location("derive_task_graph", path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _DTG_CACHE = mod
    return _DTG_CACHE


def _is_verifiable_criterion(text: str) -> bool:
    """acceptance_criterion が検証可能か (検証不能な短い自然文 "がんばる" 等を除外)。

    ヒューリスティック: 20 文字以上なら実質的な事前解決判断を内包しうるとみなし True、
    未満でも具体語 (ファイル名/数値/比較/一致 等) を含めば True。20 文字未満かつ
    具体語なしのみを検証不能 (False) とする。
    """
    t = str(text or "").strip()
    if not t:
        return False
    if len(t) >= 20:
        return True
    return bool(_CONCRETE_RE.search(t))


def _node_has_produces(node: dict, producers: set) -> bool:
    """node が検証可能成果物を指すか (inline produces field or produces エッジの from)。"""
    p = node.get("produces")
    if isinstance(p, list):
        if any(isinstance(x, str) and x.strip() for x in p):
            return True
    elif isinstance(p, str) and p.strip():
        return True
    return node.get("id") in producers


def acceptance_attachment_rate(nodes, edges=None, criterion_key: str = "acceptance_criterion") -> float:
    """nodes のうち検証可能 acceptance_criterion を携帯し検証可能成果物を指す node の割合。

    produces 判定: edges が渡された場合は produces エッジ (from=node id) を 1 件以上持つこと、
    もしくは node が inline produces field を持つことを要求する。edges 未指定 (None) かつ node に
    produces field も無い場合は produces 要件を課さず acceptance_criterion 非空 (かつ検証可能) の
    みで判定する (P04 C14 精度受入例)。検証不能な自然文 ("がんばる" 等) は携帯カウントから除外。
    """
    if not nodes:
        return 0.0
    producers: set = set()
    if edges:
        for e in edges:
            if isinstance(e, dict) and e.get("type") == "produces":
                producers.add(e.get("from"))
    attached = 0
    for n in nodes:
        if not isinstance(n, dict):
            continue
        crit = n.get(criterion_key)
        if not (isinstance(crit, str) and crit.strip()):
            continue
        if not _is_verifiable_criterion(crit):
            continue
        node_has_produces_field = "produces" in n
        requires_produces = edges is not None or node_has_produces_field
        if requires_produces and not _node_has_produces(n, producers):
            continue
        attached += 1
    return attached / len(nodes)


def legacy_baseline_rate(phase_files) -> float:
    """旧shape §5 完了チェックリスト項目のうち検証可能な outcome を文中携帯する率。

    §5 項目は定義上受入基準を兼ねるが、旧shape の散文アクション項目 (「〜を実装する」) は
    検証可能成果物/受入基準を文中に携帯しないため 0 とカウントする (P04 C14 精度受入例:
    旧shape fixture の携帯率 0/1=0% を基準線とする)。項目が 1 件も無ければ 0.0。
    """
    dtg = _load_derive_task_graph()
    items: list[str] = []
    for pf in phase_files:
        try:
            text = Path(pf).read_text(encoding="utf-8")
        except OSError:
            continue
        sections = specfm.phase_body_sections(text)
        body = sections.get(dtg.CHECKLIST_SECTION, "")
        items.extend(dtg._parse_checklist_items(body))
    if not items:
        return 0.0
    carried = sum(1 for it in items if _LEGACY_OUTCOME_RE.search(str(it)))
    return carried / len(items)


def check_reproducibility(plan_dir) -> list[str]:
    """同一 plan_dir で derive を 2 回実行し canonical byte 一致 + node id 集合一致を検証する。"""
    dtg = _load_derive_task_graph()
    plan_dir = Path(plan_dir)
    run1 = dtg.derive(plan_dir)
    run2 = dtg.derive(plan_dir)
    violations: list[str] = []
    j1 = dtg.canonical_json(run1).encode("utf-8")
    j2 = dtg.canonical_json(run2).encode("utf-8")
    if j1 != j2:
        violations.append("再現性違反: 2 回の derive 出力が canonical byte 不一致")
    ids1 = {n.get("id") for n in dtg.canonicalize(run1).get("nodes", [])}
    ids2 = {n.get("id") for n in dtg.canonicalize(run2).get("nodes", [])}
    if ids1 != ids2:
        violations.append(f"再現性違反: node id 集合が両実行で不一致 (差分={sorted(ids1 ^ ids2)})")
    return violations


def _usage() -> int:
    print("usage: check-shape-non-regression.py <PLAN_DIR> [--recommend-fallback]", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    recommend_fallback = False
    positional: list[str] = []
    for a in argv:
        if a == "--recommend-fallback":
            recommend_fallback = True
        elif a.startswith("-"):
            print(f"unknown option: {a}", file=sys.stderr)
            return _usage()
        else:
            positional.append(a)
    if len(positional) != 1:
        return _usage()

    plan_dir = Path(positional[0])
    if not plan_dir.is_dir():
        print(f"not a directory: {plan_dir}", file=sys.stderr)
        return 2

    nodes: list = []
    edges = None
    tg_path = plan_dir / "task-graph.json"
    if tg_path.exists():
        try:
            graph = json.loads(tg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"task-graph.json 読込/parse 失敗: {exc}", file=sys.stderr)
            return 2
        if isinstance(graph, dict):
            nodes = graph.get("nodes") or []
            edges = graph.get("edges")

    attach = acceptance_attachment_rate(nodes, edges=edges)
    phase_files = sorted(plan_dir.glob("phase-*.md"), key=lambda p: p.name)
    baseline = legacy_baseline_rate(phase_files)
    repro = check_reproducibility(plan_dir)

    violations: list[str] = []
    if attach < baseline:
        violations.append(
            f"acceptance 携帯率劣化: 新shape {attach:.3f} < 旧基準線 {baseline:.3f} (平均回帰禁止)"
        )
    violations.extend(repro)

    if violations:
        for v in violations:
            print(v)
        if recommend_fallback:
            print("shape_marker: fixed-13-phase (推奨: 非劣化ゲート未達のため task-graph-derived への解放を block)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
