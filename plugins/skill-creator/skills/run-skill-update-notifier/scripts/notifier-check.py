#!/usr/bin/env python3
"""Skill update notifier: changelog/version cache check.

非破壊原則: plugin manifest / marketplace.json / bundles.json は読み取りのみ。
graceful degradation: 例外は握りつぶし stderr に短文を出すのみ。exit は常に 0。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CACHE_DIR = Path.home() / ".cache" / "xl-skills"
CACHE_PATH = CACHE_DIR / "version-snapshot.json"
TTL_HOURS = 24
SUPPRESS_ENV = "XL_SKILLS_NOTIFY"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(data: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(CACHE_PATH)
    except Exception as exc:
        print(f"[notifier] cache save skipped: {exc}", file=sys.stderr)


def _is_fresh(cache: dict) -> bool:
    ts = cache.get("last_refreshed_at")
    if not ts:
        return False
    try:
        last = datetime.fromisoformat(ts)
    except Exception:
        return False
    return datetime.now(timezone.utc) - last < timedelta(hours=TTL_HOURS)


_VERSION_RE = re.compile(r"^##\s*\[?v?(\d+\.\d+\.\d+[^\]\s]*)", re.MULTILINE)


def _extract_latest_version(changelog_path: Path) -> str | None:
    try:
        text = changelog_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    m = _VERSION_RE.search(text)
    return m.group(1) if m else None


def _installed_version(plugin_dir: Path) -> str | None:
    pj = plugin_dir / ".claude-plugin" / "plugin.json"
    if not pj.exists():
        return None
    try:
        return json.loads(pj.read_text(encoding="utf-8")).get("version")
    except Exception:
        return None


def cmd_cache_status(_args) -> int:
    cache = _load_cache()
    if not cache:
        print("absent")
    elif _is_fresh(cache):
        print("fresh")
    else:
        print("stale")
    return 0


def cmd_refresh(args) -> int:
    root = Path(args.plugins_root).resolve()
    snapshot: dict[str, dict] = {}
    for plugin_dir in sorted(root.glob("*/")):
        name = plugin_dir.name
        changelog = plugin_dir / "CHANGELOG.md"
        latest = _extract_latest_version(changelog) if changelog.exists() else None
        installed = _installed_version(plugin_dir)
        snapshot[name] = {"installed": installed, "latest": latest}
    data = {
        "last_refreshed_at": _now_iso(),
        "plugins": snapshot,
    }
    _save_cache(data)
    return 0


def _format_line(installed: str | None, latest: str | None) -> str:
    # TODO(human): R2 notification-formatting
    # 仕様:
    #   - installed と latest が両方あり、かつ異なるときのみ通知文字列を返す
    #   - それ以外 (片方欠落 / 一致) は空文字列を返す
    #   - フォーマット規約は references/output-format.md 参照:
    #     "(installed: vX.Y.Z / latest: vA.B.C — /skill-update で更新)"
    #   - 先頭の `v` 接頭辞が installed/latest どちらかに既に付いている場合は二重 v 化しない
    #   - locale 切替や ANSI カラーは出さない (純テキスト)
    raise NotImplementedError("R2 notification-formatting is TODO(human)")


def cmd_notify(args) -> int:
    if os.environ.get(SUPPRESS_ENV, "").lower() == "off":
        return 0
    cache = _load_cache()
    if not cache:
        return 0
    entry = cache.get("plugins", {}).get(args.plugin)
    if not entry:
        return 0
    try:
        line = _format_line(entry.get("installed"), entry.get("latest"))
    except NotImplementedError:
        # R2 未実装時は no-op (Skill 全体を壊さない)
        return 0
    except Exception as exc:
        print(f"[notifier] format skipped: {exc}", file=sys.stderr)
        return 0
    if line:
        print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="skill update notifier")
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("cache-status")
    p_refresh = sub.add_parser("refresh")
    p_refresh.add_argument("--plugins-root", default="plugins")
    p_notify = sub.add_parser("notify")
    p_notify.add_argument("--plugin", required=True)

    # 互換: --mode <name> 形式も受ける
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "--mode":
        argv = argv[1:]
    args = parser.parse_args(argv)
    dispatch = {
        "cache-status": cmd_cache_status,
        "refresh": cmd_refresh,
        "notify": cmd_notify,
    }
    try:
        return dispatch[args.mode](args)
    except Exception as exc:
        print(f"[notifier] no-op: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
