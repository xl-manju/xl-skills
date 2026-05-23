#!/usr/bin/env python3
"""sheet.md に 5 軸見出しが揃い、各見出しの下に空行以外の内容があるか検証。"""
import re, sys
from pathlib import Path
AXES = ["出力先", "情報源", "共有相手", "真の課題", "ナレッジ資産"]
text = Path(sys.argv[1]).read_text(encoding="utf-8")
missing = []
for axis in AXES:
    m = re.search(rf"#+\s*{re.escape(axis)}\s*\n(.+?)(?=\n#+\s|\Z)", text, re.S)
    if not m or not m.group(1).strip() or "[?]" in m.group(1):
        missing.append(axis)
if missing:
    print(f"FAIL axes incomplete: {missing}", file=sys.stderr); sys.exit(1)
print("PASS")
