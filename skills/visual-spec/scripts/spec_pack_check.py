#!/usr/bin/env python3
"""Gate a Visual Spec Pack against its own acceptance rules.

Until 2026-09-05 the acceptance rules were prose only: several skills required
the pack and nothing checked it. This script checks the structure. Substance
(does the entity map cover every noun a screen uses, is a caveat honest) stays
a judged read, printed under JUDGED so nobody mistakes a green exit for a
reviewed pack.

Checks (all deterministic, on the .mmd text, no Mermaid engine needed):
  M1 manifest.json lists every .mmd in the folder and every sha256 matches disk;
     a screen-only row (no "file", a "screen" PNG) must name a file that exists
  M2 mindmap: every leaf line (indented 6+ spaces) begins with R, W, P or U
  F1 flowchart: every declared node id is assigned a class
  F2 flowchart: at least one UNKNOWN node, or the manifest row says "unknowns": "none"
  W1 wireframe (block-beta): every block classed; a header block exists
  W2 wireframe: exactly one action block, unless the manifest row's "actions" is
     "menu" (a home or index screen, two or more) or "none" (preview, read-only)
  W3 wireframe: the manifest row carries "workflow" and "security" (the map table)
  N1 navigation map: every wireframe letter is reachable from a HOME node
  P1-P4 presence: a mindmap, a workflow flowchart, a wireframe and an entity map
  S1 index.md (if present) ends with "## Plain-English Summary"

File-name conventions the checks depend on: "wireframe-<letter>" marks a screen,
"navigation" marks the navigation map, "relationship" marks the entity map.
A pack written as one Markdown file with mermaid fences is NOT parsed (known
limit): split it into .mmd files first.

Usage:
  spec_pack_check.py <pack folder>

Exit 0 pass, 1 a rule fails, 2 no pack, missing or unparseable manifest, or a
manifest that is not a list of objects. A 2 is never a pass.
Standard library only. Python 3.9 or newer.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

TAGS = ("R ", "W ", "P ", "U ")
NODE_RE = re.compile(r'(?<![\w"])([A-Za-z][A-Za-z0-9_]*)\s*(?:\[|\(|\{|\[\[|\(\()')
CLASS_RE = re.compile(
    r"^\s*class\s+([A-Za-z0-9_,\s]+?)\s+([A-Za-z_][A-Za-z0-9_-]*)\s*;?\s*$", re.M
)
EDGE_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9_]*)(?:\[[^\]]*\]|\{[^}]*\}|\([^)]*\))?\s*"
    r"(?:-->|-\.->|==>)\s*(?:\|[^|]*\|\s*)?([A-Za-z][A-Za-z0-9_]*)"
)
BLOCK_RE = re.compile(r'(?<![\w"])([A-Za-z][A-Za-z0-9_]*)\["')
SUBGRAPH_RE = re.compile(r"^\s*subgraph\s+([A-Za-z][A-Za-z0-9_]*)", re.M)
KEYWORDS = {"flowchart", "graph", "TB", "LR", "TD", "RL", "BT", "end"}
MANIFEST_FATAL = "M1 manifest.json"

JUDGED = [
    "entity map covers every noun that appears on a wireframe",
    "caveats on note blocks are true to the interview",
    "R/W/P/U tags match the source transcript",
    "each wireframe row's concept names a rendered screen before the owner's visual pass",
    "the owner has been asked to mark anything wrong, and the review ledger has a line per view",
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def kind(text: str) -> str:
    body = re.sub(r"%%\{.*?\}%%", "", text, flags=re.S)
    lines = [
        ln for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("%%")
    ]
    head = lines[0].strip().lower() if lines else ""
    if head.startswith("mindmap"):
        return "mindmap"
    if head.startswith("block-beta"):
        return "wireframe"
    if head.startswith(("flowchart", "graph")):
        return "flowchart"
    return "other"


def classed_ids(text: str) -> set[str]:
    ids: set[str] = set()
    for m in CLASS_RE.finditer(text):
        ids.update(x.strip() for x in m.group(1).split(",") if x.strip())
    return ids


def declared_ids(text: str) -> set[str]:
    skip = ("class", "classDef", "subgraph", "end", "%%", "columns")
    body = "\n".join(ln for ln in text.splitlines() if not ln.strip().startswith(skip))
    body = re.sub(r'"[^"]*"', '""', body)
    return {m.group(1) for m in NODE_RE.finditer(body)} - KEYWORDS


def load_manifest(d: Path, fails: list[str]):
    """Return {file: row}, or None when the manifest is missing or unusable."""
    mpath = d / "manifest.json"
    if not mpath.is_file():
        fails.append(f"{MANIFEST_FATAL} missing")
        return None
    try:
        manifest = json.loads(mpath.read_text())
    except json.JSONDecodeError as e:
        fails.append(f"{MANIFEST_FATAL} unparseable: {e}")
        return None
    if not isinstance(manifest, list) or not all(isinstance(r, dict) for r in manifest):
        fails.append(f"{MANIFEST_FATAL} must be a list of objects")
        return None
    # Name each offending row and KEEP CHECKING. Stopping at the first bad row
    # (as an earlier version did, found 2026-09-06) hid four unrelated failures
    # behind one vague message: a gate that stops early under-reports the work.
    rows = {}
    for i, r in enumerate(manifest):
        if "file" in r:
            rows[r["file"]] = r
        elif "screen" in r:
            # A screen-only row is legitimate (found 2026-09-09): rendered screens
            # are the layer the owner judges, and a gate that demanded a "file" on
            # every row kept packs stuck in the diagram-only format.
            if not (d / r["screen"]).is_file():
                fails.append(
                    f"M1 manifest row {i} names a missing screen: {r['screen']}"
                )
        else:
            fails.append(
                f"M1 manifest row {i} has neither a file nor a screen: {r.get('title', '(untitled)')}"
            )
    return rows


def check_manifest_files(d: Path, rows: dict, mmds: list[str], fails, passes) -> None:
    for f in mmds:
        if f not in rows:
            fails.append(f"M1 {f} on disk but not in manifest")
    for f, r in rows.items():
        p = d / f
        if not p.is_file():
            fails.append(f"M1 {f} listed but missing")
        elif sha(p) != r.get("sha256"):
            fails.append(f"M1 {f} sha256 differs from manifest")
    if not any(x.startswith("M1") for x in fails):
        passes.append(f"M1 manifest covers {len(mmds)} files, all hashes match")


def check_mindmap(f: str, text: str, fails, passes) -> None:
    bad = []
    for line in text.splitlines()[1:]:
        s = line.strip()
        if not s or s.startswith("root"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent >= 6 and not s.startswith(TAGS):
            bad.append(s[:40])
    if bad:
        fails.append(
            f"M2 {f}: {len(bad)} leaf lines without R/W/P/U tag, e.g. '{bad[0]}'"
        )
    else:
        passes.append(f"M2 {f}: every leaf tagged")


def check_wireframe(f: str, text: str, row: dict, fails, passes):
    m = re.search(r"wireframe[-\s]([a-z0-9])", f, re.I)
    letter = m.group(1).upper() if m else None
    unclassed = sorted(set(BLOCK_RE.findall(text)) - classed_ids(text))
    if unclassed:
        fails.append(f"W1 {f}: unclassed blocks {unclassed}")
    if not re.search(r"^\s*class\s+\S+\s+header", text, re.M):
        fails.append(f"W1 {f}: no header block")
    act_ids: set[str] = set()
    for am in re.finditer(r"^\s*class\s+([A-Za-z0-9_,]+)\s+action", text, re.M):
        act_ids.update(x for x in am.group(1).split(",") if x)
    n_act = len(act_ids)
    mode = row.get("actions", "one")
    ok = (
        (mode == "one" and n_act == 1)
        or (mode == "menu" and n_act >= 2)
        or (mode == "none" and n_act == 0)
    )
    if ok:
        passes.append(f"W2 {f}: {n_act} action block(s), mode {mode}")
    else:
        fails.append(
            f"W2 {f}: {n_act} action block(s) but manifest actions={mode} "
            "(declare 'menu' or 'none' if intended)"
        )
    missing = [k for k in ("workflow", "security") if not row.get(k)]
    if missing:
        fails.append(f"W3 {f}: manifest row lacks {missing}")
    else:
        passes.append(f"W3 {f}: workflow + security recorded")
    return letter


def check_flowchart(f: str, text: str, row: dict, fails, passes) -> None:
    decl = declared_ids(text) - set(SUBGRAPH_RE.findall(text))
    unclassed = sorted(decl - classed_ids(text))
    if unclassed:
        fails.append(f"F1 {f}: unclassed nodes {unclassed}")
    else:
        passes.append(f"F1 {f}: all {len(decl)} nodes classed")
    if "relationship" in f:
        return
    if "UNKNOWN" in text or row.get("unknowns") == "none":
        passes.append(f"F2 {f}: unknowns named")
    else:
        fails.append(
            f"F2 {f}: no UNKNOWN node and manifest does not say unknowns: none"
        )


def nav_graph(nav_text: str) -> dict[str, set[str]]:
    g: dict[str, set[str]] = defaultdict(set)
    for a, b in EDGE_RE.findall(nav_text):
        g[a].add(b)
    # Chained edges (A --> B --> C): the pair regex misses the middle links.
    for line in nav_text.splitlines():
        ids = re.findall(
            r"([A-Za-z][A-Za-z0-9_]*)(?:\[[^\]]*\])?\s*(?=-->|-\.->|==>)", line
        )
        tail = re.findall(
            r"(?:-->|-\.->|==>)\s*(?:\|[^|]*\|\s*)?([A-Za-z][A-Za-z0-9_]*)", line
        )
        seq = ids + tail[-1:] if ids else []
        for a, b in zip(seq, seq[1:]):
            g[a].add(b)
    return g


def check_navigation(nav_text, letters: list[str], fails, passes) -> None:
    if nav_text is None:
        fails.append("N1 no navigation map (file name must contain 'navigation')")
        return
    g = nav_graph(nav_text)
    home = next((n for n in g if n.upper().startswith("HOME")), None)
    if not home:
        fails.append("N1 navigation map has no HOME node")
        return
    seen = {home}
    q = deque([home])
    while q:
        for n in g[q.popleft()]:
            if n not in seen:
                seen.add(n)
                q.append(n)
    # A node id rarely equals its wireframe letter: map every node whose label
    # starts "X." (for example PART_SEARCH["D. Find part"]) to letter X.
    id_letter = {
        m.group(1): m.group(2)
        for m in re.finditer(r'([A-Za-z][A-Za-z0-9_]*)\["([A-Z])\.', nav_text)
    }
    reached = set(seen) | {id_letter[n] for n in seen if n in id_letter}
    unreached = [x for x in letters if x not in reached]
    if unreached:
        fails.append(f"N1 wireframes not reachable from {home}: {unreached}")
    else:
        passes.append(f"N1 all {len(letters)} wireframes reachable from {home}")


def check_summary(d: Path, fails, passes) -> None:
    idx = d / "index.md"
    if not idx.is_file():
        return
    parts = idx.read_text().split("## Plain-English Summary", 1)
    if len(parts) == 2 and "\n## " not in parts[1]:
        passes.append("S1 index.md carries Plain-English Summary")
    else:
        fails.append(
            "S1 index.md has no '## Plain-English Summary' as its last heading"
        )


def check_pack(d: Path) -> tuple[list[str], list[str], list[str]]:
    fails: list[str] = []
    passes: list[str] = []
    rows = load_manifest(d, fails)
    if rows is None:
        return fails, passes, JUDGED
    mmds = sorted(p.name for p in d.glob("*.mmd"))
    check_manifest_files(d, rows, mmds, fails, passes)

    letters: list[str] = []
    nav_text = None
    counts = {"mindmap": 0, "workflow": 0, "relationship": 0}
    for f in mmds:
        if f not in rows:
            continue
        text = (d / f).read_text()
        row = rows[f]
        k = kind(text)
        if k == "mindmap":
            counts["mindmap"] += 1
            check_mindmap(f, text, fails, passes)
        elif k == "wireframe":
            letter = check_wireframe(f, text, row, fails, passes)
            if letter:
                letters.append(letter)
        elif k == "flowchart":
            if "navigation" in f:
                nav_text = text
                continue
            if "relationship" not in f:
                counts["workflow"] += 1
            check_flowchart(f, text, row, fails, passes)
    counts["relationship"] = sum(1 for f in mmds if "relationship" in f)

    for label, n in (
        ("P1 mindmap", counts["mindmap"]),
        ("P2 workflow flowchart", counts["workflow"]),
        ("P3 wireframe", len(letters)),
        ("P4 entity map (file name contains 'relationship')", counts["relationship"]),
    ):
        if n == 0:
            fails.append(f"{label}: none present")
        else:
            passes.append(f"{label}: {n} present")
    check_navigation(nav_text, letters, fails, passes)
    check_summary(d, fails, passes)
    return fails, passes, JUDGED


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return 2
    d = Path(argv[0]).resolve()
    if not d.is_dir():
        print(f"spec_pack_check: not a directory: {d}")
        return 2
    fails, passes, judged = check_pack(d)
    if fails and fails[0].startswith(MANIFEST_FATAL):
        print("\n".join(fails))
        return 2
    for p in passes:
        print("PASS", p)
    for f in fails:
        print("FAIL", f)
    print("JUDGED (not scripted):")
    for j in judged:
        print("  -", j)
    verdict = "FAIL" if fails else "PASS"
    print(f"spec_pack_check: {len(passes)} pass, {len(fails)} fail -> {verdict}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
