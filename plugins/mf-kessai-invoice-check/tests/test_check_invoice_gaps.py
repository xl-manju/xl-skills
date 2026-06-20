#!/usr/bin/env python3
"""check_invoice_gaps.py の出力先解決(F2)・確定リスト昇格(F1)・schema検証(F4)の回帰テスト。

ネットワーク/Notion を伴わない純ファイル操作部分のみを対象とする。
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "skills", "run-mf-invoice-check", "scripts"))
import check_invoice_gaps as c  # noqa: E402


# --- F2: 出力先解決 env > project > cwd ---

def test_eval_log_prefers_env(monkeypatch):
    monkeypatch.setenv("MFK_OUTPUT_DIR", "/tmp/mfk-a")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/tmp/mfk-b")
    assert c.eval_log_dir() == "/tmp/mfk-a/eval-log"


def test_eval_log_falls_back_to_project(monkeypatch):
    monkeypatch.delenv("MFK_OUTPUT_DIR", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/tmp/mfk-b")
    assert c.eval_log_dir() == "/tmp/mfk-b/eval-log"


def test_eval_log_falls_back_to_cwd(monkeypatch, tmp_path):
    monkeypatch.delenv("MFK_OUTPUT_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert c.eval_log_dir() == os.path.join(str(tmp_path), "eval-log")


def test_no_repo_root_assumption():
    """_REPO_ROOT 派生 (repo 配置前提) が撤廃されていること。"""
    assert not hasattr(c, "_REPO_ROOT")
    assert not hasattr(c, "DEFAULT_CANDIDATES")


# --- F4: schema 検証 ---

def test_validate_rows_ok():
    rows = [{"customer_id": "c1", "period_ym": "2026-06", "verdict": "発行漏れ候補"}]
    assert c.validate_rows(rows) == []


def test_validate_rows_rejects_empty_period():
    rows = [{"customer_id": "c1", "period_ym": "", "verdict": "発行漏れ候補"}]
    errs = c.validate_rows(rows)
    assert errs and "period_ym" in errs[0]


def test_validate_rows_rejects_bad_verdict_and_empty_cid():
    rows = [{"customer_id": "", "period_ym": "2026-06", "verdict": "謎判定"}]
    errs = c.validate_rows(rows)
    assert any("customer_id" in e for e in errs)
    assert any("verdict" in e for e in errs)


# --- F1: finalize による確定リスト昇格 (誤検出除外) ---

def _cands(tmp_path):
    p = tmp_path / "mfk-gap-candidates.json"
    p.write_text(json.dumps([
        {"customer_id": "c1", "period_ym": "2026-06", "verdict": "発行漏れ候補"},
        {"customer_id": "c2", "period_ym": "2026-06", "verdict": "発行漏れ候補"},
        {"customer_id": "c3", "period_ym": "2026-06", "verdict": "継続発行"},
    ], ensure_ascii=False), encoding="utf-8")
    return p


def test_finalize_excludes_false_positive(tmp_path):
    src = _cands(tmp_path)
    out = tmp_path / "verified.json"
    rc = c.finalize(["c2"], str(src), str(out))
    assert rc == 0
    kept = json.loads(out.read_text(encoding="utf-8"))
    ids = {r["customer_id"] for r in kept}
    assert ids == {"c1", "c3"}  # 誤検出 c2 のみ除外、継続発行 c3 は素通し


def test_finalize_keeps_all_when_no_exclusions(tmp_path):
    src = _cands(tmp_path)
    out = tmp_path / "verified.json"
    rc = c.finalize([""], str(src), str(out))  # 除外なし (空文字は無視)
    assert rc == 0
    kept = json.loads(out.read_text(encoding="utf-8"))
    assert len(kept) == 3


def test_finalize_does_not_exclude_non_gap(tmp_path):
    """継続発行は誤検出除外の対象外 (発行漏れ候補のみ exclude 可)。"""
    src = _cands(tmp_path)
    out = tmp_path / "verified.json"
    c.finalize(["c3"], str(src), str(out))
    kept = json.loads(out.read_text(encoding="utf-8"))
    assert "c3" in {r["customer_id"] for r in kept}


def test_finalize_rejects_invalid_input(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"customer_id": "x", "period_ym": "", "verdict": "発行漏れ候補"}]),
                   encoding="utf-8")
    out = tmp_path / "v.json"
    assert c.finalize([], str(bad), str(out)) == 2
    assert not out.exists()
