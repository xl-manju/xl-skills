#!/usr/bin/env python3
# /// script
# name: verify-completeness
# purpose: 正規形プロンプト YAML の7層構造網羅・Layer5 ゴールシーク必須要素・固定手順不在を検証する
# inputs:
#   - argv: --input <prompt.yaml>
#   - file: --input の正規形 YAML
# outputs:
#   - stdout: OK サマリ
#   - stderr: FAIL incomplete の不備一覧
#   - exit: 0=OK / 1=不備あり / 2=引数エラー
# contexts: [C]
# network: false
# write-scope: none
# dependencies: []
# ///
# verify-completeness.py — 正規形プロンプト（merge-layers.py 出力 YAML）の網羅性検証
#   1. 7 Layer 全てに最低 1 要素があるか（構造網羅）
#   2. ゴールシーク要素が Layer 5 に在るか（ゴール定義 / 完了チェックリスト / 達成ゴール）
#   3. 固定手順（思考プロセスのステップ列挙）が不在か（ゴールシーク禁止構造の検出）
# マーカーは scaffold-prompt.py / merge-layers.py が出力する「# Layer N:」に一致させる。
# Exit: 0=OK, 1=不備あり, 2=引数エラー
"""verify_completeness.js の python 移植。元の検証ロジック・終了コードを維持する。"""
import argparse
import re
import sys


def parse_args():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--input")
    args, _ = parser.parse_known_args()
    return args


# 「# Layer N:」マーカーで本文を 7 層に分割する。
# 半角/全角コロン・# の個数（# / ##）の揺れを許容する。
def split_layers(text):
    sections = {}
    for n in range(1, 8):
        pattern = (
            rf"#+\s*Layer\s*{n}\s*[:：][^\n]*\n([\s\S]*?)"
            rf"(?=#+\s*Layer\s*{n + 1}\s*[:：]|$)"
        )
        m = re.search(pattern, text)
        sections[n] = m.group(1) if m else None
    return sections


def non_comment_body(body):
    out = []
    for line in body.split("\n"):
        s = line.strip()
        if len(s) > 0 and not s.startswith("#"):
            out.append(line)
    return out


def main():
    args = parse_args()
    input_path = args.input
    if not input_path:
        sys.stderr.write("usage: verify-completeness.py --input <prompt.yaml>\n")
        sys.exit(2)
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()
    sections = split_layers(text)
    problems = []

    # 1. 構造網羅: 各 Layer が存在し本文が空でない
    for n in range(1, 8):
        body = sections[n]
        if body is None:
            problems.append(f"Layer {n}: section missing")
            continue
        if len(non_comment_body(body)) == 0:
            problems.append(f"Layer {n}: empty body")

    # 2. ゴールシーク要素: Layer 5 にゴール定義・完了チェックリスト・達成ゴールが在る
    layer5 = sections[5] or ""
    goal_seek_required = [
        {"key": "ゴール定義", "label": "ゴール定義（目的・背景・達成ゴール）"},
        {"key": "完了チェックリスト", "label": "完了チェックリスト（停止条件）"},
        {"key": "達成ゴール", "label": "達成ゴール（成果状態）"},
    ]
    for r in goal_seek_required:
        if sections[5] is not None and r["key"] not in layer5:
            problems.append(f"Layer 5: {r['label']} がない（ゴールシーク必須要素）")

    # 3. 固定手順の不在: 「思考プロセス」+「ステップN」列挙はゴールシーク違反
    #    実行方式.ループ の箇条書きは許容（「思考プロセス」キーを伴わない）。
    if re.search(r"思考プロセス", layer5) and re.search(r"ステップ\s*[0-9０-９]", layer5):
        problems.append(
            "Layer 5: 固定手順（思考プロセスのステップ列挙）が検出された "
            "— ゴール定義+完了チェックリストに置換すること"
        )

    if len(problems) > 0:
        sys.stderr.write("FAIL incomplete:\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        sys.exit(1)
    print("OK 7 layers verified (goal-seek 要素確認済み)")


if __name__ == "__main__":
    main()
