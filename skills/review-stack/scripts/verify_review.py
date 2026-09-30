#!/usr/bin/env python3
"""Read-only validation of the canonical review result before a checklist pass."""
import argparse
import json
import re
from pathlib import Path


def validate(data, commit):
    if not isinstance(data, dict) or data.get('commit') != commit or not re.fullmatch(r'[0-9a-f]{40,64}', commit):
        raise ValueError('review must name the exact current commit')
    if data.get('verdict') not in {'SHIP_IT', 'READY_TO_SHIP', 'FIX_THEN_SHIP', 'SHIP_WITH_CAVEATS'}:
        raise ValueError('review verdict does not permit a pass')
    if data.get('gate') not in {'PASS', 'SOFT_FAIL'}:
        raise ValueError('review gate failed or is missing')
    if not isinstance(data.get('findings'), list) or not isinstance(data.get('criteria'), list):
        raise ValueError('findings and criteria arrays are required')
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', type=Path)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    try:
        validate(json.loads(args.result.read_text()), args.commit)
    except (OSError, ValueError, TypeError) as exc:
        print(f'review proof: FAIL: {exc}')
        return 1
    print('review proof: pass')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
