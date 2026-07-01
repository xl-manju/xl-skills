"""plugin-dev-planner が単一 skill だけに退化しないことを固定する。"""
from __future__ import annotations

import json
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[3]


def test_plugin_level_surfaces_exist():
    required = [
        "skills/run-plugin-dev-plan/SKILL.md",
        "skills/assign-plugin-plan-evaluator/SKILL.md",
        "agents/plugin-dev-plan-elicitor.md",
        "agents/plugin-dev-plan-architect.md",
        "agents/plugin-dev-plan-evaluator.md",
        "commands/plugin-dev-plan.md",
        "hooks/hook-validate-plugin-plan.py",
        "EVALS.json",
        "plugin-composition.yaml",
        ".claude-plugin/plugin.json",
    ]
    missing = [p for p in required if not (PLUGIN_ROOT / p).is_file()]
    assert missing == []


def test_agents_follow_prompt_creator_adapter_spec():
    """3 agent が prompt-creator 仕様準拠の薄いアダプタ frontmatter を携帯する。
    elicitor/architect は orchestrator (run-plugin-dev-plan) 配下、evaluator は独立 skill
    (assign-plugin-plan-evaluator) 配下へ re-home され、responsibility は各 owner_skill と 1:1。"""
    import re

    agents_dir = PLUGIN_ROOT / "agents"
    expected = {
        "plugin-dev-plan-elicitor": {"owner_skill": "run-plugin-dev-plan", "responsibility_id": "R1", "isolation": "inherit"},
        "plugin-dev-plan-architect": {"owner_skill": "run-plugin-dev-plan", "responsibility_id": "R2-R3", "isolation": "fork"},
        "plugin-dev-plan-evaluator": {"owner_skill": "assign-plugin-plan-evaluator", "responsibility_id": "R1", "isolation": "fork"},
    }
    for name, want in expected.items():
        text = (agents_dir / f"{name}.md").read_text(encoding="utf-8")
        fm = text.split("---", 2)[1]
        # prompt-creator 仕様: 薄いアダプタは owner_skill + responsibility_id + isolation を持つ
        assert f"owner_skill: {want['owner_skill']}" in fm, f"{name}: owner_skill 不一致"
        assert re.search(rf"responsibility_id:\s*{re.escape(want['responsibility_id'])}\b", fm), f"{name}: responsibility_id 不一致"
        assert re.search(rf"isolation:\s*{want['isolation']}\b", fm), f"{name}: isolation 不一致"
        # SSOT 重複定義しない (本文に「薄いアダプタ」宣言がある)
        assert "薄いアダプタ" in text, f"{name}: 薄いアダプタ宣言が無い (SSOT 重複定義の疑い)"


def test_evaluator_skill_is_assign_kind_with_fork():
    """評価は独立 skill (kind=assign) へ昇格し proposer≠approver を構造保証する。"""
    sk = (PLUGIN_ROOT / "skills/assign-plugin-plan-evaluator/SKILL.md").read_text(encoding="utf-8")
    fm = sk.split("---", 2)[1]
    assert "kind: assign" in fm, "evaluator skill が kind=assign でない"
    assert "context: fork" in fm, "evaluator skill が context:fork でない (独立評価の不変条件)"
    assert "user-invocable: false" in fm, "assign-* は user-invocable:false 規約"
    # 出力 schema と rubric/criteria が揃う (再現性)
    base = PLUGIN_ROOT / "skills/assign-plugin-plan-evaluator"
    for rel in ("prompts/R1-evaluate.md", "references/plan-rubric.json",
                "references/four-condition-criteria.md", "schemas/plan-findings.schema.json"):
        assert (base / rel).is_file(), f"assign skill の {rel} が欠落"


def test_manifest_wires_plan_validation_hook():
    manifest = json.loads((PLUGIN_ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    hooks = manifest.get("hooks", {})
    commands = []
    for entries in hooks.values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                commands.append(hook.get("command", ""))
    assert any("hooks/hook-validate-plugin-plan.py" in command for command in commands)


def test_hook_relevance_targets_edited_file():
    """hook の relevance 判定が編集対象 file_path に限定され、無関係編集で過剰発火しない。"""
    import importlib.util

    hook_path = PLUGIN_ROOT / "hooks" / "hook-validate-plugin-plan.py"
    spec = importlib.util.spec_from_file_location("_hook_validate_plugin_plan", hook_path)
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)

    # 編集対象が本 plugin の plan 資産 → 発火する
    relevant = {"tool_input": {"file_path": "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/check-spec-gates.py"}}
    assert hook._is_relevant(relevant) is True
    # 他 plugin の編集で内容に plugin 名が出てくるだけ → 発火しない (過剰発火の解消)
    unrelated = {"tool_input": {"file_path": "plugins/company-master/SKILL.md", "content": "see plugin-dev-plan"}}
    assert hook._is_relevant(unrelated) is False
    # file_path 不明な編集系イベント → 保守的に従来挙動へフォールバック
    no_path = {"tool_response": {"text": "touched run-plugin-dev-plan"}}
    assert hook._is_relevant(no_path) is True


def test_hook_main_ignores_unrelated_payload():
    """runtime hook 自体はテストファイルではないが、無関係編集を exit0 で素通りすることを固定する。"""
    import json
    import subprocess
    import sys

    hook_path = PLUGIN_ROOT / "hooks" / "hook-validate-plugin-plan.py"
    payload = {"tool_input": {"file_path": "plugins/company-master/README.md"}}
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=PLUGIN_ROOT / "skills" / "run-plugin-dev-plan",
    )
    assert result.returncode == 0, result.stderr


def test_hook_main_runs_sample_plan_gate_from_skill_cwd():
    """runtime hook が CI の skill cwd からでも sample-plan gate を実行できることを固定する。"""
    import json
    import subprocess
    import sys

    hook_path = PLUGIN_ROOT / "hooks" / "hook-validate-plugin-plan.py"
    payload = {"tool_input": {"file_path": "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/SKILL.md"}}
    result = subprocess.run(
        [sys.executable, str(hook_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=PLUGIN_ROOT / "skills" / "run-plugin-dev-plan",
    )
    assert result.returncode == 0, result.stderr


def test_agent_bash_is_python_scoped():
    """子 agent の Bash 権限は無制限でなく Bash(python3 *) に絞られている (最小権限・親より広権限の逆転禁止)。"""
    import re

    agents_dir = PLUGIN_ROOT / "agents"
    for agent_file in agents_dir.glob("*.md"):
        fm = agent_file.read_text(encoding="utf-8").split("---", 2)[1]
        tools_line = next((l for l in fm.splitlines() if l.strip().startswith("tools:")), "")
        # 無制限 Bash (スコープ括弧なしの単独 Bash) を agent tools に持たせない
        assert not re.search(r"\bBash\b(?!\s*\()", tools_line), f"{agent_file.name}: 無制限 Bash は最小権限違反 (Bash(python3 *) に絞る)"


def test_evals_lists_all_expected_surfaces():
    evals = json.loads((PLUGIN_ROOT / "EVALS.json").read_text(encoding="utf-8"))
    assert set(evals["surfaces"]) == {
        "skills",
        "agents",
        "commands",
        "hooks",
        "scripts",
        "references",
        "examples",
        "harness-evals",
        "plugin-manifest",
    }


def test_resource_map_lists_plugin_entry_surfaces():
    """resource-map の plugin_surfaces が実 entry point と sample-plan anchor を落とさない。"""
    text = (
        PLUGIN_ROOT
        / "skills"
        / "run-plugin-dev-plan"
        / "references"
        / "resource-map.yaml"
    ).read_text(encoding="utf-8")
    expected_paths = [
        "../../skills/run-plugin-dev-plan/SKILL.md",
        "../../skills/assign-plugin-plan-evaluator/SKILL.md",
        "../../agents/plugin-dev-plan-elicitor.md",
        "../../agents/plugin-dev-plan-architect.md",
        "../../agents/plugin-dev-plan-evaluator.md",
        "../../commands/plugin-dev-plan.md",
        "../../hooks/hook-validate-plugin-plan.py",
        "../../EVALS.json",
        "../../plugin-composition.yaml",
        "examples/sample-plan/component-inventory.json",
        "examples/sample-plan/index.md",
        "examples/sample-plan/phase-01-requirements.md",
        "examples/sample-plan/phase-02-design.md",
        "examples/sample-plan/phase-03-design-review.md",
        "examples/sample-plan/phase-04-test-design.md",
        "examples/sample-plan/phase-05-implementation.md",
        "examples/sample-plan/phase-06-test-run.md",
        "examples/sample-plan/phase-07-acceptance-criteria.md",
        "examples/sample-plan/phase-08-refactoring.md",
        "examples/sample-plan/phase-09-quality-assurance.md",
        "examples/sample-plan/phase-10-final-review.md",
        "examples/sample-plan/phase-11-evidence.md",
        "examples/sample-plan/phase-12-documentation.md",
        "examples/sample-plan/phase-13-release.md",
        "examples/sample-plan/handoff-run-plugin-dev-plan.json",
    ]
    missing = [p for p in expected_paths if p not in text]
    assert missing == []
    base = PLUGIN_ROOT / "skills" / "run-plugin-dev-plan"
    unresolved = []
    for rel in expected_paths:
        target = (base / rel).resolve()
        if not target.is_file():
            unresolved.append(rel)
    assert unresolved == []
