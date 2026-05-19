"""output-routing.json + adapter-registry.json から task_kind に対するadapter解決。

stdlib のみ (CONVENTIONS.md §1 L2)。stdoutに {adapter, params, fallback, multi} のJSON出力。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ROUTING = REPO_ROOT / ".claude/config/output-routing.json"
REGISTRY = REPO_ROOT / ".claude/config/adapter-registry.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--routing", default=str(ROUTING))
    ap.add_argument("--registry", default=str(REGISTRY))
    args = ap.parse_args()

    routing_path = Path(args.routing)
    if not routing_path.exists():
        example = routing_path.with_name(routing_path.name + ".example")
        if example.exists():
            routing_path = example
        else:
            print(json.dumps({"status": "failure", "errors": [f"routing config not found: {args.routing}"]}))
            sys.exit(1)

    routing = json.loads(routing_path.read_text())
    registry = json.loads(Path(args.registry).read_text()) if Path(args.registry).exists() else {"adapters": []}

    routes = routing.get("routes", {})
    defaults = routing.get("defaults", {"adapter": "local"})

    route = routes.get(args.kind)
    if route is None:
        resolved = {
            "kind": args.kind,
            "adapter": defaults.get("adapter", "local"),
            "params": {},
            "fallback": defaults.get("fallback"),
            "multi": False,
            "_resolved_from": "defaults",
        }
    elif "adapters" in route:
        resolved = {
            "kind": args.kind,
            "adapters": route["adapters"],
            "params": route.get("params", {}),
            "fallback": route.get("fallback"),
            "multi": True,
            "_resolved_from": "multi-sink",
        }
    else:
        resolved = {
            "kind": args.kind,
            "adapter": route["adapter"],
            "params": route.get("params", {}),
            "fallback": route.get("fallback"),
            "multi": False,
            "_resolved_from": "route",
        }

    # adapter存在検証
    registered_names = {a["name"] for a in registry.get("adapters", [])}
    targets = resolved.get("adapters", [resolved.get("adapter")]) if resolved.get("multi") else [resolved.get("adapter")]
    for t in targets:
        if t and t not in registered_names:
            resolved.setdefault("warnings", []).append(f"adapter not registered: {t}")

    print(json.dumps(resolved, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
