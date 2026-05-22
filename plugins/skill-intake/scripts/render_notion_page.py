#!/usr/bin/env python3
"""intake-final-context.json から Notion ページペイロード（properties + children）を生成する v2 レンダラ。

責務:
  - DB プロパティは context.notion_db_properties をそのまま Notion 型に projection する
  - 本文 children は intake-final-template.md.tmpl の §0〜§11 構造を context から直接組み立てる
    （Markdown 経由ではなく context オブジェクトを正本として参照）

正本:
  - 構造: skills/run-skill-intake-aggregator/references/intake-final-schema.json
  - テンプレ: skills/run-skill-intake-aggregator/references/intake-final-template.md.tmpl
  - DB スキーマ: skills/run-skill-intake-aggregator/references/notion-db-schema.json (v2)

v1 ブリッジ (section-templates.json / SECTION_DATA_PATHS) は廃止済み。
render_v2_adapter.py は v2 経路の section_canonical_map iterator として継続使用 (dry_render_notion.py から import)。
"""

import json
import os
import sys
from pathlib import Path

import jsonschema

SCRIPT_DIR = Path(__file__).resolve().parent
with open(SCRIPT_DIR / 'notion_limits.json', 'r', encoding='utf-8') as f:
    _LIMITS = json.load(f)
MAX_RT = _LIMITS['MAX_RT']

SCHEMA_PATH = (
    SCRIPT_DIR.parent
    / 'skills'
    / 'run-skill-intake-aggregator'
    / 'references'
    / 'intake-final-schema.json'
)


def _load_schema():
    with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


# ===== Notion block primitives =====

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


def numbered(text):
    return {'object': 'block', 'type': 'numbered_list_item', 'numbered_list_item': {'rich_text': rt(text)}}


def code(text, language=None):
    return {'object': 'block', 'type': 'code', 'code': {'rich_text': rt(text), 'language': language or 'plain text'}}


def divider():
    return {'object': 'block', 'type': 'divider', 'divider': {}}


def callout(text, emoji=None):
    block = {'rich_text': rt(text)}
    if emoji:
        block['icon'] = {'type': 'emoji', 'emoji': emoji}
    return {'object': 'block', 'type': 'callout', 'callout': block}


def quote(text):
    return {'object': 'block', 'type': 'quote', 'quote': {'rich_text': rt(text)}}


# ===== DB properties projection =====

def _select(value):
    return {'select': {'name': str(value)}} if value is not None else {'select': None}


def _multi(values):
    return {'multi_select': [{'name': str(v)} for v in (values or [])]}


def _rich(text):
    return {'rich_text': rt(text)}


def _title(text):
    return {'title': rt(text)}


def _date(value):
    return {'date': {'start': value}} if value else {'date': None}


def _url(value):
    return {'url': value or None}


def project_db_properties(ctx):
    """context.notion_db_properties → Notion DB properties payload。

    notion-db-schema.json (v2) のキーと型に厳密に従う。
    """
    p = ctx.get('notion_db_properties') or {}
    return {
        '名前': _title(p.get('名前', '')),
        'ステータス': _select(p.get('ステータス')),
        'パターン': _select(p.get('パターン')),
        'ワークフロー': _select(p.get('ワークフロー')),
        '深度': _select(p.get('深度')),
        '熟練度': _select(p.get('熟練度')),
        'テーマ抽出': _select(p.get('テーマ抽出')),
        '責務境界': _select(p.get('責務境界')),
        '配信タイミング': _select(p.get('配信タイミング')),
        '出力先': _multi(p.get('出力先')),
        '共有相手': _multi(p.get('共有相手')),
        '引き渡しモード': _select(p.get('引き渡しモード')),
        '真の課題': _rich(p.get('真の課題', '')),
        'ナレッジ資産タグ': _multi(p.get('ナレッジ資産タグ')),
        '実行環境': _select(p.get('実行環境')),
        'Markdown正本URL': _url(p.get('Markdown正本URL')),
    }


# ===== Section renderers (§0〜§11) =====

def _render_meta(ctx, blocks):
    m = ctx.get('meta', {})
    blocks.append(heading(1, f"{m.get('skill_name_hint', 'skill')} — ヒアリング正本（完全版）"))
    meta_lines = [
        f"生成日時: {m.get('generated_at', '')}",
        f"パターン: {m.get('pattern_code')}（{m.get('pattern_label', '')}）／Workflow: {m.get('workflow_pattern_code', '')}（{m.get('workflow_pattern_label', '')}）",
        f"深度: {m.get('depth')}（{m.get('depth_minutes', '?')}分相当）",
        f"語彙: {m.get('vocabulary_tier')}",
        f"状態: {m.get('status')}",
        f"value_realized_score: {m.get('value_realized_score')} / 100",
    ]
    for l in meta_lines:
        blocks.append(bullet(l))
    blocks.append(divider())


def _render_executive(ctx, blocks):
    blocks.append(heading(2, '0. エグゼクティブサマリ'))
    es = ctx.get('executive_summary', {})
    blocks.append(callout(f"真の目的: 「{es.get('true_purpose', '')}」", '🎯'))
    if es.get('purpose_narrative'):
        blocks.append(paragraph(es['purpose_narrative']))
    if es.get('design_choices'):
        blocks.append(paragraph(f"設計選択: {es['design_choices']}"))
    if es.get('handoff_mode'):
        blocks.append(paragraph(f"引き渡しモード: {es['handoff_mode']}（{es.get('handoff_note', '')}）"))
    blocks.append(divider())


def _render_assumption(ctx, blocks):
    a = ctx.get('assumption', {})
    blocks.append(heading(2, '1. Phase: assumption-challenger（前提逆転）'))
    blocks.append(heading(3, '1.1 表層リクエスト'))
    blocks.append(quote(a.get('surface_request', '')))
    blocks.append(heading(3, '1.2 深層候補'))
    for c in a.get('candidates', []):
        prefix = '✅ ' if c.get('adopted') else ''
        blocks.append(bullet(f"{prefix}{c.get('id')}: {c.get('label')}"))
    blocks.append(heading(3, '1.3 確定した深層課題'))
    blocks.append(paragraph(a.get('deep_problem', '')))
    if a.get('time_freed_intent'):
        blocks.append(heading(3, '1.4 浮いた時間の使い道'))
        blocks.append(paragraph(a['time_freed_intent']))
    if a.get('blind_spots'):
        blocks.append(heading(3, '1.5 ブラインドスポット'))
        for bs in a['blind_spots']:
            blocks.append(bullet(bs))
    blocks.append(divider())


def _render_profile(ctx, blocks):
    p = ctx.get('profile', {})
    blocks.append(heading(2, '2. Phase: user-profiler（ユーザー像）'))
    for d in p.get('dimensions', []):
        blocks.append(bullet(f"{d.get('name')}: {d.get('value')} (confidence={d.get('confidence')}) — {d.get('evidence', '')}"))
    blocks.append(paragraph(f"vocabulary_tier: {p.get('vocabulary_tier', '')}"))
    if p.get('implications'):
        blocks.append(heading(3, '次フェーズへの含意'))
        for imp in p['implications']:
            blocks.append(bullet(imp))
    blocks.append(divider())


def _render_purpose(ctx, blocks):
    pu = ctx.get('purpose', {})
    blocks.append(heading(2, '3. Phase: purpose-excavator（真の目的の発掘）'))
    blocks.append(bullet(f"techniques_used: {pu.get('techniques_used_str', '')}"))
    blocks.append(bullet(f"rounds: {pu.get('rounds')} / agreement_loop_detected: {pu.get('agreement_loop_detected')}"))
    blocks.append(callout(f"真の目的: 「{pu.get('true_purpose', '')}」", '🎯'))
    if pu.get('underlying_motivation'):
        blocks.append(paragraph(f"underlying_motivation: {pu['underlying_motivation']}"))
    if pu.get('differentiation_title'):
        blocks.append(heading(3, pu['differentiation_title']))
        blocks.append(paragraph(pu.get('differentiation_text', '')))
    if pu.get('magic_wand_text'):
        blocks.append(heading(3, '浮いた時間の使い道 (Magic Wand)'))
        blocks.append(paragraph(pu['magic_wand_text']))
    if pu.get('output_priority'):
        blocks.append(heading(3, 'アウトプット優先順位'))
        for o in pu['output_priority']:
            text = f"**{o.get('text')}**" if o.get('is_top') else o.get('text', '')
            blocks.append(numbered(text))
    blocks.append(divider())


def _render_options(ctx, blocks):
    o = ctx.get('options', {})
    blocks.append(heading(2, '4. Phase: option-presenter（選択肢提示と確定）'))
    for i, g in enumerate(o.get('groups', []), 1):
        blocks.append(heading(3, f"4.{i} {g.get('title', '')}"))
        for opt in g.get('options', []):
            prefix = '✅ ' if opt.get('adopted') else ''
            blocks.append(bullet(f"{prefix}{opt.get('id')} {opt.get('label')} — Pro: {opt.get('pro')} / Con: {opt.get('con')} / Weight: {opt.get('weight')}"))
    c = o.get('connectors', {})
    blocks.append(heading(3, 'コネクタ選択'))
    for k in ('input_sources', 'knowledge_assets', 'outputs', 'scheduler'):
        blocks.append(bullet(f"{k}: {c.get(k, '')}"))
    blocks.append(divider())


def _render_figures(ctx, blocks):
    f = ctx.get('figures', {})
    blocks.append(heading(2, '5. Phase: visualizer（図解5枚）'))
    for i, fig in enumerate(f.get('entries', []), 1):
        blocks.append(heading(3, f"図{i}. {fig.get('title', '')}"))
        blocks.append(paragraph(f"言いたい一言: {fig.get('one_liner', '')}"))
        if fig.get('mermaid'):
            blocks.append(code(fig['mermaid'], 'mermaid'))
        if fig.get('legend'):
            blocks.append(paragraph(f"凡例: {fig['legend']}"))
    blocks.append(divider())


def _render_five_axes(ctx, blocks):
    fa = ctx.get('five_axes', {})
    blocks.append(heading(2, '6. 5軸サマリ（最終確定版）'))
    for row in fa.get('rows', []):
        must = '（MUST）' if row.get('must') else ''
        blocks.append(bullet(f"{row.get('name')}{must}: {row.get('content', '')} [{row.get('depth')}]"))
    pl = fa.get('pipeline', {})
    blocks.append(heading(3, 'ナレッジ抽出パイプライン'))
    for k in ('ingest', 'analysis', 'storage', 'retrieval', 'update'):
        blocks.append(bullet(f"{k}: {pl.get(k, '')}"))
    blocks.append(divider())


def _render_design_decisions(ctx, blocks):
    dd = ctx.get('design_decisions', {})
    blocks.append(heading(2, '7. 設計選択サマリ'))
    for r in dd.get('rows', []):
        blocks.append(bullet(f"{r.get('axis')}: {r.get('adopted')} — {r.get('reason', '')}"))
    if dd.get('output_priority'):
        blocks.append(heading(3, 'アウトプット優先順位'))
        for o in dd['output_priority']:
            blocks.append(numbered(o))
    blocks.append(divider())


def _render_open_questions(ctx, blocks):
    oq = ctx.get('open_questions', [])
    blocks.append(heading(2, '8. 未解決事項'))
    for q in oq:
        mark = '○' if q.get('blocking') else '×'
        blocks.append(bullet(f"[{mark}] {q.get('question')} → {q.get('defer_to', '')}"))
    blocks.append(divider())


def _render_handoff(ctx, blocks):
    h = ctx.get('handoff', {})
    blocks.append(heading(2, '9. skill-creator への申し送り'))
    blocks.append(bullet(f"recommended_mode: {h.get('recommended_mode')}"))
    blocks.append(bullet(f"skip_to_phase: {h.get('skip_to_phase')}"))
    blocks.append(bullet(f"理由: {h.get('reason', '')}"))
    if h.get('starting_note'):
        blocks.append(paragraph(h['starting_note']))
    blocks.append(divider())


def _render_self_update(ctx, blocks):
    su = ctx.get('self_update', {})
    blocks.append(heading(2, '10. Phase: self-updater（自己進化結果）'))
    for k in ('candidates_detected', 'candidates_applied', 'skipped_duplicates', 'value_realized_score'):
        blocks.append(bullet(f"{k}: {su.get(k)}"))
    if su.get('score_rationale'):
        blocks.append(paragraph(f"スコア根拠: {su['score_rationale']}"))
    for d in su.get('deductions', []):
        blocks.append(bullet(f"控除 -{d.get('points')}: {d.get('reason')}"))
    blocks.append(divider())


def _render_artifacts(ctx, blocks):
    a = ctx.get('artifacts', {})
    blocks.append(heading(2, f"11. 出力ファイル一覧（{a.get('base_path', '')}）"))
    for f in a.get('files', []):
        blocks.append(bullet(f"`{f.get('path')}` — {f.get('description', '')}"))


# ===== Top-level =====

def render(ctx):
    # render-intake-final.py と同じく intake-final-schema.json で context を厳密検証する。
    # 検証失敗は jsonschema.ValidationError として上位に伝播。
    jsonschema.validate(ctx, _load_schema())
    blocks = []
    _render_meta(ctx, blocks)
    _render_executive(ctx, blocks)
    _render_assumption(ctx, blocks)
    _render_profile(ctx, blocks)
    _render_purpose(ctx, blocks)
    _render_options(ctx, blocks)
    _render_figures(ctx, blocks)
    _render_five_axes(ctx, blocks)
    _render_design_decisions(ctx, blocks)
    _render_open_questions(ctx, blocks)
    _render_handoff(ctx, blocks)
    _render_self_update(ctx, blocks)
    _render_artifacts(ctx, blocks)
    return {'properties': project_db_properties(ctx), 'children': blocks}


def main(argv):
    if len(argv) < 2:
        sys.stderr.write('usage: render_notion_page.py <intake-final-context.json> [out.json]\n')
        return 2
    ctx_file = argv[1]
    out_file = argv[2] if len(argv) > 2 else None
    try:
        with open(ctx_file, 'r', encoding='utf-8') as f:
            ctx = json.load(f)
    except Exception as e:
        sys.stderr.write(f'input error: {e}\n')
        return 2
    out = render(ctx)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if out_file:
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(text + '\n')
    else:
        sys.stdout.write(text + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
