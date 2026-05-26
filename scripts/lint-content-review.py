#!/usr/bin/env python3
"""内容 adequacy 評価成果物の存在を機械検査する (offline, LLM 不実行)。

役割境界:
  - 機械層: SKILL.md が変更された skill について eval-log/<plugin>/<skill>/content-review/
            配下に elegance-verdict.json + rubric-verdict.json が存在し verdict=PASS であることを検査
  - LLM 層 (本 lint の対象外): 評価実行自体はローカル Claude Code で run-elegant-review +
            assign-skill-design-evaluator を SubAgent 起動して行う (リモート CI コスト回避)

skill-creator 自身および ref kind は除外 (内容評価対象外)。

Usage:
  python3 scripts/lint-content-review.py --changed-only [--base origin/main]
  python3 scripts/lint-content-review.py --all
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = ROOT / "plugins"
EVAL_LOG = ROOT / "eval-log"
REQUIRED_VERDICTS = ("elegance-verdict.json", "rubric-verdict.json")
EXEMPT_PLUGINS = {"skill-creator"}
EXEMPT_KINDS = {"ref"}


def _git_changed_skills(base):
    try:
        diff = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=ROOT,
            text=True,
        )
    except subprocess.CalledProcessError:
        return set()
    skills = set()
    pat = re.compile(r"^plugins/([^/]+)/skills/([^/]+)/SKILL\.md$")
    for line in diff.splitlines():
        m = pat.match(line.strip())
        if m:
            skills.add((m.group(1), m.group(2)))
    return skills


def _all_skills():
    skills = set()
    if not PLUGINS_DIR.exists():
        return skills
    for plugin_dir in PLUGINS_DIR.iterdir():
        if not plugin_dir.is_dir():
            continue
        sk_dir = plugin_dir / "skills"
        if not sk_dir.is_dir():
            continue
        for s in sk_dir.iterdir():
            if (s / "SKILL.md").is_file():
                # symlink は対象外 (実体側で評価される)
                if s.is_symlink():
                    continue
                skills.add((plugin_dir.name, s.name))
    return skills


def _read_kind(plugin, skill):
    md = PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md"
    if not md.is_file():
        return None
    try:
        text = md.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"^kind:\s*([a-z]+)\s*$", text, re.M)
    return m.group(1) if m else None


def _check_verdict(path):
    if not path.is_file():
        return "missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"invalid-json: {exc}"
    verdict = data.get("verdict")
    if verdict != "PASS":
        return f"verdict={verdict}"
    return None


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--changed-only", action="store_true")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--base", default="origin/main")
    args = ap.parse_args()

    targets = _git_changed_skills(args.base) if args.changed_only else _all_skills()
    # filter
    filtered = []
    for plugin, skill in sorted(targets):
        if plugin in EXEMPT_PLUGINS:
            continue
        kind = _read_kind(plugin, skill)
        if kind in EXEMPT_KINDS:
            continue
        # SKILL.md が削除された変更も target に含まれるので存在チェック
        if not (PLUGINS_DIR / plugin / "skills" / skill / "SKILL.md").is_file():
            continue
        filtered.append((plugin, skill))

    if not filtered:
        print("[OK] content-review lint: no target skill")
        return 0

    violations = []
    for plugin, skill in filtered:
        review_dir = EVAL_LOG / plugin / skill / "content-review"
        for fname in REQUIRED_VERDICTS:
            err = _check_verdict(review_dir / fname)
            if err:
                violations.append(f"{plugin}/{skill}: {fname} {err}")

    if violations:
        print(f"[FAIL] content-review lint: {len(violations)} violation(s)")
        for v in violations:
            print(f"  - {v}")
        print()
        print("Fix: ローカル Claude Code で run-elegant-review + assign-skill-design-evaluator を")
        print("     対象 skill に対し実行し eval-log/<plugin>/<skill>/content-review/ に verdict json を保存してください。")
        print("     手順詳細: plugins/skill-creator/skills/run-build-skill/references/content-review-protocol.md")
        return 1

    print(f"[OK] content-review lint: {len(filtered)} skill(s) verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
