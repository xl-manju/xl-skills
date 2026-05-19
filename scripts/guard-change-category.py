#!/usr/bin/env python3
"""guard-change-category.py

33章 Change Governance の自動分類器。git diff から変更ファイル一覧を取得し、
governance-policy.json の change_categories ルールに従って P0/P1/P2/P3 を推定する。
proposal_required カテゴリで未承認の場合 exit 1 (CI block)。

usage:
  python3 scripts/guard-change-category.py [--base origin/main] [--report]

exit code:
  0 承認済み or auto_apply 範囲のみ
  1 proposal/承認が必要な変更を検出 (CI block)
  2 設定エラー
"""
import json
import pathlib
import re
import subprocess
import sys

POLICY_PATH = pathlib.Path("creator-kit/config/governance-policy.json")
CHANGELOG_PATH = pathlib.Path(".claude/changelog/governance-log.jsonl")


def changed_files(base: str):
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            text=True,
        )
    except subprocess.CalledProcessError:
        return []
    return [line for line in out.splitlines() if line.strip()]


_SKILL_DIR_RE = re.compile(r"^creator-kit/skills/([a-z0-9][a-z0-9-]*)/")
_SKILL_MD_RE = re.compile(r"^creator-kit/skills/[a-z0-9][a-z0-9-]*/SKILL\.md$")
_SINK_ADAPTER_RE = re.compile(r"^scripts/adapters/sink_[a-z0-9_]+\.py$")
_P1_DOC_PATHS = (
    "doc/ClaudeCodeスキルの設計書/06-classification-and-naming",
    "doc/ClaudeCodeスキルの設計書/27-rubric-governance-runbook",
    "doc/ClaudeCodeスキルの設計書/28-script-execution-model",
    "doc/ClaudeCodeスキルの設計書/33-change-governance",
)
_P3_SUFFIXES = (".gitignore", ".editorconfig")


def _name_field_changed(path: str) -> bool:
    """SKILL.md の `name:` 行が変更されたか git diff で確認 (P0_breaking)。"""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--unified=0", "HEAD", "--", path], text=True
        )
    except subprocess.CalledProcessError:
        return False
    return any(re.match(r"^[+-]name:\s", line) for line in out.splitlines())


def classify_change(path: str) -> str:
    """変更パスから P0/P1/P2/P3 を推定する (33章 Change Governance)。

    fallback は P2_content (Goodhart 罠回避のため P3 にしない)。
    Phase 0 省略検出: plugins/ 配下の新規ディレクトリは P0_breaking 扱いとする。
    """
    # Phase 0 不可逆移行検出 (PF2-D2 mitigation)
    if path.startswith("plugins/"):
        return "P0_breaking"
    # Sink Contract I/F 変更
    if _SINK_ADAPTER_RE.match(path):
        return "P0_breaking"
    # Skill name 変更 (frontmatter name: 行の diff)
    if _SKILL_MD_RE.match(path) and _name_field_changed(path):
        return "P0_breaking"
    # 新 Skill 追加 (SKILL.md 新規)
    if _SKILL_MD_RE.match(path) and not pathlib.Path(path).exists():
        return "P1_structural"  # 削除 (= 旧 dir 消滅) も構造変更
    if _SKILL_DIR_RE.match(path) and path.endswith("/SKILL.md"):
        # 既存 SKILL.md の name 以外の変更
        return "P1_structural" if _name_field_changed(path) else "P2_content"
    # 命名規則 / governance / script モデル / change governance ドキュメント
    if any(path.startswith(p) for p in _P1_DOC_PATHS):
        return "P1_structural"
    # manifest forbidden_dependencies
    if path == "creator-kit/manifest.json":
        return "P1_structural"
    # rubric 本体
    if path.endswith("/rubric.json"):
        return "P1_structural"
    # cosmetic
    if path.endswith(_P3_SUFFIXES):
        return "P3_cosmetic"
    # ドキュメント本文 / references / examples / templates
    if (
        path.startswith("doc/")
        or "/references/" in path
        or "/examples/" in path
        or "/templates/" in path
    ):
        return "P2_content"
    return "P2_content"


def load_policy():
    if not POLICY_PATH.exists():
        print(f"ERROR: policy not found at {POLICY_PATH}", file=sys.stderr)
        sys.exit(2)
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def needs_proposal(category: str, policy: dict) -> bool:
    rule = policy["change_categories"].get(category, {})
    return "proposal_required" in rule.get("workflow", "")


def has_recent_changelog(target_path: str) -> bool:
    if not CHANGELOG_PATH.exists():
        return False
    for line in CHANGELOG_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if target_path.split("/")[0] in entry.get("target_path", ""):
            return True
    return False


def main(argv):
    base = "origin/main"
    report = False
    for i, a in enumerate(argv):
        if a == "--base" and i + 1 < len(argv):
            base = argv[i + 1]
        if a == "--report":
            report = True
    policy = load_policy()
    files = changed_files(base)
    results = []
    blocked = []
    for f in files:
        cat = classify_change(f)
        proposal = needs_proposal(cat, policy)
        approved = has_recent_changelog(f) if proposal else True
        results.append({"path": f, "category": cat, "proposal_required": proposal, "approved": approved})
        if proposal and not approved:
            blocked.append({"path": f, "category": cat})
    if report:
        print(json.dumps({
            "base": base,
            "changes": results,
            "blocked": blocked,
        }, indent=2, ensure_ascii=False))
    else:
        for b in blocked:
            print(f"BLOCK {b['path']} ({b['category']}): proposal/承認 changelog 未記録", file=sys.stderr)
        print(f"summary: total={len(results)} blocked={len(blocked)}")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
