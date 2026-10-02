#!/usr/bin/env python3
"""Read-only validation of the canonical review result before a checklist pass."""
import argparse
import hashlib
import os
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "development-protocol" / "scripts"))
from devproto import load as load_work_record, TERMINAL


def validate(data, commit):
    if not isinstance(data, dict) or data.get('commit') != commit or not re.fullmatch(r'[0-9a-f]{40,64}', commit):
        raise ValueError('review must name the exact current commit')
    if data.get('verdict') not in {'SHIP_IT', 'READY_TO_SHIP', 'FIX_THEN_SHIP', 'SHIP_WITH_CAVEATS'}:
        raise ValueError('review verdict does not permit a pass')
    if data.get('gate') not in {'PASS', 'SOFT_FAIL'}:
        raise ValueError('review gate failed or is missing')
    if not isinstance(data.get('findings'), list) or not isinstance(data.get('criteria'), list):
        raise ValueError('findings and criteria arrays are required')
    if not data['criteria']:
        raise ValueError('at least one acceptance criterion is required')
    for finding in data['findings']:
        if not isinstance(finding, dict):
            raise ValueError('malformed finding')
        outcome = finding.get('outcome') or {}
        if not isinstance(outcome, dict):
            raise ValueError('structured finding outcome required')
        status = outcome.get('status')
        if status == 'fixed' and outcome.get('evidence'):
            continue
        if status == 'rejected' and outcome.get('reason'):
            continue
        if (status == 'deferred' and finding.get('required') is False
                and finding.get('severity') not in {'critical', 'high'}
                and outcome.get('owner') and outcome.get('reason') and outcome.get('accepted_by')):
            continue
        raise ValueError('unresolved required finding or incomplete outcome')
    for criterion in data['criteria']:
        if not isinstance(criterion, dict) or criterion.get('verdict') != 'PASS' or not criterion.get('evidence'):
            raise ValueError('acceptance criterion lacks passing evidence')


def candidate_snapshot(project):
    """Hash the complete nonignored candidate without modifying the user's Git index."""
    project = project.resolve()
    def git(*args):
        result = subprocess.run(['git', '-C', str(project), *args], capture_output=True)
        if result.returncode:
            raise ValueError('candidate Git state cannot be read')
        return result.stdout
    if Path(os.fsdecode(git('rev-parse', '--show-toplevel')).strip()).resolve() != project:
        raise ValueError('--project must name the repository root')
    head_entries = {}
    for entry in git('ls-tree', '-rz', 'HEAD').split(b'\0'):
        if entry:
            metadata, name = entry.split(b'\t', 1)
            head_entries[name] = metadata.split(b' ')[0]
    names = set(head_entries)
    names.update(git('ls-files', '-z', '-co', '--exclude-standard').split(b'\0'))
    digest = hashlib.sha256()
    index_modes = {}
    for entry in git('ls-files', '-sz').split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        if name == b'.devproto' or name.startswith(b'.devproto/'):
            continue
        index_modes[name] = metadata.split(b' ')[0]
        digest.update(b'index\0' + entry + b'\0')
    for name in sorted(names - {b''}):
        if name == b'.devproto' or name.startswith(b'.devproto/'):
            continue
        path = project / os.fsdecode(name)
        if index_modes.get(name) == b'160000':
            raise ValueError('candidate includes an unsupported indexed submodule')
        digest.update(name + b'\0')
        if path.is_symlink():
            kind, content = b'symlink', os.fsencode(os.readlink(path))
        elif not path.exists():
            kind, content = b'deleted', b''
        elif path.is_file():
            kind = b'executable' if path.stat().st_mode & 0o111 else b'file'
            content = path.read_bytes()
        elif path.is_dir() and head_entries.get(name) != b'160000' and index_modes.get(name) != b'160000':
            if (path / '.git').exists():
                raise ValueError('candidate includes an unsupported nested repository')
            kind, content = b'deleted', b''
        else:
            raise ValueError('candidate includes an unsupported directory or submodule')
        digest.update(kind + b'\0' + hashlib.sha256(content).digest())
    return digest.hexdigest()


def closed_work_record(path, identifier):
    try:
        record = load_work_record(path)
        rows = record.get('steps')
        return (record.get('work_id') == identifier and isinstance(rows, list) and bool(rows)
                and any(row.get('step_id') == 'closeout' and row.get('status') == 'passed' for row in rows)
                and all(row.get('status') in TERMINAL for row in rows))
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def has_open_baseline(project):
    store = project.resolve() / '.devproto'
    for record in store.glob('*.json'):
        if not closed_work_record(record, record.stem):
            return True
    for baseline in (store / 'evidence').glob('*-build-base.txt'):
        identifier = baseline.name.removesuffix('-build-base.txt')
        if not closed_work_record(store / f'{identifier}.json', identifier):
            return True
    return False


def validate_scope(data, project, work_id):
    if work_id is None:
        if data.get('work_id') or has_open_baseline(project):
            raise ValueError('a work review requires --work-id and its recorded baseline')
        return
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', work_id):
        raise ValueError('invalid work ID')
    baseline = project.resolve() / '.devproto' / 'evidence' / f'{work_id}-build-base.txt'
    fields = {}
    for line in baseline.read_text().splitlines():
        key, separator, value = line.partition(' ')
        if not separator or key not in {'base', 'work-id'} or key in fields or not value:
            raise ValueError('baseline requires exactly one base and work-id')
        fields[key] = value
    if set(fields) != {'base', 'work-id'} or fields['work-id'] != work_id:
        raise ValueError('baseline work ID does not match')
    base = fields['base']
    if not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', base):
        raise ValueError('baseline must name a full commit SHA')
    result = subprocess.run(['git', '-C', str(project.resolve()), 'cat-file', '-t', base],
                            capture_output=True, text=True)
    if result.returncode or result.stdout.strip() != 'commit':
        raise ValueError('recorded baseline commit cannot be verified')
    ancestor = subprocess.run(['git', '-C', str(project.resolve()), 'merge-base', '--is-ancestor', base, data['commit']], capture_output=True)
    if ancestor.returncode:
        raise ValueError('recorded baseline is not an ancestor; retain the scope gap')
    if data.get('base') != base or data.get('work_id') != work_id:
        raise ValueError('review must cover the recorded baseline and work ID')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', type=Path, nargs='?')
    parser.add_argument('--snapshot', action='store_true')
    parser.add_argument('--commit')
    parser.add_argument('--project', type=Path, default=Path.cwd())
    parser.add_argument('--work-id')
    args = parser.parse_args()
    if args.snapshot:
        if args.result or args.commit or args.work_id:
            parser.error('--snapshot accepts only --project')
        try:
            print(candidate_snapshot(args.project))
            return 0
        except (OSError, ValueError) as exc:
            print(f'review snapshot: FAIL: {exc}')
            return 1
    if not args.result or not args.commit:
        parser.error('result and --commit are required for review verification')
    try:
        data = json.loads(args.result.read_text())
        validate(data, args.commit)
        validate_scope(data, args.project, args.work_id)
        if data.get('candidate_sha256') != candidate_snapshot(args.project):
            raise ValueError('reviewed candidate snapshot changed or is missing')
    except (OSError, ValueError, TypeError) as exc:
        print(f'review proof: FAIL: {exc}')
        return 1
    print('review proof: pass')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
