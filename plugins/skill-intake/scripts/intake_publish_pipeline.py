#!/usr/bin/env python3
"""render → quality_gate → publish を単一 entry に統合する orchestrator。"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


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
    parser.add_argument('--md-url', dest='md_url')
    parser.add_argument('--json-url', dest='json_url')
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

    # Step 1: render
    render_script = SCRIPT_DIR / 'render_notion_page.py'
    if args.manifest:
        manifest_path = os.path.abspath(args.manifest)
        render_status = run('render', render_script, [intake_path, manifest_path, blocks_path])
    else:
        render_status = run('render', render_script, [intake_path], capture_stdout_to=blocks_path)
    if render_status != 0:
        sys.stderr.write(f'[pipeline] render failed (exit {render_status})\n')
        return render_status

    # Step 2: quality_gate
    gate_argv = ['--intake', intake_path, '--blocks', blocks_path]
    if gate_path:
        gate_argv += ['--out', gate_path]
    gate_status = run('quality_gate', SCRIPT_DIR / 'quality_gate.py', gate_argv)
    if gate_status != 0:
        sys.stderr.write(f'[pipeline] quality_gate failed (exit {gate_status})\n')
        return gate_status

    # Step 3: publish
    pub_argv = ['--intake', intake_path, '--blocks', blocks_path]
    if args.database_id:
        pub_argv += ['--database-id', args.database_id]
    if args.md_url:
        pub_argv += ['--md-url', args.md_url]
    if args.json_url:
        pub_argv += ['--json-url', args.json_url]
    if args.dry_run:
        pub_argv.append('--dry-run')
    pub_status = run('publish', SCRIPT_DIR / 'publish_notion_page.py', pub_argv)
    if pub_status != 0:
        sys.stderr.write(f'[pipeline] publish failed (exit {pub_status})\n')
        return pub_status

    sys.stderr.write('[pipeline] success\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
