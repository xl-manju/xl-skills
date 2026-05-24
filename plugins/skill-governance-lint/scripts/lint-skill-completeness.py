#!/usr/bin/env python3
# /// script
# name: lint-skill-completeness
# purpose: kind 別の必須サポート資産(prompts/schemas/references/scripts/rubric)が
#          ローカル実在・共有正本参照(*_refs)・理由付き免除(completeness_exempt)の
#          いずれかで満たされているかを検証する再現性ゲート。
# inputs:
#   - argv: skill directory or --skills-dir <dir>
# outputs:
#   - stdout: OK status
#   - stderr: completeness findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Skill の「kind 別あるべき構成」完全性を検査する lint。

lint-skill-tree.py が「在るファイルが正しいか」を見るのに対し、本 lint は
「kind から要求される資産が揃っているか」を見る (= 再現性の穴を塞ぐ)。

判定原則 (skill-build-trace の哲学と同一): **持つ or 理由付き N/A。空欄禁止。**
各必須カテゴリは次のいずれかで満たされる:
  1. ローカルに該当ファイル/ディレクトリが実在する
  2. frontmatter の `*_refs` が共有正本 (`../other-skill/...`) を指す
  3. frontmatter `completeness_exempt:` に `<category>: <理由>` を宣言する
  4. prompts 限定: `prompt_creator_policy: skip` または `use_prompt_creator: false`

kind 別必須カテゴリ (prompt-placement-convention.md / run-build-skill SKILL.md 由来):
  ref       -> references, prompts
  run       -> prompts
  assign(評価) -> rubric, schemas, prompts
  assign(生成) -> prompts, schemas
  wrap      -> scripts, schemas
  delegate  -> prompts, schemas

Exit 0 = ok, 1 = 欠落あり, 2 = usage error。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# --- 必須カテゴリ定義 ----------------------------------------------------------
# role_suffix=evaluator または名前が -evaluator で終わる assign は評価系として扱う。
REQUIRED_BY_KIND: dict[str, set[str]] = {
    "ref": {"references", "prompts"},
    "run": {"prompts"},
    "assign-evaluator": {"rubric", "schemas", "prompts"},
    "assign-generator": {"prompts", "schemas"},
    "wrap": {"scripts", "schemas"},
    "delegate": {"prompts", "schemas"},
}

# カテゴリ -> それを満たす frontmatter ref キー
REF_KEYS_FOR_CATEGORY: dict[str, tuple[str, ...]] = {
    "schemas": ("schema_refs",),
    "references": ("reference_refs",),
    "prompts": ("responsibility_refs", "prompt_refs"),
    "scripts": ("script_refs",),
    "rubric": ("rubric_refs",),
}


def parse_frontmatter(text: str) -> dict:
    """scalar + 簡易 list の frontmatter パーサ (yaml import しない)。"""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: dict = {}
    current_list_key: str | None = None
    for line in parts[1].splitlines():
        m_item = re.match(r"^\s+-\s+(.+)$", line)
        if m_item and current_list_key is not None:
            fm.setdefault(current_list_key, [])
            if isinstance(fm[current_list_key], list):
                fm[current_list_key].append(m_item.group(1).strip())
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val == "":
                current_list_key = key
                fm[key] = []
            else:
                fm[key] = val
                current_list_key = None
        elif not line.strip():
            current_list_key = None
    return fm


def _as_str(v: object) -> str:
    return str(v).strip().strip('"').strip("'") if v is not None else ""


def _is_true(v: object) -> bool:
    if isinstance(v, bool):
        return v
    return _as_str(v).lower() == "true"


def resolve_kind(fm: dict, skill_name: str) -> str | None:
    """frontmatter から必須カテゴリ表のキーを解決する。"""
    prefix = _as_str(fm.get("prefix") or fm.get("kind"))
    role = _as_str(fm.get("role_suffix"))
    if prefix == "assign" or skill_name.startswith("assign-"):
        if role == "evaluator" or skill_name.endswith("-evaluator"):
            return "assign-evaluator"
        return "assign-generator"
    if prefix in {"ref", "run", "wrap", "delegate"}:
        return prefix
    # prefix 未設定時は名前から推定
    for p in ("ref", "run", "wrap", "delegate"):
        if skill_name.startswith(p + "-"):
            return p
    return None


def parse_exempt(fm: dict) -> dict[str, str]:
    """completeness_exempt: の `<category>: <reason>` を辞書化する。"""
    out: dict[str, str] = {}
    raw = fm.get("completeness_exempt")
    if isinstance(raw, list):
        for item in raw:
            m = re.match(r"^([a-z]+)\s*[:：]\s*(.+)$", _as_str(item))
            if m:
                out[m.group(1)] = m.group(2).strip()
    return out


def category_satisfied(root: Path, fm: dict, category: str, exempt: dict[str, str]) -> bool:
    # 3. 理由付き免除
    if category in exempt and exempt[category]:
        return True
    # prompts 限定の宣言的 skip
    if category == "prompts":
        if _as_str(fm.get("prompt_creator_policy")).lower() == "skip":
            return True
        if "use_prompt_creator" in fm and not _is_true(fm.get("use_prompt_creator")):
            return True
    # 2. 共有正本参照
    for key in REF_KEYS_FOR_CATEGORY.get(category, ()):  # noqa: B007
        val = fm.get(key)
        if val:  # 非空 list / 非空 scalar
            return True
    # 1. ローカル実在
    if category == "rubric":
        return (root / "references" / "rubric.json").is_file()
    if category == "schemas":
        d = root / "schemas"
        return d.is_dir() and any(f.suffix == ".json" for f in d.iterdir() if f.is_file())
    d = root / category  # prompts / references / scripts
    return d.is_dir() and any(f.is_file() for f in d.iterdir())


def lint_one(root: Path) -> list[str]:
    findings: list[str] = []
    skill_md = root / "SKILL.md"
    if not skill_md.exists():
        return [f"{root.name}: missing SKILL.md"]
    fm = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    kind = resolve_kind(fm, root.name)
    if kind is None:
        return findings  # 判定不能 (skill 以外) は対象外
    required = REQUIRED_BY_KIND.get(kind, set())
    exempt = parse_exempt(fm)
    for category in sorted(required):
        if not category_satisfied(root, fm, category, exempt):
            findings.append(
                f"{root.name}: [{kind}] 必須カテゴリ '{category}' が不在。"
                f" 次のいずれかで解消: (1) {category}/ に実体を置く"
                f" (2) frontmatter {REF_KEYS_FOR_CATEGORY.get(category, ('<*_refs>',))[0]}"
                f" で共有正本を参照 (3) completeness_exempt に '{category}: <理由>' を宣言"
            )
    return findings


def main() -> int:
    args = sys.argv[1:]
    if "--skills-dir" in args:
        idx = args.index("--skills-dir")
        if idx + 1 >= len(args):
            print("usage: lint-skill-completeness.py --skills-dir <dir>", file=sys.stderr)
            return 2
        base = Path(args[idx + 1])
        if not base.is_dir():
            print(f"not a directory: {base}", file=sys.stderr)
            return 2
        total: list[str] = []
        n = 0
        for d in sorted(base.iterdir()):
            if d.is_dir():
                n += 1
                total.extend(lint_one(d))
        if total:
            for e in total:
                print(e, file=sys.stderr)
            return 1
        print(f"ok: {base} ({n} skills, completeness)")
        return 0

    if not args:
        print("usage: lint-skill-completeness.py <skill-dir> | --skills-dir <dir>", file=sys.stderr)
        return 2
    root = Path(args[0])
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    errs = lint_one(root)
    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        return 1
    print(f"ok: {root.name} (completeness)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
