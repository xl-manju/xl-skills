#!/usr/bin/env python3
# /// script
# name: lint-capability-graph-knowledge
# purpose: brief.goal_seek.engine=task-graph 指定で生成された harness が、C06 による cross-surface dependency graph 抽出、C07 による Loop A/Loop B knowledge 記録、各 surface の実行前 knowledge consult 指示を携帯しているかを fail-closed で検査する。checklist 順序実行だけで終わらず、依存グラフ由来 knowledge を各 surface が使うことの機械ゲートにする (H6 の実装物)。
# inputs:
#   - argv: <generated_harness_dir_or_skill_md>
# outputs:
#   - stdout: OK / not-applicable
#   - stderr: missing token・dangling dependency・knowledge consult 未配線 violation 一覧
#   - exit: 0=OK / 1=violation / 2=usage/IO error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""生成 task-graph harness の dependency graph knowledge 利用契約を検査する lint (C08)。

engine:task-graph 指定で生成された harness に対し、C04 (lint-goal-seek.py) が goal-seek schema /
consumption verifier の SSOT drift を見るのと分離して、本 lint は「依存グラフ由来 knowledge を
各 surface が実際に使う」横断契約を検査する:
  1. C06/C07 (extract/record) が生成先 scripts/ に同梱されている。
  2. engine:task-graph を宣言する各 skill surface が dependency graph knowledge consult token を持つ。
  3. command/agent surface が存在する場合は advisory consult token 欠落を warning として収集する。
  4. 記録済み knowledge entry (knowledge-capability-graph.json) が全て source_ref を持つ (dangling
     gap entry を含め出所が追える)。

スコープ注記: consult token の hard 検査対象は「ループを回す skill surface」(engine:task-graph 宣言
SKILL.md)。command/agent surface は consult token の欠如を warning で報告する (skill 側 wiring が
consult の一次責務を負い、全 surface へトークンを強制するのは Goodhart 化するため)。script surface は
実体 (C01/C02/C06/C07) の同梱有無で担保する。

engine:task-graph を宣言する SKILL.md が 1 件も無ければ not-applicable として exit0。

Exit 0 = OK / not-applicable, 1 = violation, 2 = usage/IO error。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CONSULT_TOKEN = "dependency graph knowledge"
# 生成 SKILL.md の task-graph 変種配線が scripts/ 経由で参照する 4 本すべてを同梱ゲート対象にする
# (gate-coverage parity: 参照集合と検査集合を一致させ「C06/C07 だけコピーすれば緑」の誤メンタルモデルを排す)。
# ready-set-from-checklist.py(C01)/self-reflect-append.py(C02) が漏れると実行時 dangling するため
# build-time に fail-closed 検出する。
BUNDLED_SCRIPTS = (
    "ready-set-from-checklist.py",
    "self-reflect-append.py",
    "extract-capability-dependency-graph.py",
    "record-capability-graph-knowledge.py",
)
KNOWLEDGE_STORE = "knowledge-capability-graph.json"
# concrete な engine: task-graph 宣言 (frontmatter YAML 行・末尾コメント許容) のみに一致。
# 機能を説明する散文/コメント中の言及や template placeholder には誤発火しない。
_CONCRETE_TASK_GRAPH_ENGINE_RE = re.compile(
    r"^\s*engine:\s*task-graph\s*(?:#.*)?$", re.MULTILINE
)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def resolve_harness_root(target: Path) -> Path:
    """入力が SKILL.md ファイルなら harness root (skills/ を持つ祖先) を、dir ならそのまま返す。"""
    if target.is_dir():
        return target
    # skills/<name>/SKILL.md → 祖先を辿り skills/ を持つディレクトリを root とする。
    for anc in target.parents:
        if (anc / "skills").is_dir() or (anc / "scripts").is_dir():
            return anc
    return target.parent


def collect_task_graph_skills(root: Path, single_file: Path | None) -> list[Path]:
    """engine:task-graph を concrete 宣言する SKILL.md 群を返す。"""
    if single_file is not None and single_file.is_file():
        candidates = [single_file]
    else:
        candidates = sorted(root.glob("skills/*/SKILL.md")) + sorted(root.glob("SKILL.md"))
    return [p for p in candidates if _CONCRETE_TASK_GRAPH_ENGINE_RE.search(_read(p))]


def script_roots(root: Path) -> list[Path]:
    """C06/C07 同梱を探す scripts/ ディレクトリ群 (plugin-root と各 skill 配下)。"""
    roots = [root / "scripts"]
    roots.extend(sorted(root.glob("skills/*/scripts")))
    roots.extend(sorted(root.glob("skills/*/templates/task-graph-engine/scripts")))
    return [r for r in roots if r.is_dir()]


def check_bundling(root: Path) -> list[str]:
    """C06/C07 が scripts/ 配下のいずれかに同梱されているか検査する。"""
    findings: list[str] = []
    roots = script_roots(root)
    present = {name for r in roots for name in BUNDLED_SCRIPTS if (r / name).is_file()}
    for name in BUNDLED_SCRIPTS:
        if name not in present:
            findings.append(
                f"C06/C07 同梱欠落: {name} が scripts/ 配下に不在 "
                f"(探索先: {[str(r) for r in roots] or '(scripts dir なし)'})"
            )
    return findings


_TEMPLATE_SCRIPTS_MARKER = "templates/task-graph-engine/scripts"


def activated_script_roots(root: Path) -> list[Path]:
    """活性化を意図して生成先へコピーされた scripts/ のみを返す。

    テンプレ元 (`templates/task-graph-engine/scripts`) は engine の *コピー元* であって
    活性化ではないため除外する (harness-creator 自身での inert 誤発火を防ぐ)。
    """
    return [
        r
        for r in script_roots(root)
        if _TEMPLATE_SCRIPTS_MARKER not in str(r).replace("\\", "/")
    ]


def check_inert_engine(root: Path) -> list[str]:
    """駆動体空洞 (inert engine) の fail-closed 検出。

    task-graph engine スクリプトが *生成先* `scripts/` へ同梱 (= 活性化意図) されているのに、
    どの SKILL.md も frontmatter `engine: task-graph` を concrete 宣言していない状態を violation とする。
    これは `brief.goal_seek.engine=task-graph` が生成 frontmatter へ具体化されず feature が惰性化
    (全ゲート緑のまま runtime verifier/consult が自己 skip) する穴を build-time に封鎖する
    (absence-as-violation: 同梱の存在に対し engine 宣言の不在を違反として扱う)。
    """
    roots = activated_script_roots(root)
    present = sorted({name for r in roots for name in BUNDLED_SCRIPTS if (r / name).is_file()})
    if not present:
        return []  # 活性化意図なし (テンプレ元のみ or 非同梱) → inert 判定の対象外
    if collect_task_graph_skills(root, None):
        return []  # engine:task-graph が宣言済み → 活性化されている
    return [
        "駆動体空洞 (inert engine): task-graph engine スクリプト "
        f"{present} が生成先 scripts/ へ同梱されているが、どの SKILL.md も frontmatter "
        "'engine: task-graph' を宣言していない (brief.goal_seek.engine=task-graph が生成 "
        "frontmatter へ具体化されず feature 惰性化)。Step 10.6 で生成 SKILL.md の "
        "goal_seek.engine を task-graph へ設定すること"
    ]


def check_consult_tokens(skills: list[Path]) -> list[str]:
    """engine:task-graph skill が dependency graph knowledge consult token を持つか検査する。"""
    findings: list[str] = []
    for skill in skills:
        if CONSULT_TOKEN not in _read(skill):
            findings.append(
                f"consult 未配線: {skill} に '{CONSULT_TOKEN}' consult token が不在 "
                "(engine:task-graph skill は実行前に依存グラフ knowledge を consult すること)"
            )
    return findings


def collect_advisory_surfaces(root: Path) -> list[Path]:
    """command/agent surface を収集する。

    skill surface は hard gate、script surface は bundled script 実在で担保するためここでは扱わない。
    command/agent は routing surface であり、欠落は警告に留めて実行前 consult の改善余地として返す。
    """
    candidates: list[Path] = []
    for pattern in ("commands/*.md", "agents/*.md"):
        candidates.extend(sorted(root.glob(pattern)))
    return [p for p in candidates if p.is_file()]


def check_advisory_surface_consults(root: Path) -> list[str]:
    """command/agent surface の consult token 欠落を warning として返す。"""
    warnings: list[str] = []
    for surface in collect_advisory_surfaces(root):
        if CONSULT_TOKEN not in _read(surface):
            warnings.append(
                f"advisory consult 未配線: {surface} に '{CONSULT_TOKEN}' consult token が不在 "
                "(command/agent surface は warning。skill surface が hard gate)"
            )
    return warnings


def check_source_refs(root: Path) -> tuple[list[str], list[str]]:
    """記録済み knowledge store の各 entry が source_ref を持つか検査する。(findings, warnings)。"""
    findings: list[str] = []
    warnings: list[str] = []
    stores = sorted(root.glob(f"**/{KNOWLEDGE_STORE}"))
    if not stores:
        warnings.append(
            f"{KNOWLEDGE_STORE} が未生成 (record-capability-graph-knowledge.py 未実行)。"
            "runtime で記録されるため build 時点では warning 止まり"
        )
        return findings, warnings
    for store in stores:
        try:
            data = json.loads(store.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            findings.append(f"{store}: 読込/parse 失敗: {e}")
            continue
        for item in data.get("items", []):
            if not isinstance(item, dict):
                continue
            if not item.get("source_ref"):
                findings.append(
                    f"{store}: entry '{item.get('id')}' が source_ref を持たない "
                    "(Loop A/B knowledge entry は出所追跡のため source_ref 必須)"
                )
    return findings, warnings


def lint(target: Path) -> tuple[list[str], list[str], bool]:
    """(findings, warnings, applicable) を返す。"""
    root = resolve_harness_root(target)
    single = target if target.is_file() else None
    skills = collect_task_graph_skills(root, single)
    if not skills:
        inert = check_inert_engine(root)
        if inert:
            return inert, [], True  # 同梱済みだが未活性 = 駆動体空洞 violation (not-applicable ではない)
        return [], [], False  # not-applicable (engine スクリプト同梱もなし)

    findings: list[str] = []
    findings.extend(check_bundling(root))
    findings.extend(check_consult_tokens(skills))
    sr_findings, warnings = check_source_refs(root)
    warnings.extend(check_advisory_surface_consults(root))
    findings.extend(sr_findings)
    return findings, warnings, True


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        sys.stderr.write("usage: lint-capability-graph-knowledge.py <generated_harness_dir_or_skill_md>\n")
        return 0 if argv[:1] in (["-h"], ["--help"]) else 2
    target = Path(argv[0])
    if not target.exists():
        sys.stderr.write(f"対象が存在しない: {target}\n")
        return 2

    findings, warnings, applicable = lint(target)
    for w in warnings:
        sys.stderr.write(f"WARN: {w}\n")
    if not applicable:
        sys.stdout.write("not-applicable: engine:task-graph を宣言する skill surface が無い\n")
        return 0
    if findings:
        for f in findings:
            sys.stderr.write(f + "\n")
        return 1
    suffix = f" ({len(warnings)} warning(s))" if warnings else ""
    sys.stdout.write(f"OK: dependency graph knowledge 利用契約 準拠{suffix}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
