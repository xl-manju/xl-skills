"""verify-index-topsort.py の機能テスト。"""
from __future__ import annotations

import pytest
from conftest import write_spec


def _index(directory, ids, *, frontmatter=False):
    head = "---\nid: IDX0\ntitle: plan\n---\n" if frontmatter else ""
    text = head + "# index\n## 仕様書一覧 (top-sort)\n" + "".join(
        f"{n+1}. {i}: 仕様書\n" for n, i in enumerate(ids)
    )
    p = directory / "index.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_body_after_frontmatter_strips(topsort):
    assert topsort.body_after_frontmatter("---\nid: IDX0\n---\nbody C01").strip() == "body C01"
    assert topsort.body_after_frontmatter("no fm C01") == "no fm C01"


def test_index_frontmatter_id_not_leaked(tmp_path, topsort):
    # plugin_meta 等を持つ index frontmatter の id(IDX0) を phantom 参照として拾わない
    write_spec(tmp_path, "C01")
    _index(tmp_path, ["C01"], frontmatter=True)
    code, errs = topsort.run(tmp_path, "index.md", None)
    assert code == 0 and errs == [], errs


def test_parse_frontmatter_scalar_inline_block(topsort):
    text = "---\nid: C01\ndepends_on: [C02, C03]\ntags:\n  - x\n  - y\n---\nbody"
    fm = topsort.parse_frontmatter(text)
    assert fm["id"] == "C01"
    assert fm["depends_on"] == ["C02", "C03"]
    assert fm["tags"] == ["x", "y"]


def test_parse_frontmatter_no_frontmatter(topsort):
    assert topsort.parse_frontmatter("no fm here") == {}


def test_extract_ordered_ids_keeps_order_and_dups(topsort):
    text = "1. C01\n2. C02\n3. C01\nnoise line\n"
    assert topsort.extract_ordered_ids(text) == ["C01", "C02", "C01"]


def test_detect_cycle_finds_loop(topsort):
    cyc = topsort.detect_cycle({"A1", "B1"}, [("A1", "B1"), ("B1", "A1")])
    assert cyc and cyc[0] == cyc[-1]


def test_detect_cycle_none_for_dag(topsort):
    assert topsort.detect_cycle({"A1", "B1"}, [("A1", "B1")]) is None


def test_verify_clean_topsort(topsort):
    specs = {"C01": {}, "C02": {"depends_on": ["C01"]}}
    assert topsort.verify(["C01", "C02"], specs) == []


def test_verify_detects_order_violation(topsort):
    specs = {"C01": {}, "C02": {"depends_on": ["C01"]}}
    errs = topsort.verify(["C02", "C01"], specs)
    assert any("top-sort 違反" in e for e in errs)


def test_verify_detects_missing_and_phantom_and_dup(topsort):
    specs = {"C01": {}, "C02": {}}
    errs = topsort.verify(["C01", "C01", "C99"], specs)
    assert any("id 重複" in e for e in errs)
    assert any("未列挙" in e for e in errs)  # C02 missing
    assert any("存在しない" in e for e in errs)  # C99 phantom


def test_verify_dependency_without_spec(topsort):
    specs = {"C01": {"depends_on": ["C02"]}}
    errs = topsort.verify(["C01"], specs)
    assert any("対応する仕様書が無い" in e for e in errs)


def test_verify_detects_cycle(topsort):
    specs = {"C01": {"depends_on": ["C02"]}, "C02": {"depends_on": ["C01"]}}
    errs = topsort.verify(["C01", "C02"], specs)
    assert any("循環" in e for e in errs)


def test_depends_on_string_form(topsort):
    assert topsort._depends_on({"depends_on": "[C01, C02]"}) == ["C01", "C02"]


def test_run_and_main_ok(tmp_path, topsort, capsys):
    write_spec(tmp_path, "C01")
    write_spec(tmp_path, "C02", depends_on=["C01"])
    _index(tmp_path, ["C01", "C02"])
    assert topsort.main([str(tmp_path)]) == 0
    assert "OK" in capsys.readouterr().out


def test_run_uses_specs_subdir(tmp_path, topsort):
    specs = tmp_path / "specs"
    specs.mkdir()
    write_spec(specs, "C01")
    _index(tmp_path, ["C01"])
    code, errs = topsort.run(tmp_path, "index.md", None)
    assert code == 0 and errs == []


def test_main_violation_returns_1(tmp_path, topsort, capsys):
    write_spec(tmp_path, "C01")
    write_spec(tmp_path, "C02", depends_on=["C01"])
    _index(tmp_path, ["C02", "C01"])  # wrong order
    assert topsort.main([str(tmp_path)]) == 1
    assert "top-sort" in capsys.readouterr().err


def test_main_missing_index_returns_2(tmp_path, topsort):
    write_spec(tmp_path, "C01")
    assert topsort.main([str(tmp_path)]) == 2


def test_main_no_specs_returns_2(tmp_path, topsort):
    _index(tmp_path, [])
    # index references nothing and no specs present
    assert topsort.main([str(tmp_path)]) == 2


def test_main_not_a_directory(tmp_path, topsort):
    f = tmp_path / "x.txt"
    f.write_text("x", encoding="utf-8")
    assert topsort.main([str(f)]) == 2


def test_main_explicit_specs_dir(tmp_path, topsort):
    specs = tmp_path / "components"
    specs.mkdir()
    write_spec(specs, "C01")
    _index(tmp_path, ["C01"])
    assert topsort.main([str(tmp_path), "--specs-dir", str(specs)]) == 0
