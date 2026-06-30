#!/usr/bin/env python3
# /// script
# name: render-spec-skeleton
# purpose: specfm の実行可能契約から component_kind 別の最小 Markdown skeleton を生成する。
# inputs:
#   - argv: --kind KIND [--skill-kind run|ref|wrap|assign|delegate] [--id C01]
# outputs:
#   - stdout: Markdown skeleton
#   - exit: 0=OK / 2=usage error
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""静的ひな形ファイルを増やさず、specfm の正本から skeleton を生成する。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="component_kind 別の最小 spec skeleton を生成する")
    ap.add_argument("--kind", required=True, choices=specfm.COMPONENT_KINDS, help="component_kind")
    ap.add_argument("--skill-kind", default="run", choices=specfm.SKILL_KINDS, help="skill kind")
    ap.add_argument("--id", default="C01", help="spec id")
    args = ap.parse_args(argv)
    sys.stdout.write(specfm.render_minimal_spec(args.kind, spec_id=args.id, skill_kind=args.skill_kind))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
