#!/usr/bin/env python3
# /// script
# name: guard-confirmed-chapter-overwrite
# version: 0.1.0
# purpose: 確定済み仕様章 (system-spec/ の status:confirmed 章 かつ spec-state.json の
#          対応セルが『確定』・非再オープン) と spec-state.json 自身への Write/Edit/Bash 動的書換を
#          PreToolUse で遮断する defense-in-depth の fail-closed hook (要件 C3 の派生安全要件)。
#          正本防御は C01/C03 の単一 writer/transition gate。本 hook は二重化の補助防御。
# inputs:
#   - stdin: PreToolUse hook JSON ({tool_name, tool_input{file_path|command}})
#   - env: CLAUDE_PROJECT_DIR (spec-state.json / system-spec/ 探索起点。未設定時は cwd)
# outputs:
#   - exit: 0=許可 / 2=ブロック(stderr に理由)。判定不能で明確に protected でないものは通す
#           (誤爆回避)。spec-state 参照の危険な動的 Bash 書換のみ安全側で 2 (fail-closed)。
# contexts: [E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""PreToolUse(Write|Edit|Bash) 確定章 / spec-state.json 保護ガード。

判定ソース (章保護 = 2 系統の論理積・章粒度の集約):
  1. system-spec/ 配下の章 Markdown の frontmatter 確定マーカー `status: confirmed`
  2. C03 実出力 frontmatter の `spec_cells:[<cat>.<pf>, ...]` (後方互換で単一
     `cell`/`cell_id`/`spec_cell` や `category`+`platform` も可) が指す全対応セルが
     spec-state.json 上で終端状態 (確定 or 対象外) かつ再オープン対象を含まないこと

Write|Edit:
  (a) file_path が spec-state.json かつ確定 (非再オープン) セルを含むなら exit2
      (Bash 経路と同格の直接書換/確定巻き戻し防御)。
  (b) file_path が上記 2 条件をともに満たす確定章のときも exit2。
  それ以外 (通常ファイル・未確定/再オープン章・新規章・確定セルなき spec-state) は
  exit0 で素通し。

Bash:
  読み取り専用コマンド (cat/grep/ls 等・書込指標なし) は保護パス参照でも exit0。
  書込コマンド (リダイレクト/sed -i/tee/cp/mv/rm/dd/truncate/python の open(...,'w') 等) が
    - spec-state.json を書換対象にする
    - 解決可能な確定章を書換対象にする
    - system-spec/ or spec-state.json を参照する曖昧な動的書換 (glob/変数/find 経由) である
  いずれかなら安全側で exit2。再オープン章・新規章への具体的書込は通す。

fail-closed 方針: 「対象が明確に protected と判定できないなら通す」を基本とし、spec-state を
参照する危険な動的 Bash 書換のみ安全側で拒否する (計画 C11 exit_semantics=fail-closed-exit2)。
全書換経路の正本防御は C01/C03 の単一 writer/transition gate が担う。本 hook は補助 (二重化)。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

CONFIRMED = "確定"
GUARD_NAME = "guard-confirmed-chapter-overwrite"
# 章保護の終端セル状態 (確定 or 対象外)。両者とも settled であり確定章に含まれ得る
# (例: security 章 = web/mobile/tablet 確定 + desktop×3 対象外 の混在でも status:confirmed)。
TERMINAL_STATES = {"確定", "対象外"}
# writer (apply-spec-transition.py apply_cell_op reopen) が確定巻き戻し時に付す正本キー
# (reopened_from/reopen_reason) + 後方互換キー。いずれかがあれば当該セルは R4-reopen 済み。
_REOPEN_KEYS = ("reopened_from", "reopen_reason", "reopened", "reopen", "reopened_at", "reopened_by")

# system-spec/ を参照する書込で in-place 変更を行うツール群 (対象ファイルを引数で受ける)。
_MUTATION_TOOLS = (
    (re.compile(r"\bsed\s+(?:-[a-zA-Z]*i|--in-place)\b"), "sed -i"),
    (re.compile(r"\btee\b"), "tee"),
    (re.compile(r"\bcp\b"), "cp"),
    (re.compile(r"\bmv\b"), "mv"),
    (re.compile(r"\brm\b"), "rm"),
    (re.compile(r"\bdd\b"), "dd"),
    (re.compile(r"\btruncate\b"), "truncate"),
    (re.compile(r"\binstall\b"), "install"),
    (re.compile(r"\bln\b"), "ln"),
)
# python ワンライナ等での書込操作。
_PY_WRITE = re.compile(
    r"""open\s*\([^)]*['"][wax]\+?b?['"]"""
    r"""|write_text\s*\("""
    r"""|\.write\s*\("""
    r"""|json\.dump\s*\("""
    r"""|os\.(?:remove|unlink|rename|replace)\s*\("""
    r"""|shutil\.(?:copy|move|rmtree)\s*\("""
)
# 出力リダイレクト (`>`/`>>`) の対象トークン。`2>&1` 等の fd 複製は (?!&) で除外。
_REDIRECT = re.compile(r"""\d*>>?\s*(?!&)("[^"]*"|'[^']*'|[^\s;|&>]+)""")
# 曖昧な動的書換 (target を静的に列挙できない) を示す指標。
_DYNAMIC = re.compile(r"[*?\[]|\$|`|\bfind\b|\bxargs\b")


# ── パス種別判定 ────────────────────────────────────────────────────────────
def _is_system_spec_md(p: Path) -> bool:
    """system-spec/ 配下の .md か。"""
    return p.suffix == ".md" and "system-spec" in p.parts


def project_root() -> Path:
    """spec-state.json / system-spec/ の探索起点。env 優先・無ければ cwd。"""
    env = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if env and Path(env).is_dir():
        return Path(env)
    return Path.cwd()


# ── frontmatter / spec-state 読み取り ───────────────────────────────────────
def parse_frontmatter(text: str) -> dict:
    """章 Markdown の YAML 風 frontmatter (--- ... ---) をスカラ辞書へ。"""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: dict = {}
    for raw in parts[1].splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.split("#", 1)[0].strip().strip('"').strip("'")
    return fm


def _parse_spec_cells(raw) -> list[tuple[str, str]]:
    """frontmatter の spec_cells を (category, platform) 列へ。

    C03 実出力は `spec_cells: [database.web, database.mobile, ...]` (`.` 区切り list)。
    parse_frontmatter はこれをスカラ文字列 '[database.web, ...]' として渡すため
    文字列/リスト双方を受け、各要素を最初の '.' で category/platform に分割する
    (category・platform とも '.' を含まないため一意)。
    """
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]
        items = [x.strip() for x in s.split(",")]
    elif isinstance(raw, (list, tuple)):
        items = [str(x).strip() for x in raw]
    else:
        return []
    out: list[tuple[str, str]] = []
    for it in items:
        cat, sep, pf = it.partition(".")
        if sep and cat.strip() and pf.strip():
            out.append((cat.strip(), pf.strip()))
    return out


def _extract_cell_refs(fm: dict) -> list[tuple[str, str]]:
    """frontmatter から spec-state 対応セル (category, platform) 群を得る。

    C03 実出力 (`category` + `spec_cells:[<cat>.<pf>, ...]`) を第一に解釈し、後方互換で
    単一 `cell`/`cell_id`/`spec_cell` (区切り /:|) や `category`+`platform` (単数) も解釈する。
    重複は排除し frontmatter 出現順を保つ。
    """
    refs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add(cat: str, plat: str) -> None:
        key = (cat.strip(), plat.strip())
        if key[0] and key[1] and key not in seen:
            seen.add(key)
            refs.append(key)

    # C03 実形状: spec_cells list
    for cat, plat in _parse_spec_cells(fm.get("spec_cells")):
        _add(cat, plat)
    # 後方互換: 単一 cell 系キー
    for key in ("cell", "cell_id", "spec_cell"):
        v = fm.get(key)
        if isinstance(v, str) and v:
            for sep in ("/", ":", "|"):
                if sep in v:
                    cat, _, plat = v.partition(sep)
                    _add(cat, plat)
                    break
    # 後方互換: category + platform (単数)
    cat, plat = fm.get("category"), fm.get("platform")
    if cat and plat:
        _add(cat, plat)
    return refs


def load_spec_state(root: Path) -> dict | None:
    """spec-state.json を root 直下優先で読む。無ければ配下を 1 件探索。"""
    cand = root / "spec-state.json"
    paths = [cand] if cand.exists() else sorted(root.rglob("spec-state.json"))[:1]
    for p in paths:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None
    return None


def _resolve_cell(spec: dict, category: str, platform: str):
    if not isinstance(spec, dict):
        return None
    row = (spec.get("matrix") or {}).get(category)
    if not isinstance(row, dict):
        return None
    return row.get(platform)


def _cell_reopened(cell: dict) -> bool:
    """セルが R4-reopen 済みか。writer 正本キー reopened_from/reopen_reason を第一に見る。

    apply-spec-transition.py の reopen は確定巻き戻し時に
    {"state":"未収集","reopened_from":"確定","reopen_reason":...} を書く。従来 hook が見ていた
    reopened/reopen/reopened_at/reopened_by は writer 実出力に存在せず死んでいたため正本キーへ整合。
    """
    return any(cell.get(k) for k in _REOPEN_KEYS)


def _cell_terminal(cell) -> bool:
    """セルが終端状態 (確定 or 対象外) かつ再オープンされていない (=保護対象) か。

    R4-reopen 済み (state が 未収集 へ戻る / reopen 正本キー付与) のセルは保護しない (通す)。
    """
    if not isinstance(cell, dict):
        return False
    if _cell_reopened(cell):
        return False
    return cell.get("state") in TERMINAL_STATES


def chapter_protected(p: Path, root: Path) -> bool:
    """章ファイル p が確定章 (章粒度の集約で保護対象) か。

    保護条件 (全て満たすときのみ True):
      1. system-spec/ 配下の .md でファイルが存在する
      2. frontmatter が status: confirmed
      3. frontmatter の対応セル (spec_cells list / 後方互換単一キー) が 1 つ以上解決でき、
         その全てが spec-state 上で終端状態 (確定 or 対象外) かつ再オープン対象を含まない

    ファイル不在 (新規 Write) / frontmatter 未確定 / セル解決不能 / 非終端・再オープンセルを
    含む章 / spec-state 不在は「明確に protected と判定できない」ため False (通す・誤爆回避)。
    security 章のような 確定+対象外 混在でも status:confirmed なら (全セル終端ゆえ) 保護する。
    """
    if not _is_system_spec_md(p):
        return False
    fpath = p if p.is_absolute() else (root / p)
    if not fpath.is_file():
        return False
    try:
        text = fpath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    fm = parse_frontmatter(text)
    if fm.get("status") != "confirmed":
        return False
    refs = _extract_cell_refs(fm)
    if not refs:
        return False
    spec = load_spec_state(root)
    if spec is None:
        return False
    # 章粒度の集約: 全対応セルが終端かつ非再オープンのときだけ保護。1 つでも
    # 非終端 / 再オープン / 解決不能セルがあれば「明確に protected」でない → 通す。
    for cat, plat in refs:
        if not _cell_terminal(_resolve_cell(spec, cat, plat)):
            return False
    return True


# ── spec-state.json 直接書換ガード ──────────────────────────────────────────
def _is_spec_state_path(p: Path) -> bool:
    """対象が spec-state.json 自身か (ディレクトリ位置は問わずファイル名で判定)。"""
    return p.name == "spec-state.json"


def spec_state_has_confirmed_cell(root: Path) -> bool:
    """spec-state.json に確定 (非再オープン) セルが 1 つでもあるか。

    True のとき spec-state.json は確定巻き戻しの温床になり得るため直接 Write/Edit を遮断する。
    確定セルなし (init 直後・全 未収集/対象外) は通す (新規作成/初期化を妨げない)。
    """
    spec = load_spec_state(root)
    if not isinstance(spec, dict):
        return False
    matrix = spec.get("matrix")
    if not isinstance(matrix, dict):
        return False
    for row in matrix.values():
        if not isinstance(row, dict):
            continue
        for cell in row.values():
            if isinstance(cell, dict) and not _cell_reopened(cell) and cell.get("state") == CONFIRMED:
                return True
    return False


# ── Bash 解析 ───────────────────────────────────────────────────────────────
def _redirect_targets(cmd: str) -> list[str]:
    out = []
    for m in _REDIRECT.finditer(cmd):
        t = m.group(1).strip().strip('"').strip("'")
        if t:
            out.append(t)
    return out


def _system_spec_md_tokens(cmd: str) -> list[str]:
    """コマンド中の system-spec/ 配下 .md らしきトークンを抽出。"""
    toks = []
    for raw in re.split(r"[\s;|&<>()'\"]+", cmd):
        if raw and "system-spec" in raw and raw.endswith(".md"):
            toks.append(raw)
    return toks


def _token_is_protected_chapter(token: str, root: Path) -> bool:
    return chapter_protected(Path(token), root)


def bash_decision(cmd: str, root: Path) -> tuple[int, str]:
    """Bash コマンドの許可 (0) / 遮断 (2) を判定する。"""
    redirects = _redirect_targets(cmd)
    mutation = any(pat.search(cmd) for pat, _ in _MUTATION_TOOLS)
    py_write = bool(_PY_WRITE.search(cmd))
    is_write = bool(redirects) or mutation or py_write
    if not is_write:
        # 書込指標なし = read-only。保護パス参照でも通す (cat/grep/ls 等)。
        return 0, ""

    refs_spec_state = "spec-state.json" in cmd

    # 1) リダイレクト先が保護対象
    for t in redirects:
        if "spec-state.json" in t:
            return 2, f"spec-state.json への出力リダイレクト ('{t}') を遮断"
        if _token_is_protected_chapter(t, root):
            return 2, f"確定章への出力リダイレクト ('{t}') を遮断"

    # 2) in-place / python 書込が spec-state.json を対象
    if refs_spec_state and (mutation or py_write):
        return 2, "spec-state.json への動的書換 (in-place/python) を遮断"

    # 3) in-place / python 書込が解決可能な確定章を対象
    if mutation or py_write:
        for t in _system_spec_md_tokens(cmd):
            if _token_is_protected_chapter(t, root):
                return 2, f"確定章 '{t}' への動的書換を遮断"

    # 4) 曖昧な動的書換が保護領域を参照 (glob/変数/find 経由) → 安全側で遮断
    if ("system-spec" in cmd or refs_spec_state) and _DYNAMIC.search(cmd):
        return 2, "保護領域 (system-spec/ または spec-state.json) を参照する曖昧な動的書換を安全側で遮断"

    return 0, ""


# ── 中核ディシジョン ───────────────────────────────────────────────────────
def decide(payload: dict, root: Path) -> tuple[int, str]:
    """PreToolUse ペイロードから許可 (0) / 遮断 (2) と理由を返す。"""
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input") or {}
    if tool in ("Write", "Edit"):
        fp = ti.get("file_path") or ti.get("path") or ""
        if not fp:
            return 0, ""
        path = Path(fp)
        # (a) spec-state.json 自身への直接書換 (確定セルあり) は Bash 経路と同格に遮断。
        if _is_spec_state_path(path) and spec_state_has_confirmed_cell(root):
            return 2, (
                f"spec-state.json '{fp}' への直接 {tool} を遮断 "
                "(確定セルを含む。確定変更は apply-spec-transition の R4-reopen 経由のみ)"
            )
        # (b) 確定章への書換を遮断。
        if chapter_protected(path, root):
            return 2, f"確定済み仕様章 '{fp}' への {tool} を遮断 (再オープン経由でのみ変更可)"
        return 0, ""
    if tool == "Bash":
        cmd = ti.get("command") or ""
        return bash_decision(cmd, root)
    return 0, ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # 解釈不能な入力は対象を特定できず「明確に protected」でない → 素通し (誤爆回避)。
        return 0
    code, reason = decide(payload, project_root())
    if code == 2:
        sys.stderr.write(
            f"[{GUARD_NAME}] BLOCKED: {reason}。\n"
            "  確定済み仕様章 / spec-state.json は C01/C03 の単一 writer (根拠付き R4-reopen) 経由でのみ変更してください。\n"
        )
    return code


if __name__ == "__main__":
    sys.exit(main())
