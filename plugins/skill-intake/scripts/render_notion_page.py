#!/usr/bin/env python3
"""intake.json + manifest.json から Notion ブロック配列を生成する。"""

import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
with open(SCRIPT_DIR / 'notion_limits.json', 'r', encoding='utf-8') as f:
    _LIMITS = json.load(f)
MAX_RT = _LIMITS['MAX_RT']


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
    # JS 実装は icon: undefined のとき key 自体は出力するが JSON.stringify で undefined は脱落する。
    if emoji:
        block['icon'] = {'type': 'emoji', 'emoji': emoji}
    return {'object': 'block', 'type': 'callout', 'callout': block}


def push_if_text(blocks, text, factory):
    if text is None:
        return
    s = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
    if not s.strip():
        return
    blocks.append(factory(s))


def render_key_value_list(blocks, obj):
    if not isinstance(obj, dict):
        return
    for k, v in obj.items():
        val = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        blocks.append(bullet(f'{k}: {val}'))


def render_array(blocks, arr, formatter=None):
    if not isinstance(arr, list):
        return
    for item in arr:
        if formatter:
            text = formatter(item)
        elif isinstance(item, str):
            text = item
        else:
            text = json.dumps(item, ensure_ascii=False)
        if text and text.strip():
            blocks.append(bullet(text))


def load_mermaid_source(item):
    src = item.get('mermaid_source')
    if src:
        return src
    p = item.get('path')
    if p and p.lower().endswith('.mmd'):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None
    return None


def render_diagram(blocks, item):
    caption = item.get('caption')
    if caption:
        blocks.append(paragraph(caption))
    mermaid = load_mermaid_source(item)
    if mermaid:
        blocks.append(code(mermaid, 'mermaid'))
        return
    if item.get('public_url'):
        blocks.append(image(item['public_url']))
        return
    blocks.append(paragraph(f"[asset pending] {item.get('path') or '(no path)'}"))


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


def render(intake, assets):
    blocks = []
    title = intake.get('skill_name_hint') or intake.get('skill_name') or 'Skill Intake'
    blocks.append(heading(1, title))
    desc = intake.get('description') or intake.get('purpose')
    if desc:
        blocks.append(callout(desc, '📝'))

    blocks.append(heading(2, '5 軸'))
    axes = intake.get('five_axes') or intake.get('5_axes') or {}
    axis_labels = {
        'output_target': '出力先',
        'info_source': '情報源',
        'share_target': '共有相手',
        'true_problem': '真の課題',
        'knowledge_assets': 'ナレッジ資産',
    }
    for k, label in axis_labels.items():
        blocks.append(heading(3, label))
        v = axes.get(k)
        if v is None:
            text = '(未充足)'
        elif isinstance(v, str):
            text = v
        elif isinstance(v, dict):
            text = v.get('answer') or json.dumps(v, ensure_ascii=False)
        else:
            text = json.dumps(v, ensure_ascii=False)
        blocks.append(paragraph(text))

    if intake.get('user_profile'):
        blocks.append(heading(2, 'User Profile'))
        up = intake['user_profile']
        if isinstance(up, str):
            blocks.append(paragraph(up))
        else:
            render_key_value_list(blocks, up)

    p = intake.get('pattern') or intake.get('pattern_classification')
    if p:
        blocks.append(heading(2, 'パターン分類'))
        if isinstance(p, str):
            blocks.append(paragraph(p))
        else:
            render_key_value_list(blocks, p)

    integ = intake.get('integrations') or intake.get('external_integrations')
    if integ:
        blocks.append(heading(2, '外部連携'))
        if isinstance(integ, list):
            def fmt(i):
                if isinstance(i, str):
                    return i
                name = i.get('name') or i.get('service') or ''
                purpose = i.get('purpose')
                return f"{name}{' — ' + purpose if purpose else ''}"
            render_array(blocks, integ, fmt)
        else:
            render_key_value_list(blocks, integ)

    vkpi = intake.get('value_kpi') or intake.get('outcome') or intake.get('value_realization')
    if vkpi:
        blocks.append(heading(2, '価値・KPI'))
        if isinstance(vkpi, str):
            blocks.append(paragraph(vkpi))
        elif isinstance(vkpi, list):
            render_array(blocks, vkpi)
        else:
            render_key_value_list(blocks, vkpi)

    if intake.get('anti_patterns') is not None:
        ap = intake['anti_patterns']
        # JS は truthy 判定: 空配列も truthy なので heading は出るが、empty array なら何も追加されない
        if ap or ap == []:
            blocks.append(heading(2, 'アンチパターン'))
            if isinstance(ap, list):
                render_array(blocks, ap)
            else:
                push_if_text(blocks, ap, paragraph)

    c = intake.get('completion_criteria') or intake.get('completeness')
    if c:
        blocks.append(heading(2, '完了条件'))
        if isinstance(c, list):
            render_array(blocks, c)
        elif isinstance(c, str):
            blocks.append(paragraph(c))
        else:
            render_key_value_list(blocks, c)

    oq = intake.get('open_questions')
    if isinstance(oq, list) and len(oq) > 0:
        blocks.append(heading(2, 'Open Questions'))
        def qfmt(q):
            if isinstance(q, str):
                return q
            if isinstance(q, dict):
                return q.get('text') or q.get('question') or json.dumps(q, ensure_ascii=False)
            return json.dumps(q, ensure_ascii=False)
        render_array(blocks, oq, qfmt)

    if isinstance(assets, dict) and isinstance(assets.get('items'), list):
        diagram_items = assets['items']
    elif isinstance(intake.get('visualizations'), list):
        diagram_items = intake['visualizations']
    else:
        diagram_items = []
    if diagram_items:
        blocks.append(heading(2, '図解'))
        for a in diagram_items:
            render_diagram(blocks, a)

    next_action = intake.get('recommended_next') or intake.get('next_action') or intake.get('next_actions')
    if next_action:
        blocks.append(divider())
        blocks.append(heading(2, 'Next Action (skill-creator 引き渡し)'))
        if isinstance(next_action, str):
            blocks.append(paragraph(next_action))
        elif isinstance(next_action, list):
            render_array(blocks, next_action)
        else:
            render_key_value_list(blocks, next_action)

    h = intake.get('handoff_candidates') or intake.get('handoff')
    if h:
        blocks.append(heading(2, 'Handoff 候補'))
        if isinstance(h, list):
            render_array(blocks, h)
        elif isinstance(h, str):
            blocks.append(paragraph(h))
        else:
            render_key_value_list(blocks, h)

    b = intake.get('skill_construction_brief') or intake.get('skill_creator_brief')
    if b:
        blocks.append(heading(2, 'スキル構築 brief サマリ'))
        if isinstance(b, str):
            blocks.append(paragraph(b))
        else:
            render_key_value_list(blocks, b)

    return {'children': blocks}


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
    v = validate_required_sections(intake, assets)
    if not v['ok']:
        for r in v['reasons']:
            sys.stderr.write(f'required-section: {r}\n')
        return 2
    out = render(intake, assets)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if out_file:
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
    else:
        sys.stdout.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
