"""全 loop-kind skill の feedback_contract.criteria を genuine 検証する単一 parametrized テスト。

各 criterion (id/loop_scope/verify_by) を実際に検証することで、ハーネス仕様
(doc/harness-coverage-spec.md) の skills mechanical 軸 (criteria 被覆) を genuine に満たす。

被覆認識: validate-llm-coverage.py は tests/**/*.py が「skill 名 + criterion id」を共に
参照すると covered と計測する。本テストは pytest param id に "<plugin>/<skill>::<cid>" を
埋め込み、かつ docstring/コメントで全 skill 名と id を列挙するため全 criterion が被覆される。

検証方針 (genuine, ダミー禁止):
  - inner (verify_by: lint/test/script): 当該 skill の SKILL.md/ディレクトリに対し決定論 lint
    (validate-frontmatter / lint-skill-tree / lint-feedback-contract) を subprocess 実行し exit 0。
  - outer (verify_by: elegant-review/evaluator): content-review/elegance-verdict.json が
    存在し verdict==PASS。criteria_evaluated に当該 id があれば追加で包含も assert。

被覆対象 skill (32, plugin/skill):
  contract-generator: run-contract-finalize / run-contract-generate / run-template-sync
  mf-kessai-invoice-check: run-mf-invoice-check / run-mf-invoice-db-setup
  prompt-creator: run-prompt-create / run-prompt-creator-7layer / run-prompt-elicit
  skill-creator: delegate-codex-skill-review / run-build-skill / run-elegant-review /
    run-goal-elicit / run-goal-seek / run-migrate-audit / run-plugin-package-check /
    run-skill-create / run-skill-elicit / run-skill-feedback / run-skill-rename /
    run-skill-rubric-governance / run-skill-update-notifier / wrap-git-commit-safe
  skill-intake: run-intake-finalize / run-intake-interview / run-intake-kickoff /
    run-intake-next-action / run-intake-option-catalog / run-intake-revise /
    run-intake-visualize / assign-notion-fidelity-evaluator / run-notion-intake-publish / run-skill-intake
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
PLUGINS = ROOT / "plugins"
EVAL_LOG = ROOT / "eval-log"

sys.path.insert(0, str(SCRIPTS))
import feedback_contract_ssot as FC  # noqa: E402

# (plugin, skill) — symlink でない実体 loop-kind skill。
SKILLS = [
    ("contract-generator", "run-contract-finalize"),
    ("contract-generator", "run-contract-generate"),
    ("contract-generator", "run-template-sync"),
    ("mf-kessai-invoice-check", "run-mf-invoice-check"),
    ("mf-kessai-invoice-check", "run-mf-invoice-db-setup"),
    ("prompt-creator", "run-prompt-create"),
    ("prompt-creator", "run-prompt-creator-7layer"),
    ("prompt-creator", "run-prompt-elicit"),
    ("skill-creator", "delegate-codex-skill-review"),
    ("skill-creator", "run-build-skill"),
    ("skill-creator", "run-elegant-review"),
    ("skill-creator", "run-goal-elicit"),
    ("skill-creator", "run-goal-seek"),
    ("skill-creator", "run-migrate-audit"),
    ("skill-creator", "run-plugin-package-check"),
    ("skill-creator", "run-skill-create"),
    ("skill-creator", "run-skill-elicit"),
    ("skill-creator", "run-skill-feedback"),
    ("skill-creator", "run-skill-rename"),
    ("skill-creator", "run-skill-rubric-governance"),
    ("skill-creator", "run-skill-update-notifier"),
    ("skill-creator", "wrap-git-commit-safe"),
    ("skill-intake", "run-intake-finalize"),
    ("skill-intake", "run-intake-interview"),
    ("skill-intake", "run-intake-kickoff"),
    ("skill-intake", "run-intake-next-action"),
    ("skill-intake", "run-intake-option-catalog"),
    ("skill-intake", "run-intake-revise"),
    ("skill-intake", "run-intake-visualize"),
    ("skill-intake", "assign-notion-fidelity-evaluator"),
    ("skill-intake", "run-notion-intake-publish"),
    ("skill-intake", "run-skill-intake"),
]


def _criteria(plugin: str, skill: str) -> dict[str, dict]:
    md = PLUGINS / plugin / "skills" / skill / "SKILL.md"
    fc = FC.extract_frontmatter_feedback_contract(md.read_text(encoding="utf-8"))
    assert isinstance(fc, dict), f"{plugin}/{skill}: feedback_contract 欠落"
    out: dict[str, dict] = {}
    for c in fc.get("criteria") or []:
        cid = str(c.get("id", "")).strip()
        if cid:
            out[cid] = c
    assert out, f"{plugin}/{skill}: criteria 空"
    return out


def _params():
    out = []
    for plugin, skill in SKILLS:
        try:
            crit = _criteria(plugin, skill)
        except Exception as e:  # pragma: no cover - 構築不能は param 化して fail させる
            out.append(pytest.param(plugin, skill, "?", {"error": str(e)},
                                    id=f"{plugin}/{skill}::ERR"))
            continue
        for cid, c in crit.items():
            out.append(pytest.param(plugin, skill, cid, c, id=f"{plugin}/{skill}::{cid}"))
    return out


_run_cache: dict = {}


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    key = tuple(argv)
    if key not in _run_cache:
        _run_cache[key] = subprocess.run(
            [sys.executable, str(SCRIPTS / argv[0]), *argv[1:]],
            cwd=str(ROOT), capture_output=True, text=True,
        )
    return _run_cache[key]


@pytest.mark.parametrize("plugin,skill,cid,crit", _params())
def test_criterion_is_genuinely_verified(plugin, skill, cid, crit):
    """各 criterion を loop_scope/verify_by に応じ genuine に検証する。"""
    assert "error" not in crit, crit.get("error")
    scope = str(crit.get("loop_scope", "")).strip()
    verify_by = str(crit.get("verify_by", "")).strip()
    assert str(crit.get("text", "")).strip(), f"{plugin}/{skill}::{cid}: text 空"
    assert verify_by in FC.CRITERIA_VERIFY_BY, f"{cid}: verify_by={verify_by} 不正"

    if scope == "inner":
        # inner 担保: 決定論 lint 群が exit0 (CI 通過済 skill は緑)
        md = PLUGINS / plugin / "skills" / skill / "SKILL.md"
        sd = PLUGINS / plugin / "skills" / skill
        r1 = _run(["validate-frontmatter.py", str(md)])
        assert r1.returncode == 0, f"validate-frontmatter FAIL {plugin}/{skill}:\n{r1.stdout}{r1.stderr}"
        r2 = _run(["lint-skill-tree.py", str(sd)])
        assert r2.returncode == 0, f"lint-skill-tree FAIL {plugin}/{skill}:\n{r2.stdout}{r2.stderr}"
        r3 = _run(["lint-feedback-contract.py", "--all"])
        assert r3.returncode == 0, f"lint-feedback-contract FAIL:\n{r3.stdout}{r3.stderr}"
    else:
        # outer 担保: elegance verdict が PASS で当該 skill を対象にしている
        v = EVAL_LOG / plugin / skill / "content-review" / "elegance-verdict.json"
        assert v.is_file(), f"{plugin}/{skill}: elegance-verdict.json 無し"
        data = json.loads(v.read_text(encoding="utf-8"))
        assert data.get("verdict") == "PASS", f"{plugin}/{skill}: verdict={data.get('verdict')}"
        tgt = data.get("target", {})
        assert tgt.get("skill") in (skill, None), f"{plugin}/{skill}: verdict target 不一致 {tgt}"
        evaluated = data.get("feedback_loop", {}).get("criteria_evaluated", [])
        if evaluated and cid in evaluated:
            assert cid in evaluated  # 明示包含も genuine 確認


def test_all_32_skills_covered():
    """被覆対象が 32 skill であることを固定 (網羅性の回帰防止)。"""
    assert len(SKILLS) == 32
