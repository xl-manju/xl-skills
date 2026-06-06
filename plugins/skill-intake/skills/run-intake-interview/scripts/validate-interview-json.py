#!/usr/bin/env python3
import json, sys
from pathlib import Path
REQUIRED = ["filled_ratio", "five_axes_complete", "unresolved", "needs_excavation", "abstract_answers"]
d = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
miss = [k for k in REQUIRED if k not in d]
if miss:
    print(f"FAIL missing {miss}", file=sys.stderr); sys.exit(1)
if not isinstance(d["filled_ratio"], (int, float)) or not 0 <= d["filled_ratio"] <= 1:
    print("FAIL filled_ratio range", file=sys.stderr); sys.exit(1)
print("PASS")
