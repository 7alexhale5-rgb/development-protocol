#!/usr/bin/env python3
"""Fail if any shipped file carries private paths, names, secrets or house-only tooling.

Usage: python3 tests/scan_private.py [path ...]   (default: the whole repo)
Exit 0 clean, 1 leaks found. Patterns live in tests/generic-patterns.txt, plus
any file named by the DEVPROTO_PRIVATE_PATTERNS env var (kept outside the repo).
"""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = ROOT / "tests" / "generic-patterns.txt"
# Maintainer-only list of private names, never committed.
PRIVATE = os.environ.get("DEVPROTO_PRIVATE_PATTERNS", "")
SKIP_DIRS = {".git", "__pycache__"}
SKIP_FILES = {PATTERNS, Path(__file__).resolve(), ROOT / "LICENSE"}
# Author credit is allowed only in these exact files, by relative path (not by
# basename), so a same-named file elsewhere in the repo does not get a free pass.
CREDIT_PATHS = {
    ROOT / "README.md",
    ROOT / "docs" / "SETUP.md",
    ROOT / "docs" / "UPDATING.md",
    ROOT / "CHANGELOG.md",
}
CREDIT_DIR = ROOT / ".claude-plugin"
CREDIT_RE = re.compile(r"Alex Hale|7alexhale5-rgb|PrettyFly|prettyflyforai\.com", re.I)


def is_credit_file(f):
    if f in CREDIT_PATHS:
        return True
    return f.parent == CREDIT_DIR and f.suffix == ".json"


def load_patterns():
    pats = []
    sources = [PATTERNS] + ([Path(PRIVATE).expanduser()] if PRIVATE else [])
    lines = [l for src in sources for l in src.read_text().splitlines()]
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            pats.append(re.compile(line, re.I))
    return pats


def shippable():
    """Files git would publish (tracked plus untracked, minus ignored). None outside git."""
    r = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "-co", "--exclude-standard"],
        capture_output=True,
        text=True,
    )
    return (
        {(ROOT / l).resolve() for l in r.stdout.split("\0") if l}
        if r.returncode == 0
        else None
    )


def files(targets):
    ship = shippable()
    for f in _walk(targets):
        if ship is None or f in ship:
            yield f


def _walk(targets):
    for t in targets:
        p = Path(t).resolve()
        if p.is_file():
            yield p
            continue
        for f in p.rglob("*"):
            if f.is_file() and not SKIP_DIRS.intersection(f.relative_to(ROOT).parts):
                yield f


def scan(targets):
    pats, hits = load_patterns(), []
    for f in files(targets):
        if f in SKIP_FILES or f.suffix in {".pyc", ".png", ".pdf"}:
            continue
        text = f.read_text(errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            check = CREDIT_RE.sub("", line) if is_credit_file(f) else line
            for p in pats:
                m = p.search(check)
                if m:
                    hits.append(
                        f"{f.relative_to(ROOT)}:{n}: {m.group(0)!r}  [{p.pattern}]"
                    )
    return hits


if __name__ == "__main__":
    hits = scan(sys.argv[1:] or [ROOT])
    for h in hits:
        print(h)
    scope = "generic + private list" if PRIVATE else "generic list only"
    print(
        f"private-data scan ({scope}): {'clean' if not hits else f'{len(hits)} hit(s)'}"
    )
    sys.exit(1 if hits else 0)
