#!/usr/bin/env python3
# /// script
# name: lint-feedback-contract
# purpose: 量産先 loop-kind スキルが frontmatter に per-skill 評価基準(feedback_contract)を携帯することを強制する。
# inputs:
#   - argv: --changed-only [--base origin/main] | --all
# outputs:
#   - stdout: OK/FAIL サマリ
#   - exit: 0=PASS / 1=violation / 2=usage
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, E]
# network: false
# write-scope: none
# ///
"""loop 実行系スキル(kind=run/wrap/delegate)の SKILL.md frontmatter に
`feedback_contract.criteria` が存在し SSOT 制約を満たすことを機械検査する。

これは「skill-creator が量産するスキルへ評価基準を毎回 frontmatter に焼き込む」
仕組みの fail-closed ゲート。criteria の中身は各スキル固有のため AI が brief から
導出するが(内容判断の自由度)、欠落・不正は本 lint が CI/pre-push で必ず落とす(機構保証)。

ref/assign/agent 等の非ループ系は対象外。skip_reason があれば loop-kind でも N/A escape。

criteria 制約の正本: repo-root scripts/feedback_contract_ssot.py。

Usage:
  python3 scripts/lint-feedback-contract.py --changed-only [--base origin/main]
  python3 scripts/lint-feedback-contract.py --all
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"

sys.path.insert(0, str(ROOT / "scripts"))
import feedback_contract_ssot as FC  # noqa: E402

# 評価基準を frontmatter に携帯すべき loop 実行系。ref/assign/agent 等は対象外。
LOOP_KINDS = FC.FEEDBACK_LOOP_KINDS


def _git_changed_skills(base: str) -> set[tuple[str, str]]:
    try:
        diff = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base}...HEAD"], cwd=ROOT, text=True
        )
    except subprocess.CalledProcessError:
        return set()
    pat = re.compile(r"^plugins/([^/]+)/skills/([^/]+)/SKILL\.md$")
    out: set[tuple[str, str]] = set()
    for line in diff.splitlines():
        m = pat.match(line.strip())
        if m:
            out.add((m.group(1), m.group(2)))
    return out


def _all_skills() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    if not PLUGINS_DIR.exists():
        return out
    for plugin_dir in PLUGINS_DIR.iterdir():
        sk_dir = plugin_dir / "skills"
        if not sk_dir.is_dir():
            continue
        for s in sk_dir.iterdir():
            if s.is_symlink():  # symlink は実体側で検査
                continue
            if (s / "SKILL.md").is_file():
                out.add((plugin_dir.name, s.name))
    return out


def _read_kind(text: str) -> str | None:
    return FC.read_kind(text)  # kind 抽出は SSOT の単一実装に委譲 (lint 間の正規表現乖離を排除)


def _fallback_warnings(plugin: str, skill: str, fc: dict) -> list[str]:
    """criteria が brief 非導出のフォールバック既定 (同語反復) のままなら WARN を返す。

    機構 (lint) は criteria の「存在」を fail-closed 保証するが「内容の per-skill 性」は
    LLM 層の責務。ただしフォールバック既定の残存だけは機械検出して可視化し、
    content-review が見落とした空洞 criteria を CI で surface する (Goodhart 対策)。
    """
    criteria = fc.get("criteria")
    if not isinstance(criteria, list):
        return []
    warns: list[str] = []
    for item in criteria:
        if isinstance(item, dict) and FC.is_fallback_text(item.get("text")):
            warns.append(
                f"{plugin}/{skill}: criteria[{item.get('id', '?')}] が brief 非導出の"
                " フォールバック既定文のまま (per-skill 評価基準へ具体化推奨)"
            )
    return warns


def _check_skill(plugin: str, skill: str) -> list[str]:
    md = PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md"
    if not md.is_file():
        return []
    text = md.read_text(encoding="utf-8")
    kind = _read_kind(text)
    if kind not in LOOP_KINDS:
        return []  # 非ループ系は評価基準携帯の対象外

    fc = FC.extract_frontmatter_feedback_contract(text)
    if not isinstance(fc, dict):
        return [
            f"{plugin}/{skill}: frontmatter に feedback_contract がありません "
            f"(kind={kind} は loop 実行系。brief.goal/Checklist から criteria を導出し "
            "frontmatter へ焼き込むこと。N/A の場合は feedback_contract.skip_reason を記載)"
        ]
    skip_reason = str(fc.get("skip_reason", "")).strip()
    criteria = fc.get("criteria")
    if (not isinstance(criteria, list) or not criteria) and skip_reason:
        return []  # 明示的 N/A escape
    errs = FC.validate_criteria(
        criteria, require_both_scopes=True, prefix=f"{plugin}/{skill}: feedback_contract.criteria"
    )
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--changed-only", action="store_true")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--base", default="origin/main")
    args = ap.parse_args()

    targets = _git_changed_skills(args.base) if args.changed_only else _all_skills()
    violations: list[str] = []
    warnings: list[str] = []
    checked = 0
    for plugin, skill in sorted(targets):
        md = PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md"
        if not md.is_file():
            continue
        text = md.read_text(encoding="utf-8")
        kind = _read_kind(text)
        if kind in LOOP_KINDS:
            checked += 1
            fc = FC.extract_frontmatter_feedback_contract(text)
            if isinstance(fc, dict):
                warnings.extend(_fallback_warnings(plugin, skill, fc))
        violations.extend(_check_skill(plugin, skill))

    if warnings:
        print(f"[WARN] lint-feedback-contract: {len(warnings)} fallback criteria (非 fail)")
        for w in warnings:
            print(f"  ~ {w}")
        print(
            "  この WARN は brief 既定文(fallback)の残存を示す。content-review が PASS でも"
            " per-skill 性が空洞の可能性。criteria.text を当該スキル固有の検証対象へ書き換え推奨。"
        )
        print()

    if violations:
        print(f"[FAIL] lint-feedback-contract: {len(violations)} violation(s)")
        for v in violations:
            print(f"  - {v}")
        print()
        print("Fix: loop 実行系スキルの SKILL.md frontmatter に feedback_contract.criteria を")
        print("     inner/outer 各1件以上で記載してください(id=^(IN|OUT|C)[0-9]+$ / verify_by enum)。")
        print("     正本制約: scripts/feedback_contract_ssot.py / 配置: commonCore.feedback_contract")
        return 1

    print(f"[OK] lint-feedback-contract: {checked} loop-kind skill(s) carry per-skill criteria")
    return 0


if __name__ == "__main__":
    sys.exit(main())
