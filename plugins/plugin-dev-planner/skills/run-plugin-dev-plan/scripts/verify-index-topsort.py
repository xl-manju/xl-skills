#!/usr/bin/env python3
# /// script
# name: verify-index-topsort
# purpose: 生成 plan の index(main) が 13 フェーズ(P01..P13)を phase_number 昇順で全列挙し、かつ component-inventory.json の component 依存 DAG が非循環(top-sort 可能)であることを検証する二層決定論ゲート。
# inputs:
#   - argv: <plan-dir> [--index NAME] [--inventory PATH]
# outputs:
#   - stdout: OK サマリ
#   - stderr: phase 列挙漏れ / 昇順違反 / 重複 / DAG 循環 violation
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""index.md(main) の phase 完全性と component 依存 DAG の非循環を二層で機械検証する。

per-phase 転換 (凍結契約 §3/§4/§8/§13-C4) の C4 依存整合:
  - 層1 (phase 完全性): index の `## フェーズ一覧` が P01..P13 を **phase_number 昇順** で
    全 13 列挙する (漏れ 0 / 重複 0 / 昇順)。id 体系は specfm.PHASE_ID_RE。
  - 層2 (component DAG): component-inventory.json の components[] の `depends_on` 有向グラフが
    非循環 (top-sort 可能) で、各 depends_on が実在 component を指す。

旧 per-component (C*.md) の spec-id top-sort 突合は廃止 (phase 軸へ全面転換)。
yaml は import しない (scripts 規約)。inventory は JSON。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

# 行内から phase id (P01..P13) を拾う探索用パターン (specfm.PHASE_ID_RE は full-match ゆえ別途定義)。
PHASE_TOKEN_RE = re.compile(r"\bP(?:0[1-9]|1[0-3])\b")
_PHASE_LIST_HEADING = "フェーズ一覧"


def body_after_frontmatter(text: str) -> str:
    """先頭 --- frontmatter を除いた本文を返す (frontmatter 内 id を拾わない)。"""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2]
    return text


def expected_phase_ids() -> list[str]:
    """canonical な P01..P13 (phase_number 昇順) を返す。"""
    return [specfm.phase_id(n) for n in range(1, 14)]


def extract_phase_list_ids(index_body: str) -> tuple[list[str], bool]:
    """index 本文の `## フェーズ一覧` section 内から phase id を出現順に集める。

    section 見出しから次の `## ` 見出し(または EOF)までの各行の最初の phase-id を拾う。
    prose の他 section が phase id を言及しても拾わないよう section を限定する。
    戻り値 = (出現順 id 列, section が見つかったか)。
    """
    ids: list[str] = []
    in_section = False
    found = False
    for line in index_body.splitlines():
        if line.startswith("## "):
            in_section = _PHASE_LIST_HEADING in line
            found = found or in_section
            continue
        if in_section:
            m = PHASE_TOKEN_RE.search(line)
            if m:
                ids.append(m.group(0))
    return ids, found


def verify_phase_enumeration(ordered: list[str], has_section: bool) -> list[str]:
    """index の phase 列挙が P01..P13 を昇順で全列挙するか検査する。"""
    errors: list[str] = []
    if not has_section:
        errors.append(f"index に `## {_PHASE_LIST_HEADING}` section が無い (P01..P13 を昇順列挙すること)")
        return errors
    seen: set[str] = set()
    for pid in ordered:
        if pid in seen:
            errors.append(f"index フェーズ一覧に id 重複: {pid}")
        seen.add(pid)
    expected = expected_phase_ids()
    missing = [p for p in expected if p not in seen]
    if missing:
        errors.append(f"index フェーズ一覧に未列挙の phase: {missing} (13 フェーズ P01..P13 を全列挙すること)")
    extra = [p for p in ordered if p not in expected]
    if extra:
        errors.append(f"index フェーズ一覧に想定外の phase id: {sorted(set(extra))} (P01..P13 のみ許容)")
    # 昇順: 重複/余分を除いた出現順が expected と一致するか。
    dedup_ordered = list(dict.fromkeys(ordered))
    canonical_seq = [p for p in dedup_ordered if p in expected]
    if canonical_seq != expected and not missing and not extra:
        errors.append(
            f"index フェーズ一覧が phase_number 昇順でない: 出現順={canonical_seq} 期待={expected}"
        )
    return errors


def load_components(inventory_path: Path) -> tuple[list[dict], str | None]:
    """component-inventory.json の components[] を返す (エラー時 (_, message))。"""
    try:
        data = json.loads(inventory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], f"component-inventory JSON parse error: {exc}"
    if not isinstance(data, dict) or not isinstance(data.get("components"), list):
        return [], "component-inventory.json に components[] list が無い"
    return [c for c in data["components"] if isinstance(c, dict)], None


def detect_cycle(nodes: set[str], edges: list[tuple[str, str]]) -> list[str] | None:
    """dep->node の有向グラフから循環経路を 1 つ返す (無ければ None)。"""
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for dep, node in edges:
        adj.setdefault(dep, []).append(node)
        adj.setdefault(node, adj.get(node, []))
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in adj}
    stack: list[str] = []

    def dfs(u: str) -> list[str] | None:
        color[u] = GRAY
        stack.append(u)
        for v in adj.get(u, []):
            if color[v] == GRAY:
                return stack[stack.index(v):] + [v]
            if color[v] == WHITE:
                r = dfs(v)
                if r:
                    return r
        stack.pop()
        color[u] = BLACK
        return None

    for n in sorted(adj):
        if color[n] == WHITE:
            r = dfs(n)
            if r:
                return r
    return None


def verify_component_dag(components: list[dict]) -> list[str]:
    """components[] の depends_on 有向グラフが非循環で、各依存が実在 component を指すか検査する。"""
    errors: list[str] = []
    ids = {str(c.get("id", "")).strip() for c in components if str(c.get("id", "")).strip()}
    edges: list[tuple[str, str]] = []
    for c in components:
        node = str(c.get("id", "")).strip()
        if not node:
            continue
        raw = c.get("depends_on", [])
        deps = raw if isinstance(raw, list) else []
        for dep in deps:
            dep = str(dep).strip()
            if not dep:
                continue
            if dep not in ids:
                errors.append(f"component {node} の depends_on={dep!r} に対応する component が無い")
                continue
            edges.append((dep, node))
    cyc = detect_cycle(ids, [(d, n) for d, n in edges if d in ids])
    if cyc:
        errors.append(f"component 依存グラフに循環 (top-sort 不能): {' -> '.join(cyc)}")
    return errors


def run(plan_dir: Path, index_name: str, inventory_path: Path | None) -> tuple[int, list[str]]:
    index_path = plan_dir / index_name
    if not index_path.is_file():
        return 2, [f"index が見つからない: {index_path}"]
    if inventory_path is None:
        inventory_path = plan_dir / "component-inventory.json"
    if not inventory_path.is_file():
        return 2, [f"component-inventory.json が見つからない: {inventory_path}"]

    errors: list[str] = []
    ordered, has_section = extract_phase_list_ids(
        body_after_frontmatter(index_path.read_text(encoding="utf-8"))
    )
    errors.extend(verify_phase_enumeration(ordered, has_section))

    components, msg = load_components(inventory_path)
    if msg:
        return 2, [msg]
    errors.extend(verify_component_dag(components))
    return (1 if errors else 0), errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="index の phase 完全性 + component DAG 非循環を二層検証する")
    ap.add_argument("plan_dir", help="plan ディレクトリ")
    ap.add_argument("--index", default="index.md", help="index ファイル名 (既定 index.md)")
    ap.add_argument("--inventory", default=None, help="component-inventory.json (既定 <plan_dir>/component-inventory.json)")
    args = ap.parse_args(argv)

    plan_dir = Path(args.plan_dir)
    if not plan_dir.is_dir():
        sys.stderr.write(f"not a directory: {plan_dir}\n")
        return 2
    inventory_path = Path(args.inventory) if args.inventory else None
    code, msgs = run(plan_dir, args.index, inventory_path)
    if code == 0:
        sys.stdout.write("OK: index が P01..P13 を昇順全列挙し component 依存 DAG が非循環\n")
        return 0
    for m in msgs:
        sys.stderr.write(m + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
