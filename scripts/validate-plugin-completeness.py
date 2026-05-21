#!/usr/bin/env python3
"""validate-plugin-completeness.py — plugin が「丸ごとインストール」可能かを検査する。

Claude Code の /plugin install <name> は plugin ディレクトリ配下の
skills/ agents/ commands/ hooks/ をまとめて配布する。本スクリプトは:

  1. plugin ディレクトリに含まれる SKILL.md / agents/*.md / commands/*.md /
     hooks 定義 を列挙
  2. .claude-plugin/plugin.json の hooks 宣言と実体ファイルの整合
  3. README / .claude/ symlink との照合 (任意)

を行い、配布時に欠落するアセットがないことを保証する。
"""

from __future__ import annotations

import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGINS_DIR = ROOT / "plugins"
BUNDLES_JSON = ROOT / ".claude-plugin" / "bundles.json"


def load_bundle_members() -> set[str]:
    if not BUNDLES_JSON.exists():
        return set()
    data = json.loads(BUNDLES_JSON.read_text())
    members: set[str] = set()
    for b in data.get("bundles", []):
        for p in b.get("plugins", []):
            members.add(p)
    return members


def collect(plugin_dir: pathlib.Path) -> dict:
    out = {
        "skills": sorted(p.parent.name for p in plugin_dir.glob("skills/*/SKILL.md")),
        "agents": sorted(p.name for p in plugin_dir.glob("agents/*.md")),
        "commands": sorted(p.name for p in plugin_dir.glob("commands/*.md")),
        "hooks": sorted(p.name for p in plugin_dir.glob("hooks/*.sh")),
        "scripts": sorted(p.name for p in plugin_dir.rglob("scripts/**/*.py")),
        "config": sorted(p.name for p in plugin_dir.glob("config/*.json")),
    }
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    out["manifest"] = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    return out


def validate(plugin_name: str, data: dict, bundle_members: set[str]) -> list[str]:
    errs: list[str] = []
    m = data["manifest"]
    if m is None:
        errs.append(f"{plugin_name}: .claude-plugin/plugin.json missing")
        return errs

    for required in ("name", "version", "description"):
        if required not in m:
            errs.append(f"{plugin_name}: manifest missing '{required}'")

    if m.get("name") != plugin_name:
        errs.append(f"{plugin_name}: manifest.name '{m.get('name')}' != directory name")

    declared_hooks = set()
    for hook_event, entries in (m.get("hooks") or {}).items():
        for entry in entries:
            for h in entry.get("hooks", []):
                cmd = h.get("command", "")
                if "$CLAUDE_PLUGIN_ROOT/hooks/" in cmd:
                    declared_hooks.add(cmd.split("/hooks/", 1)[1])
    on_disk_hooks = set(data["hooks"])
    missing = declared_hooks - on_disk_hooks
    if missing:
        errs.append(f"{plugin_name}: manifest declares hooks not on disk: {sorted(missing)}")

    has_any_asset = any(data[k] for k in ("skills", "agents", "commands", "hooks", "scripts", "config"))
    if not has_any_asset:
        errs.append(f"{plugin_name}: plugin contains no assets — empty distribution")

    if plugin_name not in bundle_members:
        errs.append(f"{plugin_name}: not registered in any .claude-plugin/bundles.json bundle (BD-001/BND-001)")

    return errs


def main() -> int:
    if not PLUGINS_DIR.exists():
        print(f"ERROR: {PLUGINS_DIR} not found", file=sys.stderr)
        return 2

    bundle_members = load_bundle_members()
    all_errs: list[str] = []
    summary = []
    for plugin_dir in sorted(PLUGINS_DIR.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("."):
            continue
        data = collect(plugin_dir)
        errs = validate(plugin_dir.name, data, bundle_members)
        all_errs.extend(errs)
        summary.append(
            f"{plugin_dir.name}: skills={len(data['skills'])} "
            f"agents={len(data['agents'])} commands={len(data['commands'])} "
            f"hooks={len(data['hooks'])} scripts={len(data['scripts'])} config={len(data['config'])}"
        )

    for line in summary:
        print(line)
    print("---")
    if all_errs:
        for e in all_errs:
            print(f"VIOLATION {e}", file=sys.stderr)
        print(f"summary: VIOLATION={len(all_errs)}", file=sys.stderr)
        return 1
    print(f"OK: {len(summary)} plugin(s) complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
