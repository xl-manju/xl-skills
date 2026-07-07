#!/usr/bin/env python3
# /// script
# name: validate-report-visual
# purpose: output_mode=report の report.html を静的解析し report 特有の視覚崩れ (section 構造欠落 / 1項目1ビジュアル逸脱 / 段落過密 / 未解決プレースホルダ / 印刷letterbox兆候) を fail-closed 検出する plugin-root glue。slide の verify-slides.js/validate-print.js に対応する report 版の決定論視覚ゲート。CLI と import (pytest) 両対応・Python 標準ライブラリのみ。
# inputs:
#   - CLI: <report.html> [--structure <report-structure.json>] [--strict] [--json]
# outputs:
#   - stdout: JSON (呼び出し側が食える検証結果 findings[])
#   - exit: 0=崩れ無し (PASS) / 1=崩れ検出 (fail-closed) / 2=usage・ファイル不在。
#           --strict では warn 兆候も 1 に昇格する。
# contexts: [glue]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""report.html の決定論視覚ゲート (fail-closed)。

C7 で vendor/ は byte 不可侵のため、report.html 用の視覚崩れ検出を plugin-root
scripts/ に Python 標準ライブラリのみ (html.parser + re) で新設する。slide が持つ
verify-slides.js (16:9比率) / validate-print.js (letterbox) に対応する report 版。

検査項目 (report-structure.json があれば併用・無ければ report.html 単体で):
  C1 section-structure  : h1 (report-title) 起点と report-section/h2 見出し階層の存在。
                          --structure 指定時は sections[].id/heading の欠落を fail 検出。
  C2 one-visual         : 1セクション1ビジュアル原則。過剰重複を閾値超過で warn/fail。
                          render フォールバック図 (描画失敗の兆候) も検出。
  C3 paragraph-density  : 極端に長い連続段落・段落数過密 (オーバーフロー兆候)。
  C4 placeholder        : 未解決プレースホルダ ({{...}}) 残存・空セクションを fail 検出。
  C5 print-letterbox    : @media print 内の cover/16:9 letterbox 兆候 (slide 用印刷指定の
                          report 混入)・@page landscape を warn 検出 (任意)。

exit code 規約:
  - 0: 崩れ無し (PASS)。--strict 時は warn も無い。
  - 1: 崩れ検出 (fail-closed)。--strict では warn 兆候も 1 に昇格。
  - 2: usage / report.html or --structure ファイル不在 (fail-closed)。

pytest からは analyze_report() / check_report() を import して使う。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# 検査閾値の SSOT。ここが唯一の値域定義 (テストは thresholds= で上書き可)。
DEFAULT_THRESHOLDS = {
    "max_visuals_per_section": 1,   # 1項目1ビジュアル。これを超えると warn。
    "visuals_fail_bound": 3,        # ビジュアルがこの数以上で fail (過剰重複)。
    "para_len_warn": 2000,          # 単一段落の文字数がこれ以上で warn。
    "para_len_fail": 3800,          # 単一段落の文字数がこれ以上で fail (schema max 4000 近傍)。
    "section_para_warn": 15,        # 1セクションの段落数がこれ以上で warn (過密)。
}

# 未解決プレースホルダ ({{...}} / {{}})。pre/code/svg 内は走査対象外にして
# mermaid の hexagon 記法 A{{...}} 等の誤検出を避ける。
_PLACEHOLDER_RE = re.compile(r"\{\{[^{}]*\}\}")

# 走査から外す (プレースホルダ誤検出源) タグ。style/script は data 自体を捨てる。
_SUPPRESS_TAGS = {"pre", "code", "svg"}


class _ReportParser(HTMLParser):
    """report.html を1パスで走査し、検査に必要な事実だけを収集する。

    収集物:
      - h1_texts[]            : report-title 起点の h1 テキスト。
      - sections[]            : {id, heading, p_count, max_p_len, text_len,
                                 figure_count, img_count, table_count, has_fallback}
      - style_text            : <style> 内容 (連結)。@media print 解析用。
      - placeholder_text      : pre/code/svg/script/style を除いた可視テキスト。
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.h1_texts: list[str] = []
        self.sections: list[dict] = []
        self._section_stack: list[dict] = []
        self._figure_depth = 0
        self._suppress_depth = 0
        self._in_style = False
        self._in_script = False
        self._style_buf: list[str] = []
        self._placeholder_buf: list[str] = []
        self._capture: str | None = None
        self._capture_buf: list[str] = []

    # -- 収集アクセサ --------------------------------------------------------
    @property
    def style_text(self) -> str:
        return "".join(self._style_buf)

    @property
    def placeholder_text(self) -> str:
        return "".join(self._placeholder_buf)

    def _cur_section(self):
        return self._section_stack[-1] if self._section_stack else None

    # -- start (通常/自己終了 両方) ------------------------------------------
    def handle_starttag(self, tag, attrs):
        self._on_start(tag, dict(attrs), self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._on_start(tag, dict(attrs), self_closing=True)

    def _on_start(self, tag, attrd, self_closing):
        cls = attrd.get("class", "") or ""

        if tag == "style":
            self._in_style = True
            return
        if tag == "script":
            self._in_script = True
            return

        if tag in _SUPPRESS_TAGS and not self_closing:
            self._suppress_depth += 1

        if tag == "section" and "report-section" in cls:
            self._section_stack.append(
                {
                    "id": attrd.get("id", ""),
                    "heading": "",
                    "p_count": 0,
                    "max_p_len": 0,
                    "text_len": 0,
                    "figure_count": 0,
                    "img_count": 0,
                    "table_count": 0,
                    "has_fallback": False,
                }
            )
            return

        sec = self._cur_section()

        if tag == "h1":
            self._start_capture("h1")
        elif tag == "h2" and sec is not None:
            self._start_capture("h2")
        elif tag == "p" and sec is not None:
            sec["p_count"] += 1
            self._start_capture("p")
        elif tag == "figure":
            if sec is not None and "report-visual" in cls:
                sec["figure_count"] += 1
                if "report-visual--fallback" in cls:
                    sec["has_fallback"] = True
            if not self_closing:
                self._figure_depth += 1
        elif tag == "img":
            # figure 直下の img は figure 側でビジュアル計上済み。単独 img のみ数える。
            if sec is not None and self._figure_depth == 0:
                sec["img_count"] += 1
        elif tag == "table":
            if sec is not None:
                sec["table_count"] += 1

    # -- end -----------------------------------------------------------------
    def handle_endtag(self, tag):
        if tag == "style":
            self._in_style = False
            return
        if tag == "script":
            self._in_script = False
            return
        if tag in _SUPPRESS_TAGS and self._suppress_depth > 0:
            self._suppress_depth -= 1
        if tag == "figure" and self._figure_depth > 0:
            self._figure_depth -= 1
        if self._capture and tag == self._capture:
            self._finish_capture()
        if tag == "section" and self._section_stack:
            self.sections.append(self._section_stack.pop())

    # -- data ----------------------------------------------------------------
    def handle_data(self, data):
        if self._in_style:
            self._style_buf.append(data)
            return
        if self._in_script:
            return
        if self._capture:
            self._capture_buf.append(data)
        # プレースホルダ走査対象は pre/code/svg を除く可視テキストのみ。
        if self._suppress_depth == 0:
            self._placeholder_buf.append(data)

    # -- capture helpers -----------------------------------------------------
    def _start_capture(self, tag):
        if self._capture:  # 入れ子開始は無視 (見出し/段落は入れ子にならない)。
            return
        self._capture = tag
        self._capture_buf = []

    def _finish_capture(self):
        text = "".join(self._capture_buf).strip()
        if self._capture == "h1":
            self.h1_texts.append(text)
        elif self._capture == "h2":
            sec = self._cur_section()
            if sec is not None and not sec["heading"]:
                sec["heading"] = text
        elif self._capture == "p":
            sec = self._cur_section()
            if sec is not None:
                length = len(text)
                sec["text_len"] += length
                if length > sec["max_p_len"]:
                    sec["max_p_len"] = length
        self._capture = None
        self._capture_buf = []


def analyze_report(html: str) -> dict:
    """report.html を静的解析して検査用の事実 dict を返す (副作用なし)。

    返り値: {"h1_texts": [...], "sections": [ {..} ], "style_text": str,
             "placeholders": [str], "print_css": str}
    """
    parser = _ReportParser()
    parser.feed(html)
    parser.close()
    # section を閉じ忘れた malformed HTML でも残りを回収する。
    while parser._section_stack:
        parser.sections.append(parser._section_stack.pop())

    placeholders = sorted(set(_PLACEHOLDER_RE.findall(parser.placeholder_text)))
    return {
        "h1_texts": parser.h1_texts,
        "sections": parser.sections,
        "style_text": parser.style_text,
        "placeholders": placeholders,
        "print_css": _extract_print_css(parser.style_text),
    }


def _extract_print_css(style_text: str) -> str:
    """<style> 内の @media print { ... } ブロックを (簡易・決定論) 抽出して連結する。"""
    blocks: list[str] = []
    idx = 0
    needle = "@media print"
    lowered = style_text.lower()
    while True:
        pos = lowered.find(needle, idx)
        if pos == -1:
            break
        brace = style_text.find("{", pos)
        if brace == -1:
            break
        depth = 0
        end = brace
        for i in range(brace, len(style_text)):
            ch = style_text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        blocks.append(style_text[brace + 1 : end])
        idx = end + 1
    return "\n".join(blocks)


def _visual_count(sec: dict) -> int:
    """1セクションのビジュアル要素数 (figure.report-visual + 単独 img + table)。"""
    return sec["figure_count"] + sec["img_count"] + sec["table_count"]


def check_report(html, structure=None, strict=False, thresholds=None) -> dict:
    """report.html の視覚崩れを検査し findings[] を返す (fail-closed 判定は passed で表現)。

    返り値:
      {"passed": bool, "strict": bool, "findings": [ {check, severity, section, message} ],
       "summary": {"h1": int, "sections": int, "fail": int, "warn": int}}
      - severity="fail": 崩れ (常に passed=False)。
      - severity="warn": 兆候 (strict のときだけ passed=False へ寄与)。
    """
    th = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        th.update(thresholds)

    facts = analyze_report(html)
    sections = facts["sections"]
    findings: list[dict] = []

    def add(check, severity, message, section=None):
        findings.append(
            {"check": check, "severity": severity, "section": section, "message": message}
        )

    # -- C1: section 構造 ----------------------------------------------------
    if not facts["h1_texts"]:
        add("section-structure", "fail", "h1 (report-title) が無い: 見出し階層の起点欠落")
    if not sections:
        add("section-structure", "fail", "report-section が1つも無い: section 構造欠落")
    for sec in sections:
        if not sec["heading"]:
            add(
                "section-structure",
                "fail",
                f"section '{sec['id'] or '?'}' に h2 見出しが無い",
                sec["id"],
            )

    if structure is not None:
        struct_sections = structure.get("sections", []) if isinstance(structure, dict) else []
        html_ids = {s["id"] for s in sections if s["id"]}
        html_by_id = {s["id"]: s for s in sections if s["id"]}
        for ss in struct_sections:
            sid = ss.get("id") if isinstance(ss, dict) else None
            if sid and sid not in html_ids:
                add(
                    "section-structure",
                    "fail",
                    f"structure の section '{sid}' が report.html に無い (欠落)",
                    sid,
                )
            elif sid:
                want = (ss.get("heading") or "").strip()
                got = (html_by_id[sid]["heading"] or "").strip()
                if want and got and want != got:
                    add(
                        "section-structure",
                        "warn",
                        f"section '{sid}' の見出し不一致: structure='{want}' / html='{got}'",
                        sid,
                    )
        if struct_sections and len(sections) > len(struct_sections):
            add(
                "section-structure",
                "warn",
                f"report.html の section 数 ({len(sections)}) が structure ({len(struct_sections)}) を超過",
            )

    # -- C2: 1項目1ビジュアル / render フォールバック -------------------------
    max_v = th["max_visuals_per_section"]
    fail_bound = th["visuals_fail_bound"]
    for sec in sections:
        vc = _visual_count(sec)
        if vc >= fail_bound:
            add(
                "one-visual",
                "fail",
                f"section '{sec['id'] or '?'}': ビジュアル {vc}個 (過剰重複・1項目1ビジュアル違反)",
                sec["id"],
            )
        elif vc > max_v:
            add(
                "one-visual",
                "warn",
                f"section '{sec['id'] or '?'}': ビジュアル {vc}個 (1項目1ビジュアル逸脱)",
                sec["id"],
            )
        if sec["has_fallback"]:
            add(
                "one-visual",
                "warn",
                f"section '{sec['id'] or '?'}': ビジュアル描画フォールバック (render 失敗の兆候)",
                sec["id"],
            )

    # -- C3: 段落過密 / オーバーフロー兆候 -----------------------------------
    for sec in sections:
        if sec["max_p_len"] >= th["para_len_fail"]:
            add(
                "paragraph-density",
                "fail",
                f"section '{sec['id'] or '?'}': 段落が極端に長い ({sec['max_p_len']}字・オーバーフロー兆候)",
                sec["id"],
            )
        elif sec["max_p_len"] >= th["para_len_warn"]:
            add(
                "paragraph-density",
                "warn",
                f"section '{sec['id'] or '?'}': 段落が長い ({sec['max_p_len']}字)",
                sec["id"],
            )
        if sec["p_count"] >= th["section_para_warn"]:
            add(
                "paragraph-density",
                "warn",
                f"section '{sec['id'] or '?'}': 段落数過密 ({sec['p_count']}段落)",
                sec["id"],
            )

    # -- C4: 未解決プレースホルダ / 空セクション -----------------------------
    for ph in facts["placeholders"]:
        add("placeholder", "fail", f"未解決プレースホルダ残存: {ph}")
    for sec in sections:
        if sec["text_len"] == 0 and _visual_count(sec) == 0:
            add(
                "placeholder",
                "fail",
                f"section '{sec['id'] or '?'}': 本文もビジュアルも無い (空セクション)",
                sec["id"],
            )

    # -- C5: 印刷 letterbox / cover 兆候 (任意・warn) --------------------------
    print_css = facts["print_css"].lower()
    if re.search(r"object-fit\s*:\s*cover", print_css):
        add("print-letterbox", "warn", "@media print に object-fit:cover (印刷端切れ兆候)")
    if re.search(r"background-size\s*:\s*cover", print_css):
        add("print-letterbox", "warn", "@media print に background-size:cover (印刷端切れ兆候)")
    if re.search(r"aspect-ratio\s*:\s*16\s*/\s*9", print_css):
        add("print-letterbox", "warn", "@media print に 16:9 letterbox 指定 (slide 用印刷指定の report 混入)")
    if re.search(r"@page[^{]*\{[^}]*landscape", facts["style_text"].lower()):
        add("print-letterbox", "warn", "@page が landscape: report は A4 portrait 想定")

    n_fail = sum(1 for f in findings if f["severity"] == "fail")
    n_warn = sum(1 for f in findings if f["severity"] == "warn")
    passed = n_fail == 0 and (not strict or n_warn == 0)

    return {
        "passed": passed,
        "strict": strict,
        "findings": findings,
        "summary": {
            "h1": len(facts["h1_texts"]),
            "sections": len(sections),
            "fail": n_fail,
            "warn": n_warn,
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="validate-report-visual",
        description="report.html の決定論視覚ゲート (fail-closed): section構造/1項目1ビジュアル/段落過密/プレースホルダ/印刷letterbox",
    )
    p.add_argument("report", help="検査対象 report.html")
    p.add_argument(
        "--structure",
        dest="structure",
        default=None,
        help="report-structure.json (指定時は sections[].id/heading の欠落も照合)",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="warn 兆候も崩れ (exit 1) に昇格させる",
    )
    p.add_argument("--json", action="store_true", help="(既定で JSON 出力・互換用フラグ)")
    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)

    report_path = Path(args.report)
    if not report_path.is_file():
        sys.stderr.write(f"error: report.html not found: {report_path}\n")
        return 2

    structure = None
    if args.structure:
        struct_path = Path(args.structure)
        if not struct_path.is_file():
            sys.stderr.write(f"error: --structure not found: {struct_path}\n")
            return 2
        try:
            structure = json.loads(struct_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            sys.stderr.write(f"error: --structure not readable JSON: {e}\n")
            return 2

    html = report_path.read_text(encoding="utf-8", errors="replace")
    result = check_report(html, structure=structure, strict=args.strict)

    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
