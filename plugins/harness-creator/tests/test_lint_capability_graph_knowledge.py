"""C08 lint-capability-graph-knowledge.py の subprocess CLI 実挙動テスト。

検証済み実挙動 + オーケストレータ修正 (F-M01 inert gate) の回帰固定:
not-applicable exit0 / 駆動体空洞 (engine スクリプト同梱だが engine:task-graph 未宣言) violation
exit1 / 活性化 exit0 / consult 欠落・同梱欠落・source_ref 欠落 violation exit1 /
テンプレ元 (harness-creator 自身) は not-applicable。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
SCRIPT = HARNESS / "skills/run-build-skill/scripts/lint-capability-graph-knowledge.py"
ENGINE_SCRIPTS = HARNESS / "skills/run-build-skill/templates/task-graph-engine/scripts"

FOUR = (
    "ready-set-from-checklist.py",
    "self-reflect-append.py",
    "extract-capability-dependency-graph.py",
    "record-capability-graph-knowledge.py",
)
CONSULT_TOKEN = "dependency graph knowledge"


def _run(target: Path | str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(target)], capture_output=True, text=True
    )


def _copy_four(dest: Path, names=FOUR) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy(ENGINE_SCRIPTS / name, dest / name)


def _skill(root: Path, *, engine: bool, consult: bool, name: str = "demo") -> Path:
    d = root / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    fm = f"---\nname: {name}\n"
    if engine:
        fm += "engine: task-graph\n"
    fm += "---\n"
    body = (
        f"consult {CONSULT_TOKEN} before acting\n" if consult else "no consult token\n"
    )
    (d / "SKILL.md").write_text(fm + body, encoding="utf-8")
    return d


def test_script_exists():
    assert SCRIPT.is_file()


def test_not_applicable_exit0(tmp_path):
    # engine 宣言も engine スクリプト同梱も無い → not-applicable。
    _skill(tmp_path, engine=False, consult=False)
    r = _run(tmp_path)
    assert r.returncode == 0
    assert "not-applicable" in r.stdout


def test_inert_engine_violation_exit1(tmp_path):
    # F-M01: engine スクリプト4本を生成先 scripts/ へ同梱しているが engine:task-graph 未宣言 → 駆動体空洞。
    d = _skill(tmp_path, engine=False, consult=False)
    _copy_four(d / "scripts")
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "駆動体空洞" in r.stderr or "inert engine" in r.stderr


def test_activated_exit0_with_warning(tmp_path):
    # engine:task-graph + 4本同梱 + consult token → 活性化 OK (knowledge store 未生成は warning)。
    d = _skill(tmp_path, engine=True, consult=True)
    _copy_four(d / "scripts")
    r = _run(tmp_path)
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout
    assert "warning" in r.stdout  # knowledge store 未生成 warning


def test_consult_token_missing_exit1(tmp_path):
    d = _skill(tmp_path, engine=True, consult=False)
    _copy_four(d / "scripts")
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "consult 未配線" in r.stderr


def test_partial_bundling_missing_exit1(tmp_path):
    # engine 宣言 + consult 有だが 4 本のうち 1 本欠落 → 同梱欠落 violation。
    d = _skill(tmp_path, engine=True, consult=True)
    _copy_four(d / "scripts", names=FOUR[:3])  # record-...py を欠落させる
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "同梱欠落" in r.stderr


def test_source_ref_missing_in_store_exit1(tmp_path):
    d = _skill(tmp_path, engine=True, consult=True)
    _copy_four(d / "scripts")
    # source_ref を持たない entry を含む knowledge store を置く。
    store = tmp_path / "skills" / "demo" / "knowledge" / "knowledge-capability-graph.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(
        json.dumps({"category": "capability-graph", "items": [{"id": "x", "title": "t"}]}),
        encoding="utf-8",
    )
    r = _run(tmp_path)
    assert r.returncode == 1
    assert "source_ref" in r.stderr


def test_template_scripts_are_not_applicable(tmp_path):
    # テンプレ元 templates/task-graph-engine/scripts はコピー元であって活性化ではない → not-applicable。
    r = _run(HARNESS)
    assert r.returncode == 0
    assert "not-applicable" in r.stdout


def test_skill_md_target_resolves_root(tmp_path):
    # 入力が SKILL.md ファイルでも harness root を解決して活性化検査する。
    d = _skill(tmp_path, engine=True, consult=True)
    _copy_four(d / "scripts")
    r = _run(d / "SKILL.md")
    assert r.returncode == 0, r.stderr


def test_usage_no_arg_exit2():
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 2


def test_nonexistent_target_exit2():
    r = _run("/nope/does-not-exist")
    assert r.returncode == 2
