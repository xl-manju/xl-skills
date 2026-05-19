#!/usr/bin/env python3
# /// script
# name: validate-frontmatter
# purpose: Validate SKILL.md frontmatter fields and combination rules.
# inputs:
#   - argv: SKILL.md path or --skills-dir
# outputs:
#   - stdout: OK status
#   - stderr: frontmatter findings
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Validate Skill frontmatter: required fields and combination sanity.

Usage:
  validate-frontmatter.py /path/to/SKILL.md
  validate-frontmatter.py --skills-dir creator-kit/skills
"""
from __future__ import annotations
import datetime
import re
import sys
from pathlib import Path

REQUIRED = {"name", "description"}
# doc/21 source-traceability 準拠の必須化（ref-* は source 必須 / 他 kind は WARN）
SOURCE_REQUIRED_FOR_KIND = {"ref"}
SOURCE_TIER_VALUES = {
    # doc/21 source-traceability.md 定義に厳密準拠
    "article-text",      # 元記事 Markdown 本文を確認済み（Agent Skill 大全等）
    "image-derived",     # 画像 OCR / 手描き図由来の翻文を含む
    "code-unavailable",  # 実コード未取得（記事説明由来の推定）
    "code-verified",     # 実コードを取得し検証済み
    "internal",          # 本リポジトリ内部発祥（doc/ 配下の内製設計書を含む）
    "external-spec",     # 外部公式仕様書（claude.com docs 等）
}
KIND_VALUES = {"run", "ref", "assign", "wrap", "delegate", "workflow", "reference",
               "evaluator", "generator"}
EFFECT_VALUES = {"none", "conversation-output", "local-artifact", "external-mutation"}
MERGE_STRATEGY_VALUES = {"deep-merge", "strict", "override", "layered"}
CONFLICT_POLICY_VALUES = {"most-specific-wins", "error", "warn-and-merge"}
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_fm(text: str) -> dict:
    """Parse YAML-ish frontmatter. Supports scalar values and `- ` list items.

    List values (e.g. `rubric_refs:` followed by `  - item`) become a list of
    strings. Scalars remain strings (trimmed).
    """
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: dict = {}
    current_list_key: str | None = None
    for raw in parts[1].splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            # blank or comment line ends list-context only if non-indented
            if line.strip() == "" or not line.startswith(" "):
                current_list_key = None
            continue
        # list item under current key
        m_item = re.match(r"^\s+-\s+(.+?)\s*$", line)
        if m_item and current_list_key is not None:
            fm.setdefault(current_list_key, [])
            if isinstance(fm[current_list_key], list):
                fm[current_list_key].append(m_item.group(1).strip())
            continue
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if m:
            key = m.group(1)
            val = m.group(2).split("#", 1)[0].strip()
            if val == "":
                # may be start of list block
                fm[key] = ""
                current_list_key = key
            elif val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                fm[key] = [
                    item.strip().strip('"').strip("'")
                    for item in inner.split(",")
                    if item.strip()
                ]
                current_list_key = None
            else:
                fm[key] = val
                current_list_key = None
    return fm


def _repo_root(p: Path) -> Path:
    """Find repo root by walking up until we find .git or fallback."""
    cur = p.resolve()
    for parent in [cur, *cur.parents]:
        if (parent / ".git").exists():
            return parent
    return cur.parent


def check_refs_exist(fm: dict, skill_path: Path) -> list[str]:
    """Verify rubric_refs / reference_refs / script_refs targets exist.

    - `ref-*` style entries: require `creator-kit/skills/<name>/` or
      `.claude/skills/<name>/` to exist at repo root.
    - other entries: treat as path; first try repo-root relative, then
      skill-directory relative.
    Returns a list of `MISSING_REF:` error strings.
    """
    errs: list[str] = []
    repo = _repo_root(skill_path)
    skill_dir = skill_path.parent
    for field in ("rubric_refs", "reference_refs", "script_refs"):
        items = fm.get(field)
        if not items:
            continue
        if isinstance(items, str):
            # comma-separated scalar fallback
            items = [s.strip() for s in items.split(",") if s.strip()]
        for entry in items:
            entry = entry.strip().strip('"').strip("'")
            if not entry:
                continue
            if re.match(r"^(ref|run|assign|wrap|delegate)-[a-z0-9-]+$", entry):
                cand1 = repo / "creator-kit" / "skills" / entry
                cand2 = repo / ".claude" / "skills" / entry
                if not (cand1.exists() or cand2.exists()):
                    errs.append(
                        f"MISSING_REF: {field} '{entry}' not found "
                        f"under creator-kit/skills/ or .claude/skills/"
                    )
            else:
                cand_root = repo / entry
                cand_local = skill_dir / entry
                if not (cand_root.exists() or cand_local.exists()):
                    errs.append(
                        f"MISSING_REF: {field} '{entry}' not found "
                        f"(tried {cand_root} and {cand_local})"
                    )
    return errs


def _check_source_tier_demotion(
    tier: str, source: str, last_audited: str, skill_path: Path
) -> str | None:
    """source-tier の降格が必要かを判定する。

    doc/21 再監査ルール（rubric-bump / source-update / quarterly）に対応する
    自動部分のみを扱う。返り値が None の場合は降格不要。

    判定対象:
      - code-verified / article-text / external-spec の高位 tier が、
        正本ファイルの不在・URL未記載・最終監査の古さで降格すべきか
      - code-unavailable のままで rubric が更新されたか

    """
    if not tier:
        return None
    source = source.strip()
    if tier == "external-spec":
        if source and not re.match(r"^https?://", source):
            return "external-spec は http(s) URL を source に持つ必要がある"
    elif tier in {"article-text", "image-derived", "code-verified"}:
        if not source:
            return f"{tier} は確認済み正本パスを source に持つ必要がある"
        if not re.match(r"^https?://", source):
            repo = _repo_root(skill_path)
            if not (repo / source).exists():
                return f"source path not found: {source}"

    if last_audited and ISO_DATE_RE.match(last_audited):
        audited = datetime.date.fromisoformat(last_audited)
        age_days = (datetime.date.today() - audited).days
        if age_days > 180:
            return f"last-audited is {age_days} days old"
    return None


def validate_file(p: Path) -> tuple[str, list[str]]:
    if not p.exists():
        return str(p), [f"not found: {p}"]

    text = p.read_text(encoding="utf-8")
    fm = parse_fm(text)
    errs: list[str] = []

    # required
    for r in REQUIRED:
        if r not in fm or not fm[r]:
            errs.append(f"missing required field: {r}")

    # description quality: 日本語トリガー句 (〜とき/〜場合/〜際/〜時) または
    # 英語の "Use when" / "Read when" のいずれかを含むこと。
    desc = fm.get("description", "")
    JP_TRIGGERS = ("とき", "場合", "際", "時に")
    has_en_trigger = ("Use when" in desc) or ("Read when" in desc)
    has_jp_trigger = any(t in desc for t in JP_TRIGGERS)
    if desc and not (has_en_trigger or has_jp_trigger):
        errs.append("description should contain a trigger phrase "
                    "(〜とき/〜場合/〜際/〜時 or 'Use when'/'Read when')")

    # trigger count: hard rule == 2 (設計書03)
    if desc:
        if has_en_trigger:
            # 英語: "when " の単純出現数を採用（接続詞 max ロジックは廃止）
            n = desc.count("when ")
        else:
            # 日本語: 「とき」「場合」「際」「時に」の出現回数を直接カウント
            # （接続詞による加算ロジックは廃止し、純粋な出現数で判定）
            n = sum(desc.count(t) for t in JP_TRIGGERS)
        if n != 2:
            errs.append(f"trigger count = {n} (expected exactly 2; hard rule)")

    # kind enum
    k = fm.get("kind", "")
    if k and k not in KIND_VALUES:
        errs.append(f"kind '{k}' not in {sorted(KIND_VALUES)}")
    # effect フィールド: 存在する場合は許容値を検証 (P1-1)
    effect_val = fm.get("effect", "")
    if effect_val and effect_val.split("#")[0].strip() not in EFFECT_VALUES:
        errs.append(
            f"effect '{effect_val.split('#')[0].strip()}' not in {sorted(EFFECT_VALUES)}"
        )

    merge_strategy = fm.get("merge_strategy", "")
    if merge_strategy and merge_strategy not in MERGE_STRATEGY_VALUES:
        errs.append(
            f"merge_strategy '{merge_strategy}' not in {sorted(MERGE_STRATEGY_VALUES)}"
        )
    conflict_policy = fm.get("conflict_policy", "")
    if conflict_policy and conflict_policy not in CONFLICT_POLICY_VALUES:
        errs.append(
            f"conflict_policy '{conflict_policy}' not in {sorted(CONFLICT_POLICY_VALUES)}"
        )

    # --- doc/21 source-traceability 検証 ---
    kind_val = fm.get("kind", "")
    source_val = fm.get("source", "").strip().strip('"').strip("'")
    source_tier = fm.get("source-tier", "").strip().strip('"').strip("'")
    last_audited = fm.get("last-audited", "").strip().strip('"').strip("'")

    # ref-* は source 必須、それ以外は WARN
    if kind_val in SOURCE_REQUIRED_FOR_KIND:
        if not source_val:
            errs.append("missing required field for kind=ref: source (doc/21)")
        if not source_tier:
            errs.append("missing required field for kind=ref: source-tier (doc/21)")
    else:
        if not source_val:
            errs.append("warn: source field missing (doc/21 recommends for traceability)")

    if source_tier and source_tier not in SOURCE_TIER_VALUES:
        errs.append(f"source-tier '{source_tier}' not in {sorted(SOURCE_TIER_VALUES)}")

    if last_audited and not ISO_DATE_RE.match(last_audited):
        errs.append(f"last-audited '{last_audited}' must be ISO date YYYY-MM-DD")

    # source-tier 降格判定（doc/21 再監査ルールの自動部分）
    demote_reason = _check_source_tier_demotion(source_tier, source_val, last_audited, p)
    if demote_reason:
        errs.append(f"warn: source-tier '{source_tier}' may need demotion ({demote_reason})")

    # cross_platform 契約検証 (doc/22-cross-platform-runtime)
    # frontmatter に cross_platform: true があれば、本文に <important if="os=...">
    # 分岐が最低 1 つは存在することを要求する。OS 分岐の機械検証は creator-kit
    # 量産時に Windows 経路の欠落を防ぐ。
    cross_platform = fm.get("cross_platform", "false").lower() == "true"
    if cross_platform:
        # text 全体（frontmatter 含む）に OS 分岐タグが含まれるかを確認
        if not re.search(r"<important\s+if\s*=\s*[\"']?os=", text):
            errs.append(
                "cross_platform=true requires at least one "
                "'<important if=\"os=...\">' branch in body (doc/22)"
            )

    # テンプレート変数の未展開検出（creator-kit 量産品質ゲート / doc/21 backfill依存ループ断ち切り）
    # 実体 SKILL.md に {{...}} が残存していたら ERROR で弾く。
    # templates/*.md は --skills-dir の */SKILL.md glob 対象外のため自動的に除外される。
    _unresolved_re = re.compile(r"\{\{[^}]+\}\}")
    for _k, _v in fm.items():
        if isinstance(_v, str) and _unresolved_re.search(_v):
            errs.append(f"unresolved template variable in '{_k}': {_v}")
        elif isinstance(_v, list):
            for _item in _v:
                if isinstance(_item, str) and _unresolved_re.search(_item):
                    errs.append(f"unresolved template variable in '{_k}' list: {_item}")

    # combo sanity
    dmi = fm.get("disable-model-invocation", "false").lower() == "true"
    ui = fm.get("user-invocable", "true").lower()
    ui_false = ui == "false"
    if dmi and not ui_false:
        # ref系: disable-model + user-invocable false ok
        # warn only when also user-invocable true explicit
        if ui == "true":
            errs.append("warn: disable-model-invocation=true + user-invocable=true (unusual)")

    # ref-fields existence (fail-fast: 依存注入の不在 → ref → fail-fast)
    errs.extend(check_refs_exist(fm, p))

    # assign系の必須
    name = fm.get("name", "")
    if name.startswith("assign-"):
        if fm.get("context", "") != "fork":
            errs.append("assign-* requires context: fork")
        if ui != "false":
            errs.append("assign-* requires user-invocable: false")

    return name, errs


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("usage: validate-frontmatter.py /path/to/SKILL.md | --skills-dir /path/to/skills", file=sys.stderr)
        return 2

    if "--skills-dir" in args:
        idx = args.index("--skills-dir")
        if idx + 1 >= len(args):
            print("usage: validate-frontmatter.py --skills-dir /path/to/skills", file=sys.stderr)
            return 2
        skills_dir = Path(args[idx + 1])
        if not skills_dir.is_dir():
            print(f"not a directory: {skills_dir}", file=sys.stderr)
            return 2
        total_errs: list[str] = []
        warn_only = True
        scanned = 0
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            scanned += 1
            name, errs = validate_file(skill_md)
            for e in errs:
                total_errs.append(f"{skill_md.parent.name}: {e}")
                if not e.startswith("warn:"):
                    warn_only = False
        if total_errs:
            for e in total_errs:
                print(e, file=sys.stderr)
            return 0 if warn_only else 1
        print(f"ok: {skills_dir} ({scanned} skills)")
        return 0

    p = Path(args[0])
    name, errs = validate_file(p)
    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        # warn-only do not fail; but any non-warn is fail
        hard = [e for e in errs if not e.startswith("warn:")]
        return 1 if hard else 0
    print(f"ok: {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
