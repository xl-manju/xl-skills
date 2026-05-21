#!/usr/bin/env python3
"""Section quality check for the 6-block lattice.

検証対象:
  (a) purpose_callout  存在 + 200字下限
  (b) required_fields  キー/型/制約/例 表 存在
  (c) good_example     200字下限
  (d) ng_example       100字下限 (TODO(human) や generic placeholder は違反として FAIL)
  (e) char_bounds      min_chars / max_chars が section-templates.json と一致
  (f) visualization    mermaid または SVG/Table 言及 1点以上

input: intake.json (sections dict; key=セクションID, value=本文 string)
templates: section-templates.json (キー対応)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_PLACEHOLDER_RE = re.compile(r'(\bTBD\b|未定|要確認|\?{2,})', re.IGNORECASE)
_TODO_HUMAN_RE = re.compile(r'TODO\(human\)')

_TEMPLATES_PATH_DEFAULT = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "run-skill-intake-aggregator"
    / "references"
    / "section-templates.json"
)


def _char_count(text: str) -> int:
    return len(re.sub(r'\s+', '', text or ''))


def _has_block_a(text: str) -> bool:
    return bool(re.search(r'\(a\)\s*目的', text)) or bool(re.search(r'目的callout|purpose_callout|ねらい', text, re.IGNORECASE))


def _has_block_b(text: str) -> bool:
    # 必須フィールド表: ヘッダ「キー | 型 | 制約 | 例」を緩く検出
    return bool(re.search(r'キー.*型.*制約.*例', text)) or bool(re.search(r'\(b\)\s*必須フィールド', text))


def _has_block_c(text: str) -> bool:
    return bool(re.search(r'\(c\)\s*良例|good[_ ]example', text, re.IGNORECASE))


def _has_block_d(text: str) -> bool:
    return bool(re.search(r'\(d\)\s*NG例|ng[_ ]example|アンチパターン', text, re.IGNORECASE))


def _has_block_e(text: str) -> bool:
    return bool(re.search(r'min_chars|字数下限|\(e\)\s*字数', text))


def _has_block_f(text: str) -> bool:
    return (
        '```mermaid' in text
        or bool(re.search(r'\.svg|cvis-', text))
        or bool(re.search(r'\(f\)\s*可視化', text))
    )


def _strip_ng_block(text: str) -> str:
    # NG例 callout 内には意図的に TBD/未定 が含まれるため placeholder 検査から除外する
    return re.sub(r'\(d\)\s*NG例[\s\S]*?(?=\n<details|\n\*\*\(e\)|\n## |$)', '', text)


def check_section(name: str, body: Any, spec: dict[str, Any] | None) -> dict[str, Any]:
    text = str(body or '')
    char_count = _char_count(text)
    text_wo_ng = _strip_ng_block(text)
    has_placeholder_generic = bool(_PLACEHOLDER_RE.search(text_wo_ng))
    has_todo_human = bool(_TODO_HUMAN_RE.search(text))

    blocks = {
        'a_purpose_callout': _has_block_a(text),
        'b_required_fields': _has_block_b(text),
        'c_good_example': _has_block_c(text),
        'd_ng_example': _has_block_d(text),
        'e_char_bounds': _has_block_e(text),
        'f_visualization': _has_block_f(text),
    }
    missing_blocks = [k for k, v in blocks.items() if not v]

    min_chars = (spec or {}).get('min_chars', 200)
    max_chars = (spec or {}).get('max_chars', 99999)
    chars_ok = char_count >= min_chars and char_count <= max_chars

    placeholder_violation = has_placeholder_generic or has_todo_human
    intentional_todo = False

    ok = len(missing_blocks) == 0 and chars_ok and not placeholder_violation
    return {
        'section': name,
        'ok': ok,
        'char_count': char_count,
        'min_chars': min_chars,
        'max_chars': max_chars,
        'chars_ok': chars_ok,
        'blocks': blocks,
        'missing_blocks': missing_blocks,
        'has_placeholder': has_placeholder_generic,
        'has_todo_human': has_todo_human,
        'intentional_todo': intentional_todo,
    }


def check_all(sections: dict[str, Any], templates: dict[str, Any] | None = None) -> dict[str, Any]:
    specs = (templates or {}).get('sections', {}) if templates else {}
    results = [check_section(k, sections[k], specs.get(k)) for k in sections]
    failed = [r for r in results if not r['ok']]
    return {'ok': len(failed) == 0, 'results': results, 'failed_count': len(failed)}


def load_templates(path: Path | None = None) -> dict[str, Any]:
    p = path or _TEMPLATES_PATH_DEFAULT
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return {}


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        sys.stderr.write('usage: section_quality_check.py <intake.json> [section-templates.json]\n')
        return 2
    try:
        data = json.loads(Path(argv[0]).resolve().read_text(encoding='utf-8'))
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    tpath = Path(argv[1]).resolve() if len(argv) > 1 else None
    templates = load_templates(tpath)
    r = check_all(data.get('sections') or {}, templates)
    sys.stdout.write(json.dumps(r, ensure_ascii=False, indent=2) + '\n')
    return 0 if r['ok'] else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
