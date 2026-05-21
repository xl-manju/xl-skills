#!/usr/bin/env python3
"""intake.json + manifest.json から Notion ブロック配列を生成する。

本ファイルは section-templates.json の 6 必須ブロック格子
((a)目的callout / (b)必須フィールド表 / (c)良例callout / (d)NG例callout /
 (e)字数下限/上限 + section_quality_check 同期 toggle / (f)図解)
に従って 12 章をテンプレート駆動で出力する。
section_quality_check.py と block_keys を共有しているため、本文構造の同期検証が可能。
"""

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
with open(SCRIPT_DIR / 'notion_limits.json', 'r', encoding='utf-8') as f:
    _LIMITS = json.load(f)
MAX_RT = _LIMITS['MAX_RT']

# section-templates.json の所在 (skills/run-skill-intake-aggregator/references)
SECTION_TEMPLATES_PATH = (
    SCRIPT_DIR.parent
    / 'skills'
    / 'run-skill-intake-aggregator'
    / 'references'
    / 'section-templates.json'
)

# intake.json の素のキー → section-templates.json の section_key への対応表。
# 値は intake.json から「主たる回答 dict / list / scalar」を取り出すためのドット区切りパス。
# 複数候補がある場合は最初に hit したものを採用する。
SECTION_DATA_PATHS = {
    '0_cover_meta': ['__meta__'],  # skill_name_hint / owner / status / interview_date 等を合成
    '1_purpose': ['purpose_and_background', 'purpose'],
    '2_user_profile': ['user_profile'],
    '3_five_axes': ['five_axes', '5_axes'],
    '4_external_integration': ['external_integrations', 'integrations'],
    '5_expected_flow': ['expected_flow', 'flow'],
    '6_value_kpi': ['value_kpi', 'kpi', 'value_realization'],
    '7_similar_skills': ['similar_skills'],
    '7_5_knowledge_asset': ['knowledge_asset', 'five_axes.knowledge_assets'],
    '8_open_questions': ['open_questions'],
    '9_next_action': ['next_action', 'recommended_next', 'next_actions'],
    '10_appendix_vocabulary': ['vocabulary', 'appendix.vocabulary'],
}


def rt(text):
    s = '' if text is None else str(text)
    return [{'type': 'text', 'text': {'content': s[:MAX_RT]}}]


def heading(level, text):
    lv = max(1, min(level, 3))
    key = f'heading_{lv}'
    return {'object': 'block', 'type': key, key: {'rich_text': rt(text)}}


def paragraph(text):
    return {'object': 'block', 'type': 'paragraph', 'paragraph': {'rich_text': rt(text)}}


def bullet(text):
    return {'object': 'block', 'type': 'bulleted_list_item', 'bulleted_list_item': {'rich_text': rt(text)}}


def image(url):
    return {'object': 'block', 'type': 'image', 'image': {'type': 'external', 'external': {'url': url}}}


def code(text, language=None):
    return {
        'object': 'block',
        'type': 'code',
        'code': {'rich_text': rt(text), 'language': language or 'plain text'},
    }


def divider():
    return {'object': 'block', 'type': 'divider', 'divider': {}}


def callout(text, emoji=None):
    block = {'rich_text': rt(text)}
    if emoji:
        block['icon'] = {'type': 'emoji', 'emoji': emoji}
    return {'object': 'block', 'type': 'callout', 'callout': block}


def toggle(summary, children=None):
    """summary 行を持ち、children を内包する Notion toggle ブロックを返す。"""
    payload = {'rich_text': rt(summary)}
    if children:
        payload['children'] = list(children)
    return {'object': 'block', 'type': 'toggle', 'toggle': payload}


def _lookup_path(obj, dotted):
    """ドット区切りパス (a.b.c) で dict を辿る。途中で欠落したら None。"""
    if dotted == '__meta__':
        return obj  # 0_cover_meta は intake 全体を渡す
    cur = obj
    for part in dotted.split('.'):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def get_section_data(intake, section_key):
    paths = SECTION_DATA_PATHS.get(section_key, [])
    for p in paths:
        v = _lookup_path(intake, p)
        if v is not None:
            return v
    return None


def _extract_field_value(section_data, field_key):
    """required_fields[].key (例: 'purpose.stated', 'five_axes.output_to.answer') を
    section_data または intake 部分木から抽出する。
    トップレベル名 (purpose / five_axes / user_profile / 等) を任意に剥がしてフォールバックする。
    """
    if section_data is None:
        return None
    candidates = [field_key]
    # 先頭セグメントを 1 つ剥がしたパスも候補に追加 (section_data が既にその木である場合)
    if '.' in field_key:
        candidates.append(field_key.split('.', 1)[1])
    # 末尾セグメントだけも候補に追加 (answer 直下を読みたい等)
    candidates.append(field_key.rsplit('.', 1)[-1])
    for c in candidates:
        v = _lookup_path(section_data, c) if isinstance(section_data, dict) else None
        if v is not None:
            return v
    return None


def _format_answer(v):
    if v is None:
        return ''
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        # {answer: ..., depth: ..., verified: ...} 形式は answer を優先表示
        if 'answer' in v and isinstance(v['answer'], (str, int, float)):
            return str(v['answer']).strip()
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)
    return str(v)


def _diagrams_for_viz_type(assets, viz_type):
    """manifest.items から viz_type に合致 (または部分一致) する図解を最大 3 件返す。
    厳密一致がなければ heuristic: 'mermaid_' で始まる viz_type は mermaid_source あり、
    'svg_' は path .svg、'table' は code(plaintext) を許容。
    """
    if not isinstance(assets, dict):
        return []
    items = assets.get('items')
    if not isinstance(items, list):
        return []
    exact = [it for it in items if it.get('viz_type') == viz_type]
    if exact:
        return exact[:3]
    # heuristic フォールバック
    if not viz_type:
        return []
    if viz_type.startswith('mermaid_'):
        fallback = [it for it in items if it.get('mermaid_source') or (it.get('path') or '').endswith('.mmd')]
    elif viz_type.startswith('svg_'):
        fallback = [it for it in items if (it.get('path') or '').lower().endswith('.svg') or it.get('public_url')]
    else:
        fallback = []
    return fallback[:3]


def render_diagram_into(blocks, item):
    caption = item.get('caption')
    if caption:
        blocks.append(paragraph(caption))
    src = item.get('mermaid_source')
    if not src:
        p = item.get('path')
        if p and p.lower().endswith('.mmd'):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    src = f.read()
            except Exception:
                src = None
    if src:
        blocks.append(code(src, 'mermaid'))
        return
    if item.get('public_url'):
        blocks.append(image(item['public_url']))
        return
    blocks.append(paragraph(f"[asset pending] {item.get('path') or '(no path)'}"))


def render_section_lattice(section_key, spec, intake_section_data, assets, unanswered_counter):
    """6 必須ブロック格子で 1 セクションを描画する。

    返り値: list[dict] (Notion blocks)
    unanswered_counter: dict 形式の参照渡しカウンタ {section_key: int}
    """
    blocks = []
    title = spec.get('title') or section_key

    # 見出し
    blocks.append(heading(2, title))

    # (a) 目的 callout
    purpose_text = spec.get('purpose_text') or ''
    if purpose_text:
        blocks.append(callout(purpose_text, '🎯'))

    # (b) 必須フィールド
    blocks.append(heading(3, '必須フィールド'))
    required_fields = spec.get('required_fields') or []
    unanswered_local = 0
    for field in required_fields:
        fkey = field.get('key', '')
        ftype = field.get('type', '')
        constraint = field.get('constraint', '')
        example = field.get('example', '')
        answer_raw = _extract_field_value(intake_section_data, fkey)
        answer_str = _format_answer(answer_raw)
        if not answer_str:
            answer_str = '（未回答 — interviewer に追加質問依頼）'
            unanswered_local += 1
        example_str = example if isinstance(example, str) else json.dumps(example, ensure_ascii=False)
        line = f'{fkey}: {ftype}({constraint}) → {answer_str} / 例: {example_str}'
        blocks.append(bullet(line))
    if unanswered_local:
        unanswered_counter[section_key] = unanswered_local

    # (c) 良例 callout
    good_example = spec.get('good_example')
    if good_example:
        blocks.append(callout(good_example, '✅'))

    # (d) NG 例 callout
    ng_example = spec.get('ng_example')
    if ng_example:
        blocks.append(callout(ng_example, '⚠️'))

    # (e) 字数下限/上限 + section_quality_check 同期 toggle
    min_chars = spec.get('min_chars')
    max_chars = spec.get('max_chars')
    toggle_children = [
        bullet(f'min_chars: {min_chars}（section_quality_check.py が下限未達で FAIL）'),
        bullet(f'max_chars: {max_chars}（超過時は冗長判定）'),
        bullet(f'block_keys 同期対象: purpose_callout / required_fields / good_example / ng_example / char_bounds / visualization'),
        bullet(f'section_key: {section_key}'),
    ]
    blocks.append(toggle('字数下限/上限 + 品質ゲート同期', toggle_children))

    # (f) 図解
    blocks.append(heading(3, '図解'))
    viz_type = spec.get('viz_type') or ''
    diagrams = _diagrams_for_viz_type(assets, viz_type)
    if diagrams:
        for d in diagrams:
            render_diagram_into(blocks, d)
    else:
        blocks.append(paragraph(f'[viz pending] viz_type={viz_type}（manifest 未提供）'))

    # セクション区切り
    blocks.append(divider())
    return blocks


def axis_answer(v):
    if v is None:
        return ''
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        a = v.get('answer')
        if isinstance(a, str):
            return a.strip()
    return ''


def validate_required_sections(intake, assets):
    reasons = []
    axes = intake.get('five_axes') or intake.get('5_axes') or {}
    keys = ['output_target', 'info_source', 'share_target', 'true_problem', 'knowledge_assets']
    filled = [k for k in keys if len(axis_answer(axes.get(k))) > 0]
    if len(filled) < 3:
        reasons.append(f'required at least 3 filled axes, got {len(filled)} ({",".join(filled) or "none"})')
    if not axis_answer(axes.get('true_problem')):
        reasons.append('true_problem axis is required but empty')
    items = assets.get('items') if isinstance(assets, dict) else None
    if not isinstance(items, list) or len(items) < 1:
        reasons.append('manifest.items must contain at least 1 diagram')
    return {'ok': len(reasons) == 0, 'reasons': reasons}


def load_section_templates():
    with open(SECTION_TEMPLATES_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def render(intake, assets):
    blocks = []

    # 冒頭: skill タイトル + 概要 callout (維持)
    title = intake.get('skill_name_hint') or intake.get('skill_name') or 'Skill Intake'
    blocks.append(heading(1, title))
    desc = intake.get('description') or intake.get('purpose')
    if desc:
        blocks.append(callout(desc, '📝'))

    # section-templates.json の格子で全 12 章を出力
    templates = load_section_templates()
    sections = templates.get('sections') or {}
    unanswered = {}

    # section-templates.json のキー順を維持しつつ、念のため自然順にソート
    def _sort_key(k):
        head = k.split('_', 1)[0]
        try:
            return float(head)
        except ValueError:
            return 99.0

    for section_key in sorted(sections.keys(), key=_sort_key):
        spec = sections[section_key]
        intake_section_data = get_section_data(intake, section_key)
        blocks.extend(
            render_section_lattice(section_key, spec, intake_section_data, assets, unanswered)
        )

    return {'children': blocks, 'unanswered_by_section': unanswered}


def main(argv):
    if len(argv) < 2:
        sys.stderr.write('usage: render_notion_page.py <intake.json> [manifest.json] [out.json]\n')
        return 2
    intake_file = argv[1]
    assets_file = argv[2] if len(argv) > 2 else None
    out_file = argv[3] if len(argv) > 3 else None
    try:
        with open(intake_file, 'r', encoding='utf-8') as f:
            intake = json.load(f)
        assets = None
        if assets_file and os.path.exists(assets_file):
            with open(assets_file, 'r', encoding='utf-8') as f:
                assets = json.load(f)
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    # validation は実行するが、失敗しても render は必ず通す（デフォルト100%出力ポリシー）。
    # 失敗理由は冒頭 callout として Notion ページに可視化し、interviewer の追加質問の根拠にする。
    # 厳密な fail/pass 判定は後段の quality_gate.py に委譲する。
    v = validate_required_sections(intake, assets)
    out = render(intake, assets)
    if not v['ok']:
        warn_lines = ['⚠️ 必須項目未充足（要追加ヒアリング）'] + [f'- {r}' for r in v['reasons']]
        warn_block = callout('\n'.join(warn_lines), '⚠️')
        # 先頭の heading_1 直後に警告を差し込む
        children = out['children']
        if children and children[0].get('type') == 'heading_1':
            out['children'] = [children[0], warn_block] + children[1:]
        else:
            out['children'] = [warn_block] + children
        for r in v['reasons']:
            sys.stderr.write(f'required-section (warn, render continues): {r}\n')
    # publish_notion_page.py は children のみを参照するので、unanswered_by_section は
    # stderr に診断出力し JSON の children は最小互換を維持する。
    diag = out.pop('unanswered_by_section', {})
    if diag:
        total = sum(diag.values())
        sys.stderr.write(f'[render_notion_page] unanswered fields total={total} sections={json.dumps(diag, ensure_ascii=False)}\n')
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if out_file:
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
    else:
        sys.stdout.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
