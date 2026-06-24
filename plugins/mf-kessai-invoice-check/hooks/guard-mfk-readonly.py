#!/usr/bin/env python3
"""PreToolUse hook: MF掛け払い APIへの変更系リクエストを Bash 経路で遮断する (参照専用の第1層)。

射程: Bash tool の command 文字列、および他 tool の tool_input JSON に api.mfkessai.co.jp と
POST/PUT/PATCH/DELETE パターンが現れたら exit 2 で拒否する。GET(参照)は許可。
boundary を指示でなく仕組みで担保する。

注意 (保証範囲の正直な明示): 本 hook は『Bash 経由の素の HTTP コマンド (curl / python -c 等)』を
捕捉する層であり、Python スクリプト内部の urllib 呼び出しまでは射程外。そのため第2層として
lib/mfk_api.py は GET 専用に設計し POST/PUT/PATCH/DELETE 関数を実装しない (構造的に変更系を持たない)。
2 層で参照専用を担保する。Notion(api.notion.com)への書き込みは対象外 (MFは読むだけ・Notionは書く の一方向)。
"""
import json
import re
import sys

_HOST = "mfkessai.co.jp"
_MUTATION_PATTERNS = [
    r"-x\s+(post|put|patch|delete)\b",
    r"--request\s+(post|put|patch|delete)\b",
    r"\.(post|put|patch|delete)\s*\(",
    r"method\s*[=:]\s*['\"]?(post|put|patch|delete)",
    # subprocess の list 形式 (例: ["curl","-X","POST"]) を JSON 文字列で検出
    r'"-x",\s*"(post|put|patch|delete)"',
    r'"--request",\s*"(post|put|patch|delete)"',
]


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input", {}) or {}
    text = ti.get("command", "") if tool == "Bash" else json.dumps(ti, ensure_ascii=False)
    if _HOST not in text:
        return 0
    lowered = text.lower()
    if any(re.search(p, lowered) for p in _MUTATION_PATTERNS):
        sys.stderr.write(
            "[guard-mfk-readonly] MF掛け払いAPIへの変更系(POST/PUT/PATCH/DELETE)は禁止です。"
            "発行漏れチェックは参照専用(GET)です。請求書の発行・更新はMF管理画面で行ってください。\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
