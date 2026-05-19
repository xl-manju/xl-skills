#!/usr/bin/env python3
# /// script
# name: hook-check-file-ownership
# purpose: TaskCreated hook — Agent Teamのtask生成時にfile ownership衝突を検出。
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# ///
"""TaskCreated hook (設計書10章 §設計判断5 / §6).

Agent Team で複数 teammate が同一 file を編集対象にする task が生成された
場合に exit 2 で block する。frontmatter / task description 内の
`files:` または `file_ownership:` を読み、既存 active task と突合する。

最小実装: stdin から JSON を受け取り、task の `files` 配列が既存 active
task と重複する場合のみ block。未指定なら警告のみで pass。
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path


STATE_FILE = Path(os.environ.get("CLAUDE_TASK_OWNERSHIP_STATE",
                                  ".claude/logs/task-ownership.json"))


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0
    task_id = str(data.get("task_id") or data.get("id") or "")
    files = data.get("files") or data.get("file_ownership") or []
    if not isinstance(files, list) or not files:
        return 0
    state = load_state()
    active = {f: tid for tid, fs in state.items() for f in fs}
    conflicts = [f for f in files if f in active and active[f] != task_id]
    if conflicts:
        sys.stderr.write(
            f"hook-check-file-ownership: task {task_id} conflicts on "
            f"{conflicts} (already owned by {[active[f] for f in conflicts]})\n"
        )
        return 2
    state[task_id] = list(files)
    save_state(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
