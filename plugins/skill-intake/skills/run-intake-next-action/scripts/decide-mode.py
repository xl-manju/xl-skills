#!/usr/bin/env python3
"""kickoff/purpose/options/summary から mode を機械判定。LLM は呼ばない。"""
import argparse, json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--kickoff", required=True)
    p.add_argument("--purpose", required=True)
    p.add_argument("--options", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    kick = json.loads(Path(a.kickoff).read_text(encoding="utf-8"))
    purp = json.loads(Path(a.purpose).read_text(encoding="utf-8"))
    summ = json.loads(Path(a.summary).read_text(encoding="utf-8"))
    verb = purp.get("true_purpose", {}).get("verb_object", "")
    # 簡易判定: Phase 1 の暫定 pattern を尊重しつつ、verb 空・分裂検知時のみ E/D に格下げ。
    init = kick.get("pattern", "E")
    mode = init
    reason = f"kickoff.pattern={init} を採用"
    multi = False
    splits = []
    if not verb.strip():
        mode = "E"
        reason = "true_purpose.verb_object が空のため判定不能"
    elif " と " in verb or "+" in verb:
        mode = "D"
        multi = True
        reason = "verb_object に複数責務の徴候 (連結語) あり"
    handoff = {
        "A": "Phase 1 (kickoff)",
        "B": "Phase 2 (existing reuse)",
        "C": "Phase 7 (prompt-only update)",
        "D": "Phase 1 (split first)",
        "E": "Phase 1 (re-intake)",
    }[mode]
    out = {
        "mode": mode,
        "reason": reason,
        "multi_skill_suspicion": multi,
        "split_candidates": splits,
        "skill_creator_handoff_phase": handoff,
    }
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"mode={mode}")


if __name__ == "__main__":
    main()
