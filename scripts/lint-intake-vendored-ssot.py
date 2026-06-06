#!/usr/bin/env python3
"""skill-intake に同梱 (vendored) した共有 SSOT が skill-creator 正本と一致するか検証する。

背景: skill-intake は単独インストールで intake→Notion publish のコアフローが自己完結動作する
ことを要件とする (不特定多数が `skill-intake` のみを install する想定)。このため、従来
skill-creator へ symlink していた共有ローダ `notion_config.py` を skill-intake/scripts/ に
実体コピー (vendoring) した。symlink は plugin 境界を越えるため単独 install で dangling になる。

二重実体は drift (内容乖離) リスクを生む。本 lint は「skill-intake 版 == skill-creator 版」を
byte 単位で機械検証し、乖離していれば exit 1。再同期は `scripts/sync-intake-vendored.sh`。

正本 (canonical) = skill-creator 側。vendored = skill-intake 側。
notion_config.py は runtime 中核のため byte 一致を強制する。doc (setup.md) は plugin 別に
パスをローカライズするため本 lint の対象外 (役割分担: コードは一致強制 / doc は localized)。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (canonical 正本, vendored 複製) のペア。byte 一致を強制する runtime SSOT のみ。
VENDORED_PAIRS = [
    (
        ROOT / "plugins" / "skill-creator" / "scripts" / "notion_config.py",
        ROOT / "plugins" / "skill-intake" / "scripts" / "notion_config.py",
    ),
]


def main():
    failures = []
    for canonical, vendored in VENDORED_PAIRS:
        rel_c = canonical.relative_to(ROOT)
        rel_v = vendored.relative_to(ROOT)
        if not canonical.exists():
            failures.append(f"canonical 不在: {rel_c}")
            continue
        if not vendored.exists():
            failures.append(
                f"vendored 不在: {rel_v} (skill-intake 単独 install 用の同梱が欠落)。"
                f" `bash scripts/sync-intake-vendored.sh` で再同期。"
            )
            continue
        # symlink に戻っていないか (単独 install で壊れる回帰を検出)。
        if vendored.is_symlink():
            failures.append(
                f"vendored が symlink に回帰: {rel_v} -> {vendored.readlink()}。"
                f" 単独 install で dangling になる。実体コピーへ戻すこと。"
            )
            continue
        if canonical.read_bytes() != vendored.read_bytes():
            failures.append(
                f"SSOT drift: {rel_v} が正本 {rel_c} と不一致。"
                f" `bash scripts/sync-intake-vendored.sh` で正本から再同期。"
            )

    if failures:
        sys.stderr.write("[lint-intake-vendored-ssot] FAIL\n")
        for f in failures:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print(f"[lint-intake-vendored-ssot] OK: vendored SSOT {len(VENDORED_PAIRS)} 件が正本と byte 一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
