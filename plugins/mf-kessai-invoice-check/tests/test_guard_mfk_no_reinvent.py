#!/usr/bin/env python3
"""PreToolUse hook `guard-mfk-no-reinvent.py` の再発明/TODO(human) 遮断の回帰テスト。

守るべき不変条件 (現行の実挙動を忠実に固定する・理想化しない):
  - 照合ドメイン文脈で `TODO(human)` を **コード**に書く Write/Edit/MultiEdit は exit 2 で遮断 (R1)。
  - 正本 (mfk_reconcile.py / reconcile_invoices.py) 以外の新規ファイルへ照合エンジンを
    再実装する `def classify`/`def reconcile` 等は exit 2 で遮断 (R2)。
  - 正本ファイル自身の編集 (allowlist)・ドキュメント (.md)・テスト (/tests/) は対象外で許可。
  - **ドメイン信号が無いコンテンツは一切遮断しない** (他プロジェクトの正当な TODO(human)/
    classify を誤遮断しない)。
  - Write/Edit/MultiEdit 以外の tool は対象外で許可。

guard はファイル名にハイフンを含むため通常 import できない。importlib の SourceFileLoader で
module ロードし `main()`/`evaluate()` を直接呼ぶ経路と、実 hook を subprocess で起動して exit
code を見る経路の両方で境界を固定する。
"""
import importlib.util
import io
import json
import os
import subprocess
import sys

import pytest


_HOOK_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "hooks", "guard-mfk-no-reinvent.py")
)


def _load_guard():
    spec = importlib.util.spec_from_file_location("guard_mfk_no_reinvent", _HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard = _load_guard()


def _run_main(payload, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload, ensure_ascii=False)))
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    return guard.main()


def _run_subprocess(payload):
    proc = subprocess.run(
        [sys.executable, _HOOK_PATH],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stderr


def _write(file_path, content):
    return {"tool_name": "Write", "tool_input": {"file_path": file_path, "content": content}}


# --- R1: TODO(human) をドメイン文脈のコードに書くと遮断 -----------------------------

def test_todo_human_in_domain_code_is_blocked(monkeypatch):
    payload = _write(
        "/repo/reconcile_judgments.py",
        "def classify(sheet_row, mf_match):\n    # 請求確認シート×MF掛け払い照合\n    TODO(human)\n",
    )
    assert _run_main(payload, monkeypatch) == 2


def test_todo_human_block_mentions_existing_engine(monkeypatch):
    payload = _write("/repo/x.py", "# mfk_reconcile 照合\nTODO(human)\n")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload, ensure_ascii=False)))
    err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", err)
    assert guard.main() == 2
    assert "lib/mfk_reconcile.py" in err.getvalue()


def test_todo_human_without_domain_is_allowed(monkeypatch):
    # 別プロジェクトの正当な TODO(human) は誤遮断しない (ドメイン信号なし)。
    payload = _write("/other/project/foo.py", "def helper():\n    TODO(human)\n")
    assert _run_main(payload, monkeypatch) == 0


# --- R2: 正本以外への照合エンジン再実装を遮断 ----------------------------------------

def test_reinvented_classify_in_new_file_is_blocked(monkeypatch):
    payload = _write(
        "/repo/my_reconcile.py",
        "def reconcile(contracts, mf_index):\n    return 発行漏れ判定\n",
    )
    assert _run_main(payload, monkeypatch) == 2


def test_reinvent_block_points_to_canonical_entry(monkeypatch):
    payload = _write("/repo/my_reconcile.py", "請求確認シート\ndef classify(row):\n    pass\n")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload, ensure_ascii=False)))
    err = io.StringIO()
    monkeypatch.setattr(sys, "stderr", err)
    assert guard.main() == 2
    assert "reconcile_invoices.py" in err.getvalue()
    assert "mfk_reconcile.py" in err.getvalue()


def test_reinvent_def_without_domain_is_allowed(monkeypatch):
    # 無関係な classify (ML 等) はドメイン信号が無ければ通す。
    payload = _write("/ml/model.py", "def classify(image):\n    return label\n")
    assert _run_main(payload, monkeypatch) == 0


# --- allowlist / 対象外 -----------------------------------------------------------

def test_editing_sanctioned_engine_is_allowed(monkeypatch):
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/p/lib/mfk_reconcile.py",
            "new_string": "def classify(contracts, mf_index, target_ym):\n    # 請求確認シート照合\n    ...\n",
        },
    }
    assert _run_main(payload, monkeypatch) == 0


def test_todo_human_in_sanctioned_engine_is_still_blocked(monkeypatch):
    # allowlist は R2 (再実装) のみ免除。R1 (判定丸投げ) は正本上でも意図的に遮断する。
    payload = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "/p/lib/mfk_reconcile.py",
            "new_string": "def classify(contract, mf):\n    # 請求確認シート照合の判定\n    TODO(human)\n",
        },
    }
    assert _run_main(payload, monkeypatch) == 2


def test_sanctioned_orchestrator_is_allowed(monkeypatch):
    payload = _write(
        "/p/scripts/reconcile_invoices.py",
        "# 請求確認シート orchestrator\ndef reconcile_main():\n    pass\n",
    )
    assert _run_main(payload, monkeypatch) == 0


def test_markdown_doc_is_exempt(monkeypatch):
    # README/SKILL が反パターンを文章で説明・引用するのは正当。
    payload = _write(
        "/p/README.md",
        "請求確認シート照合では `TODO(human)` を使わず classify を呼ぶ。",
    )
    assert _run_main(payload, monkeypatch) == 0


def test_tests_dir_is_exempt(monkeypatch):
    # hook 自身の回帰テストが fixture として TODO(human) / classify を持てるように。
    payload = _write(
        "/p/tests/test_x.py",
        "請求確認シート\ndef classify(x):\n    TODO(human)\n",
    )
    assert _run_main(payload, monkeypatch) == 0


# --- tool 種別・MultiEdit ----------------------------------------------------------

def test_non_write_tool_is_ignored(monkeypatch):
    payload = {"tool_name": "Bash", "tool_input": {"command": "echo TODO(human) 請求確認シート"}}
    assert _run_main(payload, monkeypatch) == 0


def test_bash_heredoc_reinvented_classify_is_blocked(monkeypatch):
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": (
                "cat > reconcile_judgments.py <<'PY'\n"
                "# 請求確認シート × MF掛け払い 照合\n"
                "def classify(sheet_row, mf_match):\n"
                "    TODO(human)\n"
                "PY\n"
            )
        },
    }
    assert _run_main(payload, monkeypatch) == 2


def test_bash_readonly_search_for_reinvent_terms_is_allowed(monkeypatch):
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": "rg 'def classify|TODO\\\\(human\\\\)' plugins/mf-kessai-invoice-check"
        },
    }
    assert _run_main(payload, monkeypatch) == 0


def test_multiedit_reinvention_is_blocked(monkeypatch):
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": "/repo/adhoc.py",
            "edits": [
                {"old_string": "a", "new_string": "# 掛け払い照合"},
                {"old_string": "b", "new_string": "def detect_orphans(mf, contracts):\n    pass\n"},
            ],
        },
    }
    assert _run_main(payload, monkeypatch) == 2


def test_empty_content_is_allowed(monkeypatch):
    assert _run_main(_write("/repo/x.py", ""), monkeypatch) == 0


# --- subprocess 経路で実 exit code を固定 -------------------------------------------

def test_subprocess_blocks_todo_human_in_domain():
    code, err = _run_subprocess(
        _write("/repo/reconcile_judgments.py", "請求確認シート\nTODO(human)\n")
    )
    assert code == 2
    assert "guard-mfk-no-reinvent" in err


def test_subprocess_allows_unrelated_write():
    code, _ = _run_subprocess(_write("/repo/notes.py", "x = 1\n"))
    assert code == 0


def test_malformed_payload_is_safe():
    proc = subprocess.run(
        [sys.executable, _HOOK_PATH], input="not json", capture_output=True, text=True
    )
    assert proc.returncode == 0
