"""harness-creator/scripts/*.py を file-path import するための共通ローダ。

scripts/*.py はハイフン名のため通常 import 不可。importlib で明示ロードする。
plugin-root script は cross-plugin import を避け自己完結するため specfm 依存はない。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load(stem: str) -> ModuleType:
    path = SCRIPTS_DIR / f"{stem}.py"
    spec = importlib.util.spec_from_file_location(stem.replace("-", "_"), path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def parity() -> ModuleType:
    return _load("check-route-component-parity")


@pytest.fixture(scope="session")
def emit() -> ModuleType:
    return _load("emit-improvement-handoff")


@pytest.fixture(scope="session")
def script_route_builder() -> ModuleType:
    return _load("build-script-route")


@pytest.fixture(scope="session")
def content_lint() -> ModuleType:
    return _load("lint-agent-prompt-content")
