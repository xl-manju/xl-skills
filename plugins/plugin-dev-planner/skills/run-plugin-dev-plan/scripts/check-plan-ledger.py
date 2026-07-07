#!/usr/bin/env python3
# /// script
# name: check-plan-ledger
# purpose: plugin-plans/<slug>/plan-ledger.json の cycle_id 形式・status 値域・非空・同時 active 高々1件を fail-closed 検証する (C13)。
# inputs:
#   - argv: <plugin-plans>/<slug>/plan-ledger.json
# outputs:
#   - stdout: OK summary もしくは violation 列挙
#   - exit: 0=OK / 1=violation / 2=usage error (not found / JSON parse / root shape)
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""plan-ledger.json (改善周回台帳) の fail-closed バリデータ (C13)。

複数改善周回 (cycle) が同一 plugin へ並走するとき、build dir スコープ化と衝突排除の
単一正本が plan-ledger.json である。本 script は台帳形状 (cycle_id 形式 / status 値域 /
plan_dir・summary 非空) と「同時 active は高々 1 件」不変条件を検証する。同時 active の
2 件以上は非決定的な自動解決をせず violation として fail-closed で弾く (どちらを active に
残すかの判断を機械が勝手に下さない)。cycle_id 形式・status 値域は specfm の SSOT を参照する。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import specfm  # noqa: E402


def validate_ledger(ledger: dict) -> list[str]:
    """plan-ledger.json (dict) を検証し違反メッセージのリストを返す (空=妥当)。

    検査 (io-contract / plan-ledger.schema.json と整合):
      (a) 各 entries[].cycle_id が specfm.CYCLE_ID_RE に一致
      (b) 各 entries[].status が specfm.LEDGER_STATUSES の値域内
      (c) plan_dir / summary が非空文字列
      (d) status=="active" のエントリが台帳全体で高々 1 件
    """
    errs: list[str] = []
    if not isinstance(ledger, dict):
        return ["plan-ledger root が object でない"]

    entries = ledger.get("entries")
    if not isinstance(entries, list):
        return ["plan-ledger.entries が配列でない (entries: [] を最低限持つこと)"]

    active_ids: list[str] = []
    for idx, entry in enumerate(entries):
        prefix = f"entries[{idx}]"
        if not isinstance(entry, dict):
            errs.append(f"{prefix} が object でない")
            continue

        cid = str(entry.get("cycle_id", "")).strip()
        if not cid:
            errs.append(f"{prefix}.cycle_id が空")
        elif not specfm.CYCLE_ID_RE.match(cid):
            errs.append(f"{prefix}.cycle_id={cid!r} は {specfm.CYCLE_ID_RE.pattern} に不一致")

        status = str(entry.get("status", "")).strip()
        if status not in specfm.LEDGER_STATUSES:
            errs.append(f"{prefix}.status={status!r} が値域外 {list(specfm.LEDGER_STATUSES)}")

        plan_dir = entry.get("plan_dir")
        if not (isinstance(plan_dir, str) and plan_dir.strip()):
            errs.append(f"{prefix}.plan_dir が非空文字列でない")

        summary = entry.get("summary")
        if not (isinstance(summary, str) and summary.strip()):
            errs.append(f"{prefix}.summary が非空文字列でない")

        if status == "active":
            active_ids.append(cid or f"<{prefix}>")

    if len(active_ids) > 1:
        errs.append(
            f"同時 active 重複: status=='active' は台帳全体で高々 1 件 (現 {len(active_ids)} 件: "
            f"{active_ids}) — 非決定的な自動解決はしない (fail-closed)"
        )
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="plan-ledger.json を検証する (C13)")
    ap.add_argument("ledger", help="<plugin-plans>/<slug>/plan-ledger.json")
    args = ap.parse_args(argv)

    path = Path(args.ledger)
    if not path.is_file():
        sys.stderr.write(f"plan-ledger not found: {path}\n")
        return 2
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        sys.stderr.write(f"plan-ledger read/parse error: {exc}\n")
        return 2

    errs = validate_ledger(ledger)
    if not errs:
        n = len(ledger.get("entries", [])) if isinstance(ledger, dict) else 0
        sys.stdout.write(f"OK: plan-ledger 妥当 (entries={n} / 同時 active <=1)\n")
        return 0
    for err in errs:
        sys.stdout.write(err + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
