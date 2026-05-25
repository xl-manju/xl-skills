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
    "with_knowledge": "with-knowledge.patch",
}

# goal-seek 配線を default-ON で注入する loop 実行系 kind。
# assign(評価系=一発採点でループしない) と ref(read-only) は対象外。
GOAL_SEEK_KINDS = ("run", "wrap", "delegate")


# with-knowledge.patch の決定論的注入内容。配布スキルが自己完結するよう、
# skill-creator 内部 (ref-knowledge-loop / templates/ / Loop B / --dir) への参照を一切含めない。
KNOWLEDGE_FM_BLOCK = (
    "# knowledge-loop: 蓄積/検索/§12フィードバックを組み込む。"
    "検索・追加・記録・整合性検証は本 Skill 同梱の scripts/ で完結する (外部ツール不要)。\n"
    "knowledge_loop:\n"
    "  pattern: {{knowledge_loop.pattern}}       # index-search | router-registry\n"
    "  index: knowledge/knowledge-index.json     # router-registry 型は knowledge/router.json\n"
    "  usage_log: knowledge/usage-log.jsonl\n"
    "  consult_at: {{knowledge_loop.consult_at | default([\"runtime\"])}}"
)

KNOWLEDGE_SECTION = (
    "## ナレッジループ\n"
    "本 Skill は `knowledge/` に蓄積した知見を実行時に検索し、活用結果を記録して品質を自己改善する。"
    "検索・追加・記録・整合性検証はすべて本 Skill 同梱の `scripts/` だけで完結し、外部ツールやメタリポジトリへの依存はない。\n\n"
    "### 構造（pattern: {{knowledge_loop.pattern}}）\n"
    "- `knowledge/knowledge-index.json`（index-search 型）/ `knowledge/router.json` + `registry.json`（router-registry 型）。"
    "いずれも `consult_at: [\"runtime\"]` を宣言する。\n"
    "- 各エントリは必須6フィールド `id / title|content / intent|purpose / background / keywords|tags / source` を満たす。"
    "整合性 (ID重複・必須欠落) は `scripts/build_index.py --stats` で検証する。\n\n"
    "### 検索（決定論段 → AI段）\n"
    "1. `scripts/search_knowledge.py --query \"<query>\" --limit 5`"
    "（Stage1 カテゴリ絞り込み + Stage2 重み付きスコアリング・決定論・100%再現）。\n"
    "2. 上位 N 件を文脈に照らして取捨選択する（AI判断）。\n\n"
    "### 知見の追加（日々の更新）\n"
    "- `scripts/add_entry.py --category <id> --id <eid> --title \"...\" --intent \"...\" "
    "--background \"...\" --keywords \"k1,k2,...\" --source \"<出典>\"` で追加する。"
    "必須6フィールドを検証して追記するため JSON の手編集は不要。"
    "誤ったストアへの追加はストアの `consult_at` 不一致として拒否される。\n\n"
    "### §12 フィードバックループ（使うほど良くする）\n"
    "- 検索→活用のたびに `scripts/record_usage.py --record --query ... --matched-ids ... "
    "--used-ids ... --satisfaction helpful|neutral|unhelpful` で `knowledge/usage-log.jsonl` に追記。\n"
    "- 定期的に `scripts/record_usage.py --analyze --emit-queue brushup-queue.jsonl` で"
    "「マッチするが使われない」「unhelpful 多発」等を検出してキュー化し、"
    "`--mark-needs-update` で該当エントリに status を付与、title/keywords/background を改善する。\n\n"
    "### ライフサイクル\n"
    "- 1ファイル 500行 または 25エントリ超でサブトピック分割（`scripts/build_index.py --stats` で監視）。\n"
    "- router-registry 型は `registry.json` の status（pending / processed / needs-update / deprecated）で素材の再同期を追跡。\n\n"
    "> このナレッジループは本 Skill 単体で完結する。配布先のどの環境でも、"
    "追加・更新・検索・記録が同梱 `scripts/` だけで同じ手順で行える。"
)


# with-goal-seek.patch の決定論的注入内容。loop 実行系 (run/wrap/delegate) は _base.md が
# 継承する `## ゴールシーク実行` 散文に加えて、ループを「実行可能な機構」として配線する:
# goal-spec のロード / 周回 progress JSON / 打ち切り規約。
# 重要 (self-contained): ループ本体は本 Skill 内の AI 推論で自己完結し、外部スキルへの依存を持たない。
# run-goal-seek は「重い周回時の任意の最適化手段」であり必須ではない (with-knowledge と同じ自己完結原則)。
GOAL_SEEK_FM_BLOCK = (
    "# goal-seek: 固定手順を持たず Goal+Checklist へ向けて反復する。engine は外部スキル非依存(inline)で"
    "自己完結し、反復ループは fork で分離 context に切り出し親へ最終差分のみ返す(2軸は独立)。\n"
    "goal_seek:\n"
    "  engine: {{goal_seek.engine | default(\"inline\")}}      # inline(既定/自己完結・外部スキル不要) | run-goal-seek(同梱時のみ任意で使う重量オーケストレータ)\n"
    "  spec: eval-log/goal-spec.json                       # 任意。あればロードして利用、無ければ AI が文脈から推定\n"
    "  progress: eval-log/{{skill_name}}-progress.json     # schemas/goal-seek-loop.schema.json 準拠\n"
    "  intermediate: eval-log/{{skill_name}}-intermediate.jsonl  # 各周回末に append: original_goal/current_goal_snapshot/delta/merged_directive (ドリフト圧縮アンカー)\n"
    "  max_loops: {{goal_seek.max_loops | default(5)}}\n"
    "  fork: {{goal_seek.fork | default(\"subagent\")}}        # subagent(既定/反復を分離contextで実行し親へ最終差分のみ) | agent-team | inline(軽量単発のみ opt-down)"
)

# _base.md の `### ゴールシークループ` 直後に挿入する実行配線サブセクション。
GOAL_SEEK_LOOP_ANCHOR = (
    "1. 未達 `[ ]` を特定 → 2. 手順を都度生成（固定化禁止）→ 3. 実行 → "
    "4. チェックリスト再評価し `[x]` 更新 → 全 `[x]` まで反復。規定周回で未達なら open_issues に差し戻す。"
)

GOAL_SEEK_WIRING_SECTION = (
    "### ゴールシーク配線（実行可能機構）\n"
    "本 Skill のループは散文だけでなく実行可能機構として配線される。"
    "ユーザーの悩み（要望）をゴールに変換し、達成まで自律ループを回す:\n\n"
    "- **goal-spec**: `eval-log/goal-spec.json` があればロードして利用する"
    "（spec schema が同梱されていれば検証、無ければそのまま利用）。無ければ既存コンテキスト"
    "（直近依頼・制約・対象ファイル）から AI が最適ゴール+完了チェックリストを推定生成する"
    "（ユーザーへの追加質問は原則しない）。\n"
    "- **周回状態**: 各周回で `eval-log/{{skill_name}}-progress.json`"
    "（`run-build-skill/schemas/goal-seek-loop.schema.json` 準拠）に "
    "`iteration` / 各 checklist 項目 `{id,text,status}` / `open_issues` を記録する。\n"
    "- **コンテキスト分離（fork 軸）**: 反復ループは既定で SubAgent（`Agent`）に分離して実行し、"
    "親には最終成果物と `handoff-*.json` 要約のみ返す（中間試行で親 context を汚さない）。"
    "`fork: inline` は軽量単発時の opt-down。なお重い周回で `engine: run-goal-seek`（同梱時のみ）を"
    "使うのは外部依存軸の任意最適化で、fork 分離とは独立（`references/goal-seek-paradigm.md`「コンテキスト分離」）。\n"
    "- **中間成果物アンカー (ドリフト圧縮)**: 各周回末に "
    "`eval-log/{{skill_name}}-intermediate.jsonl` へ "
    "`{iteration, original_goal, current_goal_snapshot, delta_from_original, merged_directive_for_next, drift_signal}` を "
    "1 行追記する。`original_goal` は全周回で**不変**。次周回 Step2 (手順生成) は直前の "
    "`merged_directive_for_next` と `original_goal` を**必須入力**として読み込み、AI が単独で再導出しない。"
    "これにより固定手順なしの自由度を保ちつつ、AI が確率的最尤の抽象解へ集約化していくドリフトを"
    "アンカーで毎周回押し戻す (`references/goal-seek-paradigm.md`「中間成果物」)。\n"
    "- **drift_signal** (enum 6 値、schema 必須): `initial` (iteration=0 のみ・前周回無し) / "
    "`aligned` (差分ゼロ) / `compressing` (縮んでいる・継続) / `stagnant` (2 周連続変化なし・アプローチ転換) / "
    "`widening` (広がっている・差し戻し検討) / `oscillating` (正負反転・打ち切り検討)。"
    "判定主体はループ実行 SubAgent (fork 内自己評価)、判定タイミングは Step4 検証後・Step5 反復判定前。\n"
    "- **打ち切り**: `goal_seek.max_loops`（既定 5）到達でも未達、または "
    "`drift_signal: stagnant`/`widening`/`oscillating` が 2 周連続なら、残項目と差分を `open_issues` に記録し"
    "人間 or 上位 orchestrator へ差し戻す。\n\n"
    "> この配線により、本 Skill は配布先のどの環境でも「ゴールへ向けて自動でループを回す」挙動を同じ機構で再現する。\n\n"
    "### ゴールシーク検証（機械検査）\n"
    "ループ完了時、`eval-log/{{skill_name}}-intermediate.jsonl` の整合を機械検査する。"
    "本検査は `run-goal-seek/SKILL.md` と同型 (中間成果物アンカー機構の SSOT、"
    "`references/goal-seek-paradigm.md` 「中間成果物」)。量産スキルでも同じ機構で再現性 100% を担保する。\n\n"
    "```bash\n"
    "python3 - \"$PWD/eval-log/{{skill_name}}-progress.json\" \"$PWD/eval-log/{{skill_name}}-intermediate.jsonl\" <<'PY'\n"
    "import json, sys, os, hashlib\n"
    "prog_path, inter_path = sys.argv[1], sys.argv[2]\n"
    "prog = json.load(open(prog_path, encoding=\"utf-8\")) if os.path.exists(prog_path) else {}\n"
    "required_keys = {\"iteration\",\"original_goal\",\"current_goal_snapshot\",\"delta_from_original\",\"merged_directive_for_next\",\"drift_signal\"}\n"
    "if not os.path.exists(inter_path):\n"
    "    print(\"intermediate.jsonl 未生成 (ループ未実行)\"); sys.exit(0)\n"
    "lines = [l for l in open(inter_path, encoding=\"utf-8\").read().splitlines() if l.strip()]\n"
    "assert lines, \"intermediate.jsonl が空\"\n"
    "iters = prog.get(\"iteration\", len(lines) - 1)\n"
    "assert len(lines) == iters + 1, f\"intermediate 行数 {len(lines)} != progress.iteration+1 ({iters+1})\"\n"
    "first_anchor = None\n"
    "for i, line in enumerate(lines):\n"
    "    entry = json.loads(line)\n"
    "    missing = required_keys - entry.keys()\n"
    "    assert not missing, f\"intermediate[{i}] 必須キー不足: {missing}\"\n"
    "    if i == 0:\n"
    "        first_anchor = entry[\"original_goal\"]\n"
    "        expected_hash = hashlib.sha256(first_anchor.encode()).hexdigest()\n"
    "        actual_hash = prog.get(\"original_goal_hash\")\n"
    "        assert actual_hash is None or actual_hash == expected_hash, f\"original_goal_hash drift: progress={actual_hash} vs sha256(intermediate[0])={expected_hash}\"\n"
    "    assert entry[\"original_goal\"] == first_anchor, f\"intermediate[{i}] anchor 不変性違反\"\n"
    "print(f\"intermediate 検査 OK: {len(lines)} 行 / anchor 不変 / hash 一致\")\n"
    "PY\n"
    "```"
)


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
        "--with-knowledge",
        action="store_true",
        help="inject self-contained knowledge-loop block (pattern stays as {{knowledge_loop.pattern}} template var)",
    )
    parser.add_argument(
        "--no-goal-seek",
        action="store_true",
        help="opt out of the default-ON goal-seek wiring for loop kinds (run/wrap/delegate)",
    )
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
    # goal-seek 配線は loop 実行系で default-ON (--no-goal-seek で opt-out)。
    if args.kind in GOAL_SEEK_KINDS and not args.no_goal_seek:
        patches.append("with-goal-seek.patch")
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
        # run-kind の固有差分は frontmatter のみ。手順は _base.md の `## ゴールシーク実行` を継承し、
        # 固定手順 (### Step 1/2/3) は注入しない (goal-seek 原則「固定手順は書かない」と矛盾するため)。
        text = ensure_frontmatter_line(text, "effect: {{effect | default(\"local-artifact\")}}", "kind")
        text = ensure_frontmatter_line(text, "role_suffix: {{role_suffix | default(\"workflow\")}}", "effect")
        return text
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
    if patch_name == "with-knowledge.patch":
        text = ensure_frontmatter_line(text, KNOWLEDGE_FM_BLOCK, "rubric_refs")
        return add_section_after(text, "## 主要ルール\n{{key_constraints}}", KNOWLEDGE_SECTION)
    if patch_name == "with-goal-seek.patch":
        text = ensure_frontmatter_line(text, GOAL_SEEK_FM_BLOCK, "rubric_refs")
        return add_section_after(text, GOAL_SEEK_LOOP_ANCHOR, GOAL_SEEK_WIRING_SECTION)
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
