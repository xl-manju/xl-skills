"""マトリクス散文と引用実体の整合 (A6 型誤帰属の再発防止)。

2026-06-30 elegant-review (finding L1) で、skill-creator-spec-reflection.md の A6 行が
L2 評価器固有 rule (PG-001/PG-002/BND-001/REG-001) を L0 rubric 正本に**誤帰属**していた
事実誤りを検出した。根本原因 (L10) は `check-spec-matrix-coverage.py --self-test` が
ROW-ID 集合の drift しか検査せず、散文「何を強制」列と引用パスの**実体一致を未検証**だった
こと (= 完全性証明の循環論法が機構レベルで未解消)。

本テストは reflection.md の各行について『絶対パス列が rubric.json を指す場合、その行が
「何を強制」列で挙げる rule-ID が当該 rubric に実在するか』を機械突合する。rubric.json は
rule-ID 構造が明確で false-positive を生まないため検査対象をこれに絞る (パスがディレクトリや
brace 展開の行は対象外)。standalone 配布で skill-creator が不在なら skip (repo 文脈で機能)。

射程の限界 (機械層 vs LLM 層の境界・正直開示): 本ガードは『非実在 rule-ID の引用』
(A6 の旧 PG/BND/REG=L0 に存在しない ID の誤帰属) を捕捉するが、『実在 rule-ID の**意味
ラベル**取り違え』は捕捉できない (ID 存在のみ検査するため)。実際 2026-06-30 の是正過程で
A6 に混入した『BD-004=TODO(human)』(BD-004 は L0 実在だが意味は description↔body 手順整合)
は本テストを素通りし、独立 approver の LLM 二段確認で検出された。意味ラベルの faithfulness は
機械層では縛れず、reflection.md の rule gloss 変更時は独立 SubAgent/人間の二段確認を残す運用が
前提 (機構=機械保証 / 内容判断=AI/人間 の二層分離)。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# tests/ -> run-plugin-dev-plan -> skills -> plugin-dev-planner -> plugins -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[5]
_REFLECTION = (
    Path(__file__).resolve().parents[1] / "references" / "skill-creator-spec-reflection.md"
)
_SKILL_CREATOR_SKILLS = _REPO_ROOT / "plugins" / "skill-creator" / "skills"
_ROW_RE = re.compile(r"^\|\s*[A-G]\d{1,2}\s*\|")
_RUBRIC_PATH_RE = re.compile(r"`([^`]*rubric\.json)`")
_BACKTICK_PATH_RE = re.compile(r"`([^`]+)`")
_RULE_ID_RE = re.compile(r"\b([A-Z]{2,4}-\d{1,3})\b")
# skill 名形状: prefix を伴い必ずハイフンを含む (assign-*/ref-*/run-*/wrap-*/delegate-*)。
# 表ヘッダの "skill" (ハイフン無し) や区切り "---" を確実に除外する。
_SKILL_NAME_RE = re.compile(r"[a-z][a-z0-9]*-[a-z0-9-]+")


def _completeness_proof_skill_names(md_text: str) -> set[str]:
    """reflection.md「完全性の証明」§ の skill 列挙表 (| skill | ラベル | 根拠 |) から
    skill 名集合を抽出する。`### skills/` 見出し〜次 `### ` 見出しの範囲のみ対象。"""
    names: set[str] = set()
    in_section = False
    for line in md_text.splitlines():
        if line.startswith("### skills/"):
            in_section = True
            continue
        if in_section and line.startswith("### "):
            break  # 次セクション (設計書 関連章) で終了
        if not in_section or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 4:
            continue
        # 先頭 skill 名トークンを抽出 (注記サフィックス「(22章)」「(symlink→…)」を許容)。
        # ヘッダ "skill" (ハイフン無し) / 区切り "---" は先頭一致しないため除外される。
        m = _SKILL_NAME_RE.match(cells[1])
        if m:
            names.add(m.group(0))
    return names


def _rubric_rule_ids(path: Path) -> set[str]:
    """rubric.json から rule-ID (id / rule_id) を再帰抽出する。"""
    ids: set[str] = set()

    def walk(o: object) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("id", "rule_id") and isinstance(v, str):
                    ids.add(v)
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    walk(json.loads(path.read_text(encoding="utf-8")))
    return ids


def _row_cells(line: str) -> list[str]:
    """Markdown table 行を | 区切りセルへ分解 (前後の空セルを保持)。"""
    return [c.strip() for c in line.split("|")]


def _cited_plugin_paths(md_text: str) -> list[tuple[str, str]]:
    """43行『絶対パス』列から plugins/ 接頭の引用パスを (row-id, path) で抽出する。

    cross-plugin upstream 結合 (skill-creator / skill-governance-lint / prompt-creator) のみ
    対象とし、brace 展開 ({a,b}) / glob (*) を含むトークン (複数実体を畳む) と、bare ファイル名
    や tests/ 配下の注記トークン (絶対パス列の実引用でなく説明) は除外する。
    """
    out: list[tuple[str, str]] = []
    for line in md_text.splitlines():
        if not _ROW_RE.match(line):
            continue
        cells = _row_cells(line)
        if len(cells) < 6:
            continue
        rid, path_cell = cells[1], cells[3]
        for raw in _BACKTICK_PATH_RE.findall(path_cell):
            p = raw.strip()
            if p.startswith("plugins/") and not any(ch in p for ch in "{}*"):
                out.append((rid, p))
    return out


def test_matrix_rows_cite_real_rubric_rule_ids():
    """rubric.json を引用する行の rule-ID が当該 rubric に実在する (A6 型誤帰属の封止)。"""
    if not _REFLECTION.is_file():
        pytest.skip(f"reflection.md 不在: {_REFLECTION}")
    offenders: list[str] = []
    checked = 0
    skipped_absent = 0
    for line in _REFLECTION.read_text(encoding="utf-8").splitlines():
        if not _ROW_RE.match(line):
            continue
        cells = _row_cells(line)
        # cells: ['', ID, 仕様, 絶対パス, 何を強制, 焼き先, '']
        if len(cells) < 6:
            continue
        rid, path_cell, force_cell = cells[1], cells[3], cells[4]
        pm = _RUBRIC_PATH_RE.search(path_cell)
        if not pm:
            continue  # 絶対パス列が rubric.json を指さない行は対象外
        rubric_path = _REPO_ROOT / pm.group(1)
        if not rubric_path.is_file():
            skipped_absent += 1
            continue  # standalone 配布等で実体不在 → この行のみスキップ
        real_ids = _rubric_rule_ids(rubric_path)
        cited = set(_RULE_ID_RE.findall(force_cell))
        missing = sorted(c for c in cited if c not in real_ids)
        if missing:
            offenders.append(
                f"{rid}: {pm.group(1)} に不在の rule-ID を「何を強制」列が引用: {missing}"
            )
        checked += 1
    if checked == 0:
        pytest.skip(
            f"rubric.json 引用行を検査できず (不在 {skipped_absent} 行・standalone 配布?)"
        )
    assert not offenders, (
        "マトリクス散文が引用 rubric と不整合 (L0/L2 層の取り違え等):\n" + "\n".join(offenders)
    )


def test_matrix_integrity_catches_misattribution(tmp_path):
    """本ガードが A6 型誤帰属 (実在しない rule-ID 引用) を確かに fail させる回帰固定。"""
    rubric = tmp_path / "rubric.json"
    rubric.write_text(
        json.dumps({"layer": "L0", "rules": [{"id": "FM-001"}, {"id": "BD-001"}]}),
        encoding="utf-8",
    )
    real_ids = _rubric_rule_ids(rubric)
    # 正例: 実在 ID のみ引用 → 不整合なし
    good = set(_RULE_ID_RE.findall("FM-001(frontmatter) BD-001(body)"))
    assert not [c for c in good if c not in real_ids]
    # 負例: L2 固有 rule を L0 rubric に誤帰属 → 検出される
    bad = set(_RULE_ID_RE.findall("PG-001(prompts) BND-001(bundles) REG-001(trace)"))
    assert sorted(c for c in bad if c not in real_ids) == ["BND-001", "PG-001", "REG-001"]


def test_matrix_rows_cite_existing_plugin_paths():
    """43行『絶対パス』列が引用する plugins/ 配下の実体が存在する (上流改名の無音 stale 化封止)。

    rule-ID 整合 (test_matrix_rows_cite_real_rubric_rule_ids) + skill 列挙
    (test_completeness_proof_enumerates_all_skill_creator_skills) に続く、上流結合の最後の辺
    = cross-plugin パス存在を機械保証する (2026-06-30 elegant-review DEF-1)。skill-creator が
    ファイルを改名/移動すると reflection.md のパス列が無音で stale 化し、生成 spec が dead path
    を焼いて後段 build 時に初めて発覚する因果連鎖を、plan/CI 時点へ前倒しして断つ。
    閾値値や gloss の faithfulness は機械化しない (意図的に LLM 二段確認へ残す=Goodhart 回避)。"""
    if not _REFLECTION.is_file():
        pytest.skip(f"reflection.md 不在: {_REFLECTION}")
    if not _SKILL_CREATOR_SKILLS.is_dir():
        pytest.skip(f"skill-creator/skills 不在 (standalone 配布?): {_SKILL_CREATOR_SKILLS}")
    cited = _cited_plugin_paths(_REFLECTION.read_text(encoding="utf-8"))
    if not cited:
        pytest.skip("検査可能な plugins/ 引用パスが無い")
    offenders = [
        f"{rid}: 引用パスが実在しない (上流改名/移動?): {p}"
        for rid, p in cited
        if not (_REPO_ROOT / p.rstrip("/")).exists()
    ]
    assert not offenders, (
        "マトリクス『絶対パス』列が上流実体と drift:\n" + "\n".join(offenders)
    )


def test_path_canary_helper_filters_and_extracts():
    """_cited_plugin_paths が plugins/ 接頭のみ抽出し brace/glob・非 plugins/ を除外する回帰固定。"""
    sample = (
        "| A1 | x | `plugins/skill-creator/skills/run-elegant-review/SKILL.md` | y | z |\n"
        "| F1 | x | `plugins/skill-governance-lint/scripts/{a,b}.py` | y | z |\n"  # brace 除外
        "| C3 | x | `sitecustomize.py` / `tests/test_scripts_smoke.py` | y | z |\n"  # 非 plugins/ 除外
        "| ZZ | not a row |\n"  # ID 形状でなく対象外
    )
    paths = {p for _, p in _cited_plugin_paths(sample)}
    assert paths == {"plugins/skill-creator/skills/run-elegant-review/SKILL.md"}


def test_completeness_proof_enumerates_all_skill_creator_skills():
    """循環論法 (分母自己定義) 解消の核 =「完全性の証明」のサーフェス全列挙が
    skill-creator/skills の実体と一致する。skill-creator が skill を増減したら
    本表の追記/削除漏れを機械検出し、『未分類の漏れ 0』証明の無音陳腐化を防ぐ
    (--self-test の 43 行 drift 検査 + 本テストのサーフェス被覆 = 二層機械保証)。"""
    if not _SKILL_CREATOR_SKILLS.is_dir():
        pytest.skip(f"skill-creator/skills 不在 (standalone 配布?): {_SKILL_CREATOR_SKILLS}")
    if not _REFLECTION.is_file():
        pytest.skip(f"reflection.md 不在: {_REFLECTION}")
    actual = {
        p.name for p in _SKILL_CREATOR_SKILLS.iterdir() if _SKILL_NAME_RE.fullmatch(p.name)
    }
    enumerated = _completeness_proof_skill_names(_REFLECTION.read_text(encoding="utf-8"))
    missing = sorted(actual - enumerated)  # 実体にあるが表に無い (追記漏れ)
    extra = sorted(enumerated - actual)    # 表にあるが実体に無い (削除漏れ)
    assert not missing and not extra, (
        "完全性の証明サーフェス列挙が skill-creator/skills と drift: "
        f"表に未登録の実体={missing} / 実体に無い表エントリ={extra}"
    )


def test_completeness_proof_parser_excludes_header():
    """表ヘッダ 'skill' / 区切り '---' を除外し、注記サフィックス付き名は先頭 token を抽出する回帰固定。"""
    sample = (
        "### skills/ 全 31 本\n"
        "| skill | ラベル | 根拠 |\n"
        "|---|---|---|\n"
        "| run-build-skill | 反映済 C4 | build |\n"
        "| ref-pkg-contract | 反映済 F5 | PKG |\n"
        "| ref-output-routing (31章) | 意図的除外 | routing |\n"  # 注記サフィックス
        "| run-contract-finalize (symlink→contract-generator) | 意図的除外 | x |\n"
        "### 設計書 関連章\n"
        "| run-should-not-appear | x | y |\n"  # 次セクションは対象外
    )
    names = _completeness_proof_skill_names(sample)
    assert names == {
        "run-build-skill", "ref-pkg-contract", "ref-output-routing", "run-contract-finalize",
    }
