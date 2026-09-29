#!/usr/bin/env python3
"""Verify that a plan approval record still matches the plan's exact bytes.

An approval covers the plan as it was when the person said yes. If the plan
file changed afterwards, the approval no longer covers it.

The record is a small text file with one "key: value" per line:
  plan: <path to the plan, relative to the current folder or absolute>
  sha256: <hex digest of the plan file at approval time>
  approved_by: <name>
  approved_at: <ISO 8601 date and time>
  words: "<the approver's exact words>"

Usage:
  plan_approval_check.py <approval record>

Exit 0 when every field is present and the hash matches, 1 when the record is
incomplete or the plan changed, 2 when the record or plan cannot be read.
This script only reads. Standard library only. Python 3.9 or newer.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

REQUIRED = ("plan", "sha256", "approved_by", "approved_at", "words")


def parse(text: str) -> dict:
    fields = {}
    for line in text.splitlines():
        m = re.match(r"^\s*([a-z_0-9]+)\s*:\s*(.*?)\s*$", line)
        if m and m.group(1) not in fields:
            fields[m.group(1)] = m.group(2)
    return fields


def check(record: Path) -> tuple[int, str]:
    try:
        fields = parse(record.read_text())
    except OSError as e:
        return 2, f"cannot read approval record: {e}"
    missing = [k for k in REQUIRED if not fields.get(k, "").strip('"').strip()]
    if missing:
        return 1, f"approval record lacks: {', '.join(missing)}"
    plan = Path(fields["plan"])
    try:
        actual = hashlib.sha256(plan.read_bytes()).hexdigest()
    except OSError as e:
        return 2, f"cannot read plan {plan}: {e}"
    expected = fields["sha256"].lower()
    if actual != expected:
        return 1, (
            f"plan changed since approval: {plan} is {actual[:12]}..., "
            f"approved {expected[:12]}... Write an amendment or get a new approval."
        )
    return (
        0,
        f"approval matches {plan} ({actual[:12]}...), approved by {fields['approved_by']}",
    )


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return 2
    code, message = check(Path(argv[0]))
    print(f"plan_approval_check: {message}")
    return code


if __name__ == "__main__":
    sys.exit(main())
