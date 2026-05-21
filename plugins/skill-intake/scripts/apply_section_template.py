#!/usr/bin/env python3
"""Render a section using the 6-block lattice defined in section-templates.json.

6 必須ブロック:
  (a) purpose_callout  emoji + 200字
  (b) required_fields  キー/型/制約/例 表
  (c) good_example     200字+ callout
  (d) ng_example       100字+ callout (5軸章のみ TODO(human) プレースホルダー)
  (e) char_bounds      字数下限/上限 (section_quality_check.py と同期)
  (f) visualization    mermaid / SVG / table 1-3 点

Legacy: `apply(template, vars)` で {{var}} 単純置換も維持する。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_TEMPLATE = """## {{title}}

**ねらい**: {{purpose}}

**現状**: {{current}}

**期待**: {{expected}}

{{diagram_block}}

**未解決**: {{open_questions}}
"""

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")

_TEMPLATES_PATH_DEFAULT = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "run-skill-intake-aggregator"
    / "references"
    / "section-templates.json"
)


def fill(tpl: str, vars: dict[str, Any]) -> str:
    def _sub(m: re.Match[str]) -> str:
        v = vars.get(m.group(1))
        return '' if v is None else str(v)
    return _PLACEHOLDER.sub(_sub, tpl)


def diagram_block(diagrams: Any) -> str:
    if not isinstance(diagrams, list) or not diagrams:
        return ''
    return ''.join(f"\n```mermaid\n{str(d).strip()}\n```\n" for d in diagrams)


def apply(template: str | None, vars: dict[str, Any]) -> str:
    v = dict(vars)
    if isinstance(v.get('diagrams'), list):
        v['diagram_block'] = diagram_block(v['diagrams'])
    return fill(template or DEFAULT_TEMPLATE, v)


def _render_required_fields_table(fields: list[dict[str, Any]]) -> str:
    out = ["| キー | 型 | 制約 | 例 |", "|---|---|---|---|"]
    for f in fields:
        out.append(
            f"| `{f.get('key','')}` | {f.get('type','')} | {f.get('constraint','')} | {f.get('example','')} |"
        )
    return "\n".join(out)


def _viz_block(viz_type: str) -> str:
    vt = (viz_type or '').lower()
    if vt.startswith('mermaid'):
        kind = vt.split('_', 1)[1] if '_' in vt else 'flowchart'
        return (
            f"```mermaid\n%% viz_type={viz_type}; 1-3点を配置すること (visualization-mandatory-rules.md)\n"
            f"{kind} TD\n  A[起点] --> B[処理] --> C[結果]\n```"
        )
    if vt.startswith('svg'):
        return (
            f"<!-- SVG: assets/cvis-{vt.replace('svg_','')}.svg を1-3点配置 "
            f"(visualization-mandatory-rules.md 準拠) -->"
        )
    if vt == 'table':
        return "<!-- 表形式の可視化を1点以上配置 -->"
    return "<!-- 可視化ブロックを1-3点配置 -->"


def render_section(section_key: str, spec: dict[str, Any]) -> str:
    title = spec.get('title', section_key)
    purpose = spec.get('purpose_text', '')
    fields = spec.get('required_fields', []) or []
    good = spec.get('good_example', '')
    ng = spec.get('ng_example', '')
    min_c = spec.get('min_chars', 200)
    max_c = spec.get('max_chars', 1200)
    viz = spec.get('viz_type', '')

    parts = [
        f"## {title}",
        "",
        f"> **(a) 目的**: {purpose}",
        "",
        "**(b) 必須フィールド**",
        "",
        _render_required_fields_table(fields),
        "",
        f"> **(c) 良例**: {good}",
        "",
        f"> **(d) NG例**: {ng}",
        "",
        (
            "<details><summary>(e) 字数下限/上限</summary>\n\n"
            f"- min_chars: {min_c}\n"
            f"- max_chars: {max_c}\n"
            f"- 同期先: `scripts/section_quality_check.py` (section-templates.json と同値検証)\n\n"
            "</details>"
        ),
        "",
        f"**(f) 可視化義務** ({viz}, 1-3点)",
        "",
        _viz_block(viz),
        "",
    ]
    return "\n".join(parts)


def render_all(templates_path: Path | None = None) -> str:
    p = templates_path or _TEMPLATES_PATH_DEFAULT
    data = json.loads(p.read_text(encoding='utf-8'))
    sections = data.get('sections', {})
    out = []
    for key, spec in sections.items():
        out.append(render_section(key, spec))
    return "\n".join(out)


def main(argv: list[str]) -> int:
    # サブコマンド: --lattice で6ブロック格子レンダリング
    if argv and argv[0] in ('--lattice', 'lattice'):
        tpath = Path(argv[1]).resolve() if len(argv) > 1 else _TEMPLATES_PATH_DEFAULT
        sys.stdout.write(render_all(tpath))
        return 0

    if len(argv) < 1:
        sys.stderr.write(
            'usage: apply_section_template.py <vars.json> [template.md]\n'
            '       apply_section_template.py --lattice [section-templates.json]\n'
        )
        return 2
    vars_file = argv[0]
    template_file = argv[1] if len(argv) > 1 else None
    try:
        vars = json.loads(Path(vars_file).resolve().read_text(encoding='utf-8'))
        tpl = DEFAULT_TEMPLATE
        if template_file:
            tpl = Path(template_file).resolve().read_text(encoding='utf-8')
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    sys.stdout.write(apply(tpl, vars))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
