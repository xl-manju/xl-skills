#!/usr/bin/env python3
"""feedback_protocol SSOT 整合 lint (オフライン、NOTION_TOKEN 不要)。

検証:
  R1. skill-list.schema.json#feedback_protocol が必須キーを満たす
  R2. page_body_sections に id=feedback (renderer_ref=feedback_protocol) が含まれる
  R3. run-skill-feedback/SKILL.md が schema を SSOT として参照している
  R4. run-skill-feedback/SKILL.md の triggers が firing_conditions を包含する近似 (各 firing_condition の主要キーワードが triggers のいずれかに含まれる)
  R5. notion-upsert-plugin.py が _load_feedback_protocol() を経由している
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "doc" / "notion-schema" / "skill-list.schema.json"
SKILL_MD = ROOT / "plugins" / "skill-creator" / "skills" / "run-skill-feedback" / "SKILL.md"
UPSERT = ROOT / "scripts" / "notion-upsert-plugin.py"


def main():
    violations = []
    sc = json.loads(SCHEMA.read_text())

    # R1
    fp = sc.get("feedback_protocol")
    required = {"command", "firing_conditions", "intake_fields", "status_lifecycle",
                "open_statuses", "promise_to_reporter", "callout_summary"}
    if not fp:
        violations.append("R1: skill-list.schema.json に feedback_protocol が無い")
    else:
        missing = required - set(fp.keys())
        if missing:
            violations.append(f"R1: feedback_protocol に必須キー欠落: {sorted(missing)}")

    # R2
    sections = sc.get("page_body_sections", [])
    fb_sec = next((s for s in sections if s.get("id") == "feedback"), None)
    if not fb_sec:
        violations.append("R2: page_body_sections に id=feedback が無い")
    elif fb_sec.get("renderer_ref") != "feedback_protocol":
        violations.append("R2: feedback section の renderer_ref が feedback_protocol を指していない")

    # R3
    md = SKILL_MD.read_text() if SKILL_MD.exists() else ""
    if "feedback_protocol" not in md or "skill-list.schema.json" not in md:
        violations.append("R3: run-skill-feedback/SKILL.md が schema feedback_protocol を参照していない")

    # R4: firing_conditions の主要語が triggers に存在
    if fp:
        tr_match = re.search(r"^triggers:\s*\n((?:\s+-.*\n)+)", md, re.M)
        triggers_blob = tr_match.group(1) if tr_match else ""
        keywords = ["分かりにくい", "直してほしい", "バグ", "改善", "要望"]
        missing_kw = [k for k in keywords if k not in triggers_blob and k not in md]
        if missing_kw:
            violations.append(f"R4: SKILL.md triggers/本文に発火キーワード欠落: {missing_kw}")

    # R5
    src = UPSERT.read_text() if UPSERT.exists() else ""
    if "_load_feedback_protocol" not in src:
        violations.append("R5: notion-upsert-plugin.py が _load_feedback_protocol() を未使用")

    if violations:
        print(f"[FAIL] feedback_protocol SSOT lint: {len(violations)} violation(s)")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    print("[OK] feedback_protocol SSOT lint: all checks passed")


if __name__ == "__main__":
    main()
