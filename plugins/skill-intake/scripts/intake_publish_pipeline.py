#!/usr/bin/env python3
"""render → quality_gate → publish を単一 entry に統合する orchestrator。"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def _canonical_id(value):
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        import notion_config as _nc
        return _nc.canonical_notion_id(value) or ''
    except Exception:
        compact = ''.join(ch for ch in str(value or '').lower() if ch in '0123456789abcdef')
        return compact if len(compact) == 32 else ''


def _read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _write_repaired_result(result_path, page_id, page_url):
    payload = {
        'page_id': page_id,
        'url': page_url or '',
        'mode': 'update',
        'repaired_from_explicit_target': True,
        'published_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    }
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write('\n')


def _write_log(log_path, url_path, status, exit_code, stage, page_id='', url='', mode=''):
    try:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(url_path, 'w', encoding='utf-8') as f:
            f.write((url + '\n') if url else '')
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump({
                'status': status,
                'exit_code': exit_code,
                'stage': stage,
                'page_id': page_id,
                'url': url,
                'mode': mode,
                'logged_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            }, f, ensure_ascii=False, indent=2)
            f.write('\n')
    except Exception as e:
        sys.stderr.write(f'[pipeline] notion-url/log write error: {e}\n')


def run(label, script, args, capture_stdout_to=None):
    sys.stderr.write(f'[pipeline] {label}: python3 {script.name} {" ".join(args)}\n')
    cmd = [sys.executable, str(script), *args]
    if capture_stdout_to:
        r = subprocess.run(cmd, stdout=subprocess.PIPE)
        if r.returncode == 0:
            try:
                with open(capture_stdout_to, 'wb') as f:
                    f.write(r.stdout)
            except Exception as e:
                sys.stderr.write(f'[pipeline] write blocks error: {e}\n')
                return 2
        else:
            sys.stderr.buffer.write(r.stdout)
        return r.returncode
    r = subprocess.run(cmd)
    return r.returncode if r.returncode is not None else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--intake', required=False)
    parser.add_argument('--manifest')
    parser.add_argument('--blocks-out', dest='blocks_out')
    parser.add_argument('--gate-out', dest='gate_out')
    parser.add_argument('--database-id', dest='database_id')
    parser.add_argument('--revise', dest='revise', action='store_true',
                        help='既存ページの PATCH 更新を強制 (create 禁止。--page-id/--page-url 必須)')
    parser.add_argument('--page-id', dest='page_id',
                        help='更新対象の Notion ページ ID を明示指定 (指定ページへの確実な出力)')
    parser.add_argument('--page-url', dest='page_url',
                        help='更新対象の Notion ページ URL (page_id を自動抽出)')
    parser.add_argument('--allow-create', dest='allow_create', action='store_true',
                        help='明示された初回作成だけ許可する。既定は create 禁止')
    parser.add_argument('--dry-run', dest='dry_run', action='store_true')
    args = parser.parse_args()

    if not args.intake:
        sys.stderr.write('--intake is required\n')
        return 2
    intake_path = os.path.abspath(args.intake)
    if not os.path.exists(intake_path):
        sys.stderr.write(f'intake not found: {intake_path}\n')
        return 2

    out_dir = os.path.dirname(intake_path)
    blocks_path = os.path.abspath(args.blocks_out or os.path.join(out_dir, 'notion-blocks.json'))
    gate_path = os.path.abspath(args.gate_out) if args.gate_out else None
    # publish 結果の永続先 (page_id idempotency-key)。gate の page_id 一貫性検査でも参照するため前倒し定義。
    result_path = os.path.join(out_dir, 'notion-publish-result.json')
    url_path = os.path.join(out_dir, 'notion-url.txt')
    log_path = os.path.join(out_dir, 'notion-log.json')

    # revise 時の出力先 page_id を解決 (明示 --page-id 最優先)。gate の page_id 一貫性検査の期待値に使う。
    # publish と同一の抽出関数を再利用し、解決結果が publish 側と完全一致することを保証する。
    sys.path.insert(0, str(SCRIPT_DIR))
    from publish_notion_page import _extract_page_id_from_url
    revise_page_id = None
    if args.page_id:
        revise_page_id = _extract_page_id_from_url(args.page_id)
    elif args.page_url:
        revise_page_id = _extract_page_id_from_url(args.page_url)
    if not args.revise and not revise_page_id and not args.allow_create:
        sys.stderr.write(
            'target page is required. create fallback is disabled by default '
            '(pass --page-id/--page-url with --revise, or explicit --allow-create for first-time create).\n'
        )
        _write_log(log_path, url_path, 'failed', 51, 'target_resolution')
        return 51
    if args.revise and not revise_page_id and not os.path.exists(result_path):
        sys.stderr.write('--revise 指定だが page_id を解決できない '
                         '(--page-id / --page-url / 既存 notion-publish-result.json のいずれも無し)。'
                         'create を禁止し停止します。\n')
        _write_log(log_path, url_path, 'failed', 51, 'target_resolution')
        return 51
    if args.revise and revise_page_id and os.path.exists(result_path):
        try:
            current_result = _read_json(result_path)
            current_page_id = current_result.get('page_id') or current_result.get('id')
            if current_page_id and _canonical_id(current_page_id) != _canonical_id(revise_page_id):
                sys.stderr.write(
                    f'notion-publish-result.json page_id mismatch '
                    f'(current={current_page_id}, requested={revise_page_id}). '
                    '別ページ化を防ぐため停止します。\n'
                )
                _write_log(log_path, url_path, 'failed', 51, 'target_mismatch',
                           page_id=current_page_id, url=current_result.get('url') or '')
                return 51
        except Exception as e:
            # 明示 page_id/page_url がある場合は、それを正として破損 result を復旧する。
            # これにより「破損 result があるため指定ページ更新もできない」状態を解消する。
            sys.stderr.write(
                f'[pipeline] repairing unreadable notion-publish-result.json '
                f'from explicit target ({e})\n'
            )
            try:
                _write_repaired_result(result_path, revise_page_id, args.page_url or '')
            except Exception as write_error:
                sys.stderr.write(f'[pipeline] result repair failed: {write_error}\n')
                _write_log(log_path, url_path, 'failed', 2, 'result_repair')
                return 2

    if args.manifest:
        manifest_path = os.path.abspath(args.manifest)
        if not os.path.exists(manifest_path):
            sys.stderr.write(f'manifest not found: {manifest_path}\n')
            _write_log(log_path, url_path, 'failed', 2, 'manifest_missing')
            return 2
        assets_status = run('verify_assets', SCRIPT_DIR / 'verify_notion_assets.py', [manifest_path])
        if assets_status != 0:
            sys.stderr.write(f'[pipeline] verify_assets failed (exit {assets_status})\n')
            _write_log(log_path, url_path, 'failed', assets_status, 'verify_assets')
            return assets_status

    # Step 1: render
    # render の出力先は常に --out (= blocks_path)。manifest は参考入力であり、
    # blocks で上書き破壊しない (確定バグ: 旧コードは位置引数3つを渡し manifest を破壊していた)。
    render_script = SCRIPT_DIR / 'render_notion_page.py'
    render_argv = ['--ctx', intake_path, '--out', blocks_path]
    if args.manifest:
        render_argv += ['--manifest', os.path.abspath(args.manifest)]
    render_status = run('render', render_script, render_argv)
    if render_status != 0:
        sys.stderr.write(f'[pipeline] render failed (exit {render_status})\n')
        _write_log(log_path, url_path, 'failed', render_status, 'render')
        return render_status

    # Step 1.5: fidelity guard
    # Notion へ mutation する前に、指定フォーマットとの粒度差分を必須検査する。
    fidelity_script = (
        SCRIPT_DIR.parent / 'skills' / 'assign-notion-fidelity-evaluator'
        / 'scripts' / 'validate-notion-fidelity.py'
    )
    fidelity_status = run('fidelity_guard', fidelity_script, [intake_path, '--out-dir', out_dir])
    if fidelity_status != 0:
        sys.stderr.write(f'[pipeline] fidelity_guard failed (exit {fidelity_status})\n')
        _write_log(log_path, url_path, 'failed', 2, 'fidelity_guard')
        return 2

    # Step 2: quality_gate
    # --database-id を gate にも渡し、指定 DB と解決 DB の一致を publish 前に検査する
    # (db_match。渡さないと check_db_match が skip され別DB出力を検出できない)。
    gate_argv = ['--intake', intake_path, '--blocks', blocks_path]
    if args.database_id:
        gate_argv += ['--database-id', args.database_id]
    # page_id 一貫性検査 (再公開で別ページに化けない=orphan 防止) を実効化。
    # result ファイルが既存の場合のみ、その page_id が期待値 (revise_page_id) と一致するか検証する。
    # result 不在は「矛盾そのものが無い」状態であり、明示 page_id を信頼して update に進む
    # (正当な初回 revise をブロックしない。fail-closed の厳格さは矛盾検出に限定)。
    if args.revise and revise_page_id and os.path.exists(result_path):
        gate_argv += ['--result-path', result_path, '--prev-page-id', revise_page_id]
    if gate_path:
        gate_argv += ['--out', gate_path]
    gate_status = run('quality_gate', SCRIPT_DIR / 'quality_gate.py', gate_argv)
    if gate_status != 0:
        sys.stderr.write(f'[pipeline] quality_gate failed (exit {gate_status})\n')
        _write_log(log_path, url_path, 'failed', gate_status, 'quality_gate')
        return gate_status

    # Step 3: publish (stdout に publish 結果 JSON を出すので捕捉して result ファイルへ書き戻す)
    pub_argv = ['--intake', intake_path, '--blocks', blocks_path,
                '--result-out', result_path]
    if args.database_id:
        pub_argv += ['--database-id', args.database_id]
    # 出力先 page_id を publish へ伝搬 (指定ページへの確実な出力)。
    if args.page_id:
        pub_argv += ['--page-id', args.page_id]
    if args.page_url:
        pub_argv += ['--page-url', args.page_url]
    if args.revise:
        pub_argv.append('--require-update')  # create 禁止 (同一ページ更新の保証)
    elif args.allow_create:
        pub_argv.append('--allow-create')
    if args.dry_run:
        pub_argv.append('--dry-run')
    cmd = [sys.executable, str(SCRIPT_DIR / 'publish_notion_page.py'), *pub_argv]
    sys.stderr.write(f'[pipeline] publish: python3 publish_notion_page.py {" ".join(pub_argv)}\n')
    proc = subprocess.run(cmd, stdout=subprocess.PIPE)
    pub_status = proc.returncode if proc.returncode is not None else 1
    stdout_text = proc.stdout.decode('utf-8', errors='replace') if proc.stdout else ''
    sys.stderr.write(stdout_text)

    # silent-fail 禁止: 成否に関わらず notion-log.json / notion-url.txt を書く
    # (republish-contract.md 不変条件 4 / SKILL.md 完了チェック #2,#3)。
    result = {}
    try:
        result = json.loads(stdout_text) if stdout_text.strip() else {}
    except Exception:
        result = {}
    page_url = result.get('url') or ''
    status = 'published' if (pub_status == 0 and page_url) else 'failed'
    if not args.dry_run:
        _write_log(log_path, url_path, status, pub_status, 'publish',
                   page_id=result.get('id') or result.get('page_id') or '',
                   url=page_url,
                   mode=result.get('mode') or '')

    if pub_status != 0:
        sys.stderr.write(f'[pipeline] publish failed (exit {pub_status})\n')
        return pub_status

    sys.stderr.write('[pipeline] success\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
