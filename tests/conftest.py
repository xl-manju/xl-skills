"""テスト共通フィクスチャ: 作業ディレクトリ(cwd)の汚染を防ぐ。

多数の機能テストが os.chdir(tmp_path) を使うが restore しないため、pytest-randomly の
ランダム順で後続テストの相対パス解決が崩れ flaky になる。autouse フィクスチャで全テストの
前後に cwd を保存・復元し、cwd 汚染由来の順序依存failureを構造的に排除する。
"""
import os

import pytest


@pytest.fixture(autouse=True)
def _restore_cwd():
    """各テストの実行前 cwd を記録し、終了後に必ず戻す。"""
    prev = os.getcwd()
    try:
        yield
    finally:
        try:
            os.chdir(prev)
        except OSError:
            pass
