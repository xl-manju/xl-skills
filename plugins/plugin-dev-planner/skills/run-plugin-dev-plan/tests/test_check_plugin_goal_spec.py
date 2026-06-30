from __future__ import annotations

import json
from pathlib import Path

import pytest

# tests/ -> run-plugin-dev-plan -> schemas/plugin-goal-spec.schema.json
_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "plugin-goal-spec.schema.json"


def _schema() -> dict:
    if not _SCHEMA.is_file():
        pytest.skip(f"plugin-goal-spec.schema.json 不在: {_SCHEMA}")
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))


def _goal_spec() -> dict:
    return {
        "purpose": "Notion task sync plugin の計画を作る",
        "background": "既存台帳と Notion DB の同期を再現可能にする必要がある",
        "goal": "notion-task-sync の plan artifacts が検証可能な状態になる",
        "artifact_class": "plugin-plan",
        "target_plugin_slug": "notion-task-sync",
        "plan_dir": "eval-log/plugin-dev-planner/notion-task-sync",
        "out_dir": None,
        "requested_count": None,
        "force_13": False,
        "checklist": [
            {"id": "C1", "criterion": "component inventory が生成されている", "done": False, "verify_by": "script"}
        ],
        "constraints": [],
        "handoff_targets": ["plugin-dev-plan-architect"],
        "max_loops": 5,
        "open_questions": [],
    }


def test_plugin_goal_spec_accepts_valid_contract(tmp_path, plugin_goal_spec):
    path = tmp_path / "goal-spec.json"
    path.write_text(json.dumps(_goal_spec(), ensure_ascii=False), encoding="utf-8")

    assert plugin_goal_spec.main([str(path)]) == 0


def test_plugin_goal_spec_rejects_extra_key(plugin_goal_spec):
    data = _goal_spec()
    data["unexpected"] = True

    errors = plugin_goal_spec.validate(data)

    assert any("additionalProperties" in e for e in errors)


def test_plugin_goal_spec_rejects_bad_slug(plugin_goal_spec):
    data = _goal_spec()
    data["target_plugin_slug"] = "Notion Task Sync"

    errors = plugin_goal_spec.validate(data)

    assert any("ASCII kebab-case" in e for e in errors)


def test_plugin_goal_spec_rejects_force_13_without_requested_13(plugin_goal_spec):
    data = _goal_spec()
    data["force_13"] = True
    data["requested_count"] = 5

    errors = plugin_goal_spec.validate(data)

    assert any("requested_count=13" in e for e in errors)


# ─────────── schema ↔ validator parity (CRIT-2: 重複契約の drift 封止) ───────────
# goal-spec 契約は plugin-goal-spec.schema.json (宣言) と check-plugin-goal-spec.py の
# 手書き validate() (REQUIRED/ALLOWED/enum/pattern) で二重に持たれる。本 plugin は
# test_schema_parity.py / test_kind_key_doc_parity.py で「重複契約には必ず parity test を
# 付ける」を慣行化しており、goal-spec だけがその例外だった (2026-06-30 elegant-review G-A)。
# 以下は両者を縛り、将来どちらかが drift したら fail させる (片肺更新の無音化を防ぐ)。


def test_validator_required_matches_schema(plugin_goal_spec):
    """check-plugin-goal-spec.py の REQUIRED が schema.required と集合一致する。"""
    schema = _schema()
    assert plugin_goal_spec.REQUIRED == set(schema["required"]), (
        f"required drift: validator-schema={sorted(plugin_goal_spec.REQUIRED - set(schema['required']))} "
        f"schema-validator={sorted(set(schema['required']) - plugin_goal_spec.REQUIRED)}"
    )


def test_validator_allowed_matches_schema_properties(plugin_goal_spec):
    """ALLOWED が schema.properties キー集合と一致する (additionalProperties:false ゆえ等価)。"""
    schema = _schema()
    assert schema.get("additionalProperties") is False, "schema が additionalProperties:false でない"
    props = set(schema["properties"].keys())
    assert plugin_goal_spec.ALLOWED == props, (
        f"allowed/properties drift: validator-schema={sorted(plugin_goal_spec.ALLOWED - props)} "
        f"schema-validator={sorted(props - plugin_goal_spec.ALLOWED)}"
    )


def test_validator_slug_pattern_matches_schema(plugin_goal_spec):
    """target_plugin_slug の正規表現が schema の pattern と逐語一致する。"""
    schema = _schema()
    assert plugin_goal_spec.SLUG_RE.pattern == schema["properties"]["target_plugin_slug"]["pattern"], (
        "target_plugin_slug pattern が schema と drift"
    )


def test_validator_enums_match_schema_behaviorally(plugin_goal_spec):
    """artifact_class / checklist.verify_by の enum が schema と behavioral 一致する。

    validate() は enum を関数内リテラルで持つため (定数未露出)、schema の各 enum 値を
    validate() が受理し、enum 外値を拒否することで両者の一致を間接検証する (stdlib のみ)。
    """
    schema = _schema()
    props = schema["properties"]

    # artifact_class: schema enum の各値を受理・範囲外を拒否
    for v in props["artifact_class"]["enum"]:
        d = _goal_spec()
        d["artifact_class"] = v
        assert not any("artifact_class" in e for e in plugin_goal_spec.validate(d)), (
            f"schema enum 値 {v!r} を validator が artifact_class で拒否 (enum drift)"
        )
    d = _goal_spec()
    d["artifact_class"] = "__not_in_enum__"
    assert any("artifact_class" in e for e in plugin_goal_spec.validate(d)), (
        "validator が artifact_class の enum 外値を拒否しない (enum drift)"
    )

    # checklist.verify_by: schema enum の各値を受理・範囲外を拒否
    verify_enum = props["checklist"]["items"]["properties"]["verify_by"]["enum"]
    for v in verify_enum:
        d = _goal_spec()
        d["checklist"] = [{"id": "C1", "criterion": "x", "done": False, "verify_by": v}]
        assert not any("verify_by" in e for e in plugin_goal_spec.validate(d)), (
            f"schema enum 値 {v!r} を validator が verify_by で拒否 (enum drift)"
        )
    d = _goal_spec()
    d["checklist"] = [{"id": "C1", "criterion": "x", "done": False, "verify_by": "__not_in_enum__"}]
    assert any("verify_by" in e for e in plugin_goal_spec.validate(d)), (
        "validator が verify_by の enum 外値を拒否しない (enum drift)"
    )
