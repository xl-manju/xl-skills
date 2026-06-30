#!/usr/bin/env python3
# /// script
# name: specfm
# purpose: タスク仕様書 frontmatter の最小 YAML サブセットパーサと component_kind 別契約/criteria 制約の単一正本 (import 専用モジュール)。
# inputs: []
# outputs: []
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.10"
# ///
"""タスク仕様書 frontmatter の共有パーサ + 契約定数 (SSOT)。

check-spec-frontmatter.py / check-spec-gates.py / check-spec-matrix-coverage.py が
import 共有する。yaml は import しない (scripts 規約)。nested map / inline flow list /
block list (scalar item or 平坦 map item) を扱う最小 YAML サブセットを解析する。

feedback_contract.criteria の制約は plugins/skill-creator/scripts/feedback_contract_ssot.py を
逐語複製 (plugin 自己完結のため cross-plugin import を避ける)。
"""
from __future__ import annotations

import re

# --- feedback_contract.criteria SSOT 制約 (feedback_contract_ssot.py 逐語) ---
CRITERIA_ID_RE = re.compile(r"^(IN|OUT|C)[0-9]+$")
CRITERIA_VERIFY_BY = {"lint", "test", "script", "evaluator", "elegant-review", "human"}
LOOP_SCOPES = {"inner", "outer"}
REQUIRED_CRITERION_KEYS = ("id", "loop_scope", "text", "verify_by")

# --- component_kind / skill kind の語彙 ---
COMPONENT_KINDS = ("skill", "sub-agent", "slash-command", "hook", "script")
SKILL_KINDS = ("run", "ref", "wrap", "assign", "delegate")
FEEDBACK_LOOP_SKILL_KINDS = ("run", "wrap", "delegate")
HOOK_EVENTS = ("PreToolUse", "PostToolUse", "Stop", "UserPromptSubmit", "SessionEnd")
HARNESS_MIN_REQUIRED = 80
PLUGIN_LEVEL_SURFACES = (
    "manifest",
    "composition",
    "harness_eval",
    "references_config_assets",
    "mcp_app_connector",
)

# --- component_kind 別の構造的必須 frontmatter キー (kind 別分岐) ---
# skill は skill-brief.schema.json の base required 14 と逐語一致 (schema parity の正本)。
# 旧版は言い換えで 6 フィールド(cli_tools/deterministic_checks/external_systems/mcp_tools/
# needs_independent_context/needs_lifecycle_enforcement)を欠落し「無加工で写せる」が偽だった。
# 実 schema: plugins/skill-creator/skills/run-skill-create/schemas/skill-brief.schema.json#required
SKILL_BRIEF_FIELDS = (
    "skill_name", "prefix", "kind", "hierarchy_level", "trigger_conditions",
    "output_contract", "boundary", "placement_candidates",
    "cli_tools", "deterministic_checks", "external_systems", "mcp_tools",
    "needs_independent_context", "needs_lifecycle_enforcement",
)
# 存在のみ要求 (実 schema で minItems 無し=空配列/false も valid)。空でも欠落扱いしない。
SKILL_BRIEF_PRESENCE_ONLY = frozenset({
    "cli_tools", "deterministic_checks", "external_systems", "mcp_tools",
    "needs_independent_context", "needs_lifecycle_enforcement",
})
STRUCTURAL_REQUIRED = {
    "skill": SKILL_BRIEF_FIELDS,
    "sub-agent": ("name", "description", "tools", "independent_context", "responsibility_anchor"),
    "slash-command": ("name", "description", "argument-hint", "allowed-tools", "disable-model-invocation"),
    "hook": ("event", "matcher", "exit_semantics", "settings_wiring", "fail_closed"),
    "script": ("script_name", "purpose", "inputs", "outputs", "exit_codes",
               "network", "write_scope", "stdlib_only", "tests_min"),
}


def skill_conditional_required(skill_kind: str) -> tuple[str, ...]:
    """skill-brief.schema の allOf 条件付き required を skill kind で返す。

    prefix∈{run,wrap,assign,delegate} → goal/purpose_background/checklist、
    kind∈{run,assign} → responsibilities、wrap → base_skill、delegate → delegate_agent。
    (実 schema の allOf を逐語反映。L2→rubric_refs は hierarchy_level 軸で別途)
    """
    req: list[str] = []
    if skill_kind in ("run", "wrap", "assign", "delegate"):
        req += ["goal", "purpose_background", "checklist"]
    if skill_kind in ("run", "assign"):
        req.append("responsibilities")
    if skill_kind == "wrap":
        req.append("base_skill")
    if skill_kind == "delegate":
        req.append("delegate_agent")
    return tuple(req)

# --- quality_gates.p0_lint が component_kind 別に網羅すべき lint 集合 ---
SKILL_P0_LINTS = (
    "lint-skill-name", "lint-skill-description", "lint-skill-tree", "validate-frontmatter",
    "lint-dependency-direction", "lint-skill-dep-step7", "lint-forbidden-deps", "lint-manifest-contents",
)
P0_LINT_BY_KIND = {
    "skill": SKILL_P0_LINTS,
    "sub-agent": ("validate-frontmatter", "lint-skill-description", "lint-agent-prompt-section"),
    "slash-command": ("validate-frontmatter",),  # 注: command 専用 lint は未提供。実在する validate-frontmatter のみ
    "hook": ("validate-frontmatter", "lint-script-frontmatter"),
    "script": ("lint-script-frontmatter",),
}


# ─────────────────────────── 最小 YAML サブセットパーサ ───────────────────────────
def split_frontmatter(text: str) -> str | None:
    """先頭 --- ブロック本文を返す (無ければ None)。"""
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return parts[1]


def _strip_comment(v: str) -> str:
    """スカラ値から YAML コメントを除去する (flow list / quote 内は保持)。"""
    v = v.strip()
    if v.startswith("#"):
        return ""
    if v.startswith(("[", "{", '"', "'")):
        return v
    m = re.search(r"\s#", v)
    return v[: m.start()].strip() if m else v


def _split_top(inner: str) -> list[str]:
    """カンマ区切りを深さ0で分割する (ネストした [] {} 内のカンマは保持)。"""
    parts: list[str] = []
    depth = 0
    buf = ""
    for ch in inner:
        if ch in "[{":
            depth += 1
            buf += ch
        elif ch in "]}":
            depth -= 1
            buf += ch
        elif ch == "," and depth == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)
    return [p.strip() for p in parts if p.strip()]


def _scalar(v: str):
    """文字列値を bool / int / list / dict(inline flow) / str へ変換する。"""
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in _split_top(inner)] if inner else []
    if v.startswith("{") and v.endswith("}"):
        inner = v[1:-1].strip()
        d: dict = {}
        for pair in _split_top(inner):
            if ":" in pair:
                k, _, val = pair.partition(":")
                d[k.strip()] = _scalar(val.strip())
        return d
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def _tokens(fm_text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for raw in fm_text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        out.append((indent, raw.strip()))
    return out


def _parse_map(toks: list[tuple[int, str]], pos: int, indent: int):
    result: dict = {}
    while pos < len(toks):
        ci, content = toks[pos]
        if ci != indent or content.startswith("- "):
            break
        key, _, raw = content.partition(":")
        key = key.strip()
        val = _strip_comment(raw.strip())
        pos += 1
        if val == "":
            if pos < len(toks) and toks[pos][0] > indent:
                child_indent = toks[pos][0]
                if toks[pos][1].startswith("- "):
                    child, pos = _parse_list(toks, pos, child_indent)
                else:
                    child, pos = _parse_map(toks, pos, child_indent)
                result[key] = child
            else:
                result[key] = None
        else:
            result[key] = _scalar(val)
    return result, pos


def _parse_list(toks: list[tuple[int, str]], pos: int, indent: int):
    items: list = []
    while pos < len(toks):
        ci, content = toks[pos]
        if ci != indent or not content.startswith("- "):
            break
        rest = content[2:].strip()
        inner_indent = indent + 2
        if ":" in rest and not rest.startswith("["):
            item: dict = {}
            k, _, v = rest.partition(":")
            item[k.strip()] = None if _strip_comment(v.strip()) == "" else _scalar(_strip_comment(v.strip()))
            pos += 1
            sub, pos = _parse_map(toks, pos, inner_indent)
            item.update(sub)
            items.append(item)
        else:
            items.append(_scalar(_strip_comment(rest)))
            pos += 1
    return items, pos


def parse_frontmatter(text: str) -> dict:
    """SKILL/spec の frontmatter を nested dict に解析する (yaml 非依存)。"""
    fm = split_frontmatter(text)
    if fm is None:
        return {}
    toks = _tokens(fm)
    if not toks:
        return {}
    value, _ = _parse_map(toks, 0, toks[0][0])
    return value


# ─────────────────────────── 共有バリデータ ───────────────────────────
def validate_criteria(criteria) -> list[str]:
    """feedback_contract.criteria を SSOT 制約で検査 (inner+outer 各 1 件以上)。"""
    errs: list[str] = []
    if not isinstance(criteria, list) or not criteria:
        return ["feedback_contract.criteria が空 (inner/outer 各 1 件以上を携帯すること)"]
    seen_ids: set[str] = set()
    seen_scopes: set[str] = set()
    for idx, item in enumerate(criteria):
        if not isinstance(item, dict):
            errs.append(f"criteria[{idx}] が object でない")
            continue
        for key in REQUIRED_CRITERION_KEYS:
            v = item.get(key)
            if not (isinstance(v, str) and v.strip()):
                errs.append(f"criteria[{idx}].{key} が空")
        cid = str(item.get("id", "")).strip()
        if cid and not CRITERIA_ID_RE.match(cid):
            errs.append(f"criteria[{idx}].id={cid!r} は ^(IN|OUT|C)[0-9]+$ に不一致")
        if cid and cid in seen_ids:
            errs.append(f"criteria[{idx}].id={cid!r} が重複")
        seen_ids.add(cid)
        vb = str(item.get("verify_by", "")).strip()
        if vb and vb not in CRITERIA_VERIFY_BY:
            errs.append(f"criteria[{idx}].verify_by={vb!r} が enum 外 {sorted(CRITERIA_VERIFY_BY)}")
        scope = str(item.get("loop_scope", "")).strip().lower()
        if scope and scope not in LOOP_SCOPES:
            errs.append(f"criteria[{idx}].loop_scope={scope!r} は inner|outer のみ")
        elif scope:
            seen_scopes.add(scope)
    for required_scope in ("inner", "outer"):
        if required_scope not in seen_scopes:
            errs.append(f"feedback_contract.criteria に {required_scope} loop_scope が 1 件以上必要")
    return errs


# --- purpose-acceptance (成果物が当初 purpose を満たすか) の trace 検査 ---
# R3-emit-specs.md §2.2「criteria は goal/checklist から test-first 導出・フォールバック既定文禁止」を
# 機械化する。criteria が品質ゲートの言い換え (lint exit0 / 4条件 PASS 等) に退化し purpose を
# 一度も参照しない汎用フォールバックを fail-closed で弾く。意味の正否 (criterion が purpose を
# *正しく* 受入検証するか) は evaluator の責務として残す=機械層は「purpose 語彙を一度も参照しない」
# 明白な退化のみ検出する二層分離 (Goodhart 回避)。
_PURPOSE_ASCII_RE = re.compile(r"[A-Za-z][A-Za-z0-9-]{2,}")
# Han (CJK 統合漢字 + 拡張A) + Katakana。hiragana/数字/記号は語の接着辞ゆえ区切りとして bigram を跨がせない。
_PURPOSE_CJK_RE = re.compile(r"[一-鿿㐀-䶿゠-ヿ]{2,}")


def purpose_signals(text) -> set[str]:
    """goal/checklist/criterion から「内容語シグナル」集合を抽出する (purpose 由来性の素片)。

    ascii 語 (3 文字以上・小文字化) + CJK (漢字/カタカナ) 連続の bigram。hiragana を区切りに
    することで「を/する/した」等の機能語ノイズで bigram が偽マッチするのを避ける。形態素解析に
    依存しない決定論実装 (stdlib 規約)。
    """
    s = str(text or "")
    signals: set[str] = set()
    for m in _PURPOSE_ASCII_RE.findall(s):
        signals.add(m.lower())
    for run in _PURPOSE_CJK_RE.findall(s):
        for i in range(len(run) - 1):
            signals.add(run[i : i + 2])
    return signals


def _purpose_vocab(goal, checklist) -> set[str]:
    """goal + checklist から purpose 語彙シグナルの和集合を作る。"""
    vocab = set(purpose_signals(goal))
    if isinstance(checklist, list):
        for item in checklist:
            vocab |= purpose_signals(item)
    elif checklist is not None:
        vocab |= purpose_signals(checklist)
    return vocab


def criteria_purpose_traceability_errors(criteria, *, goal=None, checklist=None) -> list[str]:
    """skill loop spec の criteria が当該 spec の goal/checklist 語彙を最低 1 件参照するか検査。

    どの criterion も purpose 語彙を参照しなければ「汎用フォールバックへの退化」と判定し error。
    goal/checklist から content シグナルが 1 つも取れない場合は判定不能として [] (lenient・
    判定材料が無いのに弾く偽陽性を避ける)。criteria の構造不備は validate_criteria が別途担う。

    機械層の射程 (二層分離・正直開示): 判定は字面 (CJK bigram + ascii 語) の重複ベースゆえ、
    (a) goal を字面再利用せず**同義語/翻訳のみ**で表した正しい purpose criterion は誤検出しうる
    (緩和=「最低 1 件」で足り inner/outer の一方が領域名詞を再利用すれば通る・最終的な意味の正否は
    evaluator の意味判定に残す)、(b) 本関数は criteria↔goal の内部整合のみ見て **goal 自体が真の
    plugin purpose に接地しているか**は検査しない (接地は受入確認章 / EVALS llm_eval / evaluator の責務)。
    """
    vocab = _purpose_vocab(goal, checklist)
    if not vocab:
        return []
    if not isinstance(criteria, list) or not criteria:
        return []
    for item in criteria:
        if isinstance(item, dict) and (purpose_signals(item.get("text", "")) & vocab):
            return []
    return [
        "feedback_contract.criteria が purpose 由来でない: どの criterion も spec の goal/checklist "
        "語彙を参照しない汎用フォールバック (R3 §2.2 違反)。goal/checklist から受入基準を test-first 導出すること"
    ]


def as_int(v) -> int | None:
    """scalar を int 化する (失敗時 None)。"""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and re.fullmatch(r"-?\d+", v.strip()):
        return int(v.strip())
    return None


# --- index.plugin_meta が要求する plugin 階層キー (値域検証用) ---
# core = 全 plugin で必須の非空 dict (manifest/marketplace は別途 field 検証も持つ・ci は CI 配線)。
PLUGIN_META_CORE_DICTS = ("manifest", "marketplace", "ci")
# conditional = 該当しない構想では {applicable: false, reason: <非空>} で明示 N/A 可。
# reflection.md A7「skill-only は PKG 一部 N/A」と gate 実装を一致させる (無条件強制を緩和)。
# 空/欠落は不可 (省略は必ず根拠付き明示=「不要なら plugin_level_surfaces.<surface>.omitted_reason に理由」原則と同型)。
PLUGIN_META_CONDITIONAL_DICTS = ("pkg_contract", "governance", "ssot_dedup", "feedback_deploy")
# 後方互換: plugin 階層キー全体 (core + conditional)。集合として従来 7 キーと等価。
PLUGIN_META_REQUIRED_DICTS = PLUGIN_META_CORE_DICTS + PLUGIN_META_CONDITIONAL_DICTS


def is_plugin_meta_na(v) -> bool:
    """plugin_meta の conditional キーが明示 N/A ({applicable: false}) かを返す。"""
    return isinstance(v, dict) and v.get("applicable") is False


# --- タスク仕様書 (計画成果物) の出力先 解決の SSOT (再現性) ---
# 既定: repo-root 相対の <PLAN_OUTPUT_BASE>/<plan_slug(name)>。同一構想 → 常に同一出力先。
PLAN_OUTPUT_BASE = "eval-log/plugin-dev-planner"


def plan_slug(name: str) -> str:
    """プラグイン構想名を決定論的 kebab-case slug へ変換する (出力先 <plugin-slug>)。

    小文字化 → 英数とハイフン以外を '-' → 連続ハイフン圧縮 → 前後 '-' 除去。
    同一構想名は常に同一 slug = 同一出力先 (再現性アンカー)。冪等:
    plan_slug(plan_slug(x)) == plan_slug(x)。
    入力は対象プラグインの **ASCII kebab フォルダ名** を想定する (io-contract.md §9)。
    日本語(CJK)主体の自由文は ASCII 以外が脱落し別構想が同一 slug へ衝突しうるため、
    R1 は構想自由文でなく確定済みの target plugin kebab 名を渡すこと。
    """
    s = re.sub(r"[^a-z0-9-]+", "-", str(name).strip().lower())
    return re.sub(r"-+", "-", s).strip("-")


def plan_output_dir(name: str, out_dir: str | None = None, base: str = PLAN_OUTPUT_BASE) -> str:
    """タスク仕様書の出力先 (PLAN_DIR) を決定論的に解決する (repo-root 相対)。

    out_dir 明示指定があればそれを使う (相対は repo-root 基準)。無ければ
    `<base>/<plan_slug(name)>` を返す。slug が空になる name は ValueError。
    既定では plugin ごとに `eval-log/plugin-dev-planner/<plugin-slug>/` へ隔離する。

    `name` は生 plugin 名でも plan_slug 済 slug でも可 (plan_slug が冪等のため二重適用は無害)。
    戻り値は **repo-root 相対パス**。絶対化が要る場合は呼び出し側が `$CLAUDE_PROJECT_DIR`/cwd
    (repo-root 前提) で前置する責務とする (本関数は cwd を参照しない=純関数で再現性を担保)。
    """
    if out_dir is not None and str(out_dir).strip():
        return str(out_dir).strip().rstrip("/")
    slug = plan_slug(name)
    if not slug:
        raise ValueError("plan_output_dir: name から有効な slug を導出できない (--out-dir を明示指定すること)")
    return f"{base.rstrip('/')}/{slug}"


def expected_kind_pass_tokens(component_kind: str, skill_kind: str) -> set[str]:
    """harness_coverage.kind_pass が含むべき kind 別の語 (最小整合チェック)。

    harness-coverage-spec の kind 別パス (ref→source-traceability+ref-review /
    assign→evaluator verdict / loop→criteria検証test+content-review verdict) に対応。
    緩めだが「kind と無関係な値」を弾く。
    """
    if component_kind == "skill":
        if skill_kind in FEEDBACK_LOOP_SKILL_KINDS:
            return {"criteria", "content-review"}
        if skill_kind == "ref":
            return {"source-traceability", "ref-review"}
        if skill_kind == "assign":
            return {"evaluator", "verdict"}
    # 非 skill (sub-agent/slash-command/hook/script) と skill 既定
    return {"content-review", "verdict", "coverage", "test", "ref-review"}


def kind_pass_ok(kind_pass: str, component_kind: str, skill_kind: str) -> bool:
    """kind_pass が component_kind/skill kind と整合する語を含むか。"""
    kp = str(kind_pass or "").lower()
    return any(tok in kp for tok in expected_kind_pass_tokens(component_kind, skill_kind))


def validate_surface_inventory(data: dict) -> list[str]:
    """component-inventory.json の surface 採否契約を検査する。

    `considered_component_kinds` は「5 種を検討した」証跡で、`components` は実際に生成する
    必要最小の buildable spec 集合。両者を分けることで、単一 skill 退化と不要な水増し生成を
    同時に防ぐ。
    """
    errs: list[str] = []
    considered = data.get("considered_component_kinds")
    if not isinstance(considered, list) or set(considered) != set(COMPONENT_KINDS):
        errs.append(
            "considered_component_kinds は 5 component_kind 全種 "
            f"{list(COMPONENT_KINDS)} を漏れなく含むこと"
        )
    components = data.get("components")
    if not isinstance(components, list) or not components:
        errs.append("components が非空 list でない")
    else:
        for idx, comp in enumerate(components):
            if not isinstance(comp, dict):
                errs.append(f"components[{idx}] が object でない")
                continue
            ck = comp.get("component_kind")
            if ck not in COMPONENT_KINDS:
                errs.append(f"components[{idx}].component_kind={ck!r} が enum 外 {list(COMPONENT_KINDS)}")
            if not str(comp.get("build_target", "")).strip():
                errs.append(f"components[{idx}].build_target が空")
    force_13 = data.get("force_13")
    if not isinstance(force_13, bool):
        errs.append("force_13 が bool でない/欠落")
    derived_count = as_int(data.get("derived_count"))
    if force_13 is True:
        if derived_count != 13:
            errs.append(f"force_13=true では derived_count=13 が必要 (現値 {derived_count})")
        if isinstance(components, list) and len(components) != 13:
            errs.append(f"force_13=true では components 件数 13 が必要 (現値 {len(components)})")

    surfaces = data.get("plugin_level_surfaces")
    if not isinstance(surfaces, dict) or not surfaces:
        errs.append("plugin_level_surfaces が非空 dict でない")
    else:
        for surface in PLUGIN_LEVEL_SURFACES:
            item = surfaces.get(surface)
            if not isinstance(item, dict):
                errs.append(f"plugin_level_surfaces.{surface} が object でない/欠落")
                continue
            required = item.get("required")
            reason = item.get("omitted_reason")
            if required is True:
                continue
            if required is False and isinstance(reason, str) and reason.strip():
                continue
            errs.append(
                f"plugin_level_surfaces.{surface} は required:true または "
                "required:false + omitted_reason 非空で明示すること"
            )
    return errs


# ─────────────────────────── 生成 skeleton (実行可能ひな形) ───────────────────────────
def valid_quality_gates(component_kind: str) -> dict:
    """component_kind 別に最小妥当な quality_gates ブロックを返す。"""
    if component_kind not in COMPONENT_KINDS:
        raise ValueError(f"unknown component_kind: {component_kind!r}")
    return {
        "p0_lint": list(P0_LINT_BY_KIND[component_kind]),
        "build_trace": "required",
        "elegant_review": {"conditions": ["C1", "C2", "C3", "C4"], "all_pass": True},
        "content_review": {"verdict": "PASS", "sha_match": True},
        "evaluator": {"threshold": 80, "high_max": 0},
    }


def valid_harness_coverage(component_kind: str, skill_kind: str = "run") -> dict:
    """component_kind/skill kind と整合する最小 harness_coverage ブロックを返す。"""
    if component_kind == "skill":
        if skill_kind == "ref":
            kind_pass = "ref=source-traceability+ref-review"
        elif skill_kind == "assign":
            kind_pass = "assign=evaluator-verdict"
        else:
            kind_pass = "loop=criteria-test+content-review-verdict"
    else:
        kind_pass = "content-review-verdict"
    return {"min": HARNESS_MIN_REQUIRED, "kind_pass": kind_pass}


def minimal_frontmatter(component_kind: str, *, spec_id: str = "C01", skill_kind: str = "run") -> dict:
    """検証を通せる最小 frontmatter skeleton を返す。

    静的 Markdown ひな形を増やさず、`STRUCTURAL_REQUIRED` / `P0_LINT_BY_KIND` から
    生成することで「ひな形」の正本を実行可能契約へ寄せる。
    """
    if component_kind not in COMPONENT_KINDS:
        raise ValueError(f"unknown component_kind: {component_kind!r}")
    if skill_kind not in SKILL_KINDS:
        raise ValueError(f"unknown skill kind: {skill_kind!r}")

    fm: dict = {"id": spec_id, "component_kind": component_kind, "depends_on": []}
    if component_kind == "skill":
        fm.update({
            "skill_name": f"{skill_kind}-sample",
            "prefix": skill_kind,
            "kind": skill_kind,
            "hierarchy_level": "L1",
            "trigger_conditions": ["明示的に呼び出されたとき", "対象構想がこの責務に一致するとき"],
            "output_contract": "観測可能な成果物と検証結果を返す",
            "boundary": "単一責務を超える実装・配布判断は上位 plan に委ねる",
            "placement_candidates": ["Skill"],
            "cli_tools": [],
            "deterministic_checks": [],
            "external_systems": [],
            "mcp_tools": [],
            "needs_independent_context": False,
            "needs_lifecycle_enforcement": False,
        })
        if skill_kind in ("run", "wrap", "assign", "delegate"):
            fm.update({
                "goal": "この component spec の完了条件が検証可能な形で満たされている",
                "purpose_background": "後段 build が迷わない粒度で責務と評価基準を固定する",
                "checklist": ["frontmatter 契約を満たす", "本文の目的・成果物・完了条件が非空"],
            })
        if skill_kind in ("run", "assign"):
            fm["responsibilities"] = ["component spec の責務を実装可能な入力へ落とす"]
            fm["prompt_layer"] = "7layer"
        if skill_kind == "wrap":
            fm["base_skill"] = "run-base"
        if skill_kind == "delegate":
            fm["delegate_agent"] = "sample-agent"
        if skill_kind in FEEDBACK_LOOP_SKILL_KINDS:
            # criteria は当該 spec の goal/checklist 由来 (purpose-acceptance) であること。
            # skeleton は domain purpose を持たないため goal/checklist 語彙を参照する雛形に留め、
            # 実 spec では「この component の goal を満たすことを test/script で確認する」へ置換する。
            # 汎用ゲートの言い換え (lint exit0 / 4条件 PASS) は criteria_purpose_traceability_errors が弾く。
            fm["feedback_contract"] = {"criteria": [
                {"id": "IN1", "loop_scope": "inner",
                 "text": "frontmatter 契約と本文セクションが満たされ決定論 lint が exit0 になる", "verify_by": "lint"},
                {"id": "OUT1", "loop_scope": "outer",
                 "text": "本文の完了条件 (goal の受入基準) が観測可能な形で満たされ受入テストが PASS する",
                 "verify_by": "test"},
            ]}
            fm["goal_seek"] = {"engine": "inline", "fork": "subagent", "max_loops": 5}
        else:
            fm["feedback_contract"] = {"skip_reason": f"{skill_kind} kind は loop criteria 必須対象外"}
        fm["combinators"] = ["with-goal-seek"] if skill_kind in FEEDBACK_LOOP_SKILL_KINDS else []
    elif component_kind == "sub-agent":
        fm.update({
            "name": "sample-subagent",
            "description": "独立 context で計画を検証する sub-agent",
            "tools": ["Read"],
            "independent_context": True,
            "responsibility_anchor": "prompts/R1.md",
            "prompt_layer": "7layer",
        })
    elif component_kind == "slash-command":
        fm.update({
            "name": "sample-command",
            "description": "計画スキルを呼び出す slash command",
            "argument-hint": "[args]",
            "allowed-tools": ["Read"],
            "disable-model-invocation": False,
        })
    elif component_kind == "hook":
        fm.update({
            "event": "PreToolUse",
            "matcher": "Write|Edit",
            "exit_semantics": "fail-closed-exit2",
            "settings_wiring": "settings.json",
            "fail_closed": True,
        })
    elif component_kind == "script":
        fm.update({
            "script_name": "sample.py",
            "purpose": "決定論検査を実行する",
            "inputs": "argv",
            "outputs": "stdout/stderr + exit code",
            "exit_codes": "0=OK / 1=violation / 2=usage",
            "network": False,
            "write_scope": "none",
            "stdlib_only": True,
            "tests_min": HARNESS_MIN_REQUIRED,
        })
    fm["quality_gates"] = valid_quality_gates(component_kind)
    fm["harness_coverage"] = valid_harness_coverage(component_kind, skill_kind)
    return fm


def _yaml_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    return str(value)


def yaml_lines(data: dict, indent: int = 0) -> list[str]:
    """本スキルが使う YAML サブセットで dict を出力する。"""
    pad = "  " * indent
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines.extend(yaml_lines(value, indent + 1))
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            lines.append(f"{pad}{key}:")
            for item in value:
                pairs = list(item.items())
                first_key, first_value = pairs[0]
                lines.append(f"{pad}  - {first_key}: {_yaml_scalar(first_value)}")
                for child_key, child_value in pairs[1:]:
                    lines.append(f"{pad}    {child_key}: {_yaml_scalar(child_value)}")
        elif isinstance(value, list):
            lines.append(f"{pad}{key}: [{', '.join(_yaml_scalar(x) for x in value)}]")
        else:
            lines.append(f"{pad}{key}: {_yaml_scalar(value)}")
    return lines


def render_minimal_spec(component_kind: str, *, spec_id: str = "C01", skill_kind: str = "run") -> str:
    """frontmatter 契約 + 本文の床を満たす最小 Markdown skeleton を返す。"""
    fm = minimal_frontmatter(component_kind, spec_id=spec_id, skill_kind=skill_kind)
    body = (
        "\n# component spec skeleton\n\n"
        "## 目的\n"
        "このコンポーネントが担当する単一責務と到達状態を具体化する。\n\n"
        "## 成果物\n"
        "後段 build が生成する実体パス、入力、検証ログを列挙する。\n\n"
        "## 完了条件\n"
        "frontmatter の quality_gates / harness_coverage と本文の受け入れ条件が満たされている。\n"
    )
    return "---\n" + "\n".join(yaml_lines(fm)) + "\n---" + body
