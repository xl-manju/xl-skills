#!/usr/bin/env python3
"""visuals.json 各 section に png_paths が存在するか検証。"""
import json, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out_dir = Path(sys.argv[2])
missing = []
for s in data.get("sections", []):
    for p in s.get("png_paths", []):
        if not (out_dir / Path(p).name).exists():
            missing.append(p)
if missing:
    print(f"FAIL missing PNGs: {missing}", file=sys.stderr); sys.exit(1)
if not data.get("sections"):
    print("FAIL no sections", file=sys.stderr); sys.exit(1)
print("PASS")
