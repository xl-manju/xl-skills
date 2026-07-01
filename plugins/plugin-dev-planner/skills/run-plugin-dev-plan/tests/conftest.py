"""run-plugin-dev-plan 同梱スクリプトを file-path import するための共通ローダ + spec ビルダ。

scripts/*.py はハイフン名のため通常 import 不可。importlib で明示ロードする。
scripts ディレクトリを sys.path に載せ、共有モジュール specfm の `import specfm` を可能にする。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))  # 各 script の `import specfm` を解決


def _load(stem: str) -> ModuleType:
    path = SCRIPTS_DIR / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def topsort() -> ModuleType:
    return _load("verify-index-topsort")


@pytest.fixture(scope="session")
def plugin_goal_spec() -> ModuleType:
    return _load("check-plugin-goal-spec")


@pytest.fixture(scope="session")
def unassigned() -> ModuleType:
    return _load("detect-unassigned")


@pytest.fixture(scope="session")
def specfm_mod() -> ModuleType:
    return _load("specfm")


@pytest.fixture(scope="session")
def specfm() -> ModuleType:
    return _load("check-spec-frontmatter")


@pytest.fixture(scope="session")
def gates() -> ModuleType:
    return _load("check-spec-gates")


@pytest.fixture(scope="session")
def matrix() -> ModuleType:
    return _load("check-spec-matrix-coverage")


@pytest.fixture(scope="session")
def handoff() -> ModuleType:
    return _load("check-build-handoff")


@pytest.fixture(scope="session")
def surfaces() -> ModuleType:
    return _load("check-surface-inventory")


@pytest.fixture(scope="session")
def plugin_surface_audit() -> ModuleType:
    return _load("check-plugin-surface-audit")


@pytest.fixture(scope="session")
def skeleton() -> ModuleType:
    return _load("render-spec-skeleton")


# ─────────────────────────── YAML 出力ヘルパ ───────────────────────────
SPECFM = _load("specfm")


def _scalar_out(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _emit(d: dict, indent: int = 0) -> list[str]:
    pad = "  " * indent
    lines: list[str] = []
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{pad}{k}:")
            lines += _emit(v, indent + 1)
        elif isinstance(v, list) and v and isinstance(v[0], dict):
            lines.append(f"{pad}{k}:")
            for item in v:
                items = list(item.items())
                fk, fv = items[0]
                lines.append(f"{pad}  - {fk}: {_scalar_out(fv)}")
                for kk, vv in items[1:]:
                    lines.append(f"{pad}    {kk}: {_scalar_out(vv)}")
        elif isinstance(v, list):
            lines.append(f"{pad}{k}: [{', '.join(_scalar_out(x) for x in v)}]")
        else:
            lines.append(f"{pad}{k}: {_scalar_out(v)}")
    return lines


def valid_quality_gates(ck: str) -> dict:
    return {
        "p0_lint": list(SPECFM.P0_LINT_BY_KIND[ck]),
        "build_trace": "required",
        "elegant_review": {"conditions": ["C1", "C2", "C3", "C4"], "all_pass": True},
        "content_review": {"verdict": "PASS", "sha_match": True},
        "evaluator": {"threshold": 80, "high_max": 0},
    }


def valid_harness(ck: str = "skill", skill_kind: str = "run") -> dict:
    """component_kind/skill kind と整合する kind_pass を持つ妥当な harness ブロック。"""
    if ck == "skill" and skill_kind == "ref":
        kp = "ref=source-traceability+ref-review"
    elif ck == "skill" and skill_kind == "assign":
        kp = "assign=evaluator-verdict"
    elif ck == "skill":
        kp = "loop=criteria-test+content-review-verdict"
    else:
        kp = "content-review-verdict"
    return {"min": 80, "kind_pass": kp}


def _base_fm(spec_id: str, ck: str, skill_kind: str) -> dict:
    fm: dict = {"id": spec_id, "component_kind": ck}
    if ck == "skill":
        fm.update({
            # skill component は component_kind との衝突回避で skill kind を canonical
            # `skill_kind` (fallback `kind`) の両方で携帯する (specfm._skill_kind_of 両受容)。
            "skill_name": "run-sample", "skill_kind": skill_kind, "prefix": skill_kind, "kind": skill_kind,
            "hierarchy_level": "L1", "trigger_conditions": ["a", "b"],
            "output_contract": "出力契約", "boundary": "境界", "placement_candidates": ["Skill"],
            # skill-brief base required の残り 6 (実 schema parity)
            "cli_tools": [], "deterministic_checks": [], "external_systems": [], "mcp_tools": [],
            "needs_independent_context": False, "needs_lifecycle_enforcement": False,
            # 任意 property (required ではないが量産プロファイル等で携帯)
            "output_language": "ja", "mass_production_profile": "strict",
        })
        # 条件付き required (prefix/kind 依存・skill_conditional_required と一致)
        if skill_kind in ("run", "wrap", "assign", "delegate"):
            fm.update({"goal": "観測可能な完了状態", "purpose_background": "目的と背景",
                       "checklist": ["c1", "c2"]})
        if skill_kind in ("run", "assign"):
            fm["responsibilities"] = ["R1"]
        if skill_kind == "wrap":
            fm["base_skill"] = "run-base"
        if skill_kind == "delegate":
            fm["delegate_agent"] = "sample-agent"
        if skill_kind in ("run", "wrap", "delegate"):
            # criteria は goal「観測可能な完了状態」由来 (purpose-traceability ゲートを満たす妥当 spec)。
            fm["feedback_contract"] = {"criteria": [
                {"id": "IN1", "loop_scope": "inner",
                 "text": "観測可能な完了状態へ向け決定論 lint が exit0", "verify_by": "lint"},
                {"id": "OUT1", "loop_scope": "outer",
                 "text": "観測可能な完了状態をテストで検証し受入が PASS", "verify_by": "test"},
            ]}
            fm["goal_seek"] = {"engine": "inline", "fork": "subagent", "max_loops": 5}
        if skill_kind in ("run", "assign"):
            fm["prompt_layer"] = "7layer"
        fm["combinators"] = ["with-goal-seek"]
    elif ck == "sub-agent":
        fm.update({"name": "sample-subagent", "description": "説明", "tools": ["Read"],
                   "independent_context": True, "responsibility_anchor": "prompts/R1.md",
                   "prompt_layer": "7layer"})
    elif ck == "slash-command":
        fm.update({"name": "sample", "description": "説明", "argument-hint": "[x]",
                   "allowed-tools": ["Read"], "disable-model-invocation": False})
    elif ck == "hook":
        fm.update({"event": "PreToolUse", "matcher": "Bash", "exit_semantics": "fail-closed-exit2",
                   "settings_wiring": "settings.json", "fail_closed": True})
    elif ck == "script":
        fm.update({"script_name": "do.py", "purpose": "処理", "inputs": "argv", "outputs": "stdout",
                   "exit_codes": "0/1", "network": False, "write_scope": "none",
                   "stdlib_only": True, "tests_min": 80})
    fm["quality_gates"] = valid_quality_gates(ck)
    fm["harness_coverage"] = valid_harness(ck, skill_kind)
    return fm


# component_kind 別の妥当な build_target (validate_inventory_component は非空のみ強制)。
_BUILD_TARGETS = {
    "skill": "plugins/sample/skills/run-sample/",
    "sub-agent": "plugins/sample/agents/sample-subagent.md",
    "slash-command": "plugins/sample/commands/sample.md",
    "hook": "plugins/sample/hooks/sample.py",
    "script": "plugins/sample/skills/run-sample/scripts/do.py",
}


def component_entry(
    spec_id: str,
    ck: str = "skill",
    *,
    skill_kind: str = "run",
    depends_on: list[str] | None = None,
    drop: list[str] | None = None,
    overrides: dict | None = None,
    features: list[str] | None = None,
) -> dict:
    """component-inventory.json の 1 component エントリ (dict) を生成 (drop/overrides で負例化)。

    per-phase 転換で旧 C*.md frontmatter は inventory の components[] へ載せ替わったため、
    _base_fm (旧 spec frontmatter 相当) に build routing フィールド
    (build_target/builder/build_kind・§6 マッピング) を足して inventory component を作る。
    """
    comp = _base_fm(spec_id, ck, skill_kind)
    comp["depends_on"] = depends_on if depends_on is not None else []
    comp["build_target"] = _BUILD_TARGETS[ck]
    comp["builder"] = SPECFM.BUILDER_BY_KIND[ck]
    comp["build_kind"] = SPECFM.BUILD_KIND_BY_KIND[ck]
    if features is not None:
        comp["features"] = features
    if overrides:
        comp.update(overrides)
    for key in drop or []:
        comp.pop(key, None)
    return comp


def default_surfaces() -> dict:
    """plugin_level_surfaces の妥当な最小ブロック (5 surface すべて明示)。"""
    return {
        "manifest": {"required": True, "path": ".claude-plugin/plugin.json"},
        "composition": {"required": True, "path": "plugin-composition.yaml"},
        "harness_eval": {"required": True, "path": "EVALS.json"},
        "references_config_assets": {"required": False, "omitted_reason": "共有 references 不要"},
        "mcp_app_connector": {"required": False, "omitted_reason": "MCP/app connector 不要"},
    }


def write_inventory(
    directory: Path,
    components: list[dict],
    *,
    considered: list[str] | None = None,
    plugin_level_surfaces: dict | None = None,
    extra: dict | None = None,
) -> Path:
    """component-inventory.json (object 形式 SSOT) を生成する。"""
    data: dict = {
        "considered_component_kinds": list(considered) if considered is not None else list(SPECFM.COMPONENT_KINDS),
        "components": components,
        "plugin_level_surfaces": plugin_level_surfaces if plugin_level_surfaces is not None else default_surfaces(),
    }
    if extra:
        data.update(extra)
    path = directory / "component-inventory.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


_PHASE_SECTIONS_BODY = "\n# phase\n## 目的\nx\n## 実行タスク\nx\n## 成果物\nx\n## 完了条件\nx\n"


def write_phase_spec(
    directory: Path,
    n: int,
    *,
    entities_covered: list[str] | None = None,
    applicable: bool = True,
    reason: str = "",
    status: str | None = None,
    overrides: dict | None = None,
    drop: list[str] | None = None,
    sections: bool = True,
) -> Path:
    """phase-NN-<kebab>.md を生成する (§2 frontmatter + §5 本文床)。"""
    fm = SPECFM.minimal_phase_frontmatter(n)
    if entities_covered is not None:
        fm["entities_covered"] = entities_covered
    if not applicable:
        fm["applicability"] = {"applicable": False, "reason": reason or "該当なし"}
    if status is not None:
        fm["status"] = status
    if overrides:
        fm.update(overrides)
    for key in drop or []:
        fm.pop(key, None)
    body = _PHASE_SECTIONS_BODY if sections else "\n# phase\n"
    text = "---\n" + "\n".join(SPECFM.yaml_lines(fm)) + "\n---" + body
    path = directory / f"phase-{n:02d}-{SPECFM.PHASE_NAMES[n - 1]}.md"
    path.write_text(text, encoding="utf-8")
    return path


def write_all_phases(directory: Path, *, entities_by_phase: dict[int, list[str]] | None = None) -> None:
    """P01..P13 を全生成する (entities_by_phase で phase 別 entities_covered を指定)。"""
    entities_by_phase = entities_by_phase or {}
    for n in range(1, 14):
        write_phase_spec(directory, n, entities_covered=entities_by_phase.get(n, []))


def write_phase_index(
    directory: Path,
    *,
    order: list[str] | None = None,
    plugin_meta: bool = False,
    distributable: bool = False,
    heading: str = "フェーズ一覧",
) -> Path:
    """index(main) を `## フェーズ一覧` 付きで生成する (verify-index-topsort 用)。"""
    ids = order if order is not None else [SPECFM.phase_id(n) for n in range(1, 14)]
    fm: dict = {"id": "IDX0", "title": "plan index"}
    if plugin_meta:
        fm["plugin_meta"] = valid_plugin_meta(distributable)
    lines = "".join(f"{i + 1}. {pid} — phase / 未実施\n" for i, pid in enumerate(ids))
    body = f"\n# index\n## {heading}\n\n{lines}"
    text = "---\n" + "\n".join(_emit(fm)) + "\n---" + body
    p = directory / "index.md"
    p.write_text(text, encoding="utf-8")
    return p


def valid_plugin_meta(distributable: bool = False) -> dict:
    """plugin-level 規律を満たす plugin_meta (非配布なら bundles 空・配布なら 1 件)。"""
    bundles = ["xl-skills-full"] if distributable else []
    return {
        "manifest": {
            "required": True,
            "path": ".claude-plugin/plugin.json",
            "name_matches_folder": True,
            "no_todo_placeholders": True,
            "validate_plugin": True,
        },
        "marketplace": {
            "default_personal": True,
            "policy": {
                "installation": "AVAILABLE",
                "authentication": "ON_INSTALL",
                "category": "Productivity",
            },
            "cachebuster_for_update": True,
        },
        "distribution": {"distributable": distributable, "bundles": bundles, "marketplace": distributable},
        "pkg_contract": {"pkg": "002-008"},
        "governance": {"runbook": "required"},
        "ci": {"workflow": "governance-check"},
        "ssot_dedup": {"lint": "ssot-duplication"},
        "feedback_deploy": {"deploy": "run-skill-feedback"},
    }
