#!/usr/bin/env python3
"""Verify creator-kit/manifest.json matches files present in the kit."""
from __future__ import annotations

import json
import sys
from pathlib import Path


KIT_DIR = Path(__file__).resolve().parents[1]
MANIFEST = KIT_DIR / "manifest.json"
SETTINGS_EXAMPLE = KIT_DIR / "config" / "claude-settings-hooks.json.example"


def expect(path: Path, findings: list[str]) -> None:
    if not path.exists() and not path.is_symlink():
        findings.append(f"missing: {path.relative_to(KIT_DIR)}")


def main() -> int:
    manifest = json.loads(MANIFEST.read_text())
    findings: list[str] = []

    for skill in manifest.get("skills", []):
        expect(KIT_DIR / "skills" / skill["name"] / "SKILL.md", findings)

    for agent in manifest.get("agents", []):
        source = agent.get("source") or f"agents/{agent['name']}.md"
        expect(KIT_DIR / source, findings)
        target = agent.get("path", "")
        if target and not target.startswith(".claude/agents/"):
            findings.append(f"agent target must be under .claude/agents/: {target}")

    scripts = manifest.get("scripts", {})
    script_group_dirs = {
        "adapters": KIT_DIR / "scripts" / "adapters",
        "secrets": KIT_DIR / "scripts" / "secrets",
        "migrate": KIT_DIR / "scripts" / "migrate",
    }
    for group, names in scripts.items():
        base_dir = script_group_dirs.get(group, KIT_DIR / "scripts")
        for name in names:
            expect(base_dir / name, findings)

    for config in manifest.get("config", []):
        expect(KIT_DIR / config["source"], findings)

    if SETTINGS_EXAMPLE.exists():
        settings = json.loads(SETTINGS_EXAMPLE.read_text(encoding="utf-8"))
        deny = settings.get("permissions", {}).get("deny", [])
        if not deny:
            findings.append("config/claude-settings-hooks.json.example missing permissions.deny")
        hooks = settings.get("hooks", {})
        if "FileChanged" not in hooks:
            findings.append("config/claude-settings-hooks.json.example missing FileChanged hook")
        if "TaskCreated" not in hooks:
            findings.append("config/claude-settings-hooks.json.example missing TaskCreated hook")

    if findings:
        for finding in findings:
            print(finding)
        return 1

    # C-5 freshness check
    warnings: list[str] = []
    check_yaml_spec_freshness(warnings)
    for w in warnings:
        print(w)
    print("OK: manifest contents match creator-kit files")
    return 0



# ---- C-5: yaml-spec-cache.md last_fetched 30日超過警告 ----
def check_yaml_spec_freshness(findings_warn: list[str]) -> None:
    """yaml-spec-cache.md の last_fetched が 30 日超過なら WARNING を stdout に出力."""
    import datetime
    cache_paths = [
        Path(__file__).resolve().parents[1]
        / ".claude" / "skills" / "ref-yaml-spec-fetcher" / "references" / "yaml-spec-cache.md",
    ]
    for cache_path in cache_paths:
        if not cache_path.exists():
            continue
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("last_fetched:"):
                ts_str = line.split(":", 1)[1].strip()
                try:
                    fetched_at = datetime.datetime.fromisoformat(
                        ts_str.replace("Z", "+00:00")
                    )
                    age_days = (
                        datetime.datetime.now(datetime.timezone.utc) - fetched_at
                    ).days
                    if age_days > 30:
                        findings_warn.append(
                            f"WARNING: yaml-spec-cache.md last_fetched={ts_str} "
                            f"is {age_days} days old (> 30 days). "
                            f"Run scripts/build-yaml-spec-cache.py to refresh."
                        )
                except (ValueError, TypeError):
                    pass
                break

if __name__ == "__main__":
    sys.exit(main())
