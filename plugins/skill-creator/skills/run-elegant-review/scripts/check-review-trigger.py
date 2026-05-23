#!/usr/bin/env python3
# 発火: Stop hook (Claude Code)
# 副作用境界: git status をサブプロセス read-only で参照のみ。stdout に推奨を出すだけ。
# 想定 input: {"session_id": "...", ...} 形式 JSON(本スタブは内容に依存しない)。
# 閾値: 変更ファイル合計が 20 件以上なら run-elegant-review 起動を推奨。常に exit 0。
"""Stop hook。直近の編集量から run-elegant-review 起動を推奨するか判定する."""
from __future__ import annotations

import json
import subprocess
import sys

THRESHOLD = 20


def _read_stdin_json() -> dict:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def _git_status_count() -> int:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            return 0
        return len([l for l in proc.stdout.splitlines() if l.strip()])
    except Exception:
        return 0


def main() -> int:
    try:
        _ = _read_stdin_json()
        count = _git_status_count()
        if count >= THRESHOLD:
            sys.stdout.write(
                json.dumps(
                    {
                        "hook": "check-review-trigger",
                        "recommendation": "run-elegant-review",
                        "changed_files": count,
                        "threshold": THRESHOLD,
                        "reason": f"git status の変更ファイルが {count} 件 (閾値 {THRESHOLD})",
                    },
                    ensure_ascii=False,
                )
            )
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
