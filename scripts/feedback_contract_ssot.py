#!/usr/bin/env python3
# /// script
# name: feedback_contract_ssot
# purpose: feedback_contract.criteria 制約の単一正本 (SSOT)。複数 lint/validator が共有する。
# inputs: []  (import 専用モジュール。CLI なし)
# outputs: []
# requires-python = ">=3.10"
# dependencies: []
# contexts: [A, B, C, D, E]
# network: false
# write-scope: none
# ///
"""feedback_contract.criteria の制約を一箇所に集約した SSOT モジュール。

従来 `id` の pattern / `verify_by` の enum / `loop_scope` / 必須キーは
  - build-flags.schema.json#/properties/feedback_contract
  - skill-build-trace.schema.json#/properties/feedback_contract
  - validate-build-trace.py の CRITERIA_ID_RE / CRITERIA_VERIFY_BY
の3者にミラーされ「値を変える際は3者同時更新」という drift 温床だった。
本モジュールを唯一の正本とし、validate-build-trace.py / lint-feedback-contract.py /
lint-content-review.py が import して共有する (Python による機械 SSOT)。

JSON schema 側は cross-file $ref をハンドロール validator が解決できないため、
本モジュールを正本とし schema の制約記述は「正本=feedback_contract_ssot.py」と注記する。
"""
from __future__ import annotations

import re

# --- criteria 単一正本 (この4定数が唯一の真実) ---
CRITERIA_ID_RE = re.compile(r"^(IN|OUT|C)[0-9]+$")
CRITERIA_VERIFY_BY = {"lint", "test", "script", "evaluator", "elegant-review", "human"}
LOOP_SCOPES = {"inner", "outer"}
REQUIRED_CRITERION_KEYS = ("id", "loop_scope", "text", "verify_by")

# --- kind 分類 (loop 実行系=criteria 必須 / ref・assign=N/A escape 可) ---
FEEDBACK_LOOP_KINDS = {"run", "wrap", "delegate"}
FEEDBACK_SKIP_KINDS = {"ref", "assign"}


def validate_criteria(
    criteria: object,
    *,
    require_both_scopes: bool = True,
    prefix: str = "feedback_contract.criteria",
) -> list[str]:
    """criteria 配列を検査し errors のリストを返す (kind 非依存の純検査)。

    - 各 criterion に id/loop_scope/text/verify_by を要求
    - id は ^(IN|OUT|C)[0-9]+$ / 重複禁止
    - verify_by は CRITERIA_VERIFY_BY のいずれか
    - loop_scope は inner|outer
    - require_both_scopes=True なら inner と outer を最低各1件
    """
    errs: list[str] = []
    if not isinstance(criteria, list) or not criteria:
        return [f"{prefix} must be a non-empty array"]
    seen_ids: set[str] = set()
    seen_scopes: set[str] = set()
    for idx, item in enumerate(criteria):
        if not isinstance(item, dict):
            errs.append(f"{prefix}[{idx}] must be object")
            continue
        for key in REQUIRED_CRITERION_KEYS:
            v = item.get(key)
            if not (isinstance(v, str) and v.strip()):
                errs.append(f"{prefix}[{idx}].{key} is empty")
        cid = str(item.get("id", "")).strip()
        if cid and not CRITERIA_ID_RE.match(cid):
            errs.append(f"{prefix}[{idx}].id={cid!r} must match ^(IN|OUT|C)[0-9]+$")
        if cid and cid in seen_ids:
            errs.append(f"{prefix}[{idx}].id={cid!r} duplicated")
        seen_ids.add(cid)
        vb = str(item.get("verify_by", "")).strip()
        if vb and vb not in CRITERIA_VERIFY_BY:
            errs.append(
                f"{prefix}[{idx}].verify_by={vb!r} not in {sorted(CRITERIA_VERIFY_BY)}"
            )
        scope = str(item.get("loop_scope", "")).strip().lower()
        if scope and scope not in LOOP_SCOPES:
            errs.append(f"{prefix}[{idx}].loop_scope={scope!r} must be inner or outer")
        elif scope:
            seen_scopes.add(scope)
    if require_both_scopes:
        for required_scope in ("inner", "outer"):
            if required_scope not in seen_scopes:
                errs.append(
                    f"{prefix} must include >=1 {required_scope} loop_scope criterion"
                )
    return errs


def criteria_ids(criteria: object) -> set[str]:
    """criteria 配列から id 集合を抽出 (空白/非 dict は無視)。"""
    out: set[str] = set()
    if not isinstance(criteria, list):
        return out
    for item in criteria:
        if isinstance(item, dict):
            cid = str(item.get("id", "")).strip()
            if cid:
                out.add(cid)
    return out


def is_loop_kind(kind: object) -> bool:
    """loop 実行系 (run/wrap/delegate) なら True。criteria 必須判定に使う。"""
    return str(kind or "").strip().lower() in FEEDBACK_LOOP_KINDS


def extract_frontmatter_feedback_contract(skill_md_text: str) -> dict | None:
    """SKILL.md テキストの YAML frontmatter から feedback_contract dict を抽出。

    yaml が import 可能ならそれを使う。無ければ feedback_contract ブロックを
    最小インデントパーサで読む (criteria の id/loop_scope/text/verify_by のみ抽出)。
    見つからなければ None。
    """
    if not skill_md_text.startswith("---"):
        return None
    parts = skill_md_text.split("\n---", 1)
    if len(parts) < 2:
        return None
    fm_text = parts[0].lstrip("-").lstrip("\n")
    try:  # 任意依存
        import yaml  # type: ignore

        data = yaml.safe_load(fm_text) or {}
        if isinstance(data, dict):
            fc = data.get("feedback_contract")
            return fc if isinstance(fc, dict) else None
    except Exception:
        pass
    return _parse_feedback_contract_block(fm_text)


def _parse_feedback_contract_block(fm_text: str) -> dict | None:
    """yaml 非搭載環境向けの最小パーサ。

    frontmatter から `feedback_contract:` ブロックを取り出し、その配下の
    `criteria:` 配列要素 (- id: .. / loop_scope: .. / text: .. / verify_by: ..) を
    抽出する。max_iterations / skip_reason のスカラも拾う。
    """
    lines = fm_text.splitlines()
    n = len(lines)
    i = 0
    fc_indent = None
    block: list[str] = []
    while i < n:
        line = lines[i]
        if fc_indent is None:
            if re.match(r"^feedback_contract:\s*$", line):
                fc_indent = len(line) - len(line.lstrip())
                i += 1
                continue
            i += 1
            continue
        # ブロック内: より浅いインデントの非空行で終了
        if line.strip() and (len(line) - len(line.lstrip())) <= fc_indent:
            break
        block.append(line)
        i += 1
    if fc_indent is None:
        return None
    fc: dict = {}
    criteria: list[dict] = []
    cur: dict | None = None
    for line in block:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^(max_iterations|skip_reason):\s*(.+)$", stripped)
        if m and "- " not in line.split(":", 1)[0]:
            key, val = m.group(1), m.group(2).strip().strip('"').strip("'")
            fc[key] = int(val) if key == "max_iterations" and val.isdigit() else val
            continue
        if stripped.startswith("- "):
            cur = {}
            criteria.append(cur)
            stripped = stripped[2:].strip()
            if not stripped:
                continue
        if cur is not None and ":" in stripped:
            key, val = stripped.split(":", 1)
            cur[key.strip()] = val.strip().strip('"').strip("'")
    if criteria:
        fc["criteria"] = criteria
    return fc or None
