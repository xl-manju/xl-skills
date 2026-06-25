#!/usr/bin/env python3
"""UserPromptSubmit hook: stale 時のみ cache refresh。常に exit 0。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NOTIFIER = HERE / "notifier-check.py"


def main() -> int:
    try:
        status = subprocess.run(
            ["python3", str(NOTIFIER), "cache-status"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if status in ("stale", "absent"):
            subprocess.run(
                ["python3", str(NOTIFIER), "refresh", "--plugins-root", "plugins"],
                capture_output=True, text=True, timeout=15,
            )
    except Exception as exc:
        print(f"[notifier-hook] skipped: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
