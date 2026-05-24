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

import json
import re
import sys
from pathlib import Path

GOAL_SEEK_HEADING = "## ゴールシーク実行"
# 行頭の実見出しのみを一致 (本文中に `## ゴールシーク実行` を引用しただけでは不可)。
GOAL_SEEK_HEADING_RE = re.compile(r"^##\s*ゴールシーク実行\s*$", re.MULTILINE)
# 実行系とみなす prefix/kind。ref は除外。
EXECUTION_PREFIXES = ("run", "wrap", "delegate", "assign")
# loop 実行系 (達成までループを回す)。assign は一発採点でループしないため除外。
LOOP_PREFIXES = ("run", "wrap", "delegate")
# 局面カタログ配下の `### Step` は許容 (順序非固定の例示)。
CATALOG_MARKERS = ("局面カタログ", "順序は都度判断", "順序非固定")
STEP_RE = re.compile(r"^### Step\s*\d+\s*[:：]", re.MULTILINE)
FIXED_PROCEDURE_HEADING_RE = re.compile(r"^## 手順\s*$", re.MULTILINE)
# 完了チェックリスト領域と二値項目。
CHECKLIST_HEADING_RE = re.compile(r"^###\s*完了チェックリスト", re.MULTILINE)
NEXT_HEADING_RE = re.compile(r"^#{2,3}\s", re.MULTILINE)
CHECKLIST_ITEM_RE = re.compile(r"^- \[[ xX]\]\s*(.+)$", re.MULTILINE)
# YES/NO 判定不能な曖昧語 (goal-seek-paradigm.md「チェックリストの良し悪し」)。
VAGUE_TERMS = ("丁寧", "品質を高める", "適切に", "きちんと", "しっかり", "なるべく", "可能な限り")
# with-goal-seek combinator が注入する実行配線サブセクション。
# 行頭の実見出しのみ一致 (本文に見出し名を引用しただけでは満たさない)。
WIRING_HEADING = "### ゴールシーク配線"
WIRING_HEADING_RE = re.compile(r"^###\s*ゴールシーク配線", re.MULTILINE)


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


def skill_prefix(fm: dict[str, str]) -> str:
    return (fm.get("prefix") or fm.get("kind") or "").strip().strip('"')


def checklist_region(body: str) -> str | None:
    """`### 完了チェックリスト` 見出しから次見出しまでの本文を返す (無ければ None)。"""
    m = CHECKLIST_HEADING_RE.search(body)
    if not m:
        return None
    start = m.end()
    nxt = NEXT_HEADING_RE.search(body[start:])
    end = start + nxt.start() if nxt else len(body)
    return body[start:end]


def lint_file(path: Path) -> tuple[list[str], list[str]]:
    """(findings=exit1 違反, warnings=exit0 助言) を返す。"""
    findings: list[str] = []
    warnings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"{path}: read error: {e}"], warnings

    fm = parse_frontmatter(text)
    prefix = skill_prefix(fm)
    if prefix not in EXECUTION_PREFIXES:
        return findings, warnings  # ref など実行系以外は対象外

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

    # 4. loop 実行系 (run/wrap/delegate): チェックリスト二値性 + 曖昧語 + 配線
    if prefix in LOOP_PREFIXES:
        region = checklist_region(body)
        # template placeholder ({{...}}) 未展開の中間物は二値検査をスキップ。
        if region is not None and "{{" not in region:
            items = CHECKLIST_ITEM_RE.findall(region)
            if not items:
                findings.append(
                    f"{path}: loop実行系に二値チェックリスト項目 (- [ ] / - [x]) が無い "
                    "(ゴール達成の受入基準を YES/NO 判定可能な項目で列挙すること)"
                )
            for item in items:
                hit = [t for t in VAGUE_TERMS if t in item]
                if hit:
                    findings.append(
                        f"{path}: チェックリスト項目に曖昧語 {hit} があり YES/NO 判定不能: "
                        f"'{item.strip()}' (観測可能な条件へ書き換えること)"
                    )
        # 実行配線サブセクションは助言 (既存スキルは次回更新時に combinator で注入)。
        if not WIRING_HEADING_RE.search(body):
            warnings.append(
                f"{path}: '{WIRING_HEADING}' が無い "
                "(with-goal-seek combinator で goal-spec/progress JSON/fork 委譲を配線推奨)"
            )

    return findings, warnings


# --- SSOT drift 自己検査 -----------------------------------------------------
# goal_seek 既定値は物理的に複数ファイルへ分散する (Python定数 / JSON schema / patchテキスト)。
# with-knowledge の lint-knowledge-loop.py check_schema_drift() と同型に、分散コピーの一致を
# 機械保証する。escaped quote(\") と raw quote(") の両方を許容し同一検査器で抽出する。
_RENDER = Path(__file__).resolve().parent / "render-combinators.py"
_PATCH = Path(__file__).resolve().parents[1] / "templates" / "combinators" / "with-goal-seek.patch"
_BUILD_FLAGS = Path(__file__).resolve().parents[1] / "schemas" / "build-flags.schema.json"
_LOOP_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "goal-seek-loop.schema.json"
_ENGINE_RE = re.compile(r"goal_seek\.engine \| default\(\\?\"([\w-]+)\\?\"\)")
_FORK_RE = re.compile(r"goal_seek\.fork \| default\(\\?\"([\w-]+)\\?\"\)")
_MAXLOOPS_RE = re.compile(r"goal_seek\.max_loops \| default\((\d+)\)")


def _extract_defaults(text: str) -> dict[str, str | None]:
    """Python 定数 / patch テキストから engine/fork/max_loops の既定値を抽出する。"""
    e = _ENGINE_RE.search(text)
    f = _FORK_RE.search(text)
    m = _MAXLOOPS_RE.search(text)
    return {
        "engine": e.group(1) if e else None,
        "fork": f.group(1) if f else None,
        "max_loops": m.group(1) if m else None,
    }


def check_default_drift() -> list[str]:
    """render定数 / patch / build-flags schema / goal-seek-loop schema の既定値一致を検証する。"""
    findings: list[str] = []
    try:
        render = _extract_defaults(_RENDER.read_text(encoding="utf-8"))
        patch = _extract_defaults(_PATCH.read_text(encoding="utf-8"))
        build_flags = json.loads(_BUILD_FLAGS.read_text(encoding="utf-8"))
        loop_schema = json.loads(_LOOP_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [f"self-test: source read error: {e}"]

    bf_gs = (
        build_flags.get("properties", {}).get("with_goal_seek", {}).get("properties", {})
    )
    ls_props = loop_schema.get("properties", {})
    bf_engine = bf_gs.get("engine", {}).get("default")
    bf_maxloops = bf_gs.get("max_loops", {}).get("default")
    ls_fork = ls_props.get("fork_context", {}).get("default")
    ls_maxloops = ls_props.get("max_loops", {}).get("default")

    # render定数 と patch は逐語一致すべき (apply_patch_file fallback 経路の静かな乖離防止)
    for key in ("engine", "fork", "max_loops"):
        if render[key] is None:
            findings.append(f"self-test: render-combinators.py から goal_seek.{key} 既定を抽出できない")
        if patch[key] is None:
            findings.append(f"self-test: with-goal-seek.patch から goal_seek.{key} 既定を抽出できない")
        if render[key] != patch[key]:
            findings.append(
                f"self-test: goal_seek.{key} 既定が render定数({render[key]}) と patch({patch[key]}) で不一致"
            )

    # engine: render ↔ build-flags schema
    if render["engine"] != bf_engine:
        findings.append(
            f"self-test: engine 既定 drift — render({render['engine']}) vs build-flags.schema({bf_engine})"
        )
    # fork: render ↔ goal-seek-loop schema (fork_context)
    if render["fork"] != ls_fork:
        findings.append(
            f"self-test: fork 既定 drift — render({render['fork']}) vs goal-seek-loop.schema.fork_context({ls_fork})"
        )
    # max_loops: render ↔ 両 schema (int 比較)
    rml = int(render["max_loops"]) if render["max_loops"] else None
    if rml != bf_maxloops:
        findings.append(
            f"self-test: max_loops 既定 drift — render({rml}) vs build-flags.schema({bf_maxloops})"
        )
    if rml != ls_maxloops:
        findings.append(
            f"self-test: max_loops 既定 drift — render({rml}) vs goal-seek-loop.schema({ls_maxloops})"
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
    if argv and argv[0] == "--self-test":
        drift = check_default_drift()
        if drift:
            for d in drift:
                sys.stderr.write(d + "\n")
            return 1
        sys.stdout.write("OK: goal-seek 既定値 SSOT 整合 (engine/fork/max_loops drift なし)\n")
        return 0

    targets = collect_targets(argv)
    if not targets:
        sys.stderr.write(
            "usage: lint-goal-seek.py <SKILL.md> | --skills-dir <dir> | --self-test\n"
        )
        return 2

    all_findings: list[str] = []
    all_warnings: list[str] = []
    for path in targets:
        findings, warnings = lint_file(path)
        all_findings.extend(findings)
        all_warnings.extend(warnings)

    for w in all_warnings:
        sys.stderr.write(f"WARN: {w}\n")

    if all_findings:
        for f in all_findings:
            sys.stderr.write(f + "\n")
        return 1

    suffix = f" ({len(all_warnings)} warning(s))" if all_warnings else ""
    sys.stdout.write(
        f"OK: {len(targets)} skill file(s) passed goal-seek lint{suffix}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
