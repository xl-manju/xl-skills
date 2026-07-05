#!/usr/bin/env python3
"""lint-vendor-parity.py — vendor byte-parity ゲート。

vendor/ 配下の byte 携行ツリー (scripts/ assets/ schemas-fixtures/ package.json
package-lock.json) を、plan 同梱の再現性アンカー ``vendor-digest-manifest.json``
(195 files sha256 pin) と照合する。移植元 live tree には依存しない。

additive_new_files (report 新規 Node: render-report.js / mermaid-render.js、
および vendor/tests/ 配下、manifest 自身) は parity 対象外 (excluded_additive)
であり、品質は tests_min + lint の別検査で担保する。

exit 0 = 全 pin 一致 (missing/mismatch 0)、exit 1 = 不一致あり。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(PLUGIN_ROOT, "vendor", "vendor-digest-manifest.json")

# manifest.subtrees[].source -> vendor/ 配下の実 target ディレクトリ/ファイル
SUBTREE_TARGETS = {
    "presentation-slide-generator/scripts/": "vendor/scripts/",
    "presentation-slide-generator/assets/": "vendor/assets/",
    "presentation-slide-generator/schemas/": "vendor/schemas-fixtures/",
    "presentation-slide-generator/package.json": "vendor/",
    "presentation-slide-generator/package-lock.json": "vendor/",
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if not os.path.exists(MANIFEST):
        print(f"FAIL: manifest not found: {MANIFEST}", file=sys.stderr)
        return 1
    manifest = json.load(open(MANIFEST, encoding="utf-8"))

    total = ok = missing = mismatch = 0
    for subtree in manifest.get("subtrees", []):
        target = SUBTREE_TARGETS.get(subtree["source"])
        if target is None:
            print(f"FAIL: unmapped manifest subtree source: {subtree['source']}", file=sys.stderr)
            return 1
        for filename, digest in subtree.get("files", {}).items():
            total += 1
            path = os.path.join(PLUGIN_ROOT, target, filename)
            if not os.path.exists(path):
                missing += 1
                print(f"MISSING {target}{filename}", file=sys.stderr)
            elif sha256(path) != digest:
                mismatch += 1
                print(f"MISMATCH {target}{filename}", file=sys.stderr)
            else:
                ok += 1

    result = "PASS" if (missing == 0 and mismatch == 0) else "FAIL"
    print(f"vendor byte-parity: total={total} ok={ok} missing={missing} mismatch={mismatch} -> {result}")
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
