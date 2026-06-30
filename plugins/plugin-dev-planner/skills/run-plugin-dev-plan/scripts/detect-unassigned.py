#!/usr/bin/env python3
# /// script
# name: detect-unassigned
# purpose: コンポーネント目録に対しタスク仕様書が 1 本ずつ割り当たり未配置(unassigned-task)が 0 件であること、各仕様書が必須セクションを持つことを検証する決定論ゲート。
# inputs:
#   - argv: --inventory FILE --specs-dir DIR
# outputs:
#   - stdout: OK サマリ
#   - stderr: 未配置 / 必須セクション欠落 violation
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""コンポーネント目録(N)とタスク仕様書群を突合し、未配置 0 件を保証する。

判定 (run-plugin-dev-plan の C5 / §5 unassigned-task 検出の借用):
  - 目録の各コンポーネント id に対応する仕様書が存在する (未配置=unassigned=0)
  - 各仕様書が必須セクション (目的/成果物/完了条件) を持ち、各見出し直後の本文が非空である
    (本文の床・io-contract.md §9。frontmatter は specfm が縛り、本文は空セクションを弾く)
  - 目録に無い id の仕様書 (orphan) は warning (停止はさせない)

yaml は import しない。目録は JSON ({"components":[{"id":..}]} or ["C01",..]) か
id トークン行のテキストを受理する。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ID_RE = re.compile(r"\b([A-Z]{1,5}\d{1,3})\b")
# 各タスク仕様書が持つべき必須セクション (本文 section 契約の正本 = io-contract.md §9
# 「タスク仕様書 本文 section 契約」: 目的/成果物/完了条件)。
# frontmatter 形状は specfm が厳格に operationalize する一方、本文は「見出し存在 + 直後の
# 非空本文」を最小の床として強制する (空セクションを弾く=品質精度の床・io-contract.md §9)。
REQUIRED_SECTIONS = ("## 目的", "## 成果物", "## 完了条件")


def parse_frontmatter_id(text: str) -> str:
    """spec frontmatter の `id` スカラを返す (無ければ空)。"""
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    for line in parts[1].splitlines():
        m = re.match(r"^id:\s*(.+?)\s*$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return ""


def load_inventory(text: str) -> list[str]:
    """目録テキストから期待コンポーネント id を順序保持で抽出する。"""
    stripped = text.strip()
    if stripped:
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and isinstance(data.get("components"), list):
            return [str(c.get("id", "")).strip() for c in data["components"] if str(c.get("id", "")).strip()]
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    ids: list[str] = []
    for line in text.splitlines():
        m = ID_RE.search(line)
        if m:
            ids.append(m.group(1))
    # 重複排除 (出現順保持)
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def load_inventory_components(text: str) -> list[dict]:
    """目録が object 形式 ({"components":[{..}]}) のとき component dict 一覧を返す。

    list 形式 (["C01",..]) や id トークン行のテキスト形式では [] を返し、
    build_target 検査をスキップする (後方互換: 後者は build_target を持たないため)。
    実 plan の component-inventory.json は object 形式で、各 component が L4 実体化先
    `build_target` を持つ (io-contract.md §9 L3→L4 追跡)。
    """
    stripped = text.strip()
    if not stripped:
        return []
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict) and isinstance(data.get("components"), list):
        return [c for c in data["components"] if isinstance(c, dict)]
    return []


def collect_spec_ids(specs_dir: Path) -> dict[str, Path]:
    """specs_dir 配下 *.md (index/main を除く) の id->path を収集する。"""
    out: dict[str, Path] = {}
    for md in sorted(specs_dir.glob("*.md")):
        if md.stem in {"index", "main"}:
            continue
        sid = parse_frontmatter_id(md.read_text(encoding="utf-8"))
        if sid:
            out[sid] = md
    return out


def find_unassigned(expected: list[str], present: set[str]) -> list[str]:
    """目録にあるが仕様書が無い id (未配置) を返す。"""
    return [e for e in expected if e not in present]


def find_orphans(expected: list[str], present: set[str]) -> list[str]:
    """仕様書はあるが目録に無い id を返す。"""
    return sorted(present - set(expected))


def missing_sections(spec_text: str) -> list[str]:
    """必須セクション欠落を返す。"""
    return [sec for sec in REQUIRED_SECTIONS if sec not in spec_text]


def empty_body_sections(spec_text: str) -> list[str]:
    """必須セクション見出しは在るが直後の本文が空のもの (本文の床違反) を返す。

    見出し行 (`## 目的` 等) を行単位で検出し、次の `## ` 見出し or EOF までの本文に
    非空テキストが 1 行も無ければ「空セクション」とみなす。見出し自体の欠落は
    `missing_sections()` の責務なので、ここでは見出しが存在する section のみ対象にする。
    frontmatter は specfm が厳格に縛るが本文は自由記述ゆえ、空セクションだけは最小の
    機械的な床として弾く (品質精度の床・io-contract.md §9)。
    """
    lines = spec_text.splitlines()
    out: list[str] = []
    for sec in REQUIRED_SECTIONS:
        idx = next(
            (i for i, ln in enumerate(lines)
             if ln.strip() == sec or ln.strip().startswith(sec + " ")),
            None,
        )
        if idx is None:
            continue  # 見出し欠落は missing_sections の責務
        body: list[str] = []
        for ln in lines[idx + 1:]:
            if ln.startswith("## "):
                break
            body.append(ln)
        if not "".join(body).strip():
            out.append(sec)
    return out


def run(inventory_text: str, specs_dir: Path) -> tuple[int, list[str], list[str]]:
    """(exit_code, errors, warnings) を返す。"""
    expected = load_inventory(inventory_text)
    if not expected:
        return 2, ["目録から期待コンポーネント id を抽出できない"], []
    present = collect_spec_ids(specs_dir)
    errors: list[str] = []
    warnings: list[str] = []
    for uid in find_unassigned(expected, set(present)):
        errors.append(f"未配置(unassigned-task): コンポーネント {uid} に対応する仕様書が無い")
    for oid in find_orphans(expected, set(present)):
        warnings.append(f"orphan: 仕様書 {oid} は目録に無い (目録へ追記検討)")
    for sid, path in sorted(present.items()):
        spec_text = path.read_text(encoding="utf-8")
        for sec in missing_sections(spec_text):
            errors.append(f"{sid} ({path.name}): 必須セクション欠落 '{sec}'")
        for sec in empty_body_sections(spec_text):
            errors.append(
                f"{sid} ({path.name}): 必須セクション '{sec}' の本文が空 "
                f"(見出し直後に非空本文を要求・io-contract.md §9 本文の床)"
            )
    # build_target (L3→L4 追跡) 検査: object 形式の目録のみ。各 component が L4 実体化先を持つこと。
    for comp in load_inventory_components(inventory_text):
        if not str(comp.get("build_target", "")).strip():
            cid = str(comp.get("id", "")).strip() or "?"
            errors.append(
                f"build_target 欠落: コンポーネント {cid} に L4 実体化先 (build_target) が無い "
                f"(計画 L3 と実体 L4 のトレーサビリティ・io-contract.md §9)"
            )
    return (1 if errors else 0), errors, warnings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="未配置タスク(unassigned)0 件と必須セクションを検証する")
    ap.add_argument("--inventory", required=True, help="コンポーネント目録 (JSON or text)")
    ap.add_argument("--specs-dir", required=True, help="タスク仕様書ディレクトリ")
    args = ap.parse_args(argv)

    inv = Path(args.inventory)
    specs_dir = Path(args.specs_dir)
    if not inv.is_file():
        sys.stderr.write(f"inventory not found: {inv}\n")
        return 2
    if not specs_dir.is_dir():
        sys.stderr.write(f"not a directory: {specs_dir}\n")
        return 2
    code, errors, warnings = run(inv.read_text(encoding="utf-8"), specs_dir)
    for w in warnings:
        sys.stderr.write(f"WARN: {w}\n")
    if code == 0:
        sys.stdout.write("OK: unassigned-task 0 件・全仕様書が必須セクションを保持\n")
        return 0
    for e in errors:
        sys.stderr.write(e + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
