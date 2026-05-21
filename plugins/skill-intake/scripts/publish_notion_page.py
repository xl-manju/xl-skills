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


def build_properties(intake, args):
    axes = intake.get('five_axes') or intake.get('5_axes') or {}
    output_target_text = axis_text(axes.get('output_target')) or axis_text(axes.get('output_destination'))
    props = {
        '名前': {'title': rt(intake.get('skill_name_hint') or intake.get('skill_name') or 'untitled')},
        'ステータス': {'select': {'name': intake.get('status') or '下書き'}},
        'パターン': {'select': {'name': intake.get('pattern') or 'その他'}},
        '出力先': {'rich_text': rt(output_target_text)},
        '情報源': {'rich_text': rt(axis_text(axes.get('info_source')))},
        '共有相手': {'rich_text': rt(axis_text(axes.get('share_target')))},
        '真の課題': {'rich_text': rt(axis_text(axes.get('true_problem')))},
        'ナレッジ資産': {'rich_text': rt(axis_text(axes.get('knowledge_assets')))},
    }
    up = intake.get('user_profile')
    if up:
        text = up if isinstance(up, str) else json.dumps(up, ensure_ascii=False)
        props['ユーザープロファイル'] = {'rich_text': rt(text)}
    oq = intake.get('open_questions')
    if isinstance(oq, list) and len(oq) > 0:
        props['未解決事項'] = {'rich_text': rt('- ' + '\n- '.join(str(q) for q in oq))}
    integs = intake.get('integrations')
    if isinstance(integs, list) and len(integs) > 0:
        props['外部連携'] = {'multi_select': [{'name': str(n)} for n in integs]}
    if getattr(args, 'md_url', None):
        props['Markdown 正本'] = {'url': args.md_url}
    if getattr(args, 'json_url', None):
        props['JSON 副本'] = {'url': args.json_url}
    if isinstance(intake.get('handoff_to_creator'), bool):
        props['Creator 引き渡し'] = {'checkbox': intake['handoff_to_creator']}
    if isinstance(intake.get('viz_count'), (int, float)) and not isinstance(intake.get('viz_count'), bool):
        props['図解枚数'] = {'number': intake['viz_count']}
    if isinstance(intake.get('value_score'), (int, float)) and not isinstance(intake.get('value_score'), bool):
        props['価値実現スコア'] = {'number': intake['value_score']}
    return props


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
    database_id = args.database_id or os.environ.get('INTAKE_NOTION_DATABASE_ID') or schema_default
    if not database_id:
        print('INTAKE_NOTION_DATABASE_ID is required (env, --database-id, or schema database_id_default)', file=sys.stderr)
        return 2

    with open(args.intake, 'r', encoding='utf-8') as f:
        intake = json.load(f)
    body = {
        'parent': {'database_id': database_id},
        'properties': build_properties(intake, args),
        'children': block_children,
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
