#!/usr/bin/env python3
# /// script
# name: verify-index-topsort
# purpose: 生成 plan の index(main) が依存 top-sort 順で全タスク仕様書を漏れなく列挙しているかを検証する決定論ゲート。
# inputs:
#   - argv: <plan-dir> [--index NAME] [--specs-dir DIR]
# outputs:
#   - stdout: OK サマリ
#   - stderr: top-sort / 列挙漏れ / 循環 violation
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""index.md(main) が依存 top-sort 順で全タスク仕様書を列挙しているかを機械検証する。

判定 (run-plugin-dev-plan の C1 / §8 index 契約):
  - 各タスク仕様書 frontmatter の `id` 集合 == index が参照する id 集合 (列挙漏れ 0)
  - 仕様書 `depends_on` の各辺 dep->node について index 上で dep が node より前に出現
  - 依存グラフに循環が無い
  - index 内 id 重複が無い

yaml は import しない (scripts 規約)。frontmatter は最小パーサで読む。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 仕様書 id トークン (例: C01 / P1 / R12)。行内の最初の 1 個を採る。
ID_RE = re.compile(r"\b([A-Z]{1,5}\d{1,3})\b")


def parse_frontmatter(text: str) -> dict:
    """SKILL/spec の YAML frontmatter を最小パースする (scalar + inline/block list)。"""
    fm: dict = {}
    if not text.startswith("---"):
        return fm
    parts = text.split("---", 2)
    if len(parts) < 3:
        return fm
    current_list_key: str | None = None
    for line in parts[1].splitlines():
        m_item = re.match(r"^\s+-\s+(.+?)\s*$", line)
        if m_item and current_list_key is not None:
            fm.setdefault(current_list_key, [])
            if isinstance(fm[current_list_key], list):
                fm[current_list_key].append(m_item.group(1).strip().strip('"').strip("'"))
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            if not line.strip():
                current_list_key = None
            continue
        key, val = m.group(1), m.group(2).split("#", 1)[0].strip()
        if val == "":
            fm[key] = []
            current_list_key = key
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            fm[key] = [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]
            current_list_key = None
        else:
            fm[key] = val.strip().strip('"').strip("'")
            current_list_key = None
    return fm


def body_after_frontmatter(text: str) -> str:
    """先頭 --- frontmatter を除いた本文を返す (frontmatter 内の id/plugin_meta を拾わない)。"""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2]
    return text


def extract_ordered_ids(index_text: str) -> list[str]:
    """index 本文を行走査し、各行の最初の id トークンを出現順に集める (重複も保持)。

    frontmatter (plugin_meta 等) は走査対象外。呼び出し側で body_after_frontmatter 済みを渡す。
    """
    ids: list[str] = []
    for line in index_text.splitlines():
        m = ID_RE.search(line)
        if m:
            ids.append(m.group(1))
    return ids


def _depends_on(meta: dict) -> list[str]:
    raw = meta.get("depends_on", [])
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.strip("[]").split(",") if x.strip()]
    return [str(x).strip() for x in raw if str(x).strip()]


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


def verify(ordered_ids: list[str], specs: dict[str, dict]) -> list[str]:
    """ordered_ids(index 順) と specs(id->frontmatter) を突合して errors を返す。"""
    errors: list[str] = []
    spec_ids = set(specs)
    seen: set[str] = set()
    pos: dict[str, int] = {}
    for idx, sid in enumerate(ordered_ids):
        if sid in seen:
            errors.append(f"index に id 重複: {sid}")
        else:
            seen.add(sid)
            pos[sid] = idx
    for sid in sorted(spec_ids - seen):
        errors.append(f"index に未列挙の仕様書: {sid} (全タスク仕様書を index に列挙すること)")
    for iid in sorted(seen - spec_ids):
        errors.append(f"index が参照する仕様書が存在しない: {iid}")

    edges: list[tuple[str, str]] = []
    for node, meta in specs.items():
        for dep in _depends_on(meta):
            edges.append((dep, node))
            if dep not in spec_ids:
                errors.append(f"{node} の依存 {dep} に対応する仕様書が無い")
                continue
            if dep in pos and node in pos and pos[dep] > pos[node]:
                errors.append(
                    f"top-sort 違反: {dep} は依存先 {node} より前に列挙される必要がある"
                )
    cyc = detect_cycle(spec_ids, [(d, n) for d, n in edges if d in spec_ids])
    if cyc:
        errors.append(f"依存グラフに循環: {' -> '.join(cyc)}")
    return errors


def collect_specs(specs_dir: Path, index_path: Path) -> dict[str, dict]:
    """specs_dir 配下 *.md (index を除く) を id->frontmatter で収集する。"""
    specs: dict[str, dict] = {}
    for md in sorted(specs_dir.glob("*.md")):
        if md.resolve() == index_path.resolve():
            continue
        fm = parse_frontmatter(md.read_text(encoding="utf-8"))
        sid = str(fm.get("id", "")).strip()
        if sid:
            specs[sid] = fm
    return specs


def run(plan_dir: Path, index_name: str, specs_dir: Path | None) -> tuple[int, list[str]]:
    index_path = plan_dir / index_name
    if not index_path.is_file():
        return 2, [f"index が見つからない: {index_path}"]
    if specs_dir is None:
        sub = plan_dir / "specs"
        specs_dir = sub if sub.is_dir() else plan_dir
    specs = collect_specs(specs_dir, index_path)
    if not specs:
        return 2, [f"タスク仕様書が見つからない: {specs_dir}"]
    ordered = extract_ordered_ids(body_after_frontmatter(index_path.read_text(encoding="utf-8")))
    return (1 if (errs := verify(ordered, specs)) else 0), errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="index(main) の依存 top-sort 全列挙を検証する")
    ap.add_argument("plan_dir", help="plan ディレクトリ")
    ap.add_argument("--index", default="index.md", help="index ファイル名 (既定 index.md)")
    ap.add_argument("--specs-dir", default=None, help="タスク仕様書ディレクトリ (既定 plan_dir[/specs])")
    args = ap.parse_args(argv)

    plan_dir = Path(args.plan_dir)
    if not plan_dir.is_dir():
        sys.stderr.write(f"not a directory: {plan_dir}\n")
        return 2
    specs_dir = Path(args.specs_dir) if args.specs_dir else None
    code, msgs = run(plan_dir, args.index, specs_dir)
    if code == 0:
        sys.stdout.write("OK: index は依存 top-sort 順で全タスク仕様書を列挙している\n")
        return 0
    for m in msgs:
        sys.stderr.write(m + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
