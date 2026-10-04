#!/usr/bin/env python3
"""check_version_bump.py: a change users receive must carry a new plugin version.

Plugin installs that sync automatically only fetch a new copy when `version` in
`.claude-plugin/plugin.json` changes. So when a branch changes anything under `skills/` or
`.claude-plugin/` compared with its base, its version must differ from the base's.

    python3 scripts/check_version_bump.py --base origin/main [--repo <folder>]

Exit 0 no shipped change, or the version changed. Exit 1 a shipped change with the base's
version. Exit 2 could not measure (unknown base ref, unreadable manifest, git failed).

Python 3.9+, standard library only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

MANIFEST = ".claude-plugin/plugin.json"
SHIPPED = ("skills/", ".claude-plugin/")


class Unmeasurable(Exception):
    pass


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise Unmeasurable(f"git {' '.join(args)}: {r.stderr.strip() or r.returncode}")
    return r.stdout


def version_at(repo: Path, ref: str | None) -> str:
    """The plugin version at a commit, or the working tree when ref is None."""
    try:
        text = (
            (repo / MANIFEST).read_text(encoding="utf-8")
            if ref is None
            else git(repo, "show", f"{ref}:{MANIFEST}")
        )
        version = json.loads(text)["version"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        where = "working tree" if ref is None else ref
        raise Unmeasurable(f"{MANIFEST} at {where} has no readable version: {exc}")
    if not isinstance(version, str) or not version.strip():
        raise Unmeasurable(f"{MANIFEST} version is not a non-empty string: {version!r}")
    return version.strip()


def shipped_changes(repo: Path, base: str) -> list[str]:
    """Files under the shipped paths that differ between the merge base and the working
    tree, committed or not."""
    merge_base = git(repo, "merge-base", base, "HEAD").strip()
    out = git(repo, "diff", "--name-only", merge_base, "--", *SHIPPED)
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "--", *SHIPPED)
    return sorted({p for p in (out + untracked).splitlines() if p})


def check(repo: Path, base: str) -> tuple[int, str]:
    try:
        git(repo, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
        changed = shipped_changes(repo, base)
        if not changed:
            return (
                0,
                f"no change under {', '.join(SHIPPED)} since {base}; no bump needed",
            )
        old, new = version_at(repo, base), version_at(repo, None)
    except Unmeasurable as exc:
        return 2, f"COULD NOT MEASURE: {exc}"
    if new == old:
        listing = "\n".join(f"  {p}" for p in changed)
        return 1, (
            f"FAIL: {len(changed)} shipped file(s) changed since {base} but "
            f"{MANIFEST} is still {old}. Bump the version so installed copies update, "
            f"and add a CHANGELOG.md entry.\n{listing}"
        )
    return 0, f"OK: version {old} -> {new} covers {len(changed)} shipped file(s)."


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", required=True, help="base branch ref, e.g. origin/main")
    ap.add_argument("--repo", default=".", help="repository folder (default: current)")
    args = ap.parse_args(argv)
    code, message = check(Path(args.repo).resolve(), args.base)
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
