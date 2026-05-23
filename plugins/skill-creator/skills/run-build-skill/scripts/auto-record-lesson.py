#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""auto-record-lesson.py

Claude Code Hook input (JSON via stdin) を解釈し、失敗パターンが検出された場合に
plugins/skill-creator/lessons-learned/ 配下へ構造化 lesson を追記する。

副作用境界:
    - lessons-learned ディレクトリへの書き込みのみ。
    - git・他ディレクトリには触れない。

exit_code 仕様 (Claude Code Hooks 準拠):
    0  非ブロック (正常 / 失敗未検出 / 書き込み成功)
    2  明示拒否 (本 hook は使用しない)
    その他 非ブロック警告

想定発火イベント:
    - PostToolUse:Skill
    - PostToolUse:Edit (rubric.json 等)
    - Stop
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# --- 失敗検出パターン ---------------------------------------------------------
# tool_response / stderr / messages 内に現れる代表的な失敗シグネチャ。
_FAILURE_PATTERNS = [
    re.compile(r"\bFAIL(ED|URE)?\b", re.IGNORECASE),
    re.compile(r"\bERROR\b", re.IGNORECASE),
    re.compile(r"\bTraceback\b"),
    re.compile(r"\bvalidator\b.*\bFAIL", re.IGNORECASE),
    re.compile(r"\bnon-?zero exit\b", re.IGNORECASE),
    re.compile(r"\bexit (?:code|status)\s*[:=]?\s*[1-9]\d*", re.IGNORECASE),
]

# severity 推定: 強いキーワードがあれば high、それ以外は medium。
_HIGH_SEVERITY_HINTS = re.compile(
    r"\b(FATAL|CRITICAL|Traceback|validator FAIL)\b", re.IGNORECASE
)

# capability 推定 (tool 名から大雑把に分類)。
_CAPABILITY_MAP = {
    "Edit": "edit",
    "Write": "write",
    "Bash": "shell",
    "Skill": "skill-invoke",
    "Read": "read",
}


def _repo_root_from_script() -> Path:
    # このスクリプトは plugins/skill-creator/skills/run-build-skill/scripts/ 配下。
    here = Path(__file__).resolve()
    # 4 つ上って plugins/skill-creator
    return here.parents[3]


def _lessons_dir() -> Path:
    return _repo_root_from_script() / "lessons-learned"


def _read_hook_input() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 不正入力も非ブロックで握りつぶす (hook の sla)。
        return {}


def _flatten_text(payload: Any) -> str:
    """payload 内の文字列を再帰的に抽出して結合 (失敗パターン走査用)。"""
    bucket: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            bucket.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    _walk(payload)
    return "\n".join(bucket)


def _detect_failure(text: str) -> bool:
    return any(p.search(text) for p in _FAILURE_PATTERNS)


def _estimate_severity(text: str) -> str:
    return "high" if _HIGH_SEVERITY_HINTS.search(text) else "medium"


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "lesson"


def _extract_slug(hook: dict[str, Any], text: str) -> str:
    tool = hook.get("tool_name") or hook.get("tool") or "event"
    event = hook.get("hook_event_name") or hook.get("event") or "post"
    # tool_input から file_path 等のヒントを拾う。
    ti = hook.get("tool_input") or {}
    hint = ""
    if isinstance(ti, dict):
        for k in ("file_path", "path", "skill", "command"):
            v = ti.get(k)
            if isinstance(v, str) and v:
                hint = Path(v).name if k.endswith("path") else v
                break
    base = f"{event}-{tool}-{hint}" if hint else f"{event}-{tool}"
    return _slugify(base)[:60]


def _build_entry(hook: dict[str, Any], text: str, severity: str) -> dict[str, str]:
    tool = str(hook.get("tool_name") or hook.get("tool") or "unknown")
    event = str(hook.get("hook_event_name") or hook.get("event") or "unknown")
    capability = _CAPABILITY_MAP.get(tool, "unknown")
    # 観測サマリ: 先頭の失敗一致行を 240 文字以内で。
    observation = ""
    for line in text.splitlines():
        if _detect_failure(line):
            observation = line.strip()[:240]
            break
    if not observation:
        observation = "(失敗シグネチャは検出されたが該当行抽出に失敗)"
    return {
        "date": _dt.date.today().isoformat(),
        "trigger_event": event,
        "tool": tool,
        "severity": severity,
        "capability": capability,
        "observation": observation,
    }


def _render_markdown(entry: dict[str, str]) -> str:
    fm_lines = [
        "---",
        f"date: {entry['date']}",
        f"trigger_event: {entry['trigger_event']}",
        f"tool: {entry['tool']}",
        f"severity: {entry['severity']}",
        f"capability: {entry['capability']}",
        "---",
        "",
        "## observation",
        "",
        entry["observation"],
        "",
        "## hypothesis",
        "",
        "(自動記録: 失敗パターンを検出。根本原因は要 human triage)",
        "",
        "## proposed_action",
        "",
        "- 当該 capability に対する rubric 強化 / validator 追加を検討",
        "- 再現条件を別 issue に起票",
        "",
    ]
    return "\n".join(fm_lines)


def _upsert_lesson(path: Path, entry: dict[str, str]) -> None:
    """同日同 slug は新規 observation を追記 (upsert)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(_render_markdown(entry), encoding="utf-8")
        return
    # 追記モード: 既存ファイル末尾に observation セクションを足す。
    appended = [
        "",
        f"## observation ({_dt.datetime.now().isoformat(timespec='seconds')})",
        "",
        entry["observation"],
        "",
    ]
    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(appended))


def main() -> int:
    hook = _read_hook_input()
    text = _flatten_text(hook)
    if not text or not _detect_failure(text):
        # サイレント正常終了。
        return 0
    severity = _estimate_severity(text)
    slug = _extract_slug(hook, text)
    today = _dt.date.today().isoformat()
    target = _lessons_dir() / f"{today}-{slug}.md"
    entry = _build_entry(hook, text, severity)
    try:
        _upsert_lesson(target, entry)
    except OSError as exc:
        # 書き込み失敗は非ブロック警告で。
        sys.stderr.write(f"[auto-record-lesson] write failed: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
