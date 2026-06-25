"""scripts/validate-plugin-completeness.py の genuine 機能テスト。

純関数 (load_bundle_members / collect / validate) を tmp_path 上に構築した
擬似 plugin ツリーで実入力により呼び、実出力を assert する。main() は
PLUGINS_DIR / BUNDLES_JSON を monkeypatch で tmp_path へ向け in-process 駆動し、
OK / VIOLATION / PLUGINS_DIR 不在 の returncode を検証する。
network/keychain/Notion 等の外部 I/O は一切なし (純粋なファイル検査スクリプト)。
subprocess 経路は実 repo に対し returncode (0 or 1) を許容範囲で検証する。
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate-plugin-completeness.py"

SPEC = importlib.util.spec_from_file_location("validate_plugin_completeness_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


# --- helpers -----------------------------------------------------------------

def _make_plugin(base: Path, name: str, manifest: dict | None = None,
                 *, skills=(), agents=(), commands=(), hooks=(),
                 scripts=(), config=()) -> Path:
    d = base / name
    d.mkdir(parents=True)
    for s in skills:
        sd = d / "skills" / s
        sd.mkdir(parents=True)
        (sd / "SKILL.md").write_text(f"---\nname: {s}\n---\nbody\n", encoding="utf-8")
    for a in agents:
        (d / "agents").mkdir(exist_ok=True)
        (d / "agents" / a).write_text("agent", encoding="utf-8")
    for c in commands:
        (d / "commands").mkdir(exist_ok=True)
        (d / "commands" / c).write_text("cmd", encoding="utf-8")
    for h in hooks:
        (d / "hooks").mkdir(exist_ok=True)
        (d / "hooks" / h).write_text("#!/bin/sh\n", encoding="utf-8")
    for sc in scripts:
        sd = d / "scripts"
        sd.mkdir(exist_ok=True)
        (sd / sc).write_text("# py\n", encoding="utf-8")
    for cf in config:
        (d / "config").mkdir(exist_ok=True)
        (d / "config" / cf).write_text("{}", encoding="utf-8")
    if manifest is not None:
        md = d / ".claude-plugin"
        md.mkdir(parents=True)
        (md / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    return d


# --- load_bundle_members -----------------------------------------------------

def test_load_bundle_members_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(MOD, "BUNDLES_JSON", tmp_path / "absent.json")
    assert MOD.load_bundle_members() == set()


def test_load_bundle_members_collects_all_plugins(tmp_path, monkeypatch):
    bj = tmp_path / "bundles.json"
    bj.write_text(json.dumps({
        "bundles": [
            {"name": "core", "plugins": ["skill-creator", "skill-intake"]},
            {"name": "extra", "plugins": ["skill-intake", "another"]},
        ]
    }), encoding="utf-8")
    monkeypatch.setattr(MOD, "BUNDLES_JSON", bj)
    assert MOD.load_bundle_members() == {"skill-creator", "skill-intake", "another"}


def test_load_bundle_members_empty_bundles_key(tmp_path, monkeypatch):
    bj = tmp_path / "bundles.json"
    bj.write_text(json.dumps({"bundles": []}), encoding="utf-8")
    monkeypatch.setattr(MOD, "BUNDLES_JSON", bj)
    assert MOD.load_bundle_members() == set()


# --- collect -----------------------------------------------------------------

def test_collect_enumerates_all_asset_kinds(tmp_path):
    d = _make_plugin(
        tmp_path, "p1",
        manifest={"name": "p1", "version": "1.0.0", "description": "d"},
        skills=["run-a", "run-b"],
        agents=["x.md"],
        commands=["c.md"],
        hooks=["h.sh", "g.py"],
        scripts=["tool.py"],
        config=["conf.json"],
    )
    out = MOD.collect(d)
    assert out["skills"] == ["run-a", "run-b"]
    assert out["agents"] == ["x.md"]
    assert out["commands"] == ["c.md"]
    assert out["hooks"] == ["g.py", "h.sh"]  # sorted
    assert out["scripts"] == ["tool.py"]
    assert out["config"] == ["conf.json"]
    assert out["manifest"]["name"] == "p1"


def test_collect_hooks_filter_only_sh_and_py(tmp_path):
    d = _make_plugin(tmp_path, "p2", manifest={"name": "p2"}, hooks=["a.sh", "b.py"])
    # 非 .sh/.py のファイルを hooks/ に追加 -> 列挙されない
    (d / "hooks" / "readme.txt").write_text("x", encoding="utf-8")
    out = MOD.collect(d)
    assert out["hooks"] == ["a.sh", "b.py"]


def test_collect_manifest_none_when_absent(tmp_path):
    d = _make_plugin(tmp_path, "p3", manifest=None, skills=["run-a"])
    out = MOD.collect(d)
    assert out["manifest"] is None


# --- validate ----------------------------------------------------------------

def _data(manifest, **assets):
    base = {"skills": [], "agents": [], "commands": [],
            "hooks": [], "scripts": [], "config": []}
    base.update(assets)
    base["manifest"] = manifest
    return base


def test_validate_happy_path_no_errors():
    data = _data(
        {"name": "p", "version": "1.0", "description": "d"},
        skills=["run-a"],
    )
    errs = MOD.validate("p", data, {"p"})
    assert errs == []


def test_validate_missing_manifest():
    data = _data(None, skills=["run-a"])
    errs = MOD.validate("p", data, {"p"})
    assert errs == ["p: .claude-plugin/plugin.json missing"]


def test_validate_missing_required_fields():
    data = _data({"name": "p"}, skills=["run-a"])  # version/description 欠如
    errs = MOD.validate("p", data, {"p"})
    assert any("missing 'version'" in e for e in errs)
    assert any("missing 'description'" in e for e in errs)


def test_validate_name_mismatch():
    data = _data(
        {"name": "wrong", "version": "1", "description": "d"},
        skills=["run-a"],
    )
    errs = MOD.validate("p", data, {"p"})
    assert any("!= directory name" in e for e in errs)


def test_validate_declared_hook_not_on_disk():
    manifest = {
        "name": "p", "version": "1", "description": "d",
        "hooks": {
            "PreToolUse": [
                {"hooks": [{"command": "python3 $CLAUDE_PLUGIN_ROOT/hooks/guard.py"}]}
            ]
        },
    }
    data = _data(manifest, skills=["run-a"], hooks=[])  # guard.py がディスクに無い
    errs = MOD.validate("p", data, {"p"})
    assert any("declares hooks not on disk" in e and "guard.py" in e for e in errs)


def test_validate_declared_hook_present_on_disk_ok():
    manifest = {
        "name": "p", "version": "1", "description": "d",
        "hooks": {
            "Stop": [
                {"hooks": [{"command": "$CLAUDE_PLUGIN_ROOT/hooks/stop.sh"}]}
            ]
        },
    }
    data = _data(manifest, skills=["run-a"], hooks=["stop.sh"])
    errs = MOD.validate("p", data, {"p"})
    assert errs == []


def test_validate_empty_distribution():
    data = _data({"name": "p", "version": "1", "description": "d"})  # 全 asset 空
    errs = MOD.validate("p", data, {"p"})
    assert any("no assets" in e for e in errs)


def test_validate_not_in_bundle():
    data = _data(
        {"name": "p", "version": "1", "description": "d"},
        skills=["run-a"],
    )
    errs = MOD.validate("p", data, set())  # bundle メンバーでない
    assert any("not registered in any" in e for e in errs)


def test_validate_malformed_hook_command_falls_back_to_split():
    # shlex.split が ValueError を投げる不正コマンド (未閉じクォート) -> cmd.split() fallback
    manifest = {
        "name": "p", "version": "1", "description": "d",
        "hooks": {
            "PreToolUse": [
                {"hooks": [{"command": 'echo "unterminated $CLAUDE_PLUGIN_ROOT/hooks/h.py'}]}
            ]
        },
    }
    data = _data(manifest, skills=["run-a"], hooks=[])
    errs = MOD.validate("p", data, {"p"})
    # fallback split でも h.py が抽出され missing として検出される
    assert any("h.py" in e for e in errs)


# --- main(): in-process 駆動 (PLUGINS_DIR / BUNDLES_JSON を tmp に向ける) ----

def test_main_plugins_dir_missing_returns_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(MOD, "PLUGINS_DIR", tmp_path / "absent")
    assert MOD.main() == 2
    assert "not found" in capsys.readouterr().err


def test_main_all_complete_returns_0(tmp_path, monkeypatch, capsys):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    _make_plugin(
        plugins, "good",
        manifest={"name": "good", "version": "1", "description": "d"},
        skills=["run-a"],
    )
    bj = tmp_path / "bundles.json"
    bj.write_text(json.dumps({"bundles": [{"plugins": ["good"]}]}), encoding="utf-8")
    monkeypatch.setattr(MOD, "PLUGINS_DIR", plugins)
    monkeypatch.setattr(MOD, "BUNDLES_JSON", bj)
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK: 1 plugin(s) complete" in out
    assert "good: skills=1" in out


def test_main_violation_returns_1(tmp_path, monkeypatch, capsys):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    # bundle 未登録 + version/description 欠如 -> VIOLATION
    _make_plugin(plugins, "bad", manifest={"name": "bad"}, skills=["run-a"])
    bj = tmp_path / "bundles.json"
    bj.write_text(json.dumps({"bundles": []}), encoding="utf-8")
    monkeypatch.setattr(MOD, "PLUGINS_DIR", plugins)
    monkeypatch.setattr(MOD, "BUNDLES_JSON", bj)
    rc = MOD.main()
    captured = capsys.readouterr()
    assert rc == 1
    assert "VIOLATION" in captured.err
    assert "summary: VIOLATION=" in captured.err


def test_main_skips_dotdir_entries(tmp_path, monkeypatch, capsys):
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / ".hidden").mkdir()  # dot-dir は無視
    _make_plugin(
        plugins, "good",
        manifest={"name": "good", "version": "1", "description": "d"},
        skills=["run-a"],
    )
    bj = tmp_path / "bundles.json"
    bj.write_text(json.dumps({"bundles": [{"plugins": ["good"]}]}), encoding="utf-8")
    monkeypatch.setattr(MOD, "PLUGINS_DIR", plugins)
    monkeypatch.setattr(MOD, "BUNDLES_JSON", bj)
    rc = MOD.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert ".hidden" not in out
    assert "OK: 1 plugin(s)" in out


# --- subprocess: 実 repo に対して実行 (returncode は 0 or 1 を許容) ----------

def test_subprocess_runs_on_real_repo():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True,
    )
    # 実 repo の状態に依存するため returncode は 0(完全) or 1(違反) を許容。
    # いずれにせよ summary 区切り "---" を必ず stdout に出す。
    assert proc.returncode in (0, 1)
    assert "---" in proc.stdout
