#!/usr/bin/env python3
# /// script
# name: notion_config
# purpose: repo-root の .notion-config.json (gitignore 対象) を SSOT として解決し、Notion DB ID / 送信元設定を返す。symlink 共有プラグインでも install パス非依存で動く。
# inputs:
#   - env: NOTION_GMAIL_CONFIG (任意) / CLAUDE_PROJECT_DIR (任意)
#   - file: .notion-config.json
# outputs:
#   - load_config(): dict / get_db_id(name): str / get_sender(): dict
# contexts: [C, E]
# network: false
# write-scope: none
# dependencies: []
# requires-python: ">=3.9"
# ///
"""Notion 設定ローダー (per-repo config SSOT)。

DB ID や送信元ドメインなど環境依存の固有値は repo-root の .notion-config.json に分離し、
コードには直書きしない (仕様書 §3 取得時の確定事項・abstraction_variables)。探索順は
env(明示) > CLAUDE_PROJECT_DIR > __file__ から上位ディレクトリ走査 > CWD。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_FILENAME = ".notion-config.json"


class ConfigError(Exception):
    """設定不在 / キー欠落 (G2 で fail-closed させる)。"""


def _candidate_paths(explicit_path: str | os.PathLike[str] | None = None) -> list[Path]:
    cands: list[Path] = []
    if explicit_path:
        cands.append(Path(explicit_path))
    env = os.environ.get("NOTION_GMAIL_CONFIG")
    if env:
        cands.append(Path(env))
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        cands.append(Path(proj) / CONFIG_FILENAME)
    # __file__ から上位を走査 (repo-root を見つける)
    here = Path(__file__).resolve()
    for parent in here.parents:
        cands.append(parent / CONFIG_FILENAME)
    cands.append(Path.cwd() / CONFIG_FILENAME)
    # 重複排除 (順序保持)
    seen: set[str] = set()
    uniq: list[Path] = []
    for c in cands:
        s = str(c)
        if s not in seen:
            seen.add(s)
            uniq.append(c)
    return uniq


def find_config_path(explicit_path: str | os.PathLike[str] | None = None) -> Path | None:
    for c in _candidate_paths(explicit_path):
        if c.is_file():
            return c
    return None


def load_config(path: str | os.PathLike[str] | None = None) -> dict:
    """.notion-config.json を読み込む。不在なら ConfigError。"""
    resolved = find_config_path(path)
    if resolved is None:
        target = f"指定パス {path}" if path else CONFIG_FILENAME
        raise ConfigError(
            f"{target} が見つかりません。repo-root に作成してください "
            f"(notion-gmail-send の例は .notion-config.json.example を参照)。"
        )
    try:
        return json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ConfigError(f"{resolved} の読み込みに失敗: {e}") from e


def get_db_id(name: str, config: dict | None = None) -> str:
    """databases.<name>.db_id を返す。未解決なら ConfigError (G2 で送信中断)。"""
    cfg = config if config is not None else load_config()
    databases = cfg.get("databases") or {}
    if not isinstance(databases, dict):
        raise ConfigError("databases は {name: {db_id: ...}} 形式の dict である必要があります "
                          "(.notion-config.json.example 参照)。")
    db = databases.get(name) or {}
    db_id = db.get("db_id") if isinstance(db, dict) else None
    if not db_id:
        raise ConfigError(f"databases.{name}.db_id が .notion-config.json に未設定です。")
    return db_id


def get_sender(config: dict | None = None) -> dict:
    """送信元設定 (notion_gmail_send.sender)。from_domain / impersonate などの固有値。"""
    cfg = config if config is not None else load_config()
    return (cfg.get("notion_gmail_send") or {}).get("sender") or {}
