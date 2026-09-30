#!/usr/bin/env python3
"""Read-only checks for a design report or its explicitly requested asset slots."""
import argparse
import os
import re
from pathlib import Path

DIMENSIONS = (
    'source-to-build trace', 'code and build', 'configuration and service contracts',
    'data', 'primary journey and recovery',
    'visual quality, accessibility, performance, contrast and types',
)


def verify_report(project: Path, report: Path, non_runtime=False):
    text = report.read_text()
    section = re.search(r'^## Verify report\s*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    if not section:
        raise ValueError('missing Verify report section')
    dimensions = {}
    for line in section.group(1).splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'-\s+(.+?):\s*(pass|fail|unverified|n/a)\s+-\s+(.+)', line, re.I)
        if not match:
            raise ValueError('malformed verification dimension')
        label, status, evidence = match.groups()
        label = ' '.join(label.lower().split())
        if label in dimensions:
            raise ValueError('duplicate verification dimension')
        dimensions[label] = status.lower()
        if status.lower() in ('fail', 'unverified'):
            raise ValueError(f'unproven dimension: {label}')
    required = set(DIMENSIONS)
    if (project / 'DESIGN.md').exists():
        required.add('design.md lint')
    if required - dimensions.keys():
        raise ValueError('missing dimensions: ' + ', '.join(sorted(required - dimensions.keys())))
    always_pass = {'source-to-build trace', 'code and build'}
    if 'design.md lint' in required:
        always_pass.add('design.md lint')
    if not non_runtime:
        always_pass.update(('primary journey and recovery', DIMENSIONS[-1]))
    if any(dimensions[key] != 'pass' for key in always_pass):
        raise ValueError('required dimension cannot be n/a')
    if not non_runtime:
        for width in (390, 768, 1440):
            path = report.parent / f'design-{width}.png'
            if not path.is_file() or not path.stat().st_size:
                raise ValueError(f'missing screenshot: {width}')


def verify_assets(project: Path, slots: list):
    manifest = project / 'ASSETS.md'
    text = manifest.read_text()  # missing/unreadable manifests must fail
    if not slots:
        raise ValueError('expected asset slots are required')
    entries = {}
    for line in text.splitlines():
        if 'slot:' not in line:
            continue
        match = re.match(r'^- slot: (\S+) file: (\S+)(?:\s|$)', line)
        if not match:
            raise ValueError('malformed asset manifest entry')
        slot, name = match.groups()
        if slot in entries:
            raise ValueError('duplicate asset slot')
        entries[slot] = name
    if not entries or set(slots) - entries.keys():
        raise ValueError('missing expected asset slots')
    kit = (project / 'public/kit').resolve()
    listed = set()
    for name in entries.values():
        file = (project / 'public' / name).resolve()
        if kit not in file.parents or not file.is_file() or not file.stat().st_size:
            raise ValueError('missing, empty or out-of-kit asset')
        listed.add(file)
    actual = {p.resolve() for p in kit.rglob('*') if p.is_file() and not p.name.endswith('.prompt.json')}
    if actual != listed:
        raise ValueError('unlisted kit asset')
    source = []
    for folder, dirs, files in os.walk(project):
        dirs[:] = [d for d in dirs if d not in {'node_modules', 'public', '.git', '.next', 'dist', '.devproto'}]
        for name in files:
            if name == 'ASSETS.md':
                continue
            path = Path(folder) / name
            try:
                source.append(path.read_text())
            except UnicodeError:
                continue
    for file in listed:
        if not any(file.name in body for body in source):
            raise ValueError(f'unused kit asset: {file.name}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path('.'))
    sub = parser.add_subparsers(dest='command', required=True)
    report = sub.add_parser('report')
    report.add_argument('path', type=Path)
    report.add_argument('--non-runtime', action='store_true')
    assets = sub.add_parser('assets')
    assets.add_argument('--slots', nargs='+', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'report':
            verify_report(args.project.resolve(), args.path.resolve(), args.non_runtime)
        else:
            verify_assets(args.project.resolve(), args.slots)
    except (OSError, ValueError) as exc:
        print(f'{args.command} check: FAIL: {exc}')
        return 1
    print(f'{args.command} check: pass')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
