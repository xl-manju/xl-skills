#!/usr/bin/env python3
# /// script
# name: lint-goal-seek
# purpose: 実行系 Skill が固定手順ではなくゴールシーク (Goal+Checklist+Loop) で構成されているか検査する。
# inputs:
#   - argv: SKILL.md path(s) or --skills-dir <dir>
# outputs:
#   - stdout: OK status
#   - stderr: violation findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""skill-creator が生成する実行系 Skill のゴールシーク準拠を機械検証する lint。

ルール (run-build-skill SKILL.md Key Rule 18 / references/goal-seek-paradigm.md):
  - 実行系 kind (run / wrap / delegate / assign / orchestrator / agent / hook) は
    `## ゴールシーク実行` 見出しを持つこと。
  - 固定手順の連番羅列 (`## 手順` セクション直下の番号付き / `### Step N:` の 2 連以上が
    「局面カタログ」表記外で出現) は violation。
  - ref-* (read-only) は対象外 (skip)。

Exit 0 = ok, 1 = violation, 2 = usage error。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

GOAL_SEEK_HEADING = "## ゴールシーク実行"
# 行頭の実見出しのみを一致 (本文中に `## ゴールシーク実行` を引用しただけでは不可)。
GOAL_SEEK_HEADING_RE = re.compile(r"^##\s*ゴールシーク実行\s*$", re.MULTILINE)
# 実行系とみなす prefix/kind。ref は除外。
EXECUTION_PREFIXES = ("run", "wrap", "delegate", "assign")
# 局面カタログ配下の `### Step` は許容 (順序非固定の例示)。
CATALOG_MARKERS = ("局面カタログ", "順序は都度判断", "順序非固定")
STEP_RE = re.compile(r"^### Step\s*\d+\s*[:：]", re.MULTILINE)
FIXED_PROCEDURE_HEADING_RE = re.compile(r"^## 手順\s*$", re.MULTILINE)


def parse_frontmatter(text: str) -> dict[str, str]:
    """軽量 frontmatter パーサ (key: value のフラットなもののみ)。yaml import しない。"""
    fm: dict[str, str] = {}
    if not text.startswith("---"):
        return fm
    end = text.find("\n---", 3)
    if end == -1:
        return fm
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm


def is_execution_skill(fm: dict[str, str]) -> bool:
    prefix = (fm.get("prefix") or fm.get("kind") or "").strip().strip('"')
    return prefix in EXECUTION_PREFIXES


def body_after_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :]
    return text


def lint_file(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{path}: read error: {e}"]

    fm = parse_frontmatter(text)
    if not is_execution_skill(fm):
        return findings  # ref など実行系以外は対象外

    body = body_after_frontmatter(text)

    # 1. ゴールシーク見出しの存在 (行頭の実見出しのみ; 本文引用では満たさない)
    if not GOAL_SEEK_HEADING_RE.search(body):
        findings.append(
            f"{path}: 実行系 Skill に '{GOAL_SEEK_HEADING}' 見出しがない "
            "(固定手順ではなく Goal+Checklist+Loop で構成すること)"
        )

    # 2. 固定 `## 手順` セクションの残存
    if FIXED_PROCEDURE_HEADING_RE.search(body):
        findings.append(
            f"{path}: 実行系 Skill に固定 '## 手順' セクションが残存 "
            "(ゴールシークへ移行すること)"
        )

    # 3. 局面カタログ外での `### Step N:` 連番羅列 (2 連以上)
    has_catalog = any(m in body for m in CATALOG_MARKERS)
    step_count = len(STEP_RE.findall(body))
    if step_count >= 2 and not has_catalog:
        findings.append(
            f"{path}: 固定手順の連番 (### Step N:) が {step_count} 件検出された。"
            "順序固定の手順は書かず、必要なら '局面カタログ (順序は都度判断)' として記述すること"
        )

    return findings


def collect_targets(argv: list[str]) -> list[Path]:
    if not argv:
        return []
    if argv[0] == "--skills-dir":
        if len(argv) < 2:
            return []
        d = Path(argv[1])
        return sorted(d.glob("**/SKILL.md")) if d.is_dir() else []
    return [Path(p) for p in argv]


def main(argv: list[str]) -> int:
    targets = collect_targets(argv)
    if not targets:
        sys.stderr.write(
            "usage: lint-goal-seek.py <SKILL.md> | --skills-dir <dir>\n"
        )
        return 2

    all_findings: list[str] = []
    for path in targets:
        all_findings.extend(lint_file(path))

    if all_findings:
        for f in all_findings:
            sys.stderr.write(f + "\n")
        return 1

    sys.stdout.write(f"OK: {len(targets)} skill file(s) passed goal-seek lint\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
