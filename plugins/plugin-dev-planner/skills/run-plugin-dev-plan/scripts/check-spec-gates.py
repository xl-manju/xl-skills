#!/usr/bin/env python3
# /// script
# name: check-spec-gates
# purpose: 各 buildable タスク仕様書の quality_gates ブロック(p0_lint網羅/build_trace/elegant_review C1-C4/content_review verdict/evaluator>=80,high0)と harness_coverage(min>=80/kind_pass)を機械検証し skill-creator 規律を出力強制する決定論ゲート。
# inputs:
#   - argv: <spec.md ...> | --specs-dir DIR
# outputs:
#   - stdout: OK サマリ
#   - stderr: quality_gates / harness violation
#   - exit: 0=OK / 1=violation / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""quality_gates / harness_coverage を機械検証して skill-creator 規律を出力強制する。

参照(口頭指示)では検証されない A1(4条件)/A5(evaluator)/A8(content-review)/C1-C2(harness)/
F1(P0 lint)/F2(build-trace) を、各 buildable spec の frontmatter キーへ焼かせ本 script が
fail-closed で検査する。component_kind 別に p0_lint の必須集合を変える (specfm.P0_LINT_BY_KIND)。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402

ELEGANT_CONDITIONS = ["C1", "C2", "C3", "C4"]


def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def check_gates(text: str) -> list[str]:
    """1 spec の quality_gates + harness_coverage を検査し errors を返す。"""
    if specfm.split_frontmatter(text) is None:
        return ["frontmatter (--- ブロック) が無い"]
    fm = specfm.parse_frontmatter(text)
    ck = str(fm.get("component_kind", "")).strip()
    if ck not in specfm.COMPONENT_KINDS:
        return [f"component_kind={ck!r} が未宣言/enum 外 (gates 検証不能)"]
    errs: list[str] = []

    qg = fm.get("quality_gates")
    if not isinstance(qg, dict):
        return [f"[{ck}] quality_gates ブロックが無い (skill-creator 規律の出力強制に必須)"]

    # p0_lint: component_kind 別の必須 lint 集合を網羅 (superset)
    required = set(specfm.P0_LINT_BY_KIND.get(ck, ()))
    declared = set(_as_list(qg.get("p0_lint")))
    missing_lints = sorted(required - declared)
    if missing_lints:
        errs.append(f"[{ck}] quality_gates.p0_lint が必須 lint を欠く: {missing_lints}")

    # build_trace: required
    if str(qg.get("build_trace", "")).strip() != "required":
        errs.append(f"[{ck}] quality_gates.build_trace は 'required' であること")

    # elegant_review: conditions==C1-C4 / all_pass:true
    er = qg.get("elegant_review")
    if not isinstance(er, dict):
        errs.append(f"[{ck}] quality_gates.elegant_review ブロックが無い")
    else:
        if sorted(str(c) for c in _as_list(er.get("conditions"))) != ELEGANT_CONDITIONS:
            errs.append(f"[{ck}] elegant_review.conditions は {ELEGANT_CONDITIONS} 全部であること")
        if er.get("all_pass") is not True:
            errs.append(f"[{ck}] elegant_review.all_pass は true であること")

    # content_review: verdict==PASS / sha_match:true
    cr = qg.get("content_review")
    if not isinstance(cr, dict):
        errs.append(f"[{ck}] quality_gates.content_review ブロックが無い")
    else:
        if str(cr.get("verdict", "")).strip() != "PASS":
            errs.append(f"[{ck}] content_review.verdict は PASS であること")
        if cr.get("sha_match") is not True:
            errs.append(f"[{ck}] content_review.sha_match は true であること")

    # evaluator: threshold>=80 / high_max==0
    ev = qg.get("evaluator")
    if not isinstance(ev, dict):
        errs.append(f"[{ck}] quality_gates.evaluator ブロックが無い")
    else:
        th = specfm.as_int(ev.get("threshold"))
        if th is None or th < 80:
            errs.append(f"[{ck}] evaluator.threshold は >=80 (現値 {ev.get('threshold')!r})")
        hm = specfm.as_int(ev.get("high_max"))
        if hm is None or hm != 0:
            errs.append(f"[{ck}] evaluator.high_max は 0 (現値 {ev.get('high_max')!r})")

    # harness_coverage: min>=80 / kind_pass 非空
    hc = fm.get("harness_coverage")
    if not isinstance(hc, dict):
        errs.append(f"[{ck}] harness_coverage ブロックが無い")
    else:
        mn = specfm.as_int(hc.get("min"))
        if mn is None or mn < specfm.HARNESS_MIN_REQUIRED:
            errs.append(f"[{ck}] harness_coverage.min は >={specfm.HARNESS_MIN_REQUIRED} (現値 {hc.get('min')!r})")
        kp = str(hc.get("kind_pass", "")).strip()
        if not kp:
            errs.append(f"[{ck}] harness_coverage.kind_pass が空 (kind 別パスを明記)")
        elif not specfm.kind_pass_ok(kp, ck, str(fm.get("kind", "")).strip()):
            tokens = sorted(specfm.expected_kind_pass_tokens(ck, str(fm.get("kind", "")).strip()))
            errs.append(f"[{ck}] harness_coverage.kind_pass='{kp}' が kind と無関係 (期待語のいずれかを含むこと: {tokens})")

    # 構造キーの値検証: script は tests_min>=80 を強制 (存在だけでは不可)
    if ck == "script":
        tm = specfm.as_int(fm.get("tests_min"))
        if tm is None or tm < specfm.HARNESS_MIN_REQUIRED:
            errs.append(f"[script] tests_min は >={specfm.HARNESS_MIN_REQUIRED} (現値 {fm.get('tests_min')!r})")
    return errs


def check_plugin_meta(pm: dict) -> list[str]:
    """index.plugin_meta の plugin 階層規律を値域検証する (F3/F4/F6 等)。"""
    errs: list[str] = []
    manifest = pm.get("manifest")
    if not isinstance(manifest, dict):
        errs.append("plugin_meta.manifest が dict でない (.claude-plugin/plugin.json 契約必須)")
    else:
        if manifest.get("required") is not True:
            errs.append("manifest.required は true であること")
        if str(manifest.get("path", "")).strip() != ".claude-plugin/plugin.json":
            errs.append("manifest.path は .claude-plugin/plugin.json であること")
        if manifest.get("name_matches_folder") is not True:
            errs.append("manifest.name_matches_folder は true であること")
        if manifest.get("no_todo_placeholders") is not True:
            errs.append("manifest.no_todo_placeholders は true であること")
        if manifest.get("validate_plugin") is not True:
            errs.append("manifest.validate_plugin は true であること")

    marketplace = pm.get("marketplace")
    if not isinstance(marketplace, dict):
        errs.append("plugin_meta.marketplace が dict でない (marketplace policy 契約必須)")
    else:
        default_personal = marketplace.get("default_personal")
        if not isinstance(default_personal, bool):
            errs.append(f"marketplace.default_personal は bool であること (現値 {default_personal!r})")
        policy = marketplace.get("policy")
        if not isinstance(policy, dict):
            errs.append("marketplace.policy が dict でない")
        else:
            if policy.get("installation") not in {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"}:
                errs.append(f"marketplace.policy.installation の値域違反: {policy.get('installation')!r}")
            if policy.get("authentication") not in {"ON_INSTALL", "ON_USE"}:
                errs.append(f"marketplace.policy.authentication の値域違反: {policy.get('authentication')!r}")
            if not str(policy.get("category", "")).strip():
                errs.append("marketplace.policy.category が空")
        if marketplace.get("cachebuster_for_update") is not True:
            errs.append("marketplace.cachebuster_for_update は true であること")

    dist = pm.get("distribution")
    if not isinstance(dist, dict):
        errs.append("plugin_meta.distribution が dict でない (配布判定 F3 必須)")
    else:
        d = dist.get("distributable")
        if not isinstance(d, bool):
            errs.append(f"distribution.distributable は bool であること (現値 {d!r})")
        else:
            bundles = dist.get("bundles") or []
            mk = dist.get("marketplace")
            if d is False:
                if bundles:
                    errs.append(f"distributable:false なのに bundles 非空 {bundles!r} (非配布整合違反)")
                if mk not in (None, False):
                    errs.append(f"distributable:false なのに marketplace={mk!r} (false/不在であること)")
            else:
                if not bundles:
                    errs.append("distributable:true なのに bundles が空 (最低1件の bundle 登録が必要)")
    # core: 全 plugin で必須の非空 dict
    for key in specfm.PLUGIN_META_CORE_DICTS:
        v = pm.get(key)
        if not isinstance(v, dict) or not v:
            errs.append(f"plugin_meta.{key} が非空 dict でない (plugin 階層コア規律 {key} 未充足)")
    # conditional: 該当時は規律 dict、非該当は {applicable: false, reason: <非空>} で明示 N/A (A7 整合)
    for key in specfm.PLUGIN_META_CONDITIONAL_DICTS:
        v = pm.get(key)
        if not isinstance(v, dict) or not v:
            errs.append(
                f"plugin_meta.{key} が非空 dict でない (該当時は規律 dict、非該当は {{applicable: false, reason}} を明示)"
            )
        elif specfm.is_plugin_meta_na(v):
            reason = v.get("reason")
            if not (isinstance(reason, str) and reason.strip()):
                errs.append(f"plugin_meta.{key} が applicable:false だが reason が空 (N/A の根拠を明示すること)")
    return errs


def collect_specs(specs_dir: Path) -> list[Path]:
    # index/main も含めて収集し、内容で component / plugin-meta を dispatch する。
    return sorted(specs_dir.glob("*.md"))


def run(paths: list[Path]) -> tuple[int, list[str]]:
    errors: list[str] = []
    for p in paths:
        text = p.read_text(encoding="utf-8")
        fm = specfm.parse_frontmatter(text)
        if "component_kind" in fm:
            errs = check_gates(text)
        elif isinstance(fm.get("plugin_meta"), dict):
            errs = check_plugin_meta(fm["plugin_meta"])  # index spec の plugin 階層検証
        else:
            continue  # component_kind も plugin_meta も無い .md は対象外 (README 等)
        for e in errs:
            errors.append(f"{p.name}: {e}")
    return (1 if errors else 0), errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="buildable spec の quality_gates/harness を検証する")
    ap.add_argument("specs", nargs="*", help="タスク仕様書 .md")
    ap.add_argument("--specs-dir", default=None, help="タスク仕様書ディレクトリ")
    args = ap.parse_args(argv)

    paths: list[Path] = [Path(s) for s in args.specs]
    if args.specs_dir:
        d = Path(args.specs_dir)
        if not d.is_dir():
            sys.stderr.write(f"not a directory: {d}\n")
            return 2
        paths.extend(collect_specs(d))
    if not paths:
        sys.stderr.write("usage: check-spec-gates.py <spec.md ...> | --specs-dir DIR\n")
        return 2
    missing = [p for p in paths if not p.is_file()]
    if missing:
        for p in missing:
            sys.stderr.write(f"not found: {p}\n")
        return 2
    code, errors = run(paths)
    if code == 0:
        sys.stdout.write(f"OK: {len(paths)} 仕様書が quality_gates + harness 規律を機械強制で満たす\n")
        return 0
    for e in errors:
        sys.stderr.write(e + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
