#!/usr/bin/env python3
"""icm_check.py: does a project pass the ICM walk test?

The rules live in the icm skill's SKILL.md (the only home of the rules).

    python3 icm_check.py <project-root>          # human report
    python3 icm_check.py <project-root> --json   # one JSON object

Exit 0 the layout holds, 1 something is broken, 2 could not measure (no such folder, or a
folder or guide could not be read). Warnings (a long map, a crowded folder) never change the
exit code.

It checks what a file can prove: the map exists and carries a routing table, every room
CONTEXT.md has the contract headings and fits in 80 lines, stage folders are named
NN_kebab-name and have a CONTEXT.md, and every local link in the map and the context files
resolves. Whether a room is the RIGHT room is a reading job, not this.

Python 3.9+, standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from urllib.parse import unquote

ROOM_HEADINGS = ("## Inputs", "## Process", "## Outputs", "## Human check")
MAX_CONTEXT_LINES = 80
MAP_WARN_LINES = 120  # "one screen" is about 60; warn well past it, never fail on it
CROWDED = 10
SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
    ".vercel",
    "coverage",
    "dist",
    "build",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "vendor",
    "test-results",
    ".turbo",
    ".cache",
    "_archive",
    "archive",
    "preserved",
    "worktrees",
}
STAGE_RE = re.compile(r"^\d{2}_[a-z0-9]+(?:[-_][a-z0-9]+)*$")
REF_DEF_RE = re.compile(r"^ {0,3}\[([^\]]+)\]:\s*(?:<([^>\n]+)>|(\S+))[^\n]*$", re.M)
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")


def is_project_boundary(path):
    """A folder with its own map or repository is a separate project."""
    names = set(os.listdir(path))
    return any(
        name in names and os.path.lexists(os.path.join(path, name))
        for name in ("CLAUDE.md", "AGENTS.md", ".git")
    )


def _walk(root: str):
    """Walk the project, never descending into a nested project (a folder with its own
    CLAUDE.md, AGENTS.md or .git is checked on its own) or a skipped folder. A folder that
    cannot be read raises, so the caller reports "could not measure", never a pass."""

    def fail(error):
        raise error

    for dirpath, dirnames, filenames in os.walk(root, onerror=fail):
        keep = []
        for d in sorted(dirnames):
            if (d in SKIP_DIRS or d.startswith(".")) and d != ".planning":
                continue
            full = os.path.join(dirpath, d)
            if os.path.islink(full):
                continue
            if is_project_boundary(full):
                continue
            keep.append(d)
        dirnames[:] = keep
        yield dirpath, dirnames, filenames


def _without_fences(text: str) -> str:
    """Drop fenced code blocks: an example inside a fence is not a link or a heading."""
    prose = []
    fence = None
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if (
                marker
                and marker[1][0] == fence[0]
                and len(marker[1]) >= len(fence)
                and not marker[2].strip()
            ):
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        prose.append(line)
    return "".join(prose)


def _inline_links(text):
    """Read balanced bare destinations and angle destinations; return the targets and the
    text with those links blanked out (reference links stay for the next pass)."""
    targets, spans = [], []
    for opening in re.finditer(r"\[[^\]\n]*\]\(\s*", text):
        i = opening.end()
        target, depth = [], 0
        angle = i < len(text) and text[i] == "<"
        if angle:
            i += 1
        while i < len(text):
            ch = text[i]
            if ch == "\\" and i + 1 < len(text):
                target.append(text[i + 1])
                i += 2
                continue
            if angle and ch == ">":
                i += 1
                break
            if not angle:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    if depth == 0:
                        break
                    depth -= 1
                elif ch.isspace() and depth == 0:
                    break
            if ch == "\n":
                break
            target.append(ch)
            i += 1
        closing = re.match(r'\s*(?:["\'][^"\']*["\']\s*)?\)', text[i:])
        if target and closing:
            targets.append("".join(target))
            spans.append((opening.start(), i + closing.end()))
    remaining = text
    for a, b in reversed(spans):
        remaining = remaining[:a] + " " * (b - a) + remaining[b:]
    return targets, remaining


def _normalize_label(label: str) -> str:
    return " ".join(label.split()).casefold()


def _local_links(text: str, routing=False) -> list[str]:
    """Every local link target in a guide: inline, angle, reference, shortcut and collapsed
    links, plus backtick routes to a room CONTEXT.md in a routing row when `routing`."""
    prose = _without_fences(text)
    routes = []
    for line in prose.splitlines():
        if routing and (re.match(r"^\s*[-*]\s", line) or TABLE_ROW_RE.match(line)):
            _, unlinked = _inline_links(line)
            routes.extend(re.findall(r"`([^`]+/CONTEXT\.md)`", unlinked))
            plain = re.sub(r"`[^`]*`", "", unlinked)
            routes.extend(re.findall(r"(?<![\w/])[~/\w.@-]+/CONTEXT\.md", plain))
    text = re.sub(r"(`+)(?!`)([\s\S]*?)(?<!`)\1(?!`)", "", prose)
    definitions = {
        _normalize_label(label): angle or bare
        for label, angle, bare in REF_DEF_RE.findall(text)
    }
    text = REF_DEF_RE.sub("", text)
    targets, remaining = _inline_links(text)
    ref_re = re.compile(r"\[([^\]]+)\]\[([^\]]*)\]")
    for label, ref in ref_re.findall(remaining):
        target = definitions.get(_normalize_label(ref or label))
        if target:
            targets.append(target)
    remaining = ref_re.sub("", remaining)
    for label in re.findall(r"\[([^\]]+)\]", remaining):
        target = definitions.get(_normalize_label(label))
        if target:
            targets.append(target)
    out = []
    for target in targets:
        if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith("#"):
            continue
        out.append(unquote(target.split("#", 1)[0]))
    return list(dict.fromkeys([t for t in out if t] + routes))


def _has_routing_table(text: str) -> bool:
    """Routes somewhere: a table with a data row naming a path, or a "Where to go" list
    that names a room CONTEXT.md."""
    text = _without_fences(text)
    if re.search(r"^\s*[-*]\s.*[\w./-]+/CONTEXT\.md", text, re.M):
        return True
    rows = [ln for ln in text.splitlines() if TABLE_ROW_RE.match(ln)]
    data = [r for r in rows if not re.match(r"^\s*\|[\s:|-]+\|\s*$", r)]
    return len(data) >= 2 and any(("/" in r or "CONTEXT.md" in r) for r in data[1:])


def exact_exists(path: str) -> bool:
    """Resolve the requested spelling, even on a case-insensitive filesystem."""
    current = os.path.sep
    for part in os.path.abspath(path).split(os.path.sep)[1:]:
        try:
            if part not in os.listdir(current):
                return False
        except OSError:
            return False
        current = os.path.join(current, part)
    return os.path.exists(current)


def resolve_link(base, target, origin_root=None, materialized_root=None):
    """Resolve a decoded link. With an origin root, interpret it in the original Git
    namespace and map it back into the materialized tree, without changing the text."""
    target = os.path.expanduser(target)
    if origin_root is None:
        return os.path.normpath(os.path.join(base, target))
    original_base = os.path.join(origin_root, os.path.relpath(base, materialized_root))
    original_target = os.path.normpath(os.path.join(original_base, target))
    if os.path.commonpath([origin_root, original_target]) == origin_root:
        return os.path.join(
            materialized_root, os.path.relpath(original_target, origin_root)
        )
    return original_target


def _check(root: str, origin_root=None, materialized_root=None) -> dict:
    manifest = {}
    texts = {}

    def read_checked(path):
        """Read a guide once, refuse a file that changed while being read, and record a
        SHA-256 of the bytes actually checked."""
        if path not in texts:
            before = os.lstat(path)
            data = Path(path).read_bytes()
            after = os.lstat(path)
            if (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size) != (
                after.st_dev,
                after.st_ino,
                after.st_mtime_ns,
                after.st_size,
            ):
                raise OSError("guide changed while being read: " + str(path))
            alias = os.path.islink(path)
            link = os.readlink(path) if alias else None
            if alias:
                mode = "120000"
            elif after.st_mode & stat.S_IXUSR:
                mode = "100755"
            else:
                mode = "100644"
            manifest[path] = {
                "mode": mode,
                "blob_sha256": hashlib.sha256(
                    link.encode() if alias else data
                ).hexdigest(),
                "content_sha256": hashlib.sha256(data).hexdigest(),
                "link_target": link,
            }
            texts[path] = data.decode("utf-8", errors="replace")
        return texts[path]

    root = os.path.abspath(os.path.expanduser(root))
    result = {"root": root, "errors": [], "warnings": [], "rooms": 0, "stages": 0}
    if not os.path.isdir(root):
        result["unmeasured"] = f"not a directory: {root}"
        return result
    err, warn = result["errors"].append, result["warnings"].append

    map_path = next(
        (
            os.path.join(root, n)
            for n in ("CLAUDE.md", "AGENTS.md")
            if os.path.isfile(os.path.join(root, n))
        ),
        None,
    )
    router = os.path.join(root, "CONTEXT.md")
    linked_files = []
    if not map_path:
        err("no map: CLAUDE.md (or AGENTS.md) missing at the root")
    else:
        text = read_checked(map_path)
        linked_files.append(map_path)
        n = len(text.splitlines())
        other = os.path.join(
            root, "AGENTS.md" if map_path.endswith("CLAUDE.md") else "CLAUDE.md"
        )
        routed_elsewhere = (
            os.path.isfile(router) and _has_routing_table(read_checked(router))
        ) or (os.path.isfile(other) and _has_routing_table(read_checked(other)))
        if not _has_routing_table(text) and not routed_elsewhere:
            err(
                f"{os.path.basename(map_path)} routes nowhere: no routing table or "
                "Where-to-go list, and the root CONTEXT.md does not route either"
            )
        if n > MAP_WARN_LINES:
            warn(
                f"{os.path.basename(map_path)} is {n} lines; the map should fit on one screen"
            )
        if os.path.basename(map_path) == "CLAUDE.md" and not os.path.exists(
            os.path.join(root, "AGENTS.md")
        ):
            warn("AGENTS.md missing; Codex reads it (make it a symlink to CLAUDE.md)")

    # Both native entry guides can supply routing; validate both, not only the preferred
    # Claude map. Explicitly routed hidden rooms are contracts too.
    for name in ("CLAUDE.md", "AGENTS.md", "CONTEXT.md"):
        candidate = os.path.join(root, name)
        if os.path.isfile(candidate) and os.path.realpath(candidate) not in {
            os.path.realpath(p) for p in linked_files
        }:
            linked_files.append(candidate)
    native_agents = os.path.join(root, "AGENTS.md")
    if os.path.lexists(native_agents) and not os.path.isfile(native_agents):
        err("AGENTS.md is not a readable map (dangling alias or non-file)")
    if os.path.isfile(native_agents):
        native_text = _without_fences(read_checked(native_agents))
        if (
            os.path.realpath(native_agents)
            != os.path.realpath(os.path.join(root, "CLAUDE.md"))
            and "CLAUDE.md" not in native_text
            and not _has_routing_table(native_text)
        ):
            err("AGENTS.md has no routing map or pointer to CLAUDE.md")
    walked = list(_walk(root))
    seen_dirs = {d for d, _, _ in walked}
    queue = linked_files + [
        os.path.join(d, "CONTEXT.md") for d, _, fs in walked if "CONTEXT.md" in fs
    ]
    visited = set()
    while queue:
        guide = queue.pop()
        if guide in visited:
            continue
        visited.add(guide)
        for target in _local_links(
            read_checked(guide), routing=os.path.dirname(guide) == root
        ):
            full = resolve_link(
                os.path.dirname(guide), target, origin_root, materialized_root
            )
            if (
                os.path.basename(full) != "CONTEXT.md"
                or not exact_exists(full)
                or os.path.commonpath([root, full]) != root
            ):
                continue
            parts = os.path.relpath(full, root).split(os.sep)
            if any(x in SKIP_DIRS for x in parts):
                continue
            directory = os.path.dirname(full)
            ancestor = directory
            nested = False
            while ancestor != root:
                if is_project_boundary(ancestor):
                    nested = True
                    break
                ancestor = os.path.dirname(ancestor)
            if nested:
                continue
            queue.append(full)
            if directory not in seen_dirs:
                walked.append((directory, [], ["CONTEXT.md"]))
                seen_dirs.add(directory)
    for dirpath, _dirnames, filenames in walked:
        rel = os.path.relpath(dirpath, root)
        name = os.path.basename(dirpath)
        if rel != "." and re.match(r"^\d{2}_", name):
            result["stages"] += 1
            if not STAGE_RE.match(name):
                err(f"{rel}: stage folder not named NN_kebab-name")
            if "CONTEXT.md" not in filenames:
                err(f"{rel}: stage folder has no CONTEXT.md")
        loose = [f for f in filenames if not f.startswith(".")]
        if rel != "." and len(loose) > CROWDED and "CONTEXT.md" in filenames:
            warn(f"{rel}: {len(loose)} files at one level; consider subfolders")
        if "CONTEXT.md" not in filenames:
            continue
        path = os.path.join(dirpath, "CONTEXT.md")
        text = read_checked(path)
        linked_files.append(path)
        lines = len(text.splitlines())
        if lines > MAX_CONTEXT_LINES:
            err(
                f"{os.path.relpath(path, root)}: {lines} lines (limit {MAX_CONTEXT_LINES})"
            )
        if rel == ".":
            continue  # workspace context: purpose, form, runs, status; its shape is prose
        result["rooms"] += 1
        missing = [
            h
            for h in ROOM_HEADINGS
            if not re.search(rf"^{re.escape(h)}\b", _without_fences(text), re.M)
        ]
        if missing:
            err(f"{os.path.relpath(path, root)}: missing {', '.join(missing)}")

    for path in linked_files:
        base = os.path.dirname(path)
        for target in _local_links(read_checked(path), routing=base == root):
            full = resolve_link(base, target, origin_root, materialized_root)
            if not exact_exists(full):
                err(f"{os.path.relpath(path, root)}: broken link -> {target}")

    if result["rooms"] >= 3 and not os.path.isfile(router):
        err("workspace CONTEXT.md missing: required for three or more rooms")

    if result["rooms"] == 0 and result["stages"] == 0 and map_path:
        err("no rooms: no folder below the root has a CONTEXT.md")
    result["contracts"] = sorted(
        set(linked_files + ([native_agents] if os.path.isfile(native_agents) else []))
    )
    result["manifest"] = manifest
    return result


def check(root, origin_root=None, materialized_root=None):
    """Measure one project. An unreadable tree or guide is "unmeasured", never a pass."""
    try:
        return _check(root, origin_root, materialized_root)
    except OSError as error:
        return {
            "root": os.path.abspath(root),
            "errors": [],
            "warnings": [],
            "rooms": 0,
            "stages": 0,
            "contracts": [],
            "manifest": {},
            "unmeasured": "tree or guide could not be read: " + str(error),
        }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--origin-root",
        help="Original Git namespace for a read-only check of an exported tree",
    )
    ap.add_argument(
        "--materialized-root", help="Exported Git tree corresponding to --origin-root"
    )
    args = ap.parse_args(argv)
    if bool(args.origin_root) != bool(args.materialized_root):
        ap.error("--origin-root and --materialized-root must be supplied together")
    origin = os.path.abspath(args.origin_root) if args.origin_root else None
    materialized = (
        os.path.abspath(args.materialized_root) if args.materialized_root else None
    )
    r = check(args.root, origin, materialized)
    code = 2 if "unmeasured" in r else (1 if r["errors"] else 0)
    r["exit"] = code
    if args.json:
        print(json.dumps(r))
        return code
    if code == 2:
        print(f"COULD NOT MEASURE: {r['unmeasured']}")
        return code
    print(
        f"{'HOLDS' if code == 0 else 'BROKEN'}: {r['root']} "
        f"({r['rooms']} rooms, {r['stages']} stages)"
    )
    for e in r["errors"]:
        print(f"  error: {e}")
    for w in r["warnings"]:
        print(f"  warn:  {w}")
    return code


if __name__ == "__main__":
    sys.exit(main())
