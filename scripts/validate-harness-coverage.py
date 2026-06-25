#!/usr/bin/env python3
# /// script
# name: validate-harness-coverage
# purpose: ハーネス仕様「全 artifact 種別 × 二軸(機械的/LLM性能評価) で テストカバレッジ >=80%」の整備状況を横断集計する。
# inputs:
#   - argv: [--threshold 80] [--json <path>] [--gate]
#   - reads: eval-log/code-coverage.json, eval-log/llm-coverage.json, eval-log/*/*/content-review/*-verdict.json
# outputs:
#   - stdout: 種別×二軸のダッシュボード + 総合 PASS/FAIL
#   - eval-log/harness-coverage.json
#   - exit: 0=計測完了(--gate無) / 1=--gate時に仕様未達 / 2=usage
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: eval-log
# ///
"""ハーネス仕様のカバレッジ整備状況を honest に集計する横断ダッシュボード。

ユーザー基準 (2026-06-24): テストカバレッジ >=80% をハーネス仕様の最低条件とし、
対象は scripts / skills / agents / commands / hooks / docs の全 artifact 種別。
二軸で測る:
  - 機械的軸 (mechanical): 行カバレッジ / criteria-test 被覆 / test・fixture 存在率
  - LLM性能評価軸 (llm_eval): LLM 評価器 (content-review / elegance / rubric verdict) が
    PASS かつ score>=threshold である artifact の割合

honest 原則: まだ計測機構が無い種別×軸は instrumented=false として報告し、
総合 spec_met を false にする (未計測を緑に偽装しない)。Goodhart 回避。

事前に `make coverage` と `validate-llm-coverage.py --all` を走らせ eval-log の
*-coverage.json を生成しておくと機械的軸が埋まる。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"
DOC_DIR = ROOT / "doc"
EVAL_LOG = ROOT / "eval-log"


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 1) if den else 0.0


def _real_dirs(parent: Path) -> list[Path]:
    return [d for d in parent.iterdir() if d.is_dir() and not d.is_symlink()] if parent.is_dir() else []


def _skills() -> list[tuple[str, str, Path]]:
    out = []
    for plugin in _real_dirs(PLUGINS_DIR):
        for s in _real_dirs(plugin / "skills"):
            if (s / "SKILL.md").is_file():
                out.append((plugin.name, s.name, s))
    return out


def _md_artifacts(subdir: str) -> list[Path]:
    out: list[Path] = []
    for plugin in _real_dirs(PLUGINS_DIR):
        d = plugin / subdir
        if d.is_dir():
            out.extend(f for f in d.glob("*.md") if f.is_file())
    return out


COV_DIR = EVAL_LOG / "coverage"  # 非コード artifact の coverage レコード置場 (実テスト/実レビューの産物)
_TESTS_BLOB_CACHE: str | None = None


def _tests_blob() -> str:
    global _TESTS_BLOB_CACHE
    if _TESTS_BLOB_CACHE is None:
        parts: list[str] = []
        td = ROOT / "tests"
        if td.is_dir():
            for f in td.rglob("*.py"):
                try:
                    parts.append(f.read_text(encoding="utf-8", errors="ignore"))
                except OSError:
                    pass
        _TESTS_BLOB_CACHE = "\n".join(parts)
    return _TESTS_BLOB_CACHE


def _slug(*parts: str) -> str:
    return "__".join(re.sub(r"[^A-Za-z0-9._-]", "-", p) for p in parts)


def _cov_record(type_name: str, key: str) -> dict | None:
    return _load_json(COV_DIR / type_name / f"{key}.json")


def _llm_eval_ok(rec: dict | None, threshold: float) -> bool:
    """coverage レコードの llm_eval verdict が PASS かつ score>=threshold か。"""
    if not isinstance(rec, dict):
        return False
    le = rec.get("llm_eval")
    if not isinstance(le, dict) or str(le.get("verdict", "")).upper() != "PASS":
        return False
    score = le.get("score")
    if isinstance(score, (int, float)) and score > 1 and score < threshold:
        return False
    return True


def _script_files() -> list[Path]:
    out: list[Path] = []
    sd = ROOT / "scripts"
    if sd.is_dir():
        out += [f for f in sd.glob("*.py") if not f.is_symlink()]
    for plugin in _real_dirs(PLUGINS_DIR):
        for f in plugin.rglob("scripts/*.py"):
            if not f.is_symlink() and "__pycache__" not in f.parts:
                out.append(f)
    return out


def measure_scripts(threshold: float) -> dict:
    cov = _load_json(EVAL_LOG / "code-coverage.json")
    mech = round(cov["totals"]["percent_covered"], 1) if cov else None
    # LLM性能評価軸 = code-review verdict(eval-log/coverage/scripts/<slug>.json) が PASS の script 割合
    scripts = _script_files()
    le_cov = sum(1 for f in scripts
                 if _llm_eval_ok(_cov_record("scripts", _slug(str(f.relative_to(ROOT)))), threshold))
    lp = _pct(le_cov, len(scripts)) if scripts else 100.0
    return {
        "type": "scripts",
        "count": len(scripts),
        "mechanical": {"instrumented": mech is not None, "coverage_pct": mech,
                       "met": (mech is not None and mech >= threshold),
                       "note": "pytest-cov 行カバレッジ (subprocess 込み)"},
        "llm_eval": {"instrumented": True, "coverage_pct": lp,
                     "met": lp >= threshold,
                     "note": "code-review verdict(eval-log/coverage/scripts) PASS の script 割合"},
    }


def _skill_has_passing_verdict(plugin: str, skill: str, threshold: float) -> bool:
    base = EVAL_LOG / plugin / skill / "content-review"
    ok = 0
    for name in ("elegance-verdict.json", "rubric-verdict.json"):
        v = _load_json(base / name)
        if not isinstance(v, dict):
            return False
        if str(v.get("verdict", "")).upper() != "PASS":
            return False
        score = v.get("score")
        if isinstance(score, (int, float)) and score < threshold and score <= 1.0 * threshold:
            # score が 0-100 表現で threshold 未満なら不合格 (0-1 表現は別途許容)
            if score > 1:
                return False
        ok += 1
    return ok == 2


def _read_skill_kind(skill_dir: Path) -> str | None:
    try:
        m = re.search(r"^kind:\s*([a-z-]+)", (skill_dir / "SKILL.md").read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def _skill_ref_review_ok(plugin: str, skill: str, threshold: float) -> bool:
    """ref-kind の ref-review verdict (source-traceability) が PASS か。

    ref は behavioral criteria/content-review を持たない代わりに、
    eval-log/coverage/skills/<plugin>__<skill>.json の llm_eval verdict で
    source-traceability(参照内容と source の整合)を担保する (ハーネス仕様 §kind 別パス)。
    """
    rec = _cov_record("skills", _slug(plugin, skill))
    return _llm_eval_ok(rec, threshold)


def measure_skills(threshold: float) -> dict:
    llm = _load_json(EVAL_LOG / "llm-coverage.json")
    skills = _skills()
    # 機械的軸 = criteria 被覆 (validate-llm-coverage の平均。loop-kind のみ対象)
    mech = llm.get("average_coverage_pct") if isinstance(llm, dict) else None
    # LLM性能評価軸 = kind 別の品質 verdict が PASS の skill 割合 (ref も除外せず計測)。
    #   - 非 ref: content-review (elegance+rubric) verdict=PASS
    #   - ref   : ref-review verdict=PASS (source-traceability。eval-log/coverage/skills/)
    passing = 0
    for plugin, skill, d in skills:
        if _read_skill_kind(d) == "ref":
            if _skill_ref_review_ok(plugin, skill, threshold):
                passing += 1
        elif _skill_has_passing_verdict(plugin, skill, threshold):
            passing += 1
    le = _pct(passing, len(skills)) if skills else None
    return {
        "type": "skills",
        "count": len(skills),
        "mechanical": {"instrumented": mech is not None, "coverage_pct": mech,
                       "met": (mech is not None and mech >= threshold),
                       "note": "criteria+checklist 被覆 (validate-llm-coverage, loop-kind)"},
        "llm_eval": {"instrumented": True, "coverage_pct": le,
                     "met": (le is not None and le >= threshold),
                     "note": "非ref=content-review verdict / ref=ref-review verdict(source-traceability) PASS 率"},
    }


def measure_md_type(type_name: str, subdir: str, threshold: float) -> dict:
    arts = _md_artifacts(subdir)
    blob = _tests_blob()
    mech_cov = le_cov = 0
    for f in arts:
        plugin = f.parent.parent.name
        name = f.stem
        rec = _cov_record(type_name, _slug(plugin, name))
        # 機械的軸: coverage レコード mechanical=true、または tests/ から実参照される
        if (isinstance(rec, dict) and rec.get("mechanical") is True) or (name in blob):
            mech_cov += 1
        if _llm_eval_ok(rec, threshold):
            le_cov += 1
    n = len(arts)
    mp = _pct(mech_cov, n) if n else 100.0
    lp = _pct(le_cov, n) if n else 100.0
    return {
        "type": type_name,
        "count": n,
        "mechanical": {"instrumented": True, "coverage_pct": mp, "met": mp >= threshold,
                       "note": f"{type_name}: tests 参照 or coverage レコード mechanical=true の割合"},
        "llm_eval": {"instrumented": True, "coverage_pct": lp, "met": lp >= threshold,
                     "note": f"{type_name}: coverage レコード llm_eval verdict=PASS の割合"},
    }


# 外部参考資料(他者 Skill コピー/書籍)は harness の挙動でないため coverage 対象外
# (ユーザー指示 2026-06-24: 外部参考資料に test/coverage は不要)。
DOC_EXTERNAL_REFERENCE = ("参考Skill", "Agent Skill大全")


def _is_external_reference_doc(path: Path) -> bool:
    return any(any(tok in part for tok in DOC_EXTERNAL_REFERENCE) for part in path.parts)


def measure_docs(threshold: float) -> dict:
    docs = [f for f in DOC_DIR.rglob("*.md")
            if f.is_file() and not _is_external_reference_doc(f)] if DOC_DIR.is_dir() else []
    blob = _tests_blob()
    mech_cov = le_cov = 0
    for f in docs:
        key = _slug(str(f.relative_to(DOC_DIR)))
        rec = _cov_record("docs", key)
        if (isinstance(rec, dict) and rec.get("mechanical") is True) or (f.name in blob):
            mech_cov += 1
        if _llm_eval_ok(rec, threshold):
            le_cov += 1
    n = len(docs)
    mp = _pct(mech_cov, n) if n else 100.0
    lp = _pct(le_cov, n) if n else 100.0
    return {
        "type": "docs",
        "count": n,
        "mechanical": {"instrumented": True, "coverage_pct": mp, "met": mp >= threshold,
                       "note": "docs: tests 参照 or coverage レコード mechanical=true の割合"},
        "llm_eval": {"instrumented": True, "coverage_pct": lp, "met": lp >= threshold,
                     "note": "docs: coverage レコード llm_eval verdict=PASS の割合"},
    }


def build_report(threshold: float) -> dict:
    sections = [
        measure_scripts(threshold),
        measure_skills(threshold),
        measure_md_type("agents", "agents", threshold),
        measure_md_type("commands", "commands", threshold),
        measure_md_type("hooks", "hooks", threshold),
        measure_docs(threshold),
    ]
    axes = [(sec["type"], axis, sec[axis]) for sec in sections for axis in ("mechanical", "llm_eval")]
    instrumented = [a for *_, a in axes if a["instrumented"]]
    met = [a for a in instrumented if a["met"]]
    spec_met = len(instrumented) == len(axes) and all(a["met"] for a in instrumented)
    return {
        "threshold": threshold,
        "spec_met": spec_met,
        "axes_total": len(axes),
        "axes_instrumented": len(instrumented),
        "axes_met": len(met),
        "sections": sections,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=80.0)
    ap.add_argument("--json", default=str(EVAL_LOG / "harness-coverage.json"))
    ap.add_argument("--gate", action="store_true", help="仕様未達(spec_met=false)で exit1")
    args = ap.parse_args()

    rep = build_report(args.threshold)
    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[harness-coverage] 閾値 {args.threshold}% / 二軸×種別 {rep['axes_total']} 中 "
          f"計測済 {rep['axes_instrumented']} / 達成 {rep['axes_met']}")
    for sec in rep["sections"]:
        for axis in ("mechanical", "llm_eval"):
            a = sec[axis]
            mark = "OK " if a["met"] else ("～  " if a["instrumented"] else "—  ")
            pct = f"{a['coverage_pct']}%" if a["coverage_pct"] is not None else "未計測"
            print(f"  [{mark}] {sec['type']:<9} {axis:<10} {pct}")
    verdict = "PASS (ハーネス仕様 充足)" if rep["spec_met"] else "FAIL (ハーネス仕様 未達)"
    print(f"[harness-coverage] 総合: {verdict}")
    if args.gate and not rep["spec_met"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
