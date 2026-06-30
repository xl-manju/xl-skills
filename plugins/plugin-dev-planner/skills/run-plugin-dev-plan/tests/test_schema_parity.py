"""schema parity 回帰防止: specfm が skill-creator の *実* skill-brief.schema.json に忠実か。

elegant-review で「self-test(reflection.md 自身との一致=循環検証)だけでは実スキーマ忠実性を
検査できず、specfm.SKILL_BRIEF_FIELDS が実 required と 8/14 しか一致しない」欠陥(CRIT-2)を
検出した。本テストは *外部の実 schema* を真実源に縛り、将来ドリフトしたら fail させる。

repo-bundled 前提 (本 plugin は distributable:false で skill-creator と同梱)。standalone
配布で schema 不在なら skip (parity ガードは CI=repo 文脈で機能する)。
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

# tests/ -> run-plugin-dev-plan -> skills -> plugin-dev-planner -> plugins
_PLUGINS = Path(__file__).resolve().parents[4]
_SCHEMA = _PLUGINS / "skill-creator" / "skills" / "run-skill-create" / "schemas" / "skill-brief.schema.json"
_FC_SSOT = _PLUGINS / "skill-creator" / "scripts" / "feedback_contract_ssot.py"


def _real_schema() -> dict:
    if not _SCHEMA.is_file():
        pytest.skip(f"実 skill-brief.schema.json 不在 (standalone 配布): {_SCHEMA}")
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _real_fc_ssot() -> ModuleType:
    """skill-creator の実 feedback_contract_ssot.py を file-path import する。"""
    if not _FC_SSOT.is_file():
        pytest.skip(f"実 feedback_contract_ssot.py 不在 (standalone 配布): {_FC_SSOT}")
    spec = importlib.util.spec_from_file_location("feedback_contract_ssot", _FC_SSOT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_skill_brief_base_required_parity(specfm_mod):
    """specfm.SKILL_BRIEF_FIELDS が実 schema の base required と集合一致する。"""
    schema = _real_schema()
    real_required = set(schema.get("required", []))
    declared = set(specfm_mod.SKILL_BRIEF_FIELDS)
    assert declared == real_required, (
        f"schema parity drift: 実required-plan={sorted(real_required - declared)} "
        f"plan-実required={sorted(declared - real_required)}"
    )


def test_presence_only_fields_are_real_properties(specfm_mod):
    """presence-only 指定が実 schema の property であり minItems を持たない(空許容)。"""
    schema = _real_schema()
    props = schema.get("properties", {})
    for f in specfm_mod.SKILL_BRIEF_PRESENCE_ONLY:
        assert f in props, f"{f} が実 schema の property でない"
        if props[f].get("type") == "array":
            assert "minItems" not in props[f], f"{f} は minItems を持つ(空非許容)ため presence-only にできない"


def test_conditional_required_matches_schema_allof(specfm_mod):
    """skill_conditional_required の prefix/kind 依存が実 schema の allOf と整合する。"""
    schema = _real_schema()
    # 実 allOf から prefix∈{run,wrap,assign,delegate}→goal/purpose_background/checklist を抽出
    found_loop = found_resp = False
    for clause in schema.get("allOf", []):
        then_req = set(clause.get("then", {}).get("required", []))
        if {"goal", "purpose_background", "checklist"} <= then_req:
            found_loop = True
        if "responsibilities" in then_req:
            found_resp = True
    assert found_loop, "実 schema allOf に goal/purpose_background/checklist の条件付き required が無い"
    assert found_resp, "実 schema allOf に responsibilities の条件付き required が無い"
    # plan 側の helper が run でこれらを要求する
    run_req = set(specfm_mod.skill_conditional_required("run"))
    assert {"goal", "purpose_background", "checklist", "responsibilities"} <= run_req


def test_feedback_contract_constants_parity(specfm_mod):
    """specfm が逐語複製した feedback_contract 制約定数が実 SSOT と一致する。

    specfm.py は cross-plugin import を避けるため feedback_contract_ssot.py の
    CRITERIA_ID_RE / CRITERIA_VERIFY_BY / LOOP_SCOPES / REQUIRED_CRITERION_KEYS /
    FEEDBACK_LOOP_KINDS を逐語複製する (specfm.py:26-35 のコメント参照)。SKILL_BRIEF_FIELDS と
    同じく『複製は実 SSOT を真実源に縛り将来ドリフトで fail させる』(CRIT-2 と同一欠陥クラス=
    片肺 vendoring の予防)。本テスト追加時点で drift 0 を確認済 (2026-06-30 elegant-review S8)。
    """
    ssot = _real_fc_ssot()
    assert specfm_mod.CRITERIA_ID_RE.pattern == ssot.CRITERIA_ID_RE.pattern, "CRITERIA_ID_RE drift"
    assert specfm_mod.CRITERIA_VERIFY_BY == ssot.CRITERIA_VERIFY_BY, "CRITERIA_VERIFY_BY drift"
    assert specfm_mod.LOOP_SCOPES == ssot.LOOP_SCOPES, "LOOP_SCOPES drift"
    assert specfm_mod.REQUIRED_CRITERION_KEYS == ssot.REQUIRED_CRITERION_KEYS, "REQUIRED_CRITERION_KEYS drift"
    assert set(specfm_mod.FEEDBACK_LOOP_SKILL_KINDS) == set(ssot.FEEDBACK_LOOP_KINDS), (
        "FEEDBACK_LOOP_SKILL_KINDS が実 SSOT の FEEDBACK_LOOP_KINDS と不一致"
    )


def test_no_codex_plugin_token_remains():
    """生成規約が Claude Code(.claude-plugin) に統一され .codex-plugin 残存が無い(CRIT-1)。"""
    root = Path(__file__).resolve().parents[1]  # run-plugin-dev-plan/
    self_name = Path(__file__).name  # 本ガードは検索リテラルとして token を含むため自身を除外
    offenders = []
    for p in root.rglob("*"):
        if p.name == self_name:
            continue
        if p.suffix in {".py", ".md", ".yaml", ".json"} and "__pycache__" not in p.parts:
            try:
                if ".codex-plugin" in p.read_text(encoding="utf-8"):
                    offenders.append(p.name)
            except (UnicodeDecodeError, OSError):
                pass
    assert not offenders, f".codex-plugin が残存: {offenders} (.claude-plugin へ統一すること)"
