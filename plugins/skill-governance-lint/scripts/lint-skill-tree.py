#!/usr/bin/env python3
# /// script
# name: lint-skill-tree
# purpose: Lint skill directory trees against structure and file naming rules.
# inputs:
#   - argv: skill directory or --skills-dir
# outputs:
#   - stdout: OK status
#   - stderr: tree structure findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Lint Skill directory tree against articles 第8〜13条.

Usage:
  lint-skill-tree.py /path/to/skill-dir
  lint-skill-tree.py --skills-dir plugins/skill-creator/skills   # 全 Skill を一括検査
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\.(md|yaml|py|sh|json|patch)$")
ALLOWED_DIRS = {"templates", "references", "scripts", "examples", "hooks", "log"}
ALLOWED_NESTED_DIRS = {
    ("templates", "combinators"),
}
SCRIPT_EXTS = {".py", ".sh"}
MAX_SKILL_LINES = 300  # P0-2: 300行 cap 機械強制

OS_PREAMBLE_PATTERN = re.compile(r"!`uname -s")
# 本文先頭から探索する行数 (先頭付近の定義: 設計書13章)
OS_PREAMBLE_SEARCH_LINES = 30


def _needs_os_preamble(fm: dict) -> bool:
    """frontmatter が OS プリアンブル必須かどうかを判定する。

    条件 (13章 クロスプラットフォーム [Lint]):
      - cross_platform: true または os_preamble_required: true
      - あるいは allowed-tools に Bash(uname *) を含む
    """
    def _is_true(v: object) -> bool:
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() == "true"

    if _is_true(fm.get("cross_platform")) or _is_true(fm.get("os_preamble_required")):
        return True
    allowed = fm.get("allowed-tools", "")
    if isinstance(allowed, list):
        allowed = " ".join(allowed)
    return "Bash(uname" in str(allowed)


def _parse_fm_simple(text: str) -> dict:
    """最小限 frontmatter パーサー（scalar のみ）。"""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: dict = {}
    for line in parts[1].splitlines():
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm


def check_os_preamble(skill_md: "Path") -> list[str]:
    """B-2: cross_platform Skill に OS プリアンブルが存在するか検証する。"""
    errs: list[str] = []
    text = skill_md.read_text(encoding="utf-8")
    fm = _parse_fm_simple(text)
    if not _needs_os_preamble(fm):
        return errs

    # frontmatter 以降の本文先頭 OS_PREAMBLE_SEARCH_LINES 行を検索
    body_start = 0
    if text.startswith("---"):
        end_idx = text.find("---", 3)
        if end_idx != -1:
            body_start = end_idx + 3

    body = text[body_start:]
    body_lines = body.splitlines()[:OS_PREAMBLE_SEARCH_LINES]
    found = any(OS_PREAMBLE_PATTERN.search(line) for line in body_lines)
    if not found:
        errs.append(
            "[Lint]13章違反: cross_platform=true だが本文先頭付近に "
            "OS プリアンブル (!`uname -s 2>/dev/null || ver`) がない"
        )
    return errs



def lint_one(root: Path) -> list[str]:
    errs: list[str] = []

    # SKILL.md 必須
    skill_md = root / "SKILL.md"
    if not skill_md.exists():
        errs.append("missing SKILL.md")
        return errs

    # P0-2: 300行 cap
    line_count = len(skill_md.read_text(encoding="utf-8").splitlines())
    if line_count > MAX_SKILL_LINES:
        errs.append(
            f"P0-2違反: SKILL.md が {line_count} 行 (上限 {MAX_SKILL_LINES} 行)。"
            " 超過分は references/ に分割すること（07章）"
        )

    # 第13条 フラットツリー (深さ <= 2)
    for p in root.rglob("*"):
        # __pycache__ / .pyc を除外
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        rel = p.relative_to(root)
        if p.is_dir():
            if len(rel.parts) > 1:
                if tuple(rel.parts) not in ALLOWED_NESTED_DIRS:
                    errs.append(f"第13条違反: nested dir '{rel}'")
            elif rel.parts[0] not in ALLOWED_DIRS and rel.parts[0] != ".":
                # extra top-level dirs allowed but warn
                pass
        else:
            # 第8〜11条 ファイル命名
            if len(rel.parts) >= 2:
                top, fname = rel.parts[0], rel.parts[-1]
                if top in {"templates", "references", "examples"}:
                    allowed_template_exts = (".md", ".md.tmpl", ".yaml", ".json", ".patch", ".j2")
                    if not fname.endswith(allowed_template_exts):
                        errs.append(f"第8〜11条違反: {rel} 拡張子不正")
                if top == "scripts":
                    if Path(fname).suffix not in SCRIPT_EXTS:
                        errs.append(f"第10条違反: scripts/ には .py/.sh のみ ({rel})")
            # kebab-case 推奨（強制せずwarnのみ）

    # P1-2: references/ が 3 ファイル以上なら resource-map.yaml 必須
    refs_dir = root / "references"
    if refs_dir.is_dir():
        ref_files = [f for f in refs_dir.iterdir() if f.is_file()]
        if len(ref_files) >= 3:
            if not (refs_dir / "resource-map.yaml").exists():
                errs.append(
                    f"P1-2違反: references/ に {len(ref_files)} ファイルあるが"
                    " resource-map.yaml が不在 (設計書06 第13条)"
                )

    # B-2: OS プリアンブルチェック (13章 クロスプラットフォーム [Lint])
    errs.extend(check_os_preamble(skill_md))

    # rubric placement check: ref-* / assign-* は rubric.json を直下に置けない
    skill_name = root.name
    if skill_name.startswith("ref-") or skill_name.startswith("assign-"):
        bad_rubric = root / "rubric.json"
        if bad_rubric.is_file():
            errs.append(
                f"rubric placement 違反: {skill_name}/rubric.json は禁止。"
                f" 期待パス: {skill_name}/references/rubric.json"
            )

    return errs


def main() -> int:
    args = sys.argv[1:]

    # --skills-dir モード: ディレクトリ内の全 Skill を一括検査
    if "--skills-dir" in args:
        idx = args.index("--skills-dir")
        if idx + 1 >= len(args):
            print("usage: lint-skill-tree.py --skills-dir /path/to/skills", file=sys.stderr)
            return 2
        skills_base = Path(args[idx + 1])
        if not skills_base.is_dir():
            print(f"not a directory: {skills_base}", file=sys.stderr)
            return 2
        total_errs = []
        for skill_dir in sorted(skills_base.iterdir()):
            if skill_dir.is_dir():
                errs = lint_one(skill_dir)
                for e in errs:
                    total_errs.append(f"{skill_dir.name}: {e}")
        if total_errs:
            for e in total_errs:
                print(e, file=sys.stderr)
            return 1
        print(f"ok: {skills_base} ({sum(1 for d in skills_base.iterdir() if d.is_dir())} skills)")
        return 0

    # 単一ディレクトリモード
    if len(args) < 1:
        print("usage: lint-skill-tree.py /path/to/skill-dir", file=sys.stderr)
        return 2
    root = Path(args[0])
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    errs = lint_one(root)
    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        return 1
    print(f"ok: {root.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
