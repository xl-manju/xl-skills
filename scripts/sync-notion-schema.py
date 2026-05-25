#!/usr/bin/env python3
"""Notion 3DB スキーマ同期: doc/notion-schema/*.json を SSOT として差分検知・適用。

Usage:
  python3 scripts/sync-notion-schema.py --check   # 差分のみ表示 (CI向け、非ゼロ終了で乖離検知)
  python3 scripts/sync-notion-schema.py --apply   # Notion へ差分適用

API キー: macOS Keychain `notion-api-key` から取得 (security find-generic-password)。
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "doc" / "notion-schema"
FILES = ["hearing-sheet", "skill-list", "improvement-request"]


def keychain_token():
    if os.environ.get("NOTION_TOKEN"):
        return os.environ["NOTION_TOKEN"]
    return subprocess.check_output(
        ["security", "find-generic-password", "-s", "notion-api-key", "-w"]
    ).decode().strip()


def curl(method, url, token, body=None):
    cmd = ["curl", "-sS", "-X", method,
           "-H", f"Authorization: Bearer {token}",
           "-H", "Notion-Version: 2022-06-28",
           "-H", "Content-Type: application/json",
           "-w", "\n__HTTP__%{http_code}", url]
    tmp = None
    if body is not None:
        tmp = tempfile.NamedTemporaryFile("w", delete=False, suffix=".json")
        json.dump(body, tmp); tmp.close()
        cmd += ["--data-binary", f"@{tmp.name}"]
    out = subprocess.check_output(cmd).decode()
    if tmp: os.unlink(tmp.name)
    payload, _, code = out.rpartition("__HTTP__")
    return int(code.strip()), payload.strip()


def load_schemas():
    return {key: json.loads((SCHEMA_DIR / f"{key}.schema.json").read_text())
            for key in FILES}


def schema_to_property(name, spec, db_id_lookup):
    t = spec["type"]
    if t in ("title","rich_text","people","url","email","phone_number","files",
             "checkbox","date","number","created_time","last_edited_time"):
        return {t: {}}
    if t in ("select", "multi_select"):
        return {t: {"options": spec.get("options", [])}}
    if t == "relation":
        return {"relation": {
            "database_id": db_id_lookup[spec["target_db"]],
            "type": "dual_property",
            "dual_property": {}}}
    if t == "rollup":
        return {"rollup": {
            "relation_property_name": spec["relation_property_name"],
            "rollup_property_name": spec["rollup_property_name"],
            "function": spec.get("function", "count")}}
    raise ValueError(f"unsupported type: {t} for {name}")


def diff_props(remote_props, managed, db_id_lookup):
    """managed 側に定義があり remote と一致しないものを返す。既存追加プロパティ(non-managed)は無視。"""
    additions = {}
    for name, spec in managed.items():
        r = remote_props.get(name)
        if r is None:
            additions[name] = schema_to_property(name, spec, db_id_lookup)
            continue
        if r["type"] != spec["type"]:
            additions[name] = schema_to_property(name, spec, db_id_lookup)
    return additions


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    token = keychain_token()
    schemas = load_schemas()
    db_id_lookup = {k: v["db_id"] for k, v in schemas.items()}

    drift = False
    for key, sc in schemas.items():
        code, payload = curl("GET", f"https://api.notion.com/v1/databases/{sc['db_id']}", token)
        if code >= 300:
            print(f"[ERR] GET {key}: {code} {payload[:200]}"); sys.exit(2)
        remote = json.loads(payload)
        additions = diff_props(remote["properties"], sc["managed_properties"], db_id_lookup)
        if not additions:
            print(f"[OK] {key}: no drift"); continue
        drift = True
        print(f"[DRIFT] {key}: +{len(additions)} props -> {list(additions.keys())}")
        if args.apply:
            code, payload = curl("PATCH",
                f"https://api.notion.com/v1/databases/{sc['db_id']}",
                token, {"properties": additions})
            if code >= 300:
                print(f"  [ERR] apply: {code} {payload[:300]}"); sys.exit(2)
            print(f"  [APPLIED] {key}")
    if args.check and drift:
        sys.exit(1)


if __name__ == "__main__":
    main()
