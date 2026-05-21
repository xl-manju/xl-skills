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


def truncate(s, n):
    s = str(s or '')
    return s if len(s) <= n else s[: max(0, n - 1)] + '…'


def build_properties(intake, args):
    """7 プロパティのみ書き込む。残り 12 項目は本文 children 側 (build_extra_body_blocks) で扱う。"""
    axes = intake.get('five_axes') or intake.get('5_axes') or {}
    true_problem_short = truncate(axis_text(axes.get('true_problem')), MAX_TRUE_PROBLEM_LEN)
    tags = intake.get('knowledge_asset_tags')
    if not isinstance(tags, list):
        tags = []
    props = {
        '名前': {'title': rt(intake.get('skill_name_hint') or intake.get('skill_name') or 'untitled')},
        'ステータス': {'select': {'name': intake.get('status') or '下書き'}},
        'パターン': {'select': {'name': intake.get('pattern') or 'その他'}},
        '真の課題': {'rich_text': rt(true_problem_short)},
        'ナレッジ資産タグ': {'multi_select': [{'name': str(n)} for n in tags]},
    }
    if getattr(args, 'md_url', None):
        props['Markdown正本URL'] = {'url': args.md_url}
    # 作成日時 は created_time (Notion 自動)。書き込み不要。
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
    if isinstance(intake.get('handoff_to_creator'), bool):
        add_kv('Creator 引き渡し', 'yes' if intake['handoff_to_creator'] else 'no')
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
    if getattr(args, 'json_url', None):
        add_kv('JSON 副本 URL', args.json_url)

    if len(out) <= 1:
        return []
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--intake', required=False)
    parser.add_argument('--blocks', required=False)
    parser.add_argument('--database-id', dest='database_id')
    parser.add_argument('--md-url', dest='md_url')
    parser.add_argument('--json-url', dest='json_url')
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
    try:
        res = notion_fetch('/pages', method='POST', body=body)
        out = {'id': res.get('id'), 'url': res.get('url'), 'created_time': res.get('created_time')}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except NotionHttpError as e:
        print(f'[publish_notion_page] {e}', file=sys.stderr)
        return 44 if e.status == 401 else 1


if __name__ == '__main__':
    sys.exit(main())
