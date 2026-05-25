#!/usr/bin/env python3
"""Per-repository Notion configuration loader (SSOT for symlinked skill plugins).

シンボリックリンクで複数 repository に共有される skill-creator / skill-intake が、
各リポジトリ固有の Notion DB ID / API キー指定を解決するための唯一の経路。

解決順:
  1. CWD → 上位ディレクトリへ `.git` が見つかるまで遡る
  2. その repo-root に `.notion-config.json` があれば読み込む
  3. 無ければ env `NOTION_CONFIG_PATH` を見る
  4. それでも無ければ None を返す（呼び出し側で warn-and-skip）

config schema (JSON):
{
  "keychain_service": "notion-api-key",
  "keychain_account": "skill-intake",
  "databases": {
    "skill-list":          {"db_id": "..."},
    "hearing-sheet":       {"db_id": "..."},
    "improvement-request": {"db_id": "..."}
  },
  "schema_dir": "doc/notion-schema"
}

トークン本体は Keychain or env (NOTION_TOKEN) のまま。config には載せない。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

CONFIG_FILENAME = ".notion-config.json"
SETUP_DOC_REL = "plugins/skill-creator/references/notion-per-repo-setup.md"


REPO_MARKERS = (".notion-config.json", ".notion-config.example.json", "marketplace.json")


def find_repo_root(start: Optional[Path] = None) -> Optional[Path]:
    """Repo-root 探索: .git を上向き走査するが、xl-skills marker (.notion-config.* / marketplace.json)
    のいずれかを持つ root のみ採用。submodule の .git や別 repo の .git に誤ヒットしてグローバル
    config を盗み読むのを防ぐ。
    """
    p = (start or Path.cwd()).resolve()
    for d in [p, *p.parents]:
        if (d / ".git").exists() and any((d / m).exists() for m in REPO_MARKERS):
            return d
    return None


def find_config_path(start: Optional[Path] = None) -> Optional[Path]:
    env = os.environ.get("NOTION_CONFIG_PATH")
    if env and Path(env).exists():
        return Path(env)
    root = find_repo_root(start)
    if root and (root / CONFIG_FILENAME).exists():
        return root / CONFIG_FILENAME
    return None


def load_config(start: Optional[Path] = None) -> Optional[dict]:
    path = find_config_path(start)
    if not path:
        return None
    with path.open(encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["__path__"] = str(path)
    return cfg


DB_ENV_NAMES = {
    "hearing-sheet": "INTAKE_NOTION_DATABASE_ID",
    "skill-list": "NOTION_DB_SKILL_LIST",
    "improvement-request": "NOTION_DB_IMPROVEMENT_REQUEST",
}


def get_db_id(key: str, start: Optional[Path] = None) -> Optional[str]:
    """DB ID 統一解決: env (key-specific) → .notion-config.json → None。

    全 callsite はこの関数を経由することで、setup-doc が宣言する解決順を全 script で一致させる。
    """
    env_name = DB_ENV_NAMES.get(key)
    if env_name and os.environ.get(env_name):
        return os.environ[env_name]
    cfg = load_config(start)
    if not cfg:
        return None
    return (cfg.get("databases") or {}).get(key, {}).get("db_id")


def get_token(cfg: Optional[dict] = None) -> Optional[str]:
    """Token 解決: env NOTION_TOKEN → Keychain (config.keychain_service)."""
    tok = os.environ.get("NOTION_TOKEN")
    if tok:
        return tok
    service = (cfg or {}).get("keychain_service", "notion-api-key")
    account = (cfg or {}).get("keychain_account")
    cmd = ["security", "find-generic-password", "-s", service, "-w"]
    if account:
        cmd[2:2] = ["-a", account]
    try:
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def warn_missing(stream=sys.stderr) -> None:
    root = find_repo_root() or Path.cwd()
    stream.write(
        f"[notion_config] WARN: {CONFIG_FILENAME} not found under repo-root ({root}). "
        f"Notion sync skipped. See {SETUP_DOC_REL} to configure this repo.\n"
    )


def require_or_skip(key: str = "") -> tuple[Optional[dict], Optional[str]]:
    """便利関数: (cfg, token) を返す。どちらか欠ければ警告して (None, None)。

    呼び出し側は `if not cfg: return 0` で exit 0 スキップする。
    """
    cfg = load_config()
    if not cfg:
        warn_missing()
        return None, None
    tok = get_token(cfg)
    if not tok:
        sys.stderr.write("[notion_config] WARN: Notion token unavailable (env NOTION_TOKEN or Keychain). Skipped.\n")
        return None, None
    if key and not get_db_id(key):
        sys.stderr.write(f"[notion_config] WARN: databases.{key}.db_id missing in {cfg['__path__']}. Skipped.\n")
        return None, None
    return cfg, tok


if __name__ == "__main__":
    cfg = load_config()
    if not cfg:
        warn_missing()
        sys.exit(0)
    print(json.dumps({k: v for k, v in cfg.items() if k != "__path__"}, indent=2, ensure_ascii=False))
    print(f"# loaded from: {cfg['__path__']}")
