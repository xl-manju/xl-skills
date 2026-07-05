"""validate-report-visual.py の網羅テスト。

関数 (analyze_report / check_report) の import 経路と、CLI の exit code 規約
(0=PASS / 1=崩れ検出 / 2=usage・ファイル不在 / --strict 昇格) の subprocess 経路の
両方を検証する。fixture HTML は tests 内にインライン生成する (tmp_path・node 非依存)。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

# scripts/validate-report-visual.py はハイフン入りファイル名のため importlib で読み込む。
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "validate-report-visual.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_report_visual_mod", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()


# --- fixture 生成 (render-report.js が出す class 規約を最小再現) -------------

def _section(sec_id, heading, paragraphs=None, visuals_html="", extra=""):
    paras = "\n".join(f"  <p>{p}</p>" for p in (paragraphs or ["本文段落です。"]))
    return (
        f'<section class="report-section" id="{sec_id}" data-role="body" '
        f'style="--section-accent: var(--accent-blue-vivid);">\n'
        f"  <h2>{heading}</h2>\n{paras}\n{extra}\n  {visuals_html}\n</section>"
    )


_SVG_FIGURE = (
    '<figure class="report-visual report-visual--svg" role="img">\n'
    '  <svg viewBox="0 0 960 320"><rect x="0" y="0" width="10" height="10"/>'
    '<text>ノード</text></svg>\n  <figcaption>図</figcaption>\n</figure>'
)
_FALLBACK_FIGURE = (
    '<figure class="report-visual report-visual--fallback">\n'
    '  <svg viewBox="0 0 960 200"><text>未対応の svg variant</text></svg>\n</figure>'
)


def _doc(sections_html, style="", head_extra="", h1="レポート表題"):
    default_style = (
        "<style>\n.report{max-width:190mm;}\n"
        "@page { size: A4 portrait; margin: 18mm; }\n"
        "@media print { .report-section { break-inside: avoid-page; } }\n"
        "</style>"
    )
    return (
        "<!DOCTYPE html>\n<html lang=\"ja\">\n<head>\n<meta charset=\"UTF-8\">\n"
        '<meta name="generator" content="slide-report-generator/render-report">\n'
        f"{style or default_style}\n{head_extra}\n</head>\n"
        '<body style="--report-accent: var(--accent-blue-vivid);">\n'
        '<main class="report">\n'
        f'  <header class="report-header">\n    <h1 class="report-title">{h1}</h1>\n'
        '    <p class="report-keymessage">要点</p>\n  </header>\n'
        f"{sections_html}\n"
        '  <footer class="report-footer">report mode</footer>\n'
        "</main>\n</body>\n</html>\n"
    )


def _valid_html():
    secs = "\n".join(
        [
            _section("section-intro", "はじめに", ["**導入**の段落。", "続きの段落。"]),
            _section("section-flow", "流れ", ["本文。"], visuals_html=_SVG_FIGURE),
        ]
    )
    return _doc(secs)


VALID_STRUCTURE = {
    "meta": {"title": "T", "reportType": "internal-analysis", "audience": "a", "keyMessage": "k"},
    "theme": {"name": "kanagawa-lotus", "accentColors": ["blue"]},
    "sections": [
        {"id": "section-intro", "heading": "はじめに", "paragraphs": ["x"]},
        {"id": "section-flow", "heading": "流れ", "paragraphs": ["y"]},
    ],
}


# --- analyze_report ---------------------------------------------------------

def test_analyze_extracts_h1_and_sections():
    facts = mod.analyze_report(_valid_html())
    assert facts["h1_texts"] == ["レポート表題"]
    assert [s["id"] for s in facts["sections"]] == ["section-intro", "section-flow"]
    assert facts["sections"][1]["figure_count"] == 1
    assert facts["sections"][0]["heading"] == "はじめに"


def test_analyze_counts_paragraphs_and_text_len():
    facts = mod.analyze_report(_valid_html())
    intro = facts["sections"][0]
    assert intro["p_count"] == 2
    assert intro["text_len"] > 0
    assert facts["placeholders"] == []


def test_analyze_extracts_print_css():
    facts = mod.analyze_report(_valid_html())
    assert "break-inside" in facts["print_css"]


# --- 正常系 (PASS) ----------------------------------------------------------

def test_valid_report_passes():
    r = mod.check_report(_valid_html())
    assert r["passed"] is True, r["findings"]
    assert r["summary"]["fail"] == 0


def test_valid_report_passes_with_structure():
    r = mod.check_report(_valid_html(), structure=VALID_STRUCTURE)
    assert r["passed"] is True, r["findings"]


def test_valid_report_passes_strict():
    r = mod.check_report(_valid_html(), structure=VALID_STRUCTURE, strict=True)
    assert r["passed"] is True, r["findings"]


# --- C1: section 構造欠落 (fail-closed) -------------------------------------

def test_missing_h1_is_fail():
    html = _valid_html().replace('<h1 class="report-title">レポート表題</h1>', "")
    r = mod.check_report(html)
    assert r["passed"] is False
    assert any(f["check"] == "section-structure" and "h1" in f["message"] for f in r["findings"])


def test_no_sections_is_fail():
    html = _doc("")  # section 皆無
    r = mod.check_report(html)
    assert r["passed"] is False
    assert any("section 構造欠落" in f["message"] for f in r["findings"])


def test_section_without_h2_is_fail():
    sec = (
        '<section class="report-section" id="section-x">\n  <p>本文</p>\n  \n</section>'
    )
    r = mod.check_report(_doc(sec))
    assert r["passed"] is False
    assert any("h2 見出しが無い" in f["message"] for f in r["findings"])


def test_structure_section_missing_from_html_is_fail():
    # html には section-intro しか無いのに structure は2節を要求 → 欠落 fail。
    secs = _section("section-intro", "はじめに")
    r = mod.check_report(_doc(secs), structure=VALID_STRUCTURE)
    assert r["passed"] is False
    assert any("section-flow" in f["message"] and "欠落" in f["message"] for f in r["findings"])


def test_structure_heading_mismatch_is_warn_only():
    secs = "\n".join(
        [
            _section("section-intro", "別の見出し"),
            _section("section-flow", "流れ"),
        ]
    )
    r = mod.check_report(_doc(secs), structure=VALID_STRUCTURE)
    # 見出し不一致は warn のみ → 非 strict では passed。
    assert r["passed"] is True
    assert any(f["severity"] == "warn" and "見出し不一致" in f["message"] for f in r["findings"])
    # strict では昇格して fail。
    r2 = mod.check_report(_doc(secs), structure=VALID_STRUCTURE, strict=True)
    assert r2["passed"] is False


# --- C2: 1項目多ビジュアル (fail-closed) ------------------------------------

def test_excess_visuals_is_fail():
    # 3ビジュアル (fail_bound=3) → 過剰重複 fail。
    triple = _SVG_FIGURE + "\n  " + _SVG_FIGURE + "\n  " + _SVG_FIGURE
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", visuals_html=triple),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert r["passed"] is False
    assert any(f["check"] == "one-visual" and "過剰重複" in f["message"] for f in r["findings"])


def test_two_visuals_is_warn_only():
    double = _SVG_FIGURE + "\n  " + _SVG_FIGURE
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", visuals_html=double),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert r["passed"] is True  # 逸脱は warn 止まり
    assert any(f["severity"] == "warn" and "逸脱" in f["message"] for f in r["findings"])
    assert mod.check_report(_doc(secs), strict=True)["passed"] is False


def test_render_fallback_is_warn():
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", visuals_html=_FALLBACK_FIGURE),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert r["passed"] is True
    assert any("フォールバック" in f["message"] for f in r["findings"])


def test_standalone_img_and_table_count_as_visuals():
    extra = '<img src="a.png" alt="x">\n  <table><tr><td>1</td></tr></table>\n  ' + _SVG_FIGURE
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", visuals_html=extra),
        ]
    )
    r = mod.check_report(_doc(secs))
    # img + table + figure = 3 → fail。
    assert r["passed"] is False


# --- C3: 段落過密 / オーバーフロー ------------------------------------------

def test_extremely_long_paragraph_is_fail():
    long_p = "あ" * 4000
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", [long_p]),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert r["passed"] is False
    assert any(f["check"] == "paragraph-density" and "極端に長い" in f["message"] for f in r["findings"])


def test_moderately_long_paragraph_is_warn():
    mid_p = "い" * 2500
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", [mid_p]),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert r["passed"] is True
    assert any(f["severity"] == "warn" and "段落が長い" in f["message"] for f in r["findings"])


def test_too_many_paragraphs_is_warn():
    many = ["段落" for _ in range(16)]
    secs = "\n".join(
        [
            _section("section-intro", "はじめに"),
            _section("section-flow", "流れ", many),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert any("段落数過密" in f["message"] for f in r["findings"])


def test_threshold_override():
    mid_p = "う" * 500
    secs = "\n".join(
        [_section("section-intro", "はじめに"), _section("section-flow", "流れ", [mid_p])]
    )
    r = mod.check_report(_doc(secs), thresholds={"para_len_fail": 400})
    assert r["passed"] is False


# --- C4: プレースホルダ残存 / 空セクション (fail-closed) --------------------

def test_unresolved_placeholder_is_fail():
    secs = "\n".join(
        [
            _section("section-intro", "はじめに", ["未解決 {{ title }} が残っている。"]),
            _section("section-flow", "流れ"),
        ]
    )
    r = mod.check_report(_doc(secs))
    assert r["passed"] is False
    assert any(f["check"] == "placeholder" and "{{ title }}" in f["message"] for f in r["findings"])


def test_empty_placeholder_braces_detected():
    secs = _section("section-intro", "はじめに", ["空 {{}} プレースホルダ。"])
    r = mod.check_report(_doc(secs))
    assert any(f["check"] == "placeholder" for f in r["findings"])


def test_placeholder_inside_code_is_not_flagged():
    # インライン code 内の {{}} は誤検出しない (テンプレ例示の可能性)。
    secs = _section("section-intro", "はじめに", ["コード例です。"],
                    extra='  <p><code>{{ jinja }}</code></p>')
    r = mod.check_report(_doc(secs))
    assert not any(f["check"] == "placeholder" for f in r["findings"])


def test_empty_section_is_fail():
    sec = '<section class="report-section" id="section-empty">\n  <h2>空節</h2>\n  \n</section>'
    r = mod.check_report(_doc(sec))
    assert r["passed"] is False
    assert any("空セクション" in f["message"] for f in r["findings"])


# --- C5: 印刷 letterbox / cover 兆候 (warn) ----------------------------------

def test_print_cover_is_warn():
    style = (
        "<style>\n@media print { .report-visual img { object-fit: cover; } }\n</style>"
    )
    secs = "\n".join([_section("section-intro", "はじめに"), _section("section-flow", "流れ")])
    r = mod.check_report(_doc(secs, style=style))
    assert r["passed"] is True
    assert any(f["check"] == "print-letterbox" and "cover" in f["message"] for f in r["findings"])
    assert mod.check_report(_doc(secs, style=style), strict=True)["passed"] is False


def test_print_letterbox_aspect_ratio_is_warn():
    style = "<style>\n@media print { .report { aspect-ratio: 16 / 9; } }\n</style>"
    secs = _section("section-intro", "はじめに")
    r = mod.check_report(_doc(secs, style=style))
    assert any("letterbox" in f["message"] for f in r["findings"])


def test_page_landscape_is_warn():
    style = "<style>\n@page { size: A4 landscape; }\n</style>"
    secs = _section("section-intro", "はじめに")
    r = mod.check_report(_doc(secs, style=style))
    assert any("landscape" in f["message"] for f in r["findings"])


# --- CLI exit code 規約 (subprocess) ----------------------------------------

def _run_cli(*args):
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_cli_valid_exit_0(tmp_path):
    html = _write(tmp_path, "report.html", _valid_html())
    proc = _run_cli(str(html))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["passed"] is True


def test_cli_with_structure_exit_0(tmp_path):
    html = _write(tmp_path, "report.html", _valid_html())
    struct = _write(tmp_path, "s.json", json.dumps(VALID_STRUCTURE, ensure_ascii=False))
    proc = _run_cli(str(html), "--structure", str(struct))
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["passed"] is True


def test_cli_defect_exit_1(tmp_path):
    bad = _valid_html().replace("<h2>はじめに</h2>", "<h2>{{TITLE}}</h2>")
    html = _write(tmp_path, "report.html", bad)
    proc = _run_cli(str(html))
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["passed"] is False


def test_cli_strict_promotes_warn_to_exit_1(tmp_path):
    double = _SVG_FIGURE + "\n  " + _SVG_FIGURE
    secs = "\n".join([_section("section-intro", "はじめに"),
                      _section("section-flow", "流れ", visuals_html=double)])
    html = _write(tmp_path, "report.html", _doc(secs))
    assert _run_cli(str(html)).returncode == 0
    assert _run_cli(str(html), "--strict").returncode == 1


def test_cli_missing_report_exit_2(tmp_path):
    proc = _run_cli(str(tmp_path / "nope.html"))
    assert proc.returncode == 2
    assert "not found" in proc.stderr


def test_cli_missing_structure_exit_2(tmp_path):
    html = _write(tmp_path, "report.html", _valid_html())
    proc = _run_cli(str(html), "--structure", str(tmp_path / "nope.json"))
    assert proc.returncode == 2


def test_cli_bad_structure_json_exit_2(tmp_path):
    html = _write(tmp_path, "report.html", _valid_html())
    struct = _write(tmp_path, "s.json", "{ not json ")
    proc = _run_cli(str(html), "--structure", str(struct))
    assert proc.returncode == 2


def test_cli_no_args_exit_2():
    # 必須 positional 欠落は argparse が usage error (exit 2)。
    proc = _run_cli()
    assert proc.returncode == 2


def test_cli_help_exit_0():
    proc = _run_cli("--help")
    assert proc.returncode == 0
    assert "report.html" in proc.stdout


# --- main() in-process (exit code + JSON stdout の直接検証) ------------------

def test_main_valid_returns_0(tmp_path, capsys):
    html = _write(tmp_path, "report.html", _valid_html())
    rc = mod.main([str(html)])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["passed"] is True


def test_main_with_structure_returns_0(tmp_path, capsys):
    html = _write(tmp_path, "report.html", _valid_html())
    struct = _write(tmp_path, "s.json", json.dumps(VALID_STRUCTURE, ensure_ascii=False))
    rc = mod.main([str(html), "--structure", str(struct)])
    assert rc == 0
    capsys.readouterr()


def test_main_defect_returns_1(tmp_path, capsys):
    bad = _valid_html().replace("<h2>はじめに</h2>", "<h2>{{X}}</h2>")
    html = _write(tmp_path, "report.html", bad)
    rc = mod.main([str(html)])
    assert rc == 1
    assert json.loads(capsys.readouterr().out)["passed"] is False


def test_main_strict_returns_1(tmp_path, capsys):
    double = _SVG_FIGURE + "\n  " + _SVG_FIGURE
    secs = "\n".join([_section("section-intro", "はじめに"),
                      _section("section-flow", "流れ", visuals_html=double)])
    html = _write(tmp_path, "report.html", _doc(secs))
    assert mod.main([str(html)]) == 0
    capsys.readouterr()
    assert mod.main([str(html), "--strict"]) == 1
    capsys.readouterr()


def test_main_missing_report_returns_2(tmp_path, capsys):
    rc = mod.main([str(tmp_path / "nope.html")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_main_missing_structure_returns_2(tmp_path, capsys):
    html = _write(tmp_path, "report.html", _valid_html())
    rc = mod.main([str(html), "--structure", str(tmp_path / "nope.json")])
    assert rc == 2
    capsys.readouterr()


def test_main_bad_structure_json_returns_2(tmp_path, capsys):
    html = _write(tmp_path, "report.html", _valid_html())
    struct = _write(tmp_path, "s.json", "{ not json ")
    rc = mod.main([str(html), "--structure", str(struct)])
    assert rc == 2
    assert "JSON" in capsys.readouterr().err
