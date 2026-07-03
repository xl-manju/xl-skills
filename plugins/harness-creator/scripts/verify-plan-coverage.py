#!/usr/bin/env python3
# /// script
# name: verify-plan-coverage
# purpose: component-inventory.json (計画) と plugin のディスク実体を照合し、計画に
#          あって未 build の component / 未生成の required plugin-level surface を検出
#          する決定論 completeness gate。「同じ計画から漏れなく同じ Capability 集合が
#          生成されたか」を機械判定し、目視・AI 照合の非再現を排除する。
# inputs:
#   - argv: <component-inventory.json> [--repo-root <dir>] [--json]
# outputs:
#   - stdout: OK summary / JSON report (--json)
#   - stderr: coverage violations (未 build component / 未生成 surface)
#   - exit: 0=全 build 済 / 1=漏れあり / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""計画 (component-inventory.json) ↔ plugin 実体の completeness 照合。

背景: harness-creator の標準フローは
  /plugin-dev-plan → (routes[] を 1 個ずつ build) → /plugin-compose
  → /run-plugin-package-check
という連結で「総体を漏れなく組む」。このうち「計画にあって未 build の component が
無いか」の照合を README は『漏れなく』を測る唯一の gate と呼ぶが、従来は
plugin-compose の doc に「照合する」と散文で書かれるのみで実装が無く、AI の目視判断
に落ちていた (非再現)。plugin-compose Step2 は実体から capabilities[] を再計算する
ため、fan-out が component を 1 個落としても欠落が静かに消え、下流 (Step3/4/5) は
実在物しか見ないので「計画に対する漏れ」を誰も捕捉できない。本 script はその照合を
決定論化し、fail-closed (漏れ検出で exit 1) にする。

- check-surface-inventory.py (plugin-dev-planner) は inventory の *内部整合*
  (5 kind 検討証跡・surface 採否理由) を見る。本 script は *計画↔ディスク実体* を
  照合する (相補・別レイヤー)。
- check-build-handoff.py の inventory provenance は routes(計画)==inventory(計画)
  の計画内整合を見る。本 script は inventory(計画)==build(実体) を見る (別軸)。
- 実体が真実: trace・自己申告でなく build_target のディスク実在を検査する。

Exit 0 = 全 component + required surface が実在, 1 = 漏れあり, 2 = usage error。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# component_kind のうち build_target がディレクトリ (skill dir) になるもの。
# それ以外 (sub-agent/slash-command/hook/script) は単一ファイル。
_DIR_KINDS = {"skill"}


def _plugin_root_of(build_target: str) -> str | None:
    """build_target 'plugins/<plugin>/...' から 'plugins/<plugin>' を抽出する。

    build_target が plugins/ 配下でない (想定外) 場合は None。
    """
    parts = Path(build_target).parts
    if len(parts) >= 2 and parts[0] == "plugins":
        return str(Path(parts[0]) / parts[1])
    return None


def _target_exists(repo_root: Path, build_target: str, component_kind: str) -> tuple[bool, str]:
    """build_target のディスク実在を判定する。

    skill (ディレクトリ) は配下 SKILL.md も要求する。戻り値 (exists, detail)。
    """
    p = repo_root / build_target
    is_dir_target = build_target.rstrip().endswith("/") or component_kind in _DIR_KINDS
    if is_dir_target:
        if not p.is_dir():
            return False, "ディレクトリ不在"
        if component_kind in _DIR_KINDS and not (p / "SKILL.md").exists():
            return False, "SKILL.md 不在"
        return True, "ok"
    if not p.exists():
        return False, "ファイル不在"
    return True, "ok"


def verify(inventory: dict, repo_root: Path) -> tuple[list[str], list[str], dict]:
    """(missing_components, missing_surfaces, summary) を返す。

    missing_components: 計画にあって未 build の component (id/kind/理由)。
    missing_surfaces:   required=true だが未生成の plugin-level surface。
    """
    missing_components: list[str] = []
    components = inventory.get("components") or []
    plugin_roots: set[str] = set()

    for comp in components:
        if not isinstance(comp, dict):
            missing_components.append(f"? : component が object でない ({comp!r})")
            continue
        cid = comp.get("id", "?")
        kind = comp.get("component_kind", "")
        bt = comp.get("build_target", "")
        if not bt:
            missing_components.append(f"{cid} ({kind}): build_target 未宣言")
            continue
        pr = _plugin_root_of(bt)
        if pr:
            plugin_roots.add(pr)
        ok, detail = _target_exists(repo_root, bt, kind)
        if not ok:
            missing_components.append(f"{cid} ({kind}): {bt} — {detail}")

    # plugin-level surface 照合 (required=true かつ path を持つもののみ)。plugin-root
    # は build_target 群から導出する (1 inventory = 1 plugin 前提)。
    missing_surfaces: list[str] = []
    skipped_surfaces: list[str] = []
    surfaces = inventory.get("plugin_level_surfaces") or {}
    if len(plugin_roots) == 1:
        pr = Path(next(iter(plugin_roots)))
        for name, spec in surfaces.items():
            if not isinstance(spec, dict) or not spec.get("required"):
                continue
            rel = spec.get("path")
            if not rel:
                # path を持たない required surface (record_in / resolution 型:
                # Notion config・index 記録先など) はファイル実在照合の対象外。宣言
                # そのものの妥当性は check-surface-inventory.py (inventory 内部整合)
                # が担う。責務分離のため本 gate は skip する。
                skipped_surfaces.append(name)
                continue
            if not (repo_root / pr / rel).exists():
                missing_surfaces.append(f"{name}: {pr}/{rel} 不在")
    elif len(plugin_roots) > 1:
        missing_surfaces.append(
            f"build_target が複数 plugin を跨ぐ ({sorted(plugin_roots)})。"
            "1 inventory = 1 plugin が前提のため surface 照合を実行できない。"
        )
    # plugin_roots が空 (components 全滅 or 空) の場合、surface 照合は対象なし。

    summary = {
        "components_total": len(components),
        "components_missing": len(missing_components),
        "surfaces_missing": len(missing_surfaces),
        "surfaces_skipped": sorted(skipped_surfaces),
        "plugin_roots": sorted(plugin_roots),
    }
    return missing_components, missing_surfaces, summary


def _self_test() -> int:
    import tempfile

    inv = {
        "components": [
            {"id": "C01", "component_kind": "skill",
             "build_target": "plugins/demo/skills/run-demo/"},
            {"id": "C04", "component_kind": "sub-agent",
             "build_target": "plugins/demo/agents/demo-verifier.md"},
            {"id": "C09", "component_kind": "script",
             "build_target": "plugins/demo/scripts/demo-check.py"},
        ],
        "plugin_level_surfaces": {
            "manifest": {"required": True, "path": ".claude-plugin/plugin.json"},
            "composition": {"required": True, "path": "plugin-composition.yaml"},
            "schemas": {"required": False, "omitted_reason": "n/a"},
            # path を持たない required surface (実在照合の対象外・skip される)
            "notion_config": {"required": True, "resolution": "notion_config"},
        },
    }
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "plugins/demo/skills/run-demo").mkdir(parents=True)
        (root / "plugins/demo/skills/run-demo/SKILL.md").write_text("x", encoding="utf-8")
        (root / "plugins/demo/agents").mkdir(parents=True)
        (root / "plugins/demo/agents/demo-verifier.md").write_text("x", encoding="utf-8")
        (root / "plugins/demo/scripts").mkdir(parents=True)
        (root / "plugins/demo/scripts/demo-check.py").write_text("x", encoding="utf-8")
        (root / "plugins/demo/.claude-plugin").mkdir(parents=True)
        (root / "plugins/demo/.claude-plugin/plugin.json").write_text("{}", encoding="utf-8")
        (root / "plugins/demo/plugin-composition.yaml").write_text("x", encoding="utf-8")

        # 1. 全実体あり → 漏れなし。path 無し required surface (notion_config) は
        #    実在照合の対象外として skip される (missing に入らない)。
        mc, ms, summ = verify(inv, root)
        assert not mc, mc
        assert not ms, ms
        assert summ["components_total"] == 3
        assert "notion_config" in summ["surfaces_skipped"], summ

        # 2. skill dir はあるが SKILL.md 欠落 → component missing
        (root / "plugins/demo/skills/run-demo/SKILL.md").unlink()
        mc, ms, _ = verify(inv, root)
        assert any("C01" in e and "SKILL.md" in e for e in mc), mc
        (root / "plugins/demo/skills/run-demo/SKILL.md").write_text("x", encoding="utf-8")

        # 3. required surface (composition) 欠落 → surface missing
        (root / "plugins/demo/plugin-composition.yaml").unlink()
        mc, ms, _ = verify(inv, root)
        assert not mc, mc
        assert any("composition" in e for e in ms), ms
        (root / "plugins/demo/plugin-composition.yaml").write_text("x", encoding="utf-8")

        # 4. agent 未 build (計画にあって実体なし) → component missing
        (root / "plugins/demo/agents/demo-verifier.md").unlink()
        mc, ms, _ = verify(inv, root)
        assert any("C04" in e for e in mc), mc

    # 5. build_target 未宣言
    mc, ms, _ = verify({"components": [{"id": "Cx", "component_kind": "hook"}]}, Path("/nonexistent"))
    assert any("Cx" in e and "build_target" in e for e in mc), mc

    # 6. 複数 plugin 跨ぎ検出
    inv2 = {
        "components": [
            {"id": "C1", "component_kind": "script", "build_target": "plugins/a/scripts/x.py"},
            {"id": "C2", "component_kind": "script", "build_target": "plugins/b/scripts/y.py"},
        ],
        "plugin_level_surfaces": {"manifest": {"required": True, "path": ".claude-plugin/plugin.json"}},
    }
    _, ms, _ = verify(inv2, Path("/nonexistent"))
    assert any("跨ぐ" in e for e in ms), ms

    # 7. 空 components → 漏れなし (照合対象なし)
    mc, ms, _ = verify({"components": [], "plugin_level_surfaces": {}}, Path("/nonexistent"))
    assert not mc and not ms

    print("OK: verify-plan-coverage self-test (7 groups)")
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return _self_test()

    def _opt(name: str) -> str | None:
        if name in argv:
            i = argv.index(name)
            if i + 1 < len(argv):
                return argv[i + 1]
        return None

    repo_root_val = _opt("--repo-root")
    # 位置引数 = ハイフン始まりでなく、--repo-root の値でもないもの。
    positional = [
        a for a in argv
        if not a.startswith("-") and a != repo_root_val
    ]

    if not positional:
        print(
            "usage: verify-plan-coverage.py <component-inventory.json> "
            "[--repo-root <dir>] [--json]",
            file=sys.stderr,
        )
        return 2

    inv_path = Path(positional[0])
    repo_root = Path(repo_root_val) if repo_root_val else Path.cwd()

    if not inv_path.exists():
        print(f"component-inventory.json not found: {inv_path}", file=sys.stderr)
        return 2
    try:
        inventory = json.loads(inv_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"JSON parse error: {exc}", file=sys.stderr)
        return 2
    if not isinstance(inventory, dict):
        print("component-inventory root が object でない", file=sys.stderr)
        return 2

    missing_components, missing_surfaces, summary = verify(inventory, repo_root)
    ok = not (missing_components or missing_surfaces)

    if "--json" in argv:
        print(json.dumps(
            {
                "ok": ok,
                "summary": summary,
                "missing_components": missing_components,
                "missing_surfaces": missing_surfaces,
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 0 if ok else 1

    if not ok:
        print(
            f"FAIL: plan coverage — 計画にあって未 build "
            f"({len(missing_components)} component / {len(missing_surfaces)} surface)",
            file=sys.stderr,
        )
        for e in missing_components:
            print(f"  - [component] {e}", file=sys.stderr)
        for e in missing_surfaces:
            print(f"  - [surface] {e}", file=sys.stderr)
        print(
            "  → routes[] の build を完了させるか、計画側 (component-inventory.json) から"
            " 当該 component を除外して再実行する。plugin-compose の実体再計算では"
            "『計画に対する漏れ』は検出できず、本 gate だけが担う。",
            file=sys.stderr,
        )
        return 1

    print(
        f"OK: plan coverage — {summary['components_total']} component "
        f"+ required surface すべて実在 "
        f"({', '.join(summary['plugin_roots']) or 'n/a'})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
