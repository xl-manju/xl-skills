#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aggregate-evals.py

SessionEnd hook から発火し、plugins/skill-creator/EVALS.json を集計する。
閾値超え変動 (連続 FAIL / 平均スコア低下) を検出したら
run-skill-rubric-governance/proposals/ に rubric-update 提案ドラフトを書き出す。

副作用境界:
    - proposals/ ディレクトリへの書き込みのみ。git は触らない。

exit_code 仕様 (Claude Code Hooks 準拠):
    0  非ブロック (正常 / 提案不要 / 提案書き込み成功)
    2  明示拒否 (本 hook は使用しない)
    その他 非ブロック警告

閾値:
    - 同一 rubric_id (skill) で直近 3 連続 verdict=FAIL
    - 同一 rubric_id の平均スコアが直近窓で 0.1 以上低下
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_CONSECUTIVE_FAIL_THRESHOLD = 3
_SCORE_DROP_THRESHOLD = 0.1
_RECENT_WINDOW = 5  # 直近窓


def _plugin_root() -> Path:
    # 本ファイル: plugins/skill-creator/skills/run-skill-rubric-governance/scripts/
    return Path(__file__).resolve().parents[3]


def _repo_root() -> Path:
    # _plugin_root() == <repo>/plugins/skill-creator なので parent.parent が repo root。
    return _plugin_root().parent.parent


def _eval_log_dir() -> Path:
    # write-eval-log.py の sink 基底と一致: <repo>/eval-log/
    return _repo_root() / "eval-log"


def _evals_path() -> Path:
    return _plugin_root() / "EVALS.json"


def _proposals_dir() -> Path:
    return (
        _plugin_root()
        / "skills"
        / "run-skill-rubric-governance"
        / "proposals"
    )


def _date_of(ts: Any) -> str | None:
    # "2026-06-06T19:59:43+0900" / "2026-06-01T00:00:00Z" -> "2026-06-06"
    if not isinstance(ts, str) or not ts:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", ts)
    return m.group(1) if m else None


def _normalize_score_record(rec: dict[str, Any]) -> dict[str, Any] | None:
    """write-eval-log.py の score.jsonl 1行を共通形へ。

    sink schema: rubric{rubric_id,...} / score / passed / findings / skill_name / timestamp
    -> {skill, date, verdict, score, findings}
    """
    if not isinstance(rec, dict):
        return None
    rubric = rec.get("rubric") if isinstance(rec.get("rubric"), dict) else {}
    skill = rec.get("skill_name") or rubric.get("rubric_id")
    if not skill:
        return None
    passed = rec.get("passed")
    if passed is True:
        verdict = "PASS"
    elif passed is False:
        verdict = "FAIL"
    else:
        verdict = str(rec.get("verdict", ""))
    return {
        "skill": skill,
        "date": _date_of(rec.get("timestamp")),
        "verdict": verdict,
        "score": rec.get("score"),
        "findings": rec.get("findings", []) or [],
    }


def _normalize_verdict_record(rec: dict[str, Any]) -> dict[str, Any] | None:
    """content-review verdict.json を共通形へ。

    verdict schema: target{plugin,skill} / verdict(PASS|FAIL|INCOMPLETE) / reviewed_at
    -> {skill, date, verdict, score, findings}
    """
    if not isinstance(rec, dict):
        return None
    target = rec.get("target") if isinstance(rec.get("target"), dict) else {}
    skill = target.get("skill")
    if not skill:
        return None
    return {
        "skill": skill,
        "date": _date_of(rec.get("reviewed_at")),
        "verdict": str(rec.get("verdict", "")),
        "score": None,  # verdict は数値スコアを持たない
        "findings": [],
    }


def _load_score_jsonl() -> list[dict[str, Any]]:
    """eval-log/<plugin>/<date>-score.jsonl (write-eval-log の実 sink) を全件読む。"""
    out: list[dict[str, Any]] = []
    base = _eval_log_dir()
    if not base.exists():
        return out
    try:
        paths = sorted(base.glob("**/*-score.jsonl"))
    except OSError:
        return out
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            norm = _normalize_score_record(rec)
            if norm is not None:
                out.append(norm)
    return out


def _load_content_review_verdicts() -> list[dict[str, Any]]:
    """eval-log/<plugin>/<skill>/content-review/*-verdict.json を全件読む。"""
    out: list[dict[str, Any]] = []
    base = _eval_log_dir()
    if not base.exists():
        return out
    try:
        paths = sorted(base.glob("**/content-review/*-verdict.json"))
    except OSError:
        return out
    for path in paths:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        norm = _normalize_verdict_record(rec)
        if norm is not None:
            out.append(norm)
    return out


def _load_evals() -> dict[str, Any]:
    """評価レコードを 3 ソースから集約。

    1) EVALS.json#/evaluations[]   (従来。誰も書かない可能性が高い旧経路)
    2) eval-log/<plugin>/<date>-score.jsonl       (write-eval-log の実 sink)
    3) eval-log/<plugin>/<skill>/content-review/*-verdict.json  (content-review verdict)

    いずれも {skill,date,verdict,score,findings} 形へ正規化済みで concat する。
    新 writer は作らず既存 writer の出力を読むだけ (重複writer回避)。
    各ソースは防御的に skip (無ければ空)。
    """
    evals: list[dict[str, Any]] = []

    # 1) 従来 EVALS.json
    p = _evals_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            for ev in data.get("evaluations", []) or []:
                if isinstance(ev, dict):
                    evals.append(ev)
        except (OSError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"[aggregate-evals] EVALS.json load failed: {exc}\n")

    # 2) write-eval-log の実 sink (score.jsonl)
    try:
        evals.extend(_load_score_jsonl())
    except Exception as exc:  # 非ブロック (SessionEnd 流儀)
        sys.stderr.write(f"[aggregate-evals] score.jsonl load failed: {exc}\n")

    # 3) content-review verdict
    try:
        evals.extend(_load_content_review_verdicts())
    except Exception as exc:  # 非ブロック
        sys.stderr.write(f"[aggregate-evals] verdict load failed: {exc}\n")

    return {"evaluations": evals}


def _verdict_is_fail(verdict: str) -> bool:
    return verdict.upper() in {"FAIL", "FAILED", "REJECT", "REJECTED"}


def _score_of(ev: dict[str, Any]) -> float | None:
    # score / overall / mean 等が来る可能性に備える。
    for k in ("score", "overall", "mean_score", "average"):
        v = ev.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _detect_anomalies(evals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """rubric_id (= skill) 単位で異常を検出。"""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in evals:
        sk = ev.get("skill") or ev.get("rubric_id")
        if not sk:
            continue
        grouped[sk].append(ev)

    anomalies: list[dict[str, Any]] = []
    for rubric_id, items in grouped.items():
        # date 昇順で安定ソート (欠損は末尾)。
        items_sorted = sorted(items, key=lambda x: x.get("date") or "")
        # 1) 連続 FAIL
        tail = items_sorted[-_CONSECUTIVE_FAIL_THRESHOLD:]
        if len(tail) >= _CONSECUTIVE_FAIL_THRESHOLD and all(
            _verdict_is_fail(str(x.get("verdict", ""))) for x in tail
        ):
            anomalies.append(
                {
                    "rubric_id": rubric_id,
                    "kind": "consecutive_fail",
                    "count": _CONSECUTIVE_FAIL_THRESHOLD,
                    "evidence_dates": [x.get("date") for x in tail],
                }
            )
        # 2) 平均スコア低下 (直近窓 vs それ以前)。
        scores = [(x.get("date"), _score_of(x)) for x in items_sorted]
        scored = [(d, s) for d, s in scores if s is not None]
        if len(scored) >= _RECENT_WINDOW + 1:
            recent = [s for _, s in scored[-_RECENT_WINDOW:]]
            prior = [s for _, s in scored[:-_RECENT_WINDOW]]
            if recent and prior:
                drop = (sum(prior) / len(prior)) - (sum(recent) / len(recent))
                if drop >= _SCORE_DROP_THRESHOLD:
                    anomalies.append(
                        {
                            "rubric_id": rubric_id,
                            "kind": "score_drop",
                            "drop": round(drop, 3),
                            "recent_mean": round(sum(recent) / len(recent), 3),
                            "prior_mean": round(sum(prior) / len(prior), 3),
                        }
                    )
    return anomalies


def _top_finding_categories(evals: list[dict[str, Any]]) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for ev in evals:
        for f in ev.get("findings", []) or []:
            cat = None
            if isinstance(f, dict):
                cat = f.get("category") or f.get("rule") or f.get("kind")
            elif isinstance(f, str):
                cat = f
            if cat:
                counter[str(cat)] += 1
    return counter.most_common(5)


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.lower()).strip("-")
    return s or "rubric"


def _render_proposal(
    anomalies: list[dict[str, Any]],
    top_findings: list[tuple[str, int]],
    summary: dict[str, Any],
) -> str:
    today = _dt.date.today().isoformat()
    lines = [
        "---",
        f"date: {today}",
        "kind: rubric-update-proposal",
        "status: draft",
        f"trigger: aggregate-evals (SessionEnd)",
        "---",
        "",
        "# rubric 更新提案 (自動生成ドラフト)",
        "",
        "## 集計サマリ",
        "",
        f"- 評価件数: {summary.get('total', 0)}",
        f"- FAIL 率: {summary.get('fail_rate', 0.0):.2%}",
        f"- 平均スコア: {summary.get('mean_score', 'n/a')}",
        "",
        "## 検出された異常",
        "",
    ]
    if not anomalies:
        lines.append("- (なし)")
    else:
        for a in anomalies:
            lines.append(f"- **{a['rubric_id']}**: {a['kind']} — {json.dumps({k: v for k, v in a.items() if k not in ('rubric_id','kind')}, ensure_ascii=False)}")
    lines += ["", "## 主要 finding カテゴリ (top5)", ""]
    if not top_findings:
        lines.append("- (なし)")
    else:
        for cat, n in top_findings:
            lines.append(f"- {cat}: {n} 件")
    lines += [
        "",
        "## 提案アクション (要 human review)",
        "",
        "- 該当 rubric_id の閾値 / 観点を見直し",
        "- 主要 finding カテゴリに対応する評価項目を新設または重み調整",
        "- 関連する run-* / assign-* Skill の templates を更新",
        "",
        "## 備考",
        "",
        "本ドラフトは aggregate-evals.py により自動生成された。PR 起票は別工程。",
        "",
    ]
    return "\n".join(lines)


def _compute_summary(evals: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(evals)
    fails = sum(1 for e in evals if _verdict_is_fail(str(e.get("verdict", ""))))
    scores = [_score_of(e) for e in evals]
    scores = [s for s in scores if s is not None]
    return {
        "total": total,
        "fail_rate": (fails / total) if total else 0.0,
        "mean_score": round(sum(scores) / len(scores), 3) if scores else "n/a",
    }


def main() -> int:
    # stdin は SessionEnd hook payload。本 script では使わないが drain しておく。
    try:
        sys.stdin.read()
    except Exception:
        pass

    data = _load_evals()
    evals = data.get("evaluations", []) or []
    if not evals:
        return 0

    anomalies = _detect_anomalies(evals)
    if not anomalies:
        return 0

    summary = _compute_summary(evals)
    top_findings = _top_finding_categories(evals)
    proposal = _render_proposal(anomalies, top_findings, summary)

    out_dir = _proposals_dir()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.stderr.write(f"[aggregate-evals] proposals dir creation failed: {exc}\n")
        return 1

    today = _dt.date.today().isoformat()
    # 同日複数発火に備え、内容ハッシュではなく単純な upsert (上書き) でドラフトを更新。
    target = out_dir / f"{today}-rubric-update.md"
    try:
        target.write_text(proposal, encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(f"[aggregate-evals] write failed: {exc}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
