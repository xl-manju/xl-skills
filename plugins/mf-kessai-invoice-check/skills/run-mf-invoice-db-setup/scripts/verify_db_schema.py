#!/usr/bin/env python3
"""作成済みNotion DBが notion-db-schema.json の全プロパティを持つか検証する。

drift検知: DBプロパティと schema 正本の差分を報告。欠落があれば exit 1。
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(_PLUGIN_ROOT, "lib"))
from mfk_api import load_config  # noqa: E402
from notion_invoice_sink import _notion_token, _req  # noqa: E402


def load_schema():
    with open(os.path.join(_HERE, "..", "schemas", "notion-db-schema.json"), encoding="utf-8") as f:
        return json.load(f)


def main():
    schema = load_schema()
    cfg = load_config()
    db_id = (cfg.get("notion") or {}).get("database_id")
    if not db_id:
        sys.stderr.write("[verify_db_schema] database_id 未設定。先に build_notion_db.py を実行してください。\n")
        return 2
    token = _notion_token()
    res = _req("GET", f"/databases/{db_id}", token)
    existing = set((res.get("properties") or {}).keys())
    expected = set(schema["properties"].keys())
    deprecated = set(schema.get("deprecated_properties", []))
    missing = sorted(expected - existing)
    # 削除されるべき旧列が残っていないか (移行の drift)。extra のうち deprecated は致命。
    residual = sorted(deprecated & existing)
    extra = sorted(existing - expected - deprecated)
    if missing or residual:
        if missing:
            print(f"FAIL 欠落プロパティ: {missing}")
        if residual:
            print(f"FAIL 削除されるべき旧プロパティが残存: {residual} "
                  f"(build_notion_db.py を再実行して掃除してください)")
        if extra:
            print(f"     (参考: DBにのみ存在する追加列: {extra})")
        return 1
    print(f"PASS 全 {len(expected)} プロパティが存在し、旧プロパティの残存もありません。")
    if extra:
        print(f"     (参考: DBにのみ存在する追加列: {extra})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
