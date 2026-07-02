"""dogfooding 境界 (skill-creator 自身の除外/非除外) の SSOT 一本化を機械担保する。

findings SS-01 / SS-08 / SS-10 で検出した綻びを再発防止する:
  - 制御リテラル "skill-creator" が4 consumer に独立散在し、非対称な除外ルール
    (Stop block=除外 / feedback 配備=除外 / content-review=非除外) の SSOT が無かった。
  - 本テストは (a) SSOT 述語の真偽値、(b) 各 consumer が判定用スタンドアロン
    リテラルを残さず SSOT 述語へ委譲していること (textual + behavioral) を固定する。

二段確認 (feedback_verification_two_stage): textual grep だけでなく、各 consumer を
実際に import して _FC/FC が SSOT に解決し述語が正しい値を返すことも検証する。
"""
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SSOT_PATH = ROOT / "scripts" / "feedback_contract_ssot.py"

LINT_CONTENT_REVIEW = ROOT / "scripts" / "lint-content-review.py"
LINT_FEEDBACK_PROTOCOL = ROOT / "scripts" / "lint-feedback-protocol.py"
CHECK_REVIEW_TRIGGER = (
    ROOT
    / "plugins" / "skill-creator" / "skills" / "run-elegant-review"
    / "scripts" / "check-review-trigger.py"
)
RENDER_COMBINATORS = (
    ROOT
    / "plugins" / "skill-creator" / "skills" / "run-build-skill"
    / "scripts" / "render-combinators.py"
)

CONSUMERS = [
    LINT_CONTENT_REVIEW,
    LINT_FEEDBACK_PROTOCOL,
    CHECK_REVIEW_TRIGGER,
    RENDER_COMBINATORS,
]

# 判定用スタンドアロン *リテラル* / 比較を禁止する (パス構築や SSOT 由来エイリアスは許容)。
# 核心は「制御リテラル "skill-creator" を判定に直書きしない」こと。SSOT から値を引く
# 後方互換エイリアス (= _FC.SELF_DOGFOODING_PLUGIN) は SSOT 一本化を破らないため許容する。
_JUDGMENT_LITERAL_RES = [
    re.compile(r"""(?:==|!=)\s*["']skill-creator["']"""),       # x == "skill-creator"
    re.compile(r"""["']skill-creator["']\s*(?:==|!=)"""),       # "skill-creator" == x
    re.compile(r"""\bin\s*[\{\(\[][^\}\)\]]*["']skill-creator["']"""),  # in {"skill-creator"}
    re.compile(r"""\bSELF_EXCLUDED_PLUGIN\s*=\s*["']skill-creator["']"""),  # 旧リテラル定数
    re.compile(r"""EXEMPT_PLUGINS\s*=\s*[\{\(\[][^\}\)\]]*["']skill-creator"""),
]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(scope="module")
def fc():
    return _load(SSOT_PATH, "feedback_contract_ssot")


# ─────────────────────────── (a) 述語の真偽値 ───────────────────────────


def test_self_dogfooding_plugin_constant(fc):
    assert fc.SELF_DOGFOODING_PLUGIN == "skill-creator"


def test_stop_block_exempt_truth_table(fc):
    """Stop block: skill-creator は除外 (True)、他は非除外。"""
    assert fc.is_stop_block_exempt("skill-creator") is True
    for other in ("company-master", "mf-kessai-invoice-check", "skill-intake", ""):
        assert fc.is_stop_block_exempt(other) is False


def test_feedback_deploy_exempt_truth_table(fc):
    """feedback 配備: skill-creator は除外 (True)、他は非除外。"""
    assert fc.is_feedback_deploy_exempt("skill-creator") is True
    for other in ("company-master", "prompt-creator", "skill-intake", ""):
        assert fc.is_feedback_deploy_exempt(other) is False


def test_content_review_exempt_is_asymmetric(fc):
    """content-review: 生成器自身も dogfooding 対象なので **非除外** (常に False)。"""
    assert fc.is_content_review_exempt("skill-creator") is False
    for other in ("company-master", "prompt-creator", ""):
        assert fc.is_content_review_exempt(other) is False


def test_asymmetry_holds(fc):
    """非対称性の核: skill-creator は block/配備では除外だが content-review では非除外。"""
    p = fc.SELF_DOGFOODING_PLUGIN
    assert fc.is_stop_block_exempt(p) and fc.is_feedback_deploy_exempt(p)
    assert not fc.is_content_review_exempt(p)


def test_engine_skills_closure_is_ssot_frozenset(fc):
    """エンジン閉包 (収束ポリシー/評価経路) の列挙は SSOT の frozenset のみ (散在禁止)。"""
    assert isinstance(fc.ENGINE_SKILLS, frozenset)
    assert fc.ENGINE_SKILLS == frozenset(
        {"run-elegant-review", "run-skill-iter-improve", "run-skill-live-trial"}
    )


def test_requires_subject_copy_truth_table(fc):
    """INV7: skill-creator×エンジン閉包の交差時のみ被験体コピー強制 (True)。"""
    for engine in sorted(fc.ENGINE_SKILLS):
        assert fc.requires_subject_copy("skill-creator", engine) is True
    # 通常 skill は直接編集を維持 (False)
    for normal in ("run-build-skill", "run-skill-feedback", ""):
        assert fc.requires_subject_copy("skill-creator", normal) is False
    # 他 plugin はエンジン名の skill でも False (交差条件は自己 plugin のみ)
    for other in ("company-master", "mf-kessai-invoice-check", ""):
        assert fc.requires_subject_copy(other, "run-elegant-review") is False


# ────────────── (b-1) 判定用リテラルが consumer に残っていない ──────────────


@pytest.mark.parametrize("path", CONSUMERS, ids=lambda p: p.name)
def test_no_standalone_judgment_literal(path):
    src = path.read_text(encoding="utf-8")
    for rgx in _JUDGMENT_LITERAL_RES:
        m = rgx.search(src)
        assert m is None, (
            f"{path.name}: 判定用 'skill-creator' リテラルが残存 "
            f"(SSOT 述語へ委譲すべき): {m.group(0)!r}"
        )


# ────────────── (b-2) 各 consumer が SSOT 述語へ委譲している (textual) ──────────────


def test_content_review_uses_predicate():
    src = LINT_CONTENT_REVIEW.read_text(encoding="utf-8")
    assert "is_content_review_exempt" in src


def test_feedback_protocol_uses_predicate():
    src = LINT_FEEDBACK_PROTOCOL.read_text(encoding="utf-8")
    assert "is_feedback_deploy_exempt" in src
    assert "import feedback_contract_ssot" in src


def test_check_review_trigger_uses_predicate():
    src = CHECK_REVIEW_TRIGGER.read_text(encoding="utf-8")
    assert "is_stop_block_exempt" in src
    assert "feedback_contract_ssot" in src


def test_render_combinators_uses_predicate():
    src = RENDER_COMBINATORS.read_text(encoding="utf-8")
    assert "is_feedback_deploy_exempt" in src
    assert "feedback_contract_ssot" in src


# ───────────── (b-3) 二段確認: import して runtime で SSOT に解決する ─────────────


def test_check_review_trigger_resolves_ssot_at_runtime():
    mod = _load(CHECK_REVIEW_TRIGGER, "check_review_trigger_under_test")
    assert mod._FC.is_stop_block_exempt("skill-creator") is True
    assert mod._FC.is_stop_block_exempt("company-master") is False


def test_render_combinators_resolves_ssot_at_runtime():
    mod = _load(RENDER_COMBINATORS, "render_combinators_under_test")
    assert mod._FC.is_feedback_deploy_exempt("skill-creator") is True
    assert mod._FC.is_feedback_deploy_exempt("company-master") is False


def test_apply_feedback_loop_still_skips_self(tmp_path):
    """apply_feedback_loop は skill-creator では自己コピーを作らない。"""
    mod = _load(RENDER_COMBINATORS, "render_combinators_behavior")
    sc = tmp_path / "skill-creator"
    sc.mkdir()
    link = mod.apply_feedback_loop(sc)
    assert link == sc.resolve() / "skills" / "run-skill-feedback"
    assert not link.exists()  # 自己へのコピーは作らない

    other = tmp_path / "company-master"
    other.mkdir()
    link2 = mod.apply_feedback_loop(other)
    assert link2.is_dir()
    assert not link2.is_symlink()
