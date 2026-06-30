"""detect-unassigned.py の機能テスト。"""
from __future__ import annotations

from conftest import write_spec


def test_load_inventory_json_components(unassigned):
    text = '{"components": [{"id": "C01"}, {"id": "C02"}]}'
    assert unassigned.load_inventory(text) == ["C01", "C02"]


def test_load_inventory_json_list(unassigned):
    assert unassigned.load_inventory('["C01", "C02"]') == ["C01", "C02"]


def test_load_inventory_text_lines_dedup(unassigned):
    text = "- C01: skill\n- C02: hook\n- C01: dup\n"
    assert unassigned.load_inventory(text) == ["C01", "C02"]


def test_parse_frontmatter_id(unassigned):
    assert unassigned.parse_frontmatter_id("---\nid: C07\n---\nx") == "C07"
    assert unassigned.parse_frontmatter_id("no fm") == ""


def test_find_unassigned_and_orphans(unassigned):
    expected = ["C01", "C02", "C03"]
    present = {"C01", "C03", "C99"}
    assert unassigned.find_unassigned(expected, present) == ["C02"]
    assert unassigned.find_orphans(expected, present) == ["C99"]


def test_missing_sections(unassigned):
    assert unassigned.missing_sections("## 目的\n## 成果物\n## 完了条件") == []
    miss = unassigned.missing_sections("## 目的 only")
    assert "## 成果物" in miss and "## 完了条件" in miss


def test_empty_body_sections_all_nonempty(unassigned):
    text = "## 目的\n中身あり\n## 成果物\n- a\n## 完了条件\nok\n"
    assert unassigned.empty_body_sections(text) == []


def test_empty_body_sections_detects_empty(unassigned):
    # 見出しは在るが直後が空 (次の見出し直行) のものを検出する
    text = "## 目的\n## 成果物\n- a\n## 完了条件\n   \n"
    miss = unassigned.empty_body_sections(text)
    assert "## 目的" in miss and "## 完了条件" in miss and "## 成果物" not in miss


def test_empty_body_sections_ignores_missing_heading(unassigned):
    # 見出しそのものが無い section は missing_sections の責務 (ここでは対象外)
    text = "## 目的\nx\n"
    assert unassigned.empty_body_sections(text) == []


def test_run_empty_body_section_fails(tmp_path, unassigned):
    # 見出しは在るが本文が空 → exit1 (本文の床)
    (tmp_path / "C01-sample.md").write_text(
        "---\nid: C01\ncomponent_kind: skill\n---\n# spec\n"
        "## 目的\n## 成果物\nx\n## 完了条件\nx\n",
        encoding="utf-8",
    )
    code, errs, warns = unassigned.run('["C01"]', tmp_path)
    assert code == 1
    assert any("本文が空" in e for e in errs)


def test_collect_spec_ids_skips_index(tmp_path, unassigned):
    write_spec(tmp_path, "C01")
    (tmp_path / "index.md").write_text("---\nid: IDX1\n---", encoding="utf-8")
    ids = unassigned.collect_spec_ids(tmp_path)
    assert "C01" in ids and "IDX1" not in ids


def test_run_clean(tmp_path, unassigned):
    write_spec(tmp_path, "C01")
    write_spec(tmp_path, "C02")
    code, errs, warns = unassigned.run('["C01", "C02"]', tmp_path)
    assert code == 0 and errs == []


def test_run_detects_unassigned(tmp_path, unassigned):
    write_spec(tmp_path, "C01")
    code, errs, warns = unassigned.run('["C01", "C02"]', tmp_path)
    assert code == 1
    assert any("未配置" in e for e in errs)


def test_run_orphan_warns_only(tmp_path, unassigned):
    write_spec(tmp_path, "C01")
    write_spec(tmp_path, "C09")
    code, errs, warns = unassigned.run('["C01"]', tmp_path)
    assert code == 0
    assert any("orphan" in w for w in warns)


def test_run_missing_section_fails(tmp_path, unassigned):
    write_spec(tmp_path, "C01", sections=False)
    code, errs, warns = unassigned.run('["C01"]', tmp_path)
    assert code == 1
    assert any("必須セクション欠落" in e for e in errs)


def test_run_empty_inventory(tmp_path, unassigned):
    code, errs, warns = unassigned.run("   ", tmp_path)
    assert code == 2


def test_main_ok(tmp_path, unassigned, capsys):
    write_spec(tmp_path, "C01")
    inv = tmp_path / "inv.json"
    inv.write_text('["C01"]', encoding="utf-8")
    assert unassigned.main(["--inventory", str(inv), "--specs-dir", str(tmp_path)]) == 0
    assert "OK" in capsys.readouterr().out


def test_main_violation(tmp_path, unassigned, capsys):
    write_spec(tmp_path, "C01")
    inv = tmp_path / "inv.json"
    inv.write_text('["C01", "C02"]', encoding="utf-8")
    assert unassigned.main(["--inventory", str(inv), "--specs-dir", str(tmp_path)]) == 1
    assert "未配置" in capsys.readouterr().err


def test_main_inventory_not_found(tmp_path, unassigned):
    assert unassigned.main(["--inventory", str(tmp_path / "nope.json"), "--specs-dir", str(tmp_path)]) == 2


def test_main_specs_dir_not_dir(tmp_path, unassigned):
    inv = tmp_path / "inv.json"
    inv.write_text('["C01"]', encoding="utf-8")
    assert unassigned.main(["--inventory", str(inv), "--specs-dir", str(tmp_path / "missing")]) == 2


def test_load_inventory_components_object_form(unassigned):
    text = '{"components": [{"id": "C01", "build_target": "plugins/x/skills/y/"}]}'
    comps = unassigned.load_inventory_components(text)
    assert len(comps) == 1 and comps[0]["id"] == "C01"


def test_load_inventory_components_list_form_skips(unassigned):
    # list / テキスト形式は build_target を持たないため空 (後方互換: 検査スキップ)
    assert unassigned.load_inventory_components('["C01", "C02"]') == []
    assert unassigned.load_inventory_components("- C01: skill\n- C02: hook") == []


def test_run_build_target_present_ok(tmp_path, unassigned):
    write_spec(tmp_path, "C01")
    inv = '{"components": [{"id": "C01", "build_target": "plugins/x/skills/run-x/"}]}'
    code, errs, warns = unassigned.run(inv, tmp_path)
    assert code == 0 and errs == []


def test_run_build_target_missing_fails(tmp_path, unassigned):
    write_spec(tmp_path, "C01")
    inv = '{"components": [{"id": "C01"}]}'  # build_target 欠落
    code, errs, warns = unassigned.run(inv, tmp_path)
    assert code == 1
    assert any("build_target" in e for e in errs)


def test_run_build_target_skipped_for_list_form(tmp_path, unassigned):
    # list 形式は build_target を要求しない (後方互換)。
    write_spec(tmp_path, "C01")
    code, errs, warns = unassigned.run('["C01"]', tmp_path)
    assert code == 0 and errs == []
