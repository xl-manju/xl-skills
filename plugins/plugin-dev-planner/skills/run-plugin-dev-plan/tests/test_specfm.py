"""specfm.py (共有パーサ + criteria 制約) の機能テスト。"""
from __future__ import annotations


def test_split_frontmatter(specfm_mod):
    assert specfm_mod.split_frontmatter("---\nid: C01\n---\nbody").strip() == "id: C01"
    assert specfm_mod.split_frontmatter("no fm") is None
    assert specfm_mod.split_frontmatter("---\nonly one") is None


def test_parse_scalar_types(specfm_mod):
    fm = specfm_mod.parse_frontmatter(
        "---\nname: x\nflag: true\noff: false\nn: 42\nneg: -3\n---\n"
    )
    assert fm == {"name": "x", "flag": True, "off": False, "n": 42, "neg": -3}


def test_parse_inline_and_block_list(specfm_mod):
    fm = specfm_mod.parse_frontmatter(
        "---\ninline: [a, b, c]\nblock:\n  - x\n  - y\n---\n"
    )
    assert fm["inline"] == ["a", "b", "c"]
    assert fm["block"] == ["x", "y"]


def test_parse_quoted_and_comment(specfm_mod):
    fm = specfm_mod.parse_frontmatter(
        '---\nq: "hello world"\nc: value # trailing\nfc: # only comment\n  k: 1\n---\n'
    )
    assert fm["q"] == "hello world"
    assert fm["c"] == "value"
    assert fm["fc"] == {"k": 1}


def test_parse_nested_map(specfm_mod):
    text = (
        "---\n"
        "quality_gates:\n"
        "  p0_lint: [lint-skill-name, validate-frontmatter]\n"
        "  build_trace: required\n"
        "  elegant_review:\n"
        "    conditions: [C1, C2, C3, C4]\n"
        "    all_pass: true\n"
        "  evaluator:\n"
        "    threshold: 80\n"
        "    high_max: 0\n"
        "---\n"
    )
    fm = specfm_mod.parse_frontmatter(text)
    qg = fm["quality_gates"]
    assert qg["p0_lint"] == ["lint-skill-name", "validate-frontmatter"]
    assert qg["build_trace"] == "required"
    assert qg["elegant_review"] == {"conditions": ["C1", "C2", "C3", "C4"], "all_pass": True}
    assert qg["evaluator"] == {"threshold": 80, "high_max": 0}


def test_parse_list_of_flat_maps(specfm_mod):
    text = (
        "---\n"
        "feedback_contract:\n"
        "  criteria:\n"
        "    - id: IN1\n"
        "      loop_scope: inner\n"
        "      text: t\n"
        "      verify_by: lint\n"
        "    - id: OUT1\n"
        "      loop_scope: outer\n"
        "      text: t2\n"
        "      verify_by: evaluator\n"
        "---\n"
    )
    crit = specfm_mod.parse_frontmatter(text)["feedback_contract"]["criteria"]
    assert [c["id"] for c in crit] == ["IN1", "OUT1"]
    assert crit[0]["loop_scope"] == "inner" and crit[1]["verify_by"] == "evaluator"


def test_parse_empty_and_no_fm(specfm_mod):
    assert specfm_mod.parse_frontmatter("no fm") == {}
    assert specfm_mod.parse_frontmatter("---\n---\n") == {}


def test_parse_inline_flow_map(specfm_mod):
    # inline flow map (ネストした flow list の内側カンマも保持)
    fm = specfm_mod.parse_frontmatter(
        "---\nplugin_meta:\n  distribution: {distributable: false, bundles: [a, b], marketplace: false}\n---\n"
    )
    dist = fm["plugin_meta"]["distribution"]
    assert dist == {"distributable": False, "bundles": ["a", "b"], "marketplace": False}


def test_split_top_respects_nesting(specfm_mod):
    assert specfm_mod._split_top("a, [b, c], {d: e, f: g}") == ["a", "[b, c]", "{d: e, f: g}"]


def test_validate_criteria_ok(specfm_mod):
    crit = [
        {"id": "IN1", "loop_scope": "inner", "text": "t", "verify_by": "lint"},
        {"id": "OUT1", "loop_scope": "outer", "text": "t", "verify_by": "elegant-review"},
    ]
    assert specfm_mod.validate_criteria(crit) == []


def test_validate_criteria_empty(specfm_mod):
    assert specfm_mod.validate_criteria([]) != []
    assert specfm_mod.validate_criteria(None) != []


def test_validate_criteria_non_dict_item(specfm_mod):
    errs = specfm_mod.validate_criteria(["not a dict"])
    assert any("object でない" in e for e in errs)


def test_validate_criteria_missing_outer(specfm_mod):
    crit = [{"id": "IN1", "loop_scope": "inner", "text": "t", "verify_by": "lint"}]
    assert any("outer" in e for e in specfm_mod.validate_criteria(crit))


def test_validate_criteria_bad_fields(specfm_mod):
    crit = [
        {"id": "X1", "loop_scope": "sideways", "text": "t", "verify_by": "magic"},
        {"id": "X1", "loop_scope": "outer", "text": "", "verify_by": "lint"},
    ]
    errs = specfm_mod.validate_criteria(crit)
    assert any("^(IN|OUT|C)" in e for e in errs)
    assert any("enum 外" in e for e in errs)
    assert any("inner|outer" in e for e in errs)
    assert any("重複" in e for e in errs)
    assert any(".text が空" in e for e in errs)


def test_purpose_signals_extracts_cjk_bigrams_and_ascii(specfm_mod):
    sig = specfm_mod.purpose_signals("冪等同期され差分0 Notion へ")
    assert {"冪等", "同期", "差分"} <= sig  # CJK bigram (hiragana 区切り)
    assert "notion" in sig                  # ascii 語 (3 文字以上・小文字化)
    assert "へ" not in sig and "0" not in sig  # hiragana 単独 / 数字は素片にしない


def test_purpose_signals_empty_for_glue_only(specfm_mod):
    # hiragana / 1 文字漢字 / 短い ascii のみ → 内容語シグナル無し (判定材料なし)
    assert specfm_mod.purpose_signals("を する した で") == set()
    assert specfm_mod.purpose_signals("全 P0") == set()


def test_criteria_purpose_traceability_detects_generic_fallback(specfm_mod):
    goal = "タスク台帳が Notion へ冪等同期され差分0で完了した状態"
    checklist = ["差分抽出", "冪等upsert", "同期検証"]
    generic = [
        {"id": "IN1", "loop_scope": "inner", "text": "P0 lint 8 本 exit0", "verify_by": "lint"},
        {"id": "OUT1", "loop_scope": "outer", "text": "elegant-review の C1-C4 が全 PASS する",
         "verify_by": "elegant-review"},
    ]
    errs = specfm_mod.criteria_purpose_traceability_errors(generic, goal=goal, checklist=checklist)
    assert any("purpose 由来でない" in e for e in errs)


def test_criteria_purpose_traceability_accepts_derived(specfm_mod):
    goal = "タスク台帳が Notion へ冪等同期され差分0で完了した状態"
    checklist = ["差分抽出", "冪等upsert", "同期検証"]
    good = [
        {"id": "IN1", "loop_scope": "inner", "text": "同期ペイロードを送信前に検証する", "verify_by": "script"},
        {"id": "OUT1", "loop_scope": "outer", "text": "二回同期で差分0=冪等性を検証テストが確認", "verify_by": "test"},
    ]
    assert specfm_mod.criteria_purpose_traceability_errors(good, goal=goal, checklist=checklist) == []


def test_criteria_purpose_traceability_lenient_without_vocab(specfm_mod):
    # goal/checklist から content シグナルが取れなければ判定不能で [] (偽陽性回避)
    generic = [{"id": "OUT1", "loop_scope": "outer", "text": "4 条件 PASS", "verify_by": "lint"}]
    assert specfm_mod.criteria_purpose_traceability_errors(generic, goal="", checklist=None) == []
    assert specfm_mod.criteria_purpose_traceability_errors(generic, goal="を する", checklist=[]) == []
    # criteria が空/非 list でも構造不備は validate_criteria の責務ゆえここでは [] を返す
    assert specfm_mod.criteria_purpose_traceability_errors([], goal="冪等同期", checklist=None) == []


def test_minimal_frontmatter_criteria_are_purpose_traceable(specfm_mod):
    """skeleton 生成器が purpose-traceability ゲートを自前で満たす (汎用 fallback を吐かない)。"""
    for sk in specfm_mod.FEEDBACK_LOOP_SKILL_KINDS:
        fm = specfm_mod.minimal_frontmatter("skill", skill_kind=sk)
        crit = fm["feedback_contract"]["criteria"]
        errs = specfm_mod.criteria_purpose_traceability_errors(
            crit, goal=fm.get("goal"), checklist=fm.get("checklist"))
        assert errs == [], (sk, errs)


def test_as_int(specfm_mod):
    assert specfm_mod.as_int(80) == 80
    assert specfm_mod.as_int("80") == 80
    assert specfm_mod.as_int(True) is None
    assert specfm_mod.as_int("x") is None
    assert specfm_mod.as_int(None) is None


def test_contract_tables_present(specfm_mod):
    assert len(specfm_mod.SKILL_P0_LINTS) == 8
    assert set(specfm_mod.COMPONENT_KINDS) == {"skill", "sub-agent", "slash-command", "hook", "script"}
    assert "lint-agent-prompt-section" in specfm_mod.P0_LINT_BY_KIND["sub-agent"]
    assert set(specfm_mod.PLUGIN_META_REQUIRED_DICTS) == {
        "manifest", "marketplace", "ci", "governance", "pkg_contract", "ssot_dedup", "feedback_deploy"
    }


def test_plugin_meta_core_conditional_partition(specfm_mod):
    """core/conditional が従来 7 キーを重複なく分割する (後方互換=和集合不変)。"""
    core = set(specfm_mod.PLUGIN_META_CORE_DICTS)
    cond = set(specfm_mod.PLUGIN_META_CONDITIONAL_DICTS)
    assert core == {"manifest", "marketplace", "ci"}
    assert cond == {"pkg_contract", "governance", "ssot_dedup", "feedback_deploy"}
    assert core.isdisjoint(cond)
    assert core | cond == set(specfm_mod.PLUGIN_META_REQUIRED_DICTS)


def test_is_plugin_meta_na(specfm_mod):
    """{applicable: false} のみ N/A 判定 (true / 欠落 / 非 dict は False)。"""
    assert specfm_mod.is_plugin_meta_na({"applicable": False, "reason": "x"}) is True
    assert specfm_mod.is_plugin_meta_na({"applicable": True}) is False
    assert specfm_mod.is_plugin_meta_na({"pkg": "002"}) is False
    assert specfm_mod.is_plugin_meta_na("x") is False


def test_plan_slug_deterministic(specfm_mod):
    """plan_slug が決定論的 kebab-case を返す (同一入力→同一 slug=再現性)。"""
    assert specfm_mod.plan_slug("Notion Task Sync") == "notion-task-sync"
    assert specfm_mod.plan_slug("  MF_掛け払い  Check!! ") == "mf-check"  # 非英数は - 圧縮
    assert specfm_mod.plan_slug("already-kebab") == "already-kebab"
    assert specfm_mod.plan_slug("a---b__c") == "a-b-c"
    # 冪等性: slug(slug(x)) == slug(x)
    once = specfm_mod.plan_slug("Some Plugin v2")
    assert specfm_mod.plan_slug(once) == once


def test_plan_output_dir(specfm_mod):
    """plan_output_dir が既定/上書きを決定論的に解決する。"""
    assert specfm_mod.plan_output_dir("Notion Task Sync") == "eval-log/plugin-dev-planner/notion-task-sync"
    # --out-dir 明示は優先 (末尾スラッシュ除去)
    assert specfm_mod.plan_output_dir("x", out_dir="plans/custom/") == "plans/custom"
    # slug 化不能 (全て非英数) は ValueError
    import pytest as _pytest
    with _pytest.raises(ValueError):
        specfm_mod.plan_output_dir("日本語のみ")


def test_expected_kind_pass_tokens(specfm_mod):
    assert specfm_mod.expected_kind_pass_tokens("skill", "run") == {"criteria", "content-review"}
    assert specfm_mod.expected_kind_pass_tokens("skill", "ref") == {"source-traceability", "ref-review"}
    assert specfm_mod.expected_kind_pass_tokens("skill", "assign") == {"evaluator", "verdict"}
    assert "content-review" in specfm_mod.expected_kind_pass_tokens("hook", "")


def test_kind_pass_ok(specfm_mod):
    assert specfm_mod.kind_pass_ok("loop=criteria-test+content-review-verdict", "skill", "run")
    assert not specfm_mod.kind_pass_ok("source-traceability-only", "skill", "run")
    assert specfm_mod.kind_pass_ok("ref=source-traceability+ref-review", "skill", "ref")
    assert specfm_mod.kind_pass_ok("content-review-verdict", "hook", "")
    assert not specfm_mod.kind_pass_ok("", "skill", "run")


def test_minimal_frontmatter_each_kind_passes_contract(specfm_mod, specfm, gates):
    """specfm 生成 skeleton が静的ひな形なしで既存ゲートを通る。"""
    for ck in specfm_mod.COMPONENT_KINDS:
        text = specfm_mod.render_minimal_spec(ck, spec_id="C01", skill_kind="run")
        assert specfm.check_spec(text) == [], ck
        assert gates.check_gates(text) == [], ck


def test_render_spec_skeleton_cli(skeleton, specfm, gates, capsys):
    assert skeleton.main(["--kind", "hook", "--id", "C04"]) == 0
    out = capsys.readouterr().out
    assert "component_kind: hook" in out
    assert "## 目的" in out
    assert specfm.check_spec(out) == []
    assert gates.check_gates(out) == []
