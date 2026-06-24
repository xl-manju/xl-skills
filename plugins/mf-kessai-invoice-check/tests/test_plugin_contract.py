#!/usr/bin/env python3
"""mf-kessai-invoice-check plugin package contract regression tests."""
import json
import os
import stat


PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _json(rel_path):
    with open(os.path.join(PLUGIN_ROOT, rel_path), encoding="utf-8") as f:
        return json.load(f)


def test_plugin_manifest_bundle_contract():
    manifest = _json(".claude-plugin/plugin.json")
    assert manifest["name"] == "mf-kessai-invoice-check"
    assert manifest["package_mode"] == "bundle"
    assert manifest["entry_points"]["skills"] == [
        "run-mf-invoice-check",
        "run-mf-invoice-db-setup",
        "ref-mf-kessai-api",
    ]
    assert manifest["entry_points"]["agents"] == ["mfk-gap-verifier"]
    assert manifest["entry_points"]["hooks"] == ["guard-mfk-readonly"]
    # Claude Code 予約フィールド (skills/agents/commands) はトップレベルに置かない。
    # entry_points で宣言し、詳細メタは各 SKILL.md / agents/*.md frontmatter が SSOT。
    assert "skills" not in manifest
    assert "agents" not in manifest
    assert "commands" not in manifest


def test_manifest_hook_points_to_packaged_file():
    manifest = _json(".claude-plugin/plugin.json")
    command = manifest["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "$CLAUDE_PLUGIN_ROOT/hooks/guard-mfk-readonly.py" in command
    assert os.path.exists(os.path.join(PLUGIN_ROOT, "hooks", "guard-mfk-readonly.py"))


def test_workflow_manifest_commands_are_install_path_independent():
    workflow = _json("skills/run-mf-invoice-check/workflow-manifest.json")
    commands = [p.get("command", "") for p in workflow["phases"] if p.get("command")]
    assert commands
    assert all("$CLAUDE_PLUGIN_ROOT/" in command for command in commands)
    assert not any(command.startswith("python3 scripts/") for command in commands)


def test_package_contract_exists_for_bundle_mode():
    contract = _json("references/package-contract.json")
    assert contract["package_mode"] == "bundle"
    checks = contract["pkg_checks"]
    for key in [f"PKG-{i:03d}" for i in range(1, 16)]:
        assert key in checks
        assert checks[key]["status"] in {"pass", "fail", "skip", "not_applicable"}


def test_notion_schema_has_monthly_audit_columns():
    schema = _json("skills/run-mf-invoice-db-setup/schemas/notion-db-schema.json")
    props = schema["properties"]
    assert props["レコード種別"]["type"] == "select"
    assert props["レコード種別"]["options"] == ["月次サマリ", "明細"]
    assert "月次サマリ" in props["判定"]["options"]
    assert props["確認済み日時"]["type"] == "date"
    assert props["チェック実行ID"]["type"] == "rich_text"
    assert "確認済み日時" in schema["fact_columns"]
    assert "チェック実行ID" in schema["fact_columns"]


def test_scripts_are_executable_for_install_smoke():
    rel_paths = [
        "hooks/guard-mfk-readonly.py",
        "lib/mfk_api.py",
        "lib/mfk_keychain.py",
        "skills/run-mf-invoice-check/scripts/check_invoice_gaps.py",
        "skills/run-mf-invoice-db-setup/scripts/build_notion_db.py",
        "skills/run-mf-invoice-db-setup/scripts/verify_db_schema.py",
    ]
    for rel_path in rel_paths:
        mode = os.stat(os.path.join(PLUGIN_ROOT, rel_path)).st_mode
        assert mode & stat.S_IXUSR, f"{rel_path} is not executable"


def test_readme_direct_commands_use_plugin_root():
    with open(os.path.join(PLUGIN_ROOT, "README.md"), encoding="utf-8") as f:
        readme = f.read()
    assert "python3 plugins/mf-kessai-invoice-check/" not in readme
    assert 'python3 "$CLAUDE_PLUGIN_ROOT/lib/mfk_api.py" --smoke' in readme
    assert 'python3 "$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-db-setup/scripts/build_notion_db.py"' in readme


def test_prompts_do_not_use_bare_script_paths():
    checked = []
    for dirpath, _, filenames in os.walk(os.path.join(PLUGIN_ROOT, "skills")):
        for filename in filenames:
            if not filename.endswith(".md"):
                continue
            path = os.path.join(dirpath, filename)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            checked.append(path)
            assert "python3 scripts/" not in text
            assert "python3 plugins/mf-kessai-invoice-check/" not in text
    assert checked
