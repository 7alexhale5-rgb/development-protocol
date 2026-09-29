#!/usr/bin/env python3
"""Decide which specialist lenses fire for a planning-stack goal.

This logic once lived as prose in the skill, and the agent re-interpreted it
differently on every run (found 2026-07-14). A script gives the same answer
every time.

Usage:
  lens_classify.py --goal "<goal>" [--constraints-file <path>]

Prints JSON: {"fired_lenses": [...], "matches": {lens: [keywords hit]},
"dropped": [...]}. Exit 0 on success, 1 on an empty goal or unreadable file.

Standard library only. Python 3.9 or newer.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ALWAYS_ON = [
    "adversary",
    "observability",
    "reversibility",
    "economist",
    "test-strategist",
]

KEYWORD_GATED = {
    "sre": [
        "deploy",
        "infra",
        "runtime",
        "scaling",
        "prod",
        "oncall",
        "latency",
        "uptime",
        "slo",
        "sli",
        "region",
        "k8s",
        "lambda",
        "vercel",
        "replica",
        "throughput",
    ],
    "data-integrity": [
        "schema",
        "migration",
        "database",
        "db",
        "supabase",
        "postgres",
        "mysql",
        "etl",
        "cdc",
        "backfill",
        "dual-write",
        "sync",
        "replication",
        "cutover",
    ],
    "concurrency": [
        "async",
        "parallel",
        "queue",
        "worker",
        "distributed",
        "race",
        "lock",
        "transaction",
        "cron",
        "webhook",
        "retry",
        "idempotent",
        "leader",
        "kafka",
        "sqs",
        "redis",
        "websocket",
        "multi-tenant",
    ],
    "supply-chain": [
        "package",
        "library",
        "npm",
        "pip",
        "cargo",
        "sdk",
        "api client",
        "integrate",
        "third-party",
        "dependency",
        "install",
        "docker image",
        "container",
        "vendor",
    ],
    "compliance": [
        "pii",
        "personal data",
        "gdpr",
        "ccpa",
        "hipaa",
        "phi",
        "pci",
        "payment",
        "card",
        "billing",
        "soc 2",
        "audit",
        "consent",
        "dsar",
        "retention",
        "auth",
        "kyc",
        "age gate",
        "child",
        "financial",
        "sox",
        "hr",
        "health",
        "medical",
        "insurance",
    ],
}

MAX_LENSES = 8


def _hit(keyword: str, text: str) -> bool:
    # Whole-word match, so "prod" does not fire on "product". A plural ending
    # counts ("payments" fires "payment"); the first version missed plurals.
    pattern = r"(?<![a-z0-9])" + re.escape(keyword) + r"(?:e?s)?(?![a-z0-9])"
    return re.search(pattern, text) is not None


def classify(goal: str, constraints: str = "") -> dict:
    text = f"{goal} {constraints}".lower()
    matches = {}
    for lens, keywords in KEYWORD_GATED.items():
        hits = [kw for kw in keywords if _hit(kw, text)]
        if hits:
            matches[lens] = hits
    fired = list(ALWAYS_ON) + list(matches)
    dropped = []
    while len(fired) > MAX_LENSES:
        # Drop the gated lens with the fewest hits; ties break alphabetically.
        weakest = min(matches, key=lambda k: (len(matches[k]), k))
        fired.remove(weakest)
        dropped.append(weakest)
        del matches[weakest]
    return {"fired_lenses": fired, "matches": matches, "dropped": dropped}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Decide which specialist lenses fire.")
    ap.add_argument("--goal", required=True)
    ap.add_argument("--constraints-file", help="optional file of constraint text")
    args = ap.parse_args(argv)
    if not args.goal.strip():
        print("error: empty goal", file=sys.stderr)
        return 1
    constraints = ""
    if args.constraints_file:
        try:
            constraints = Path(args.constraints_file).read_text()
        except OSError as e:
            print(f"error: cannot read constraints file: {e}", file=sys.stderr)
            return 1
    print(json.dumps(classify(args.goal, constraints), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
