"""plugins/harness-creator/scripts/verify-plan-coverage.py の genuine 機能テスト。

計画 (component-inventory.json) ↔ plugin 実体の completeness 照合器の全分岐を
tmp_path で網羅する。network/keychain/実 repo 書換なし (全 tmp_path)。

カバー分岐:
- _plugin_root_of: plugins/<plugin>/... 抽出 / plugins/ 外 → None
- _target_exists: skill dir (SKILL.md 有/無) / 単一ファイル (有/無)
- verify: 全実在 / component 欠落 / build_target 未宣言 / component が object でない /
          required surface 欠落 / path 無し required surface skip / 複数 plugin 跨ぎ /
          空 components
- main: --self-test / usage(引数なし) / inventory 不在 / JSON parse error /
        non-dict root / 正常 OK(exit0) / FAIL(exit1) / --json(ok=false)
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugins" / "harness-creator" / "scripts" / "verify-plan-coverage.py"

SPEC = importlib.util.spec_from_file_location("verify_plan_coverage_uut", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def _make_plugin(root: Path, *, skill=True, agent=True, script=True,
                 manifest=True, composition=True):
    """tmp_path に demo plugin 実体を作る (フラグで欠落を再現)。"""
    if skill:
        (root / "plugins/demo/skills/run-demo").mkdir(parents=True, exist_ok=True)
        (root / "plugins/demo/skills/run-demo/SKILL.md").write_text("x", encoding="utf-8")
    if agent:
        (root / "plugins/demo/agents").mkdir(parents=True, exist_ok=True)
        (root / "plugins/demo/agents/demo-verifier.md").write_text("x", encoding="utf-8")
    if script:
        (root / "plugins/demo/scripts").mkdir(parents=True, exist_ok=True)
        (root / "plugins/demo/scripts/demo-check.py").write_text("x", encoding="utf-8")
    if manifest:
        (root / "plugins/demo/.claude-plugin").mkdir(parents=True, exist_ok=True)
        (root / "plugins/demo/.claude-plugin/plugin.json").write_text("{}", encoding="utf-8")
    if composition:
        (root / "plugins/demo/plugin-composition.yaml").write_text("x", encoding="utf-8")


def _inv():
    return {
        "components": [
            {"id": "C01", "component_kind": "skill", "build_target": "plugins/demo/skills/run-demo/"},
            {"id": "C04", "component_kind": "sub-agent", "build_target": "plugins/demo/agents/demo-verifier.md"},
            {"id": "C09", "component_kind": "script", "build_target": "plugins/demo/scripts/demo-check.py"},
        ],
        "plugin_level_surfaces": {
            "manifest": {"required": True, "path": ".claude-plugin/plugin.json"},
            "composition": {"required": True, "path": "plugin-composition.yaml"},
            "schemas": {"required": False, "omitted_reason": "n/a"},
            "notion_config": {"required": True, "resolution": "notion_config"},
        },
    }


# ── _plugin_root_of ─────────────────────────────────────────────────────────
def test_plugin_root_of_extracts():
    assert MOD._plugin_root_of("plugins/demo/skills/x/") == "plugins/demo"


def test_plugin_root_of_non_plugins_returns_none():
    assert MOD._plugin_root_of("other/demo/x") is None


# ── _target_exists ──────────────────────────────────────────────────────────
def test_target_exists_skill_needs_skill_md(tmp_path):
    _make_plugin(tmp_path)
    ok, _ = MOD._target_exists(tmp_path, "plugins/demo/skills/run-demo/", "skill")
    assert ok
    (tmp_path / "plugins/demo/skills/run-demo/SKILL.md").unlink()
    ok, detail = MOD._target_exists(tmp_path, "plugins/demo/skills/run-demo/", "skill")
    assert not ok and "SKILL.md" in detail


def test_target_exists_file_missing(tmp_path):
    ok, detail = MOD._target_exists(tmp_path, "plugins/demo/agents/x.md", "sub-agent")
    assert not ok and "ファイル不在" in detail


# ── verify ──────────────────────────────────────────────────────────────────
def test_verify_all_present(tmp_path):
    _make_plugin(tmp_path)
    mc, ms, summ = MOD.verify(_inv(), tmp_path)
    assert not mc and not ms
    assert "notion_config" in summ["surfaces_skipped"]


def test_verify_missing_component(tmp_path):
    _make_plugin(tmp_path, agent=False)
    mc, _, _ = MOD.verify(_inv(), tmp_path)
    assert any("C04" in e for e in mc)


def test_verify_missing_surface(tmp_path):
    _make_plugin(tmp_path, composition=False)
    _, ms, _ = MOD.verify(_inv(), tmp_path)
    assert any("composition" in e for e in ms)


def test_verify_build_target_undeclared(tmp_path):
    mc, _, _ = MOD.verify({"components": [{"id": "Cx", "component_kind": "hook"}]}, tmp_path)
    assert any("Cx" in e and "build_target" in e for e in mc)


def test_verify_component_not_object(tmp_path):
    mc, _, _ = MOD.verify({"components": ["oops"]}, tmp_path)
    assert any("object でない" in e for e in mc)


def test_verify_multi_plugin_span(tmp_path):
    inv = {
        "components": [
            {"id": "C1", "component_kind": "script", "build_target": "plugins/a/scripts/x.py"},
            {"id": "C2", "component_kind": "script", "build_target": "plugins/b/scripts/y.py"},
        ],
        "plugin_level_surfaces": {"manifest": {"required": True, "path": ".claude-plugin/plugin.json"}},
    }
    _, ms, _ = MOD.verify(inv, tmp_path)
    assert any("跨ぐ" in e for e in ms)


def test_verify_empty(tmp_path):
    mc, ms, _ = MOD.verify({"components": [], "plugin_level_surfaces": {}}, tmp_path)
    assert not mc and not ms


# ── main (CLI) ──────────────────────────────────────────────────────────────
def test_main_self_test():
    assert MOD.main(["--self-test"]) == 0


def test_main_usage_no_args():
    assert MOD.main([]) == 2


def test_main_inventory_missing(tmp_path):
    assert MOD.main([str(tmp_path / "nope.json")]) == 2


def test_main_json_parse_error(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    assert MOD.main([str(p)]) == 2


def test_main_non_dict_root(tmp_path):
    p = tmp_path / "arr.json"
    p.write_text("[]", encoding="utf-8")
    assert MOD.main([str(p)]) == 2


def test_main_ok(tmp_path):
    _make_plugin(tmp_path)
    p = tmp_path / "inv.json"
    p.write_text(json.dumps(_inv()), encoding="utf-8")
    assert MOD.main([str(p), "--repo-root", str(tmp_path)]) == 0


def test_main_fail(tmp_path):
    _make_plugin(tmp_path, agent=False)
    p = tmp_path / "inv.json"
    p.write_text(json.dumps(_inv()), encoding="utf-8")
    assert MOD.main([str(p), "--repo-root", str(tmp_path)]) == 1


def test_main_json_flag(tmp_path, capsys):
    _make_plugin(tmp_path, agent=False)
    p = tmp_path / "inv.json"
    p.write_text(json.dumps(_inv()), encoding="utf-8")
    rc = MOD.main([str(p), "--repo-root", str(tmp_path), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["ok"] is False
    assert any("C04" in e for e in out["missing_components"])
