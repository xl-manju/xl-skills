#!/usr/bin/env python3
# /// script
# name: render-combinators
# purpose: Compose an atomic SKILL.md template from _base.md and combinator patch selections.
# inputs:
#   - argv: --kind, optional flags, --templates-dir, --output
# outputs:
#   - stdout: composed SKILL.md when --output is omitted
#   - file: composed SKILL.md when --output is provided
#   - stderr: validation errors
#   - exit: 0=OK / 1=composition error / 2=usage error
# contexts: [A, B, C]
# network: false
# write-scope: output-arg-only
# dependencies: []
# requires-python: ">=3.10"
# ///
"""Compose run-build-skill atomic templates from _base.md and combinators.

The repository keeps combinators as unified diff files for reviewability. This
tool makes that route executable for mass production by applying the selected
kind combinator plus optional flag combinators in the documented order.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


KIND_PATCHES = {
    "run": "with-run.patch",
    "ref": "with-ref.patch",
    "wrap": "with-wrap.patch",
    "delegate": "with-delegate.patch",
}

FLAG_PATCHES = {
    "with_evaluator": "with-evaluator.patch",
    "with_hooks": "with-hooks.patch",
    "with_subagent": "with-subagent.patch",
}


class ComposeError(RuntimeError):
    """Raised when a selected combinator cannot be applied deterministically."""


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", required=True, choices=["run", "ref", "assign", "wrap", "delegate"])
    parser.add_argument("--role-suffix", choices=["generator", "evaluator", "workflow"], default="")
    parser.add_argument("--with-evaluator", action="store_true")
    parser.add_argument("--with-hooks", action="store_true")
    parser.add_argument("--with-subagent", action="store_true")
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "templates",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--trace", action="store_true", help="print applied patch names to stderr")
    return parser.parse_args(argv)


def selected_patches(args: argparse.Namespace) -> list[str]:
    if args.kind == "assign":
        role = args.role_suffix or "generator"
        first = f"with-assign-{role}.patch"
    else:
        first = KIND_PATCHES[args.kind]

    patches = [first]
    for flag, patch_name in FLAG_PATCHES.items():
        if getattr(args, flag):
            patches.append(patch_name)
    return patches


def apply_unified_diff(content: str, diff_text: str) -> str:
    """Apply one-file unified diff text.

    This implements the minimal deterministic subset used by the combinator
    files: one target file, standard hunk headers, context/add/remove lines.
    """
    original = content.splitlines(keepends=True)
    result: list[str] = []
    cursor = 0
    lines = diff_text.splitlines(keepends=True)
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.startswith("@@ "):
            index += 1
            continue

        match = re.match(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", line)
        if not match:
            raise ComposeError(f"invalid hunk header: {line.strip()}")

        old_start = int(match.group(1)) - 1
        if old_start < cursor:
            raise ComposeError(f"overlapping hunk at line {old_start + 1}")
        result.extend(original[cursor:old_start])
        cursor = old_start
        index += 1

        while index < len(lines) and not lines[index].startswith("@@ "):
            hunk_line = lines[index]
            if hunk_line.startswith(("--- ", "+++ ")):
                index += 1
                continue
            if not hunk_line:
                index += 1
                continue
            tag = hunk_line[0]
            text = hunk_line[1:]
            if tag == " ":
                if cursor >= len(original) or original[cursor].rstrip("\n") != text.rstrip("\n"):
                    got = "<eof>" if cursor >= len(original) else original[cursor].rstrip("\n")
                    raise ComposeError(f"context mismatch: expected {text.rstrip()} got {got}")
                result.append(original[cursor])
                cursor += 1
            elif tag == "-":
                if cursor >= len(original) or original[cursor].rstrip("\n") != text.rstrip("\n"):
                    got = "<eof>" if cursor >= len(original) else original[cursor].rstrip("\n")
                    raise ComposeError(f"removal mismatch: expected {text.rstrip()} got {got}")
                cursor += 1
            elif tag == "+":
                result.append(text)
            elif hunk_line.startswith("\\ No newline at end of file"):
                pass
            else:
                raise ComposeError(f"unsupported hunk line: {hunk_line.rstrip()}")
            index += 1

    result.extend(original[cursor:])
    return "".join(result)


def frontmatter_bounds(text: str) -> tuple[int, int]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ComposeError("_base.md must start with frontmatter")
    for idx in range(1, len(lines)):
        if lines[idx] == "---":
            return 0, idx
    raise ComposeError("_base.md frontmatter is not closed")


def normalize_base(text: str) -> str:
    """Drop the design-note fence that precedes the real template frontmatter."""
    lines = text.splitlines()
    if len(lines) < 3 or lines[0] != "---":
        return text
    for idx in range(1, len(lines)):
        if lines[idx] != "---":
            continue
        if idx + 1 < len(lines) and lines[idx + 1] == "---":
            return "\n".join(lines[idx + 1 :]) + "\n"
        if idx + 1 < len(lines) and lines[idx + 1].startswith("name:"):
            return "---\n" + "\n".join(lines[idx + 1 :]) + "\n"
        return text
    return text


def ensure_frontmatter_line(text: str, line: str, after_key: str = "") -> str:
    lines = text.splitlines()
    start, end = frontmatter_bounds(text)
    key = line.split(":", 1)[0]
    if any(item.startswith(f"{key}:") for item in lines[start + 1 : end]):
        return text
    insert_at = end
    if after_key:
        for idx in range(start + 1, end):
            if lines[idx].startswith(f"{after_key}:"):
                insert_at = idx + 1
                break
    lines.insert(insert_at, line)
    return "\n".join(lines) + "\n"


def add_section_after(text: str, anchor: str, section: str) -> str:
    if section.splitlines()[0] in text:
        return text
    if anchor not in text:
        raise ComposeError(f"anchor not found for semantic combinator: {anchor}")
    return text.replace(anchor, anchor + "\n\n" + section, 1)


def apply_semantic_patch(text: str, patch_name: str) -> str:
    """Compatibility adapter for reviewed patches whose base moved to Japanese headings."""
    if patch_name == "with-run.patch":
        text = ensure_frontmatter_line(text, "role_suffix: {{role_suffix | default(\"workflow\")}}", "effect")
        return add_section_after(
            text,
            "## 手順\n{{generated_steps}}",
            "### Step 1: 入力確認\n{{step1_input_check}}\n\n"
            "### Step 2: 主処理\n{{step2_main_process}}\n\n"
            "### Step 3: 検証\n{{step3_validation}}\n\n"
            "各 Step は副作用と返り値を明示し、失敗時の retry / rollback 条件を `## 注意点` に記載する。",
        )
    if patch_name == "with-ref.patch":
        text = ensure_frontmatter_line(text, "disable-model-invocation: true", "description")
        text = ensure_frontmatter_line(text, "user-invocable: false", "disable-model-invocation")
        text = ensure_frontmatter_line(text, "effect: read-only", "kind")
        return add_section_after(
            text,
            "## 目的と出力契約\n{{output_contract}}",
            "## 参照内容\n\n本Skillは {{ref_topic}} の正本情報を提供する Read-only スキル。\n\n"
            "- 主参照元: {{primary_source}}\n"
            "- 補助参照: {{secondary_sources | default(\"(なし)\")}}\n"
            "- 更新頻度: {{update_frequency | default(\"公式仕様改訂時\")}}\n"
            "- 鮮度ポリシー: `last-audited` を四半期ごとに更新（設計書15章）",
        )
    if patch_name == "with-assign-generator.patch":
        text = ensure_frontmatter_line(text, "role_suffix: generator", "effect")
        text = ensure_frontmatter_line(text, "pair: {{pair_skill}}", "role_suffix")
        return add_section_after(
            text,
            "## 目的と出力契約\n{{output_contract}}",
            "## 生成契約\n\n"
            "- **入力**: {{generator_input}}\n"
            "- **出力**: {{generator_output}}\n"
            "- **後段 evaluator**: `Skill({{pair_skill}})` が fork で評価\n"
            "- **再生成ループ**: evaluator findings を受け、最大 {{retry_max | default(3)}} 周まで自動再試行\n"
            "- **禁則**: 評価判断を generator 側で行わない（Goodhart 対策、09章）",
        )
    if patch_name == "with-assign-evaluator.patch":
        text = ensure_frontmatter_line(text, "user-invocable: false", "description")
        text = ensure_frontmatter_line(text, "context: fork", "user-invocable")
        text = ensure_frontmatter_line(text, "role_suffix: evaluator", "effect")
        text = ensure_frontmatter_line(text, "pair: {{pair_skill}}", "role_suffix")
        text = ensure_frontmatter_line(text, "agent: {{agent | default(\"general-purpose\")}}", "pair")
        return add_section_after(
            text,
            "## 目的と出力契約\n{{output_contract}}",
            "## Evaluator Contract\n\n評価結果は STDOUT に JSON 1 オブジェクトで返す:\n\n"
            "```json\n"
            "{\"rubric_id\":\"{{rubric_id}}\",\"rubric_version\":\"{{rubric_version}}\",\"score\":0,\"threshold\":{{threshold | default(80)}},\"passed\":false,\"findings\":[]}\n"
            "```\n\n"
            "**禁則**: 被採点物の Write/Edit を持たない。rubric も改変しない。",
        )
    if patch_name == "with-wrap.patch":
        text = ensure_frontmatter_line(text, "role_suffix: cli-wrapper", "effect")
        return add_section_after(
            text,
            "## 目的と出力契約\n{{output_contract}}",
            "## Wrapped CLI\n\n"
            "- **対象CLI**: `{{wrapped_cli}}`\n"
            "- **想定バージョン**: {{cli_version | default(\"未固定\")}}\n"
            "- **安全側デフォルト**: {{safe_defaults}}\n"
            "- **禁止サブコマンド**: {{forbidden_subcommands | default(\"(なし)\")}}\n"
            "- **dry-run 既定**: {{dry_run_default | default(\"true\")}}\n"
            "- **失敗時挙動**: {{failure_behavior | default(\"非ゼロ exit を上位に伝搬し、副作用は rollback しない\")}}",
        )
    if patch_name == "with-delegate.patch":
        text = ensure_frontmatter_line(text, "role_suffix: external-delegator", "effect")
        return add_section_after(
            text,
            "## 目的と出力契約\n{{output_contract}}",
            "## Delegation Target\n\n"
            "- **委譲先**: {{delegate_target}}\n"
            "- **委譲理由**: {{delegation_reason}}\n"
            "- **入力契約**: {{delegation_input}}\n"
            "- **出力契約**: {{delegation_output}}\n"
            "- **失敗時 fallback**: {{delegation_fallback | default(\"ユーザーに手動実行を要請\")}}\n"
            "- **タイムアウト**: {{delegation_timeout | default(\"300秒\")}}",
        )
    if patch_name == "with-evaluator.patch":
        text = ensure_frontmatter_line(text, "pair: {{pair_skill}}", "rubric_refs")
        return add_section_after(
            text,
            "## 目的と出力契約\n{{output_contract}}",
            "## Evaluator 連携\n本Skillは完了後 `Skill({{pair_skill}}) target=<artifact>` を fork で呼び、JSON評価結果を受け取る。`{{pair_skill}}` 側が `context: fork` を持つ。",
        )
    if patch_name == "with-hooks.patch":
        text = ensure_frontmatter_line(text, "with_hooks: true", "rubric_refs")
        text = ensure_frontmatter_line(text, "needs_lifecycle_enforcement: true", "with_hooks")
        return add_section_after(
            text,
            "## セキュリティと権限\n本Skillは副作用を伴う可能性がある。設計書04章の二段防御原則に従い、(1) `settings.json` の `permissions.deny` に禁止コマンド・パスを静的に列挙し、(2) `PreToolUse` hook で文脈依存の危険検査（破壊的引数・対象パス・分岐条件）を動的に行うこと。",
            "## Hook Wiring（10章 / 17章）\n"
            "- `PreToolUse`: 破壊的引数の検査。block は exit 2 または `hookSpecificOutput.permissionDecision: \"deny\"` で行う。\n"
            "- `PostToolUse`: 監査ログ + 後処理。failure 系は `PostToolUseFailure` を別途配線。\n"
            "- `SubagentStop`: Subagent ありの場合、完了 hook で evaluator JSON 検証を強制。",
        )
    if patch_name == "with-subagent.patch":
        text = ensure_frontmatter_line(text, "context: fork", "rubric_refs")
        text = ensure_frontmatter_line(text, "agent: {{subagent_type}}", "context")
        text = ensure_frontmatter_line(text, "needs_independent_context: true", "agent")
        text = ensure_frontmatter_line(text, "with_subagent_hint: true", "needs_independent_context")
        return add_section_after(
            text,
            "## 追加リソース\n- `references/`\n{{additional_resources}}",
            "## Subagent / Agent Team 連携（17章）\n"
            "- spawn prompt は lead history を継承しないため、必要な context を明示する。\n"
            "- file ownership を分け、同一 file を複数 teammate に触らせない。\n"
            "- cleanup は必ず lead 経由で行う。",
        )
    raise ComposeError(f"unknown combinator: {patch_name}")


def apply_patch_file(content: str, patch_path: Path) -> str:
    diff_text = patch_path.read_text(encoding="utf-8")
    try:
        return apply_unified_diff(content, diff_text)
    except ComposeError:
        return apply_semantic_patch(content, patch_path.name)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    base_path = args.templates_dir / "_base.md"
    combinator_dir = args.templates_dir / "combinators"
    try:
        content = normalize_base(base_path.read_text(encoding="utf-8"))
        patch_names = selected_patches(args)
        for patch_name in patch_names:
            patch_path = combinator_dir / patch_name
            if not patch_path.exists():
                raise ComposeError(f"missing combinator: {patch_path}")
            content = apply_patch_file(content, patch_path)
        if args.trace:
            print("applied: " + ", ".join(patch_names), file=sys.stderr)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding="utf-8")
        else:
            sys.stdout.write(content)
        return 0
    except (OSError, ComposeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
