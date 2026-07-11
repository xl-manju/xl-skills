"""run-ubm-consult (C09) の契約を決定論で検証する。

コーチング型相談 orchestrator の骨格が仕様どおり配線されているかを、実行時対話に
依存しない範囲で機械確認する:
  - SKILL.md frontmatter の feedback_contract(IN1 inner/test・OUT1 outer/test)存在
  - goal_seek(engine:inline / fork:subagent / max_loops:5)と combinators
  - responsibility_refs が prompts R1-R4 を列挙し実在
  - スタンス不変条件(非処方/引き出し/ユーザー言語化/ゴール指向/責務境界)の文言が SKILL.md に存在
  - prompts R1-R4 が 7 層アンカー(Layer 1..7 + 出力指示)を持つ
  - workflow-manifest の phase(r1-r4)と resourceIds prompt の整合・実在
  - references(consult-frames.md / session-record-format.md / resource-map.yaml)実在
  - OUT1 の transcript 4要素検出ヘルパを正例/負例 fixture で検証
実 knowledge/ や vault には一切触れない。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = PLUGIN_ROOT / "skills/run-ubm-consult"
SKILL_MD = SKILL_DIR / "SKILL.md"
MANIFEST = SKILL_DIR / "workflow-manifest.json"
PROMPTS = ["R1-intake-issue", "R2-elicit", "R3-frame-consult", "R4-cocreate-converge"]
REFERENCES = ["consult-frames.md", "session-record-format.md", "resource-map.yaml"]


def _frontmatter(text: str) -> str:
    assert text.startswith("---"), "frontmatter が --- で始まっていない"
    parts = text.split("---", 2)
    assert len(parts) >= 3, "frontmatter ブロックが閉じていない"
    return parts[1]


def _body(text: str) -> str:
    return text.split("---", 2)[2]


# --------------------------------------------------------------------------- #
# 骨格の実在
# --------------------------------------------------------------------------- #
def test_skill_and_supports_exist():
    assert SKILL_MD.is_file(), f"SKILL.md 不在: {SKILL_MD}"
    assert MANIFEST.is_file(), f"workflow-manifest.json 不在: {MANIFEST}"
    for slug in PROMPTS:
        p = SKILL_DIR / "prompts" / f"{slug}.md"
        assert p.is_file(), f"prompt 不在: {p}"
    for ref in REFERENCES:
        r = SKILL_DIR / "references" / ref
        assert r.is_file(), f"reference 不在: {r}"


# --------------------------------------------------------------------------- #
# frontmatter: feedback_contract / goal_seek / combinators / refs
# --------------------------------------------------------------------------- #
def test_frontmatter_core_fields():
    fm = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    assert re.search(r"^name:\s*run-ubm-consult\s*$", fm, re.M)
    assert re.search(r"^kind:\s*run\s*$", fm, re.M)
    assert re.search(r"^prefix:\s*run\s*$", fm, re.M)
    # run kind は Step 7-4 で disable-model-invocation: true が必須
    assert re.search(r"^disable-model-invocation:\s*true\s*$", fm, re.M)
    assert re.search(r"^effect:\s*local-artifact\s*$", fm, re.M)


def test_frontmatter_goal_seek():
    fm = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    assert re.search(r"engine:\s*inline", fm)
    assert re.search(r"fork:\s*subagent", fm)
    assert re.search(r"max_loops:\s*5", fm)


def test_frontmatter_combinators():
    fm = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    assert "with-goal-seek" in fm
    assert "with-feedback-contract" in fm


def test_feedback_contract_in1_out1():
    fm = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    assert "feedback_contract:" in fm
    # IN1 = inner / OUT1 = outer、双方 verify_by: test
    assert re.search(r"id:\s*IN1", fm), "IN1 が feedback_contract に無い"
    assert re.search(r"id:\s*OUT1", fm), "OUT1 が feedback_contract に無い"
    # IN1 ブロックに inner、OUT1 ブロックに outer が並ぶ
    m_in = re.search(r"id:\s*IN1.*?verify_by:\s*(\w+)", fm, re.S)
    m_out = re.search(r"id:\s*OUT1.*?verify_by:\s*(\w+)", fm, re.S)
    assert m_in and m_in.group(1) == "test"
    assert m_out and m_out.group(1) == "test"
    assert "loop_scope: inner" in fm
    assert "loop_scope: outer" in fm


def test_responsibility_refs_list_all_prompts():
    fm = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    for slug in PROMPTS:
        assert f"prompts/{slug}.md" in fm, f"responsibility_refs に {slug} 未列挙"


def test_reference_and_script_refs_resolve():
    fm = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    # reference_refs はローカル解決、script_refs は plugin scripts へ解決
    for ref in REFERENCES:
        assert f"references/{ref}" in fm
        assert (SKILL_DIR / "references" / ref).is_file()
    for script in ("consult-harness-artifact-graph.py", "validate-knowledge-graph.py"):
        assert f"../../scripts/{script}" in fm
        assert (PLUGIN_ROOT / "scripts" / script).is_file(), f"script 不在: {script}"


# --------------------------------------------------------------------------- #
# スタンス不変条件の文言が SKILL.md 本文に存在
# --------------------------------------------------------------------------- #
STANCE_MARKERS = [
    "具体解の押し付けゼロ",          # (1) 非処方
    "引き出し質問",                   # (2) 各ターン引き出し
    "ユーザーの発話",                 # (3) 解決策の言語化はユーザー主導
    "現状→ゴール→ギャップ→次の一歩",  # (4) ゴール指向の締め
    "run-ubm-goal-setting へ誘導",    # (5) 責務境界
]


@pytest.mark.parametrize("marker", STANCE_MARKERS)
def test_stance_invariants_present(marker):
    body = _body(SKILL_MD.read_text(encoding="utf-8"))
    assert marker in body, f"スタンス不変条件の文言が SKILL.md に無い: {marker}"


# --------------------------------------------------------------------------- #
# prompts: 7 層アンカー
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("slug", PROMPTS)
def test_prompt_seven_layer_anchors(slug):
    text = (SKILL_DIR / "prompts" / f"{slug}.md").read_text(encoding="utf-8")
    for n in range(1, 8):
        assert re.search(rf"##\s*Layer\s*{n}:", text), f"{slug}: Layer {n} 見出し欠落"
    assert "## 出力指示" in text, f"{slug}: 出力指示 節欠落"
    assert re.search(r"responsibility\s*\|\s*" + re.escape(slug), text), (
        f"{slug}: メタ responsibility が一致しない"
    )


# --------------------------------------------------------------------------- #
# workflow-manifest 整合
# --------------------------------------------------------------------------- #
def test_manifest_phases_align_with_prompts():
    import json

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["workflowId"] == "run-ubm-consult"
    assert data["skill"] == "run-ubm-consult"
    phase_ids = [p["id"] for p in data["phases"]]
    assert phase_ids == ["r1-intake-issue", "r2-elicit", "r3-frame-consult", "r4-cocreate-converge"]
    # 各 phase の prompt resourceId が実在
    for phase in data["phases"]:
        prompt_refs = [r for r in phase["resourceIds"] if r.startswith("prompts/")]
        assert prompt_refs, f"{phase['id']}: prompt resourceId が無い"
        for r in prompt_refs:
            assert (SKILL_DIR / r).is_file(), f"{phase['id']}: resource 不在 {r}"
    # dependsOn が直列 (R1<-R2<-R3<-R4)
    dep = {p["id"]: p["dependsOn"] for p in data["phases"]}
    assert dep["r1-intake-issue"] == []
    assert dep["r2-elicit"] == ["r1-intake-issue"]
    assert dep["r3-frame-consult"] == ["r2-elicit"]
    assert dep["r4-cocreate-converge"] == ["r3-frame-consult"]


def test_manifest_r3_consult_graceful_fallback():
    import json

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    r3 = next(p for p in data["phases"] if p["id"] == "r3-frame-consult")
    consults = r3.get("consults")
    assert consults, "R3 に consults ブロックが無い"
    assert "consult-harness-artifact-graph.py" in consults["script"]
    # グラフ未生成時の graceful fallback が note に明記されている
    assert "フォールバック" in consults["note"] or "fallback" in consults["note"]


# --------------------------------------------------------------------------- #
# OUT1: transcript 4 要素検出ヘルパ + fixture 検証
# --------------------------------------------------------------------------- #
def detect_transcript_elements(transcript: str) -> dict[str, bool]:
    """相談セッション transcript から OUT1 の4要素を検出する。

    決定論的なマーカーベース検出。run-ubm-consult の受入テスト(OUT1)が
    セッション記録の完全性を判定するための共有ヘルパ。
    """
    t = transcript
    return {
        # (1) 考え方/思考フレームの提示 (選択肢としての見方)
        "frame_presented": bool(re.search(r"考え方|思考フレーム|見方|フレーム", t)),
        # (2) 引き出し質問 (問いの存在)
        "elicit_question": ("？" in t) or ("?" in t),
        # (3) ユーザー自身の言葉での解決策言語化
        "user_verbalized": bool(re.search(r"ユーザー[:：].*(解決|やる|する|決め|言葉)", t)),
        # (4) ゴール指向の次の一歩
        "next_step": bool(
            re.search(r"次の一歩", t)
            and re.search(r"現状|ゴール|ギャップ", t)
        ),
    }


def test_out1_detector_positive_fixture():
    transcript = (
        "AI: 今回の論点はどこにありそうですか？（引き出し）\n"
        "ユーザー: 新規のお客さんとの最初の接点をどう作るかで迷っています。\n"
        "AI: いくつかの見方（考え方）を並べますね。A: 関係構築ファースト、B: 逆算。"
        "あなたの場合はどちらが当てはまりそうですか？\n"
        "ユーザー: Aで、まず既存客に紹介をお願いする、と自分の言葉で決めました。\n"
        "AI: では現状→ゴール→ギャップ→次の一歩で整理します。"
        "次の一歩: 今週中に既存客3名へ紹介依頼のメッセージを送る。\n"
    )
    result = detect_transcript_elements(transcript)
    assert all(result.values()), f"正例で未検出要素: {result}"


def test_out1_detector_negative_prescriptive():
    # 処方的で引き出しもユーザー言語化も無い transcript は不合格
    transcript = (
        "AI: あなたは値上げをすべきです。以下を実行してください。\n"
        "AI: 1. 価格を20%上げる 2. 広告を出す。以上が正解です。\n"
    )
    result = detect_transcript_elements(transcript)
    assert not all(result.values()), "負例(処方的)が全要素 True になっている"
    assert result["user_verbalized"] is False
    assert result["next_step"] is False


# --------------------------------------------------------------------------- #
# IN1: 非処方スタンス(具体解押し付けゼロ)検出ヘルパ + fixture 検証
# --------------------------------------------------------------------------- #
def detect_prescription_stance(response: str) -> dict[str, bool]:
    """相談への1応答から IN1(非処方スタンス)の2条件を決定論検出する。

    IN1 = 具体解を処方せず考え方/思考フレームを1件以上提示し、非処方スタンス
    不変条件(具体解の押し付けゼロ)を満たす。run-ubm-consult の受入テスト(IN1)が
    R3 応答の非処方性を判定するための共有ヘルパ。
    """
    r = response
    return {
        # (1) 考え方/思考フレームを1件以上提示している
        "frame_presented": bool(re.search(r"考え方|思考フレーム|見方|フレーム", r)),
        # (2) 具体解の処方(単一解の押し付け)をしていない
        #     命令形の断定/「正解」提示を処方マーカーとする(引き出し質問は処方でない)
        "no_prescription": not bool(
            re.search(r"すべきです|しなさい|が正解|以上が正解|実行してください|従ってください", r)
        ),
    }


def in1_pass(response: str) -> bool:
    s = detect_prescription_stance(response)
    return s["frame_presented"] and s["no_prescription"]


def test_in1_non_prescriptive_fixture_passes():
    # OK 例: 具体解を処方せず、考え方(見方)を選択肢で提示し、選択をユーザーに委ねる
    response = (
        "いくつかの見方（考え方）を並べますね。\n"
        "見方A: ゴール指向分解 — 現状とありたい姿の差はどこにありそうですか？\n"
        "見方B: 前提検証 — 「できない」の前提を1つ外すと何が変わりそうですか？\n"
        "どちらが今のあなたに当てはまりそうですか？ 選ぶのはあなたです。\n"
    )
    s = detect_prescription_stance(response)
    assert s["frame_presented"] is True, f"考え方/フレーム未提示: {s}"
    assert s["no_prescription"] is True, f"処方マーカーを誤検出/含有: {s}"
    assert in1_pass(response) is True


def test_in1_prescriptive_fixture_fails():
    # NG 例: 単一解を押し付ける処方的応答は IN1 不合格
    response = (
        "あなたは値上げをすべきです。以下を実行してください。\n"
        "1. 価格を20%上げる 2. 広告を出す。以上が正解です。\n"
    )
    s = detect_prescription_stance(response)
    assert s["no_prescription"] is False, "処方マーカーを検出できていない"
    assert in1_pass(response) is False, "処方的応答が IN1 合格になっている"


def test_in1_detector_separates_ok_from_ng():
    ok = (
        "こういう見方（考え方）があります。あなたの場合はどう当てはまりますか？\n"
    )
    ng = "あなたは今すぐ撤退すべきです。従ってください。"
    assert in1_pass(ok) is True
    assert in1_pass(ng) is False
