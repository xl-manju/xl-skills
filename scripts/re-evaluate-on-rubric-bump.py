#!/usr/bin/env python3
"""re-evaluate-on-rubric-bump.py — PostToolUse hook stub (root/scripts 版).

Claude Code の PostToolUse hook から呼ばれる。
CLAUDE_TOOL_INPUT_FILE_PATH 環境変数に編集対象ファイルパスが入っている場合、
それが rubric.json への変更かどうかを判定し、該当時は
creator-kit/scripts/re-evaluate-on-rubric-bump.py を起動する。

違反率 30% 超の場合は major 強制昇格アラートを stdout に出力する。

--post-tool-use フラグ付きで呼ばれることを想定 (settings.json から)。

stdlib only / Python 3.9+
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_SCRIPT = REPO_ROOT / "creator-kit" / "scripts" / "re-evaluate-on-rubric-bump.py"
VIOLATION_THRESHOLD = 0.30  # 30% 超で major 強制昇格アラート


def is_rubric_file(file_path: str | None) -> bool:
    if not file_path:
        return False
    p = Path(file_path)
    return p.name == "rubric.json"


def check_violation_rate() -> float | None:
    """eval-log/fixtures/ の fixture 結果から違反率を算出する (best-effort)."""
    fixture_result = REPO_ROOT / "eval-log" / "fixture-results.json"
    if not fixture_result.exists():
        return None
    try:
        doc = json.loads(fixture_result.read_text(encoding="utf-8"))
        results = doc.get("results", [])
        if not results:
            return None
        failed = sum(1 for r in results if not r.get("passed", True))
        return failed / len(results)
    except (json.JSONDecodeError, KeyError, ZeroDivisionError):
        return None


def main() -> int:
    # --post-tool-use フラグを確認（settings.json から渡される）
    # ファイルパスは環境変数 CLAUDE_TOOL_INPUT_FILE_PATH で受け取る
    file_path = os.environ.get("CLAUDE_TOOL_INPUT_FILE_PATH") or os.environ.get(
        "TOOL_INPUT_FILE_PATH"
    )

    if not is_rubric_file(file_path):
        # rubric.json 以外の変更は何もしない
        return 0

    print(f"[re-evaluate-on-rubric-bump] rubric.json 変更を検知: {file_path}")

    # 違反率チェック
    rate = check_violation_rate()
    if rate is not None and rate > VIOLATION_THRESHOLD:
        print(
            f"[ALERT] violation_rate={rate:.1%} > threshold={VIOLATION_THRESHOLD:.0%} "
            f"=> major 強制昇格アラート: rubric bump に伴い全スキルの再評価を推奨"
        )

    # upstream スクリプトへ委譲
    if UPSTREAM_SCRIPT.exists():
        result = subprocess.run(
            [sys.executable, str(UPSTREAM_SCRIPT)],
            capture_output=False,
        )
        return result.returncode
    else:
        print(
            f"[re-evaluate-on-rubric-bump] upstream script not found: {UPSTREAM_SCRIPT}",
            file=sys.stderr,
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
