"""validate-paradigm-coverage.py の main() / 純関数を *in-process* で網羅する genuine テスト。

network/secret を一切持たない静的 validator (network: false / write-scope: none) のため、
全分岐を実入力で到達できる。tests/scripts3 に subprocess 経由の既存契約テストが存在するが、
subprocess は COVERAGE_PROCESS_START を引き継がず main() 行が coverage 上 missed になる
(77%)。本テストは MOD.main([...]) を *同一プロセスで直接呼ぶ* ことで:

  - main: 引数不足 (exit 2) / .json 経路 OK (exit 0) / .json 経路 fail (exit 1, stderr に
    errors を逐次出力) / markdown 経路 OK (exit 0) / markdown 経路 missing (exit 1) /
    .json でない suffix は markdown 扱い
  - validate_structured_json: 正常 / invalid json / paradigm_findings 欠落・非リスト /
    item 非 object / paradigm_id 非 int / 欠落 id / meta 不一致 / observations 空 /
    issues 非リスト / issue の condition・severity・description・recommended_intervention 不正 /
    variable_abstraction 非リスト・非 object・key 欠落・非 template
  - extract_text: lower-case 化

main() を in-process で呼ぶことで main() 全行 (179-205) を coverage に計上する。
importlib.util.spec_from_file_location で実ファイルパスから直接ロード。tmp_path のみ使用。
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "plugins"
    / "skill-creator"
    / "skills"
    / "run-elegant-review"
    / "scripts"
    / "validate-paradigm-coverage.py"
)

# tests/scripts3 と衝突しないモジュール名で in-process ロードする。
_SPEC = importlib.util.spec_from_file_location("validate_paradigm_coverage_r4", SCRIPT)
MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MOD)


# --------------------------------------------------------------------------
# fixture builders
# --------------------------------------------------------------------------

def _full_findings() -> dict:
    """全 30 paradigm を EXPECTED_META 通りに埋めた合格 findings dict を組む。"""
    findings = []
    for pid in range(1, 31):
        name, category, agent = MOD.EXPECTED_META[pid]
        findings.append(
            {
                "paradigm_id": pid,
                "paradigm_name": name,
                "category": category,
                "agent": agent,
                "observations": [f"observation for paradigm {pid}"],
                "issues": [
                    {
                        "condition": "C1",
                        "severity": "high",
                        "description": f"desc {pid}",
                        "recommended_intervention": f"fix {pid}",
                    }
                ],
            }
        )
    return {
        "paradigm_findings": findings,
        # coverage.used は finding の paradigm_name から動的導出する。
        # validator L166-167 は finding ごとに EXPECTED_META[pid][0] (== paradigm_name)
        # が used に含まれることを要求するため、findings を単一ソースにして突合ズレを防ぐ。
        # 30 名は全 distinct なので len(used)==30 / skipped=[] で 30 網羅を満たす。
        "thought_method_coverage": {
            "total": 30,
            "used": [f["paradigm_name"] for f in findings],
            "skipped_with_reason": [],
        },
        "variable_abstraction": [
            {
                "concrete_value": "30",
                "variable_name": "{{paradigm_count}}",
                "source_trace": "SKILL.md:1",
            }
        ],
    }


def _full_markdown() -> str:
    """全 30 paradigm の代表トークンを 1 つずつ含む markdown を組む。"""
    lines = []
    for pid, tokens in MOD.PARADIGMS.items():
        lines.append(f"## paradigm {pid}: {tokens[0]} -- discussion")
    return "\n".join(lines) + "\n"


def _write(p: Path, obj) -> Path:
    if isinstance(obj, (dict, list)):
        p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    else:
        p.write_text(obj, encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# main() in-process — exit code / stdout / stderr contract
# --------------------------------------------------------------------------

def test_main_usage_error_no_args(capsys):
    rc = MOD.main(["validate-paradigm-coverage.py"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "usage:" in err


def test_main_json_ok(tmp_path, capsys):
    p = _write(tmp_path / "findings.json", _full_findings())
    rc = MOD.main(["prog", str(p)])
    cap = capsys.readouterr()
    assert rc == 0, cap.err
    assert "all 30 paradigms covered with structured findings" in cap.out


def test_main_json_failure_emits_each_error_to_stderr(tmp_path, capsys):
    data = _full_findings()
    data["paradigm_findings"] = data["paradigm_findings"][:-1]  # paradigm 30 欠落
    p = _write(tmp_path / "findings.json", data)
    rc = MOD.main(["prog", str(p)])
    err = capsys.readouterr().err
    assert rc == 1
    # main の for err in errors: print(...) 経路を確認
    assert "missing paradigm_findings ids" in err
    assert "[30]" in err


def test_main_markdown_ok_all_covered(tmp_path, capsys):
    p = _write(tmp_path / "review.md", _full_markdown())
    rc = MOD.main(["prog", str(p)])
    cap = capsys.readouterr()
    assert rc == 0, cap.err
    assert "all 30 paradigms covered" in cap.out


def test_main_markdown_missing_some_paradigms(tmp_path, capsys):
    # paradigm 1 (批判的思考/critical) と 7 (mece) を欠落させる
    body = _full_markdown()
    body = body.replace(MOD.PARADIGMS[1][0], "XXX").replace(MOD.PARADIGMS[1][1], "yyy")
    body = body.replace("mece", "zzz")
    p = _write(tmp_path / "review.md", body)
    rc = MOD.main(["prog", str(p)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "MISSING paradigms" in err
    # 1 と 7 が欠落 id に含まれる
    assert "1" in err and "7" in err


def test_main_non_json_suffix_is_treated_as_markdown(tmp_path, capsys):
    # .txt は suffix != .json なので markdown 経路。全 paradigm 網羅なら OK。
    p = _write(tmp_path / "review.txt", _full_markdown())
    rc = MOD.main(["prog", str(p)])
    cap = capsys.readouterr()
    assert rc == 0, cap.err
    assert "all 30 paradigms covered" in cap.out


def test_main_markdown_case_insensitive_token_match(tmp_path, capsys):
    # extract_text が lower 化するので大文字トークンでも一致する。
    body = _full_markdown().upper()
    p = _write(tmp_path / "REVIEW.MD", body)
    # suffix 判定は .json でないので markdown 経路 (大文字 .MD も .md 同様)
    rc = MOD.main(["prog", str(p)])
    cap = capsys.readouterr()
    assert rc == 0, cap.err
    assert "all 30 paradigms covered" in cap.out


# --------------------------------------------------------------------------
# validate_structured_json — 純関数の正常 / 各異常
# --------------------------------------------------------------------------

def test_structured_json_full_ok(tmp_path):
    p = _write(tmp_path / "f.json", _full_findings())
    ok, errors = MOD.validate_structured_json(p)
    assert ok is True
    assert errors == []


def test_structured_json_invalid_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert errors == ["invalid json"]


def test_structured_json_missing_paradigm_findings(tmp_path):
    p = _write(tmp_path / "f.json", {"variable_abstraction": []})
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert "missing paradigm_findings" in errors


def test_structured_json_paradigm_findings_not_list(tmp_path):
    p = _write(tmp_path / "f.json", {"paradigm_findings": {"a": 1}})
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert "missing paradigm_findings" in errors


def test_structured_json_item_not_object(tmp_path):
    data = _full_findings()
    data["paradigm_findings"].append("not-an-object")
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("is not an object" in e for e in errors)


def test_structured_json_paradigm_id_not_int(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["paradigm_id"] = "1"  # str
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("paradigm_id is not int" in e for e in errors)


def test_structured_json_missing_id(tmp_path):
    data = _full_findings()
    data["paradigm_findings"] = data["paradigm_findings"][:-5]  # 26..30 欠落
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("missing paradigm_findings ids" in e for e in errors)


def test_structured_json_meta_mismatch_name_category_agent(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["paradigm_name"] = "WRONG"
    data["paradigm_findings"][0]["category"] = "Z-bad"
    data["paradigm_findings"][0]["agent"] = "bad-agent"
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("expected paradigm_name=" in e for e in errors)
    assert any("expected category=" in e for e in errors)
    assert any("expected agent=" in e for e in errors)


def test_structured_json_observations_empty(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["observations"] = ["   "]  # 空白のみ
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("observations must contain non-empty text" in e for e in errors)


def test_structured_json_observations_not_list(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["observations"] = "a string"
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("observations must contain non-empty text" in e for e in errors)


def test_structured_json_issues_not_list(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["issues"] = "not-a-list"
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("issues must be a list" in e for e in errors)


def test_structured_json_issue_not_object(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["issues"] = ["not-an-object"]
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("not an object" in e for e in errors)


def test_structured_json_issue_invalid_condition_and_severity(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["issues"] = [
        {
            "condition": "C9",  # invalid
            "severity": "catastrophic",  # invalid
            "description": "d",
            "recommended_intervention": "r",
        }
    ]
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("invalid condition" in e for e in errors)
    assert any("invalid severity" in e for e in errors)


def test_structured_json_issue_missing_description_and_intervention(tmp_path):
    data = _full_findings()
    data["paradigm_findings"][0]["issues"] = [
        {
            "condition": "C1",
            "severity": "low",
            "description": "   ",
            "recommended_intervention": "",
        }
    ]
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("missing description" in e for e in errors)
    assert any("missing recommended_intervention" in e for e in errors)


def test_structured_json_empty_issues_list_allowed(tmp_path):
    # issues は空リストでも (list でありさえすれば) issue ループは回らず合格しうる。
    data = _full_findings()
    for f in data["paradigm_findings"]:
        f["issues"] = []
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is True, errors


def test_structured_json_variable_abstraction_not_list(tmp_path):
    data = _full_findings()
    data["variable_abstraction"] = {"x": 1}
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("variable_abstraction must be a list" in e for e in errors)


def test_structured_json_variable_abstraction_item_not_object(tmp_path):
    data = _full_findings()
    data["variable_abstraction"] = ["not-an-object"]
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("must be object" in e for e in errors)


def test_structured_json_variable_abstraction_missing_keys(tmp_path):
    data = _full_findings()
    data["variable_abstraction"] = [{"variable_name": "{{x}}"}]  # concrete_value/source_trace 欠落
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("missing concrete_value" in e for e in errors)
    assert any("missing source_trace" in e for e in errors)


def test_structured_json_variable_name_not_template(tmp_path):
    data = _full_findings()
    data["variable_abstraction"] = [
        {
            "concrete_value": "v",
            "variable_name": "plain_name",  # {{ で始まらない
            "source_trace": "t",
        }
    ]
    p = _write(tmp_path / "f.json", data)
    ok, errors = MOD.validate_structured_json(p)
    assert ok is False
    assert any("must be template variable" in e for e in errors)


# --------------------------------------------------------------------------
# extract_text
# --------------------------------------------------------------------------

def test_extract_text_lowercases(tmp_path):
    p = tmp_path / "x.md"
    p.write_text("CRITICAL Thinking MECE", encoding="utf-8")
    assert MOD.extract_text(p) == "critical thinking mece"


# --------------------------------------------------------------------------
# PARADIGMS / EXPECTED_META 整合性 (Goodhart 回避: 表が壊れたら検知)
# --------------------------------------------------------------------------

def test_paradigm_tables_cover_1_to_30():
    assert set(MOD.PARADIGMS) == set(range(1, 31))
    assert set(MOD.EXPECTED_META) == set(range(1, 31))
