#!/usr/bin/env python3
"""Lighthouse baseline helper. Python 3.9+ standard library only.

This file is copied into the project as ops/lighthouse/lh_baseline.py so the
baseline rerun and the CI "bless" flow work on any clone and any CI runner,
with no dependency on where the audit-setup skill is installed.

  lh_baseline.py summarize --raw-dir ops/lighthouse/baseline/.raw --out-dir ops/lighthouse/baseline
  lh_baseline.py assertions --baseline-dir ops/lighthouse/baseline [--out .lighthouserc.json]
  lh_baseline.py enforce --config .lighthouserc.json

summarize: raw files are named <slug>.<run>.json. For each route it keeps the
run whose performance score is the median as <slug>.report.json, then writes
SUMMARY.md. Exit 1 when no run produced a report, so a failed capture is loud.

assertions: derives an LHCI config (warn-only) from the baseline reports.
enforce: flips every warn-level assertion to error-level.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

SENTINEL = "audit-setup:lighthouse-ci v1"
# Hard floors. A baseline below a floor asserts the floor, not the baseline.
FLOORS = {
    "performance": 0.80,
    "accessibility": 1.00,
    "best-practices": 0.95,
    "seo": 0.95,
}
# Allowed dip below baseline before an assertion fires. Accessibility gets none.
TOLERANCE = 0.03
CATEGORIES = ("performance", "accessibility", "best-practices", "seo")


def _score(report: dict, cat: str):
    return ((report.get("categories") or {}).get(cat) or {}).get("score")


def _median_run(runs: list) -> dict:
    """The run whose performance score is the (upper) median. Missing scores sort as 0."""
    scores = sorted((_score(r, "performance") or 0) for r in runs)
    med = scores[len(scores) // 2]
    for r in runs:
        if (_score(r, "performance") or 0) == med:
            return r
    return runs[0]


def summarize(raw_dir: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict = {}
    for f in sorted(raw_dir.glob("*.json")):
        m = re.match(r"^(.+)\.(\d+)\.json$", f.name)
        if not m:
            continue
        try:
            grouped.setdefault(m.group(1), []).append(json.loads(f.read_text()))
        except (OSError, ValueError) as exc:
            print(f"lh_baseline: skipping unreadable {f.name}: {exc}", file=sys.stderr)
    rows = []
    form_factor = "mobile"
    for slug in sorted(grouped):
        runs = grouped[slug]
        best = _median_run(runs)
        (out_dir / f"{slug}.report.json").write_text(json.dumps(best))
        form_factor = (best.get("configSettings") or {}).get("formFactor", form_factor)
        audits = best.get("audits") or {}

        def num(key):
            return (audits.get(key) or {}).get("numericValue")

        rows.append(
            {
                "slug": slug,
                "runs": len(runs),
                **{c: _score(best, c) for c in CATEGORIES},
                "lcp": num("largest-contentful-paint"),
                "fcp": num("first-contentful-paint"),
                "cls": num("cumulative-layout-shift"),
                "tbt": num("total-blocking-time"),
            }
        )
    if not rows:
        print(f"lh_baseline: no Lighthouse runs found in {raw_dir}", file=sys.stderr)
        return 1

    def pct(v):
        return "-" if v is None else str(round(v * 100))

    def sec(v):
        return "-" if v is None else f"{v / 1000:.2f}s"

    lines = [
        f"# Lighthouse baseline - {datetime.date.today().isoformat()}",
        "",
        f"{form_factor} preset, median of runs per route, {len(rows)} routes",
        "",
        "| Route | Runs | Perf | A11y | BP | SEO | LCP | FCP | CLS | TBT |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        cls = "-" if r["cls"] is None else f"{r['cls']:.3f}"
        lines.append(
            f"| `{r['slug']}` | {r['runs']} | {pct(r['performance'])} | {pct(r['accessibility'])} | "
            f"{pct(r['best-practices'])} | {pct(r['seo'])} | {sec(r['lcp'])} | {sec(r['fcp'])} | "
            f"{cls} | {sec(r['tbt'])} |"
        )
    lines += [
        "",
        "_Scores are 0 to 100. Review floor: perf 80, a11y 90, best practices 90, SEO 85. "
        "Targets: CLS under 0.1, LCP under 4s._",
        "",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(lines))
    print(f"lh_baseline: {len(rows)} routes -> {out_dir}/SUMMARY.md")
    return 0


def assertions(baseline_dir: Path) -> dict:
    """LHCI config derived from the baseline. Reads each report's requestedUrl for the
    route path: rebuilding it from the file slug is lossy (/a/b and /a-b share a slug)."""
    reports = sorted(baseline_dir.glob("*.report.json"))
    if not reports:
        raise ValueError(f"no baseline reports in {baseline_dir}")
    first = json.loads(reports[0].read_text())
    # The LHCI preset must match the captured baseline, or the first run fails every assertion.
    form_factor = (first.get("configSettings") or {}).get("formFactor") or "mobile"
    matrix = []
    for f in reports:
        j = json.loads(f.read_text())
        path = urlparse(j.get("requestedUrl") or j.get("finalUrl") or "").path or "/"

        def floor(cat, tol):
            base = _score(j, cat)
            base = 1.0 if base is None else base
            return round(max(base - tol, FLOORS[cat]), 4)

        matrix.append(
            {
                "matchingUrlPattern": ".*" + re.escape(path) + "$",
                "assertions": {
                    "categories:performance": [
                        "warn",
                        {"minScore": floor("performance", TOLERANCE)},
                    ],
                    "categories:accessibility": [
                        "warn",
                        {"minScore": floor("accessibility", 0)},
                    ],
                    "categories:best-practices": [
                        "warn",
                        {"minScore": floor("best-practices", TOLERANCE)},
                    ],
                    "categories:seo": ["warn", {"minScore": floor("seo", TOLERANCE)}],
                },
            }
        )
    collect: dict = {"numberOfRuns": 3}
    if form_factor == "desktop":
        collect["settings"] = {"preset": "desktop"}
    return {
        "_comment": f"{SENTINEL} - regenerate via /audit-setup --ci-only --force",
        "_note": 'Assertions default to "warn". Flip to "error" to enforce, or run /audit-setup --ci-only --enforce.',
        "ci": {
            "collect": collect,
            "assert": {"assertMatrix": matrix},
            "upload": {"target": "temporary-public-storage"},
        },
    }


def enforce(config: Path) -> int:
    data = json.loads(config.read_text())
    changed = 0

    def walk(node):
        nonlocal changed
        if isinstance(node, list):
            if len(node) == 2 and node[0] == "warn" and isinstance(node[1], dict):
                node[0] = "error"
                changed += 1
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if node.get("level") == "warn":
                node["level"] = "error"
                changed += 1
            for value in node.values():
                walk(value)

    walk(data)
    config.write_text(json.dumps(data, indent=2) + "\n")
    print(f"lh_baseline: flipped {changed} warn -> error in {config}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summarize")
    s.add_argument("--raw-dir", required=True, type=Path)
    s.add_argument("--out-dir", required=True, type=Path)
    a = sub.add_parser("assertions")
    a.add_argument("--baseline-dir", default=Path("ops/lighthouse/baseline"), type=Path)
    a.add_argument("--out", type=Path)
    e = sub.add_parser("enforce")
    e.add_argument("--config", default=Path(".lighthouserc.json"), type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "summarize":
        return summarize(args.raw_dir, args.out_dir)
    if args.cmd == "assertions":
        try:
            text = json.dumps(assertions(args.baseline_dir), indent=2) + "\n"
        except (OSError, ValueError) as exc:
            print(f"lh_baseline: {exc}", file=sys.stderr)
            return 1
        if args.out:
            args.out.write_text(text)
            print(f"lh_baseline: wrote {args.out}")
        else:
            sys.stdout.write(text)
        return 0
    if not args.config.is_file():
        print(f"lh_baseline: {args.config} missing", file=sys.stderr)
        return 1
    return enforce(args.config)


if __name__ == "__main__":
    sys.exit(main())
