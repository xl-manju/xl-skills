#!/usr/bin/env python3
"""gate-phase0.py - Phase 0 移行前提条件ゲート (P2-2)

チェック項目:
  (a) 全 SKILL.md に effect: フィールドが存在する
  (b) references/ が3ファイル以上の Skill に resource-map.yaml が存在する
  (c) 同名 lint スクリプトの並存が解消されている (内容が同一であること)
  (d) .claude/skills/<name>/ ハードコード参照が SKILL.md 内に残っていない

全て pass で exit 0。

Usage:
  python3 scripts/gate-phase0.py
  python3 scripts/gate-phase0.py --skills-dir creator-kit/skills
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# .claude/skills/<name>/ の直書き参照を検出する。
# ただし fallback 探索パターン ([ -f ".claude/skills/..." ]) と
# Phase 0 注釈行 (> ※ creator-kit ...) は許容する。
HARDCODE_RE = re.compile(
    r'(?:mkdir|git mv|ls|grep|cp)\s[^\n]*\.claude/skills/[a-z][a-z0-9-]+'
)


def check_effect(skill_dir: Path) -> list[str]:
    """(a) effect: フィールドの存在確認"""
    errs = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return [f"{skill_dir.name}: SKILL.md not found"]
    text = skill_md.read_text(encoding="utf-8")
    # frontmatter 内のみチェック
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            if not re.search(r'^effect:', fm_text, re.MULTILINE):
                errs.append(f"(a) {skill_dir.name}: effect: フィールドが frontmatter に不在")
    return errs


def check_resource_map(skill_dir: Path) -> list[str]:
    """(b) references/ 3ファイル以上なら resource-map.yaml 必須"""
    errs = []
    refs_dir = skill_dir / "references"
    if not refs_dir.is_dir():
        return errs
    ref_files = [f for f in refs_dir.iterdir() if f.is_file()]
    if len(ref_files) >= 3:
        if not (refs_dir / "resource-map.yaml").exists():
            errs.append(
                f"(b) {skill_dir.name}: references/ に {len(ref_files)} ファイルあるが"
                " resource-map.yaml が不在"
            )
    return errs


def check_duplicate_scripts(repo_root: Path) -> list[str]:
    """(c) root/scripts/ と creator-kit/scripts/ の同名スクリプトが内容同一か確認"""
    errs = []
    root_scripts = repo_root / "scripts"
    ck_scripts = repo_root / "creator-kit" / "scripts"
    if not root_scripts.is_dir() or not ck_scripts.is_dir():
        return errs
    for root_script in root_scripts.glob("*.py"):
        ck_script = ck_scripts / root_script.name
        if ck_script.exists():
            root_content = root_script.read_text(encoding="utf-8")
            ck_content = ck_script.read_text(encoding="utf-8")
            if root_content != ck_content:
                errs.append(
                    f"(c) {root_script.name}: scripts/ と creator-kit/scripts/ で内容が異なる"
                    " (SSOT 違反)"
                )
    return errs


def check_hardcode_paths(skill_dir: Path) -> list[str]:
    """(d) .claude/skills/<name>/ ハードコード参照が SKILL.md 内に残っていないか確認"""
    errs = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return errs
    text = skill_md.read_text(encoding="utf-8")
    matches = HARDCODE_RE.findall(text)
    if matches:
        errs.append(
            f"(d) {skill_dir.name}: SKILL.md に .claude/skills/<name>/ ハードコード参照が残存"
            f" ({len(matches)} 箇所)"
        )
    return errs


def main() -> int:
    args = sys.argv[1:]

    # --skills-dir オプション
    skills_dir_override = None
    if "--skills-dir" in args:
        idx = args.index("--skills-dir")
        if idx + 1 < len(args):
            skills_dir_override = Path(args[idx + 1])

    # リポジトリルートを推定
    repo_root = Path(".").resolve()
    skills_base = skills_dir_override or (repo_root / "creator-kit" / "skills")
    if not skills_base.is_dir():
        print(f"ERROR: skills directory not found: {skills_base}", file=sys.stderr)
        return 2

    all_errs: list[str] = []

    # (a)(b)(d) を各 Skill について実行
    for skill_dir in sorted(skills_base.iterdir()):
        if not skill_dir.is_dir():
            continue
        all_errs.extend(check_effect(skill_dir))
        all_errs.extend(check_resource_map(skill_dir))
        all_errs.extend(check_hardcode_paths(skill_dir))

    # (c) スクリプト二重化チェック
    all_errs.extend(check_duplicate_scripts(repo_root))

    if all_errs:
        print("GATE-PHASE0: FAIL", file=sys.stderr)
        for e in all_errs:
            print(f"  {e}", file=sys.stderr)
        return 1

    skill_count = sum(1 for d in skills_base.iterdir() if d.is_dir())
    print(f"GATE-PHASE0: PASS ({skill_count} skills checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
