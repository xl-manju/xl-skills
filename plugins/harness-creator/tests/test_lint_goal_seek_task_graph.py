"""C04 回帰: lint-goal-seek.py --self-test の SSOT 整合ゲート。

task-graph 変種 (build-flags engine enum / goal-seek-loop depends_on) を additive 追加した後も、
既定 drift 自己検査 (check_default_drift) を含む全 SSOT 整合検査が exit0 で維持されること、
既存の usage 検査が壊れていないことを固定する。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/run-build-skill/scripts/lint-goal-seek.py"
)


def test_script_exists():
    assert SCRIPT.is_file()


def test_self_test_exit0():
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--self-test"], capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_usage_no_arg_exit2():
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 2
