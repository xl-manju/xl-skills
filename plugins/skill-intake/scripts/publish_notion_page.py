#!/usr/bin/env python3
"""intake.json と blocks.json を入力に Notion DB へページを投稿する。"""

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
with open(SCRIPT_DIR / 'notion_limits.json', 'r', encoding='utf-8') as f:
    _LIMITS = json.load(f)
MAX_RT = _LIMITS['MAX_RT']


def rt(s):
    return [{'type': 'text', 'text': {'content': str(s or '')[:MAX_RT]}}]


def axis_text(v):
    if v is None:
        return ''
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and isinstance(v.get('answer'), str):
        return v['answer']
    return ''


MAX_TRUE_PROBLEM_LEN = 200
MAX_TITLE_JA_LEN = 30


def truncate(s, n):
    s = str(s or '')
    return s if len(s) <= n else s[: max(0, n - 1)] + '…'


def derive_ja_title(intake):
    """日本語タイトルを優先順位に従って導出。見つからなければ None。"""
    meta = intake.get('meta') or {}
    ndp = intake.get('notion_db_properties') or {}
    # 1) meta.skill_title_ja (新規正式フィールド)
    cand = meta.get('skill_title_ja')
    if cand and str(cand).strip():
        return str(cand).strip()[:MAX_TITLE_JA_LEN]
    # 2) notion_db_properties.名前 が既に日本語の場合
    name = ndp.get('名前')
    if name and isinstance(name, str) and any(ord(c) > 127 for c in name):
        return name.strip()[:MAX_TITLE_JA_LEN]
    # 3) top-level skill_title_ja
    cand = intake.get('skill_title_ja')
    if cand and str(cand).strip():
        return str(cand).strip()[:MAX_TITLE_JA_LEN]
    # 4) purpose.verb_object から自動生成 (末尾「する」「したい」「。」を削り 30 字)
    purpose = intake.get('purpose') or {}
    vo = purpose.get('verb_object') or purpose.get('true_purpose') or ''
    if vo:
        title = str(vo).strip().rstrip('。').rstrip('.')
        for suffix in ('したい', 'します', 'する'):
            if title.endswith(suffix):
                title = title[: -len(suffix)]
                break
        title = title.strip()
        if title:
            return title[:MAX_TITLE_JA_LEN]
    return None


def build_properties(intake, args):
    """実際の Notion DB スキーマに合わせたプロパティ送信。
    DB プロパティ (2026-05-23 実測):
      名前(title), ステータス(select), パターン(select), 真の課題(rich_text),
      ナレッジ資産(rich_text), 出力先(rich_text), 情報源(rich_text), 共有相手(rich_text),
      ユーザープロファイル(rich_text), 未解決事項(rich_text),
      外部連携(multi_select), 図解枚数(number), 価値実現スコア(number),
      スキル作成完了(checkbox),
      作成日時(created_time - 自動), 更新日時(last_edited_time - 自動), 担当者(people - 省略)
    """
    axes = intake.get('five_axes') or intake.get('5_axes') or {}
    true_problem_short = truncate(axis_text(axes.get('true_problem')), MAX_TRUE_PROBLEM_LEN)

    # meta / notion_db_properties からデータ取得
    meta = intake.get('meta', {})
    ndp = intake.get('notion_db_properties', {})
    # 日本語タイトル優先（一目で何のスキルか分かるように）。なければ英語スラッグへフォールバック。
    skill_name = (
        derive_ja_title(intake)
        or meta.get('skill_name_hint')
        or ndp.get('名前')
        or intake.get('skill_name_hint')
        or 'untitled'
    )
    status = ndp.get('ステータス') or intake.get('status') or '下書き'
    pattern_val = meta.get('pattern_code') or ndp.get('パターン') or intake.get('pattern') or 'A'

    # 5軸テキスト
    output_dest = axis_text(axes.get('output_target') or axes.get('output_destination'))
    info_source = axis_text(axes.get('info_source'))
    share_target = axis_text(axes.get('share_target'))

    # ナレッジ資産
    knowledge_assets = axis_text(axes.get('knowledge_assets'))

    # ユーザープロファイル
    up = intake.get('user_profile')
    up_text = up if isinstance(up, str) else (json.dumps(up, ensure_ascii=False) if up else '')

    # 未解決事項
    oq = intake.get('open_questions') or []
    oq_items = []
    for q in oq:
        if isinstance(q, dict):
            oq_items.append(q.get('question', str(q)))
        else:
            oq_items.append(str(q))
    oq_text = truncate('; '.join(oq_items), MAX_RT)

    # 図解枚数
    figs = intake.get('figures', {})
    viz_count = len(figs.get('entries', [])) if isinstance(figs, dict) else 0

    # 価値実現スコア
    score = meta.get('value_realized_score') or ndp.get('value_realized_score') or 0

    props = {
        '名前': {'title': rt(skill_name)},
        'ステータス': {'select': {'name': status}},
        'パターン': {'select': {'name': pattern_val}},
        '真の課題': {'rich_text': rt(true_problem_short)},
        'ナレッジ資産': {'rich_text': rt(truncate(knowledge_assets, MAX_RT))},
        '出力先': {'rich_text': rt(truncate(output_dest, MAX_RT))},
        '情報源': {'rich_text': rt(truncate(info_source, MAX_RT))},
        '共有相手': {'rich_text': rt(truncate(share_target, MAX_RT))},
        '図解枚数': {'number': viz_count} if viz_count > 0 else {'number': None},
        '価値実現スコア': {'number': int(score)} if score else {'number': None},
    }
    if up_text.strip():
        props['ユーザープロファイル'] = {'rich_text': rt(truncate(up_text, MAX_RT))}
    if oq_text.strip():
        props['未解決事項'] = {'rich_text': rt(oq_text)}
    # 作成日時/更新日時 は Notion 自動。担当者は people 型で省略。
    return props


def _rt_block(kind, text):
    return {'object': 'block', 'type': kind, kind: {'rich_text': rt(text)}}


def _heading2(text):
    return {'object': 'block', 'type': 'heading_2', 'heading_2': {'rich_text': rt(text)}}


def _toggle(label, child_texts):
    children = [_rt_block('paragraph', t) for t in child_texts if str(t or '').strip()]
    return {
        'object': 'block',
        'type': 'toggle',
        'toggle': {'rich_text': rt(label), 'children': children},
    }


def build_extra_body_blocks(intake, args):
    """DB から落とした 12 項目を本文 children として返す (publish 時に先頭付加)。"""
    axes = intake.get('five_axes') or intake.get('5_axes') or {}
    out = [_heading2('メタ情報 (DB プロパティ補完)')]

    def add_kv(label, value):
        s = value if isinstance(value, str) else (json.dumps(value, ensure_ascii=False) if value is not None else '')
        if s.strip():
            out.append(_rt_block('paragraph', f'{label}: {s}'))

    add_kv('出力先', axis_text(axes.get('output_target')) or axis_text(axes.get('output_destination')))
    add_kv('情報源', axis_text(axes.get('info_source')))
    add_kv('共有相手', axis_text(axes.get('share_target')))

    if isinstance(intake.get('viz_count'), (int, float)) and not isinstance(intake.get('viz_count'), bool):
        add_kv('図解枚数', str(intake['viz_count']))
    if isinstance(intake.get('value_score'), (int, float)) and not isinstance(intake.get('value_score'), bool):
        add_kv('価値実現スコア', str(intake['value_score']))
    owner = intake.get('owner')
    if owner:
        add_kv('担当者', owner if isinstance(owner, str) else json.dumps(owner, ensure_ascii=False))
    updated = intake.get('updated_at') or intake.get('updated')
    if updated:
        add_kv('更新日時', str(updated))

    up = intake.get('user_profile')
    if up:
        text = up if isinstance(up, str) else json.dumps(up, ensure_ascii=False)
        out.append(_toggle('ユーザープロファイル', [text]))
    oq = intake.get('open_questions')
    if isinstance(oq, list) and len(oq) > 0:
        out.append(_toggle('未解決事項', [f'- {q}' for q in oq]))
    integs = intake.get('integrations')
    if isinstance(integs, list) and len(integs) > 0:
        out.append(_toggle('外部連携', [', '.join(str(n) for n in integs)]))

    if len(out) <= 1:
        return []
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--intake', required=False)
    parser.add_argument('--blocks', required=False)
    parser.add_argument('--database-id', dest='database_id')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true')
    args = parser.parse_args()

    if not args.intake:
        print('--intake is required', file=sys.stderr)
        return 2
    if not args.blocks:
        print('--blocks is required (empty body publication is forbidden)', file=sys.stderr)
        return 2
    try:
        with open(args.blocks, 'r', encoding='utf-8') as f:
            blocks = json.load(f)
    except Exception as e:
        print(f'--blocks read error: {e}', file=sys.stderr)
        return 2
    block_children = blocks.get('children') if isinstance(blocks, dict) and 'children' in blocks else blocks
    if not isinstance(block_children, list) or len(block_children) == 0:
        print('--blocks must contain a non-empty children array', file=sys.stderr)
        return 2

    schema_path = SCRIPT_DIR.parent / 'skills' / 'run-skill-intake-aggregator' / 'references' / 'notion-db-schema.json'
    schema_default = None
    if schema_path.exists():
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema_default = json.load(f).get('database_id_default')
        except Exception:
            schema_default = None
    # 3段 fallback: --database-id > env > schema.database_id_default
    if args.database_id:
        database_id, db_id_source = args.database_id, 'arg'
    elif os.environ.get('INTAKE_NOTION_DATABASE_ID'):
        database_id, db_id_source = os.environ['INTAKE_NOTION_DATABASE_ID'], 'env'
    elif schema_default:
        database_id, db_id_source = schema_default, 'schema_default'
    else:
        database_id, db_id_source = None, None
    if not database_id:
        print('database_id is required (--database-id, INTAKE_NOTION_DATABASE_ID, or schema database_id_default)', file=sys.stderr)
        return 2
    try:
        eval_log_dir = Path('eval-log')
        eval_log_dir.mkdir(parents=True, exist_ok=True)
        with open(eval_log_dir / 'db-id-resolution.json', 'w', encoding='utf-8') as f:
            json.dump({'tool': 'publish_notion_page', 'source': db_id_source, 'database_id': database_id}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    with open(args.intake, 'r', encoding='utf-8') as f:
        intake = json.load(f)
    extra_blocks = build_extra_body_blocks(intake, args)
    body = {
        'parent': {'database_id': database_id},
        'properties': build_properties(intake, args),
        'children': extra_blocks + block_children,
    }
    if args.dry_run:
        out = {
            'dry_run': True,
            'parent': body['parent'],
            'prop_count': len(body['properties']),
            'children_count': len(body['children']),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    # 実投稿: notion_http を遅延 import (dry-run 時は keychain アクセス回避)
    from notion_http import notion_fetch, NotionHttpError
    MAX_FIRST = _LIMITS.get('MAX_BLOCKS_PER_APPEND', 100)
    all_children = body['children']
    # Notion API: POST /pages children limit = MAX_FIRST
    body['children'] = all_children[:MAX_FIRST]
    remaining = all_children[MAX_FIRST:]
    try:
        res = notion_fetch('/pages', method='POST', body=body)
        page_id = res.get('id')
        page_url = res.get('url')
        # Append remaining blocks in chunks
        chunk_size = MAX_FIRST
        for i in range(0, len(remaining), chunk_size):
            chunk = remaining[i:i + chunk_size]
            notion_fetch(f'/blocks/{page_id}/children', method='PATCH', body={'children': chunk})
        out = {'id': page_id, 'url': page_url, 'created_time': res.get('created_time')}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except NotionHttpError as e:
        print(f'[publish_notion_page] {e}', file=sys.stderr)
        return 44 if e.status == 401 else 1


if __name__ == '__main__':
    sys.exit(main())
