#!/usr/bin/env python3
"""mf-kessai-invoice-check plugin package contract regression tests."""
import ast
import json
import os
import stat
import sys


PLUGIN_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# 本番ランタイムが置かれるディレクトリ (テスト/開発専用の tests/ は含めない)。
RUNTIME_DIRS = [
    "lib",
    "hooks",
    "skills/run-mf-invoice-check/scripts",
    "skills/run-mf-invoice-db-setup/scripts",
]


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


def test_notion_schema_customer_aggregated_snapshot():
    """顧客ID集約モデル: upsert キー=顧客ID単独、最新月スナップショットの事実列のみ。

    月次履歴はページ本文の table block に移したため、月次サマリ関連の列
    (レコード種別/件数3列) は schema から削除済み。
    """
    schema = _json("skills/run-mf-invoice-db-setup/schemas/notion-db-schema.json")
    props = schema["properties"]
    # upsert キーは顧客ID単独。
    assert schema["upsert_key"] == ["顧客ID"]
    # 事実列スナップショットは残る。
    assert props["確認済み日時"]["type"] == "date"
    assert props["チェック実行ID"]["type"] == "rich_text"
    assert "確認済み日時" in schema["fact_columns"]
    assert "チェック実行ID" in schema["fact_columns"]
    # 判定の select は月次サマリを廃した3値。
    assert props["判定"]["options"] == ["発行漏れ候補", "継続発行", "今月新規"]
    # 月次サマリ廃止に伴い削除した列を schema が持たないこと。
    for removed in ["レコード種別", "発行漏れ件数", "金額変動件数", "チェック件数合計"]:
        assert removed not in props
        assert removed not in schema["fact_columns"]
    # 管理列 (人の運用) は不可侵で従来通り。
    assert schema["managed_columns"] == ["請求要否", "対応状況", "チェック済", "備考"]


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


def _runtime_py_files():
    files = []
    for rel in RUNTIME_DIRS:
        base = os.path.join(PLUGIN_ROOT, rel)
        if not os.path.isdir(base):
            continue
        for dirpath, _, filenames in os.walk(base):
            for filename in filenames:
                if filename.endswith(".py"):
                    files.append(os.path.join(dirpath, filename))
    return files


def _top_level_imports(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:  # 絶対 import のみ (相対は対象外)
                names.add(node.module.split(".")[0])
    return names


def test_runtime_imports_are_stdlib_or_in_plugin_only():
    """I3 移植性: 本番ランタイムは標準ライブラリ + プラグイン内モジュールのみに依存する。

    第三者パッケージ (requests / jinja2 等) を runtime に混入させると install 先で手動
    pip が必要になり移植性が壊れる。AST 走査で import を機械的に検査し、将来の混入を
    CI で検出する (grep でなく AST なので import 文を正確に同定)。
    許可基盤は sys.stdlib_module_names (標準機構) を使い自前メンテを避ける。
    """
    files = _runtime_py_files()
    assert files, "ランタイム .py が見つからない (RUNTIME_DIRS の設定ミス)"
    in_plugin = {os.path.splitext(os.path.basename(f))[0] for f in files}
    allowed = set(sys.stdlib_module_names) | in_plugin
    violations = {}
    for path in files:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
        bad = sorted(_top_level_imports(tree) - allowed)
        if bad:
            violations[os.path.relpath(path, PLUGIN_ROOT)] = bad
    assert not violations, f"標準ライブラリ/プラグイン内 以外の import を検出: {violations}"
