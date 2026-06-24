#!/usr/bin/env python3
# /// script
# name: mfk_api
# purpose: マネーフォワード掛け払い API v2 への読み取り(GET)薄ラッパ + 疎通確認 CLI。
# inputs:
#   - argv: --smoke / --path <path> / --param key=value / --config <path>
#   - config: .mf-kessai-config.json (base_url / environment)
# outputs:
#   - stdout: JSON または疎通サマリ
#   - exit: 0=OK / 非0=失敗
# contexts: [C, E]
# network: true   # api.mfkessai.co.jp への HTTPS GET のみ
# write-scope: none
# dependencies: []
# requires-python: ">=3.11"
# ///
"""マネーフォワード掛け払い (MF KESSAI) API v2 の読み取り薄ラッパ。

- 認証: mfk_keychain.get_api_key() のキーを HTTP ヘッダ `apikey` に載せる
- base_url: .mf-kessai-config.json の "base_url" (既定: 本番 https://api.mfkessai.co.jp/v2)
- GET のみ。副作用のある POST/PATCH/DELETE は実装しない (発行漏れチェックは参照専用)

使い方:
  python3 lib/mfk_api.py --smoke
  python3 lib/mfk_api.py --path /billings/qualified --param issue_date_from=2026-05-01 \
      --param issue_date_to=2026-05-31 --param status=invoice_issued --param limit=5
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mfk_keychain import KeychainError, get_api_key  # noqa: E402

DEFAULT_BASE_URL = "https://api.mfkessai.co.jp/v2"
SANDBOX_BASE_URL = "https://sandbox-api.mfkessai.co.jp/v2"


def _deep_merge(base, over):
    """over を base に重ねる。空文字/None は「未設定」とみなし base を温存する
    (ローカル config の空欄が配布既定の database_id 等を潰さないため)。"""
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        elif v not in ("", None):
            out[k] = v
    return out


def load_config(path=None):
    """設定を 2 層で読む。

    1. コミット済み配布既定 `mf-kessai-config.default.json` (導入者はゼロ設定で動く)
    2. gitignore のローカル `.mf-kessai-config.json` または明示 path (差分上書き)

    空文字値は上書きしないので、ローカルを空にしても既定 (Notion database_id 等) が残る。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    plugin_root = os.path.dirname(here)
    cfg = {}
    default_path = os.path.join(plugin_root, "mf-kessai-config.default.json")
    if os.path.exists(default_path):
        with open(default_path, encoding="utf-8") as f:
            cfg = json.load(f)
    for c in [path, os.path.join(plugin_root, ".mf-kessai-config.json")]:
        if c and os.path.exists(c):
            with open(c, encoding="utf-8") as f:
                cfg = _deep_merge(cfg, json.load(f))
            break
    return cfg


def base_url(cfg=None):
    cfg = cfg or {}
    env = os.environ.get("MFK_BASE_URL")
    if env:
        return env.rstrip("/")
    if cfg.get("environment") == "sandbox":
        return SANDBOX_BASE_URL
    return (cfg.get("base_url") or DEFAULT_BASE_URL).rstrip("/")


def get(path, params=None, cfg=None, api_key=None):
    """GET <base_url><path>?<params> を叩いて JSON を返す。

    params の値が list の場合は doseq で同名キー複数展開 (例: status=a&status=b)。
    """
    cfg = cfg if cfg is not None else load_config()
    api_key = api_key or get_api_key(cfg=cfg)
    url = base_url(cfg) + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, method="GET")
    req.add_header("apikey", api_key)
    req.add_header("accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise SystemExit(f"HTTP {e.code} {path}: {body}")
    except urllib.error.URLError as e:
        raise SystemExit(f"接続失敗 {path}: {e.reason} (base_url={base_url(cfg)} を確認)")


def iter_all(path, params=None, cfg=None, api_key=None):
    """カーソルページングで path の全 items を yield する (limit=200 固定)。"""
    params = dict(params or {}, limit=200)
    while True:
        page = get(path, params, cfg=cfg, api_key=api_key)
        for item in page.get("items", []):
            yield item
        pg = page.get("pagination", {})
        if not pg.get("has_next"):
            break
        nxt = pg.get("end")
        if not nxt:
            raise SystemExit(
                f"ページング異常 {path}: pagination.has_next=true だが pagination.end が空です。"
                "部分取得のまま続行しないため停止します。"
            )
        params["after"] = nxt


def smoke(cfg=None):
    """疎通確認: /customers?limit=1 を叩いて HTTP 200 と顧客総数を表示。キー本体は出さない。"""
    cfg = cfg if cfg is not None else load_config()
    bu = base_url(cfg)
    print(f"base_url = {bu}")
    data = get("/customers", {"limit": 1}, cfg=cfg)
    total = data.get("pagination", {}).get("total")
    print(f"OK: /customers 到達 (HTTP 200)。顧客総数 total={total}")
    print("→ APIキーは Keychain から取得し、ヘッダ apikey に載りました (本体は非表示)")
    return 0


def main():
    p = argparse.ArgumentParser(description="MF掛け払い API 読み取りクライアント (GET 専用)")
    p.add_argument("--smoke", action="store_true", help="疎通確認 (/customers?limit=1)")
    p.add_argument("--path", help="任意の GET パス (例: /billings/qualified)")
    p.add_argument("--param", action="append", default=[], help="key=value 形式 (複数可)")
    p.add_argument("--config")
    a = p.parse_args()
    cfg = load_config(a.config)
    try:
        if a.path and not a.smoke:
            params = {}
            for kv in a.param:
                k, _, v = kv.partition("=")
                params.setdefault(k, []).append(v)
            flat = {k: (vs[0] if len(vs) == 1 else vs) for k, vs in params.items()}
            data = get(a.path, flat, cfg=cfg)
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0
        return smoke(cfg)
    except KeychainError as e:
        sys.stderr.write(f"[mfk_api] {e}\n")
        return e.exit_code


if __name__ == "__main__":
    sys.exit(main())
