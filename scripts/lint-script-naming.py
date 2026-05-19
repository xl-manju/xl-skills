#!/usr/bin/env python3
"""lint-script-naming.py

28章 §4.1-§4.6 のscript命名規約を機械強制する。
- 動詞リスト: lint/validate/format/render/extract/diff/guard/build
- 例外節 (§4.4): sink_*.py / *_helper.py / audit_*.py
- 例外節 (§4.6): adapters/*.py (Hexagonal Architecture adapter固有名)
- 禁止: アンダースコア(例外節を除く), check/run/main/utils/helper のみ命名

usage:
  python3 scripts/lint-script-naming.py [path...]
  python3 scripts/lint-script-naming.py --report

exit code:
  0 違反なし
  1 違反検出
  2 設定エラー

CONVENTIONS: stdlib only.
"""
import json
import pathlib
import re
import sys

ALLOWED_VERBS = {
    "lint", "validate", "format", "render",
    "extract", "diff", "guard", "build",
}
BANNED_NAMES = {"check.py", "run.py", "main.py", "utils.py", "helper.py"}

# §4.4 例外節
EXCEPTION_PATTERNS = [
    (re.compile(r"^sink_[a-z0-9]+\.py$"), "Sink Contract adapter (§4.4)"),
    (re.compile(r"^[a-z0-9]+_helper\.py$"), "secret helper (§4.4)"),
    (re.compile(r"^audit_[a-z0-9_]+\.py$"), "audit helper (§4.4)"),
]

# 暫定例外 (Change Governance 経由でリネーム予定)
PENDING_RENAME_PATTERNS = [
    re.compile(r"^hook-[a-z0-9-]+\.py$"),
]

VALID_NAME = re.compile(r"^([a-z]+)-[a-z0-9-]+\.py$")

SCAN_ROOTS = ["scripts", "creator-kit/scripts", "creator-kit/skills"]
SKIP_PARTS = {"_lib", "__pycache__", "node_modules", ".git"}


def find_scripts(roots):
    for root in roots:
        rp = pathlib.Path(root)
        if not rp.exists():
            continue
        for p in rp.rglob("*.py"):
            if any(part in SKIP_PARTS for part in p.parts):
                continue
            if "/scripts/" in str(p) or str(p.parent).endswith("scripts"):
                yield p
            elif rp.name == "scripts":
                yield p


def classify(path: pathlib.Path):
    name = path.name
    if name in BANNED_NAMES:
        return ("VIOLATION", f"banned name: {name}")
    if path.parent.name == "adapters":
        return ("EXCEPTION", "Hexagonal adapter (§4.6)")
    for pat, reason in EXCEPTION_PATTERNS:
        if pat.match(name):
            return ("EXCEPTION", reason)
    for pat in PENDING_RENAME_PATTERNS:
        if pat.match(name):
            return ("PENDING_RENAME", "hook-* prefix scheduled for rename (33章 Change Governance)")
    m = VALID_NAME.match(name)
    if not m:
        if "_" in name:
            return ("VIOLATION", "underscore not allowed (§4.3)")
        return ("VIOLATION", "does not match <verb>-<target>[-<scope>].py")
    verb = m.group(1)
    if verb not in ALLOWED_VERBS:
        return ("VIOLATION", f"verb '{verb}' not in allowed list {sorted(ALLOWED_VERBS)}")
    return ("OK", None)


def main(argv):
    report_mode = "--report" in argv
    paths = [a for a in argv[1:] if not a.startswith("--")]
    scripts = list(find_scripts(paths or SCAN_ROOTS))
    results = {"OK": [], "EXCEPTION": [], "PENDING_RENAME": [], "VIOLATION": []}
    for p in scripts:
        status, reason = classify(p)
        results[status].append({"path": str(p), "reason": reason})
    if report_mode:
        print(json.dumps({
            "summary": {k: len(v) for k, v in results.items()},
            "violations": results["VIOLATION"],
            "pending_rename": results["PENDING_RENAME"],
        }, indent=2, ensure_ascii=False))
    else:
        for item in results["VIOLATION"]:
            print(f"VIOLATION {item['path']}: {item['reason']}", file=sys.stderr)
        for item in results["PENDING_RENAME"]:
            print(f"PENDING  {item['path']}: {item['reason']}", file=sys.stderr)
        print(
            f"summary: OK={len(results['OK'])} "
            f"EXCEPTION={len(results['EXCEPTION'])} "
            f"PENDING={len(results['PENDING_RENAME'])} "
            f"VIOLATION={len(results['VIOLATION'])}"
        )
    return 1 if results["VIOLATION"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
