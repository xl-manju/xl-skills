"""kind→必須 frontmatter キーの散文 (io-contract.md / R3-emit-specs.md) が
コード正本 `specfm.STRUCTURAL_REQUIRED` と一致することを機械強制する (kind-key ドリフト封止)。

2026-06-30 elegant-review (Phase 2 の論理/メタ/システム analyst が独立に収束) で、kind 別
必須キーが `specfm.STRUCTURAL_REQUIRED` (= 唯一 lint が強制する実行可能正本) を io-contract.md
§9 の表と R3-emit-specs.md §2.2 が散文で再掲しており、43 行マトリクス (test_matrix_doc_integrity
が守る) と違い parity ガードが無いため、specfm にキーを足して散文を忘れると無音で乖離する欠陥を
検出した。LLM は散文を読むため、この乖離は生成品質 (再現性) に直結する。

本テストは「specfm の各 required キーが各散文の kind 行に backtick トークンとして現れる」
(forward 方向 specfm ⊆ doc) を機械突合する。

射程の限界 (正直開示):
  - forward 方向のみ縛る。doc が specfm に無い任意キー (例 sub-agent の `(任意)evaluator_pair`)
    を列挙しても fail させない。
  - R3 §2.2 の skill 行は base required 14 を列挙せず `specfm.SKILL_BRIEF_FIELDS` を名指し参照
    する doc-points-to-SSOT 設計のため、R3 では skill のみ「specfm 参照の存在」を確認する
    (io-contract.md 側は 14 キーを全列挙するので forward 突合の対象にする)。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_SKILL_DIR = Path(__file__).resolve().parents[1]
_IO_CONTRACT = _SKILL_DIR / "references" / "io-contract.md"
_R3 = _SKILL_DIR / "prompts" / "R3-emit-specs.md"
_KINDS = ("skill", "sub-agent", "slash-command", "hook", "script")
_BACKTICK_RE = re.compile(r"`([^`]+)`")


def _normalize_key(token: str) -> str:
    """backtick トークンを frontmatter キー名へ正規化する (`独自: true` → `独自`)。"""
    return re.split(r"[:( ]", token.strip())[0].strip().lower()


def _kind_line(text: str, kind: str, prefixes: tuple[str, ...]) -> str | None:
    """`**{kind}**` を含み、指定 prefix (表行 '|' / 箇条 '-') で始まる行を返す。"""
    marker = f"**{kind}**"
    for line in text.splitlines():
        stripped = line.lstrip()
        if marker in line and stripped[:1] in prefixes:
            return line
    return None


def _backtick_keys(line: str) -> set[str]:
    return {_normalize_key(t) for t in _BACKTICK_RE.findall(line)}


@pytest.mark.parametrize("kind", _KINDS)
def test_io_contract_kind_keys_match_specfm(kind, specfm_mod):
    """io-contract.md §9 の kind 行が specfm.STRUCTURAL_REQUIRED の全キーを列挙する。"""
    if not _IO_CONTRACT.is_file():
        pytest.skip(f"io-contract.md 不在: {_IO_CONTRACT}")
    line = _kind_line(_IO_CONTRACT.read_text(encoding="utf-8"), kind, ("|",))
    assert line is not None, f"io-contract.md に kind={kind} の表行 (| **{kind}** |) が無い"
    tokens = _backtick_keys(line)
    required = set(specfm_mod.STRUCTURAL_REQUIRED[kind])
    missing = sorted(required - tokens)
    assert not missing, (
        f"io-contract.md §9 の {kind} 行が specfm.STRUCTURAL_REQUIRED のキーを欠落: {missing}\n"
        f"(specfm にキーを足したら io-contract.md §9 の表へ追記すること)"
    )


@pytest.mark.parametrize("kind", [k for k in _KINDS if k != "skill"])
def test_r3_nonskill_kind_keys_match_specfm(kind, specfm_mod):
    """R3-emit-specs.md §2.2 の非 skill kind 箇条が specfm の全キーを列挙する。"""
    if not _R3.is_file():
        pytest.skip(f"R3-emit-specs.md 不在: {_R3}")
    line = _kind_line(_R3.read_text(encoding="utf-8"), kind, ("-", "*"))
    assert line is not None, f"R3-emit-specs.md に kind={kind} の箇条 (- **{kind}**:) が無い"
    tokens = _backtick_keys(line)
    required = set(specfm_mod.STRUCTURAL_REQUIRED[kind])
    missing = sorted(required - tokens)
    assert not missing, (
        f"R3-emit-specs.md §2.2 の {kind} 箇条が specfm.STRUCTURAL_REQUIRED のキーを欠落: {missing}"
    )


def test_r3_skill_delegates_to_specfm():
    """R3 の skill 箇条は 14 キーを列挙せず specfm.SKILL_BRIEF_FIELDS を名指し参照する
    (doc-points-to-SSOT パターン=二重定義回避)。参照が消えたら検出する。"""
    if not _R3.is_file():
        pytest.skip(f"R3-emit-specs.md 不在: {_R3}")
    line = _kind_line(_R3.read_text(encoding="utf-8"), "skill", ("-", "*"))
    assert line is not None, "R3-emit-specs.md に skill 箇条が無い"
    assert "specfm.SKILL_BRIEF_FIELDS" in line, (
        "R3 の skill 箇条が specfm.SKILL_BRIEF_FIELDS への参照を失った "
        "(skill は 14 キー全列挙でなく specfm 名指し参照で SSOT 一本化する設計)"
    )


def test_parity_guard_catches_drift(specfm_mod):
    """本ガードが「specfm にキーを足して散文を忘れた」drift を確かに検出する回帰固定。"""
    required = set(specfm_mod.STRUCTURAL_REQUIRED["hook"])
    # 正例: 全キーが散文行に在る → 欠落なし
    good = "| **hook** | `event`/`matcher`/`exit_semantics`/`settings_wiring`/`fail_closed: true` |"
    assert not (required - _backtick_keys(good))
    # 負例: specfm に新キー `new_required` を足したのに散文が欠く → 検出される
    drifted = required | {"new_required"}
    assert sorted(drifted - _backtick_keys(good)) == ["new_required"]
