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
import hashlib
import json
import os
import copy
import math
import shutil
import tempfile
import urllib.request
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
    categories = report.get("categories")
    category = categories.get(cat) if isinstance(categories, dict) else None
    return category.get("score") if isinstance(category, dict) else None


def _median_run(runs: list) -> dict:
    """The run whose performance score is the (upper) median. Missing scores sort as 0."""
    scores = sorted((_score(r, "performance") or 0) for r in runs)
    med = scores[len(scores) // 2]
    for r in runs:
        if (_score(r, "performance") or 0) == med:
            return r
    return runs[0]


def valid_report(report: dict) -> bool:
    if not isinstance(report, dict) or report.get("runtimeError"):
        return False
    url = report.get("requestedUrl")
    if not isinstance(url, str) or re.search(r"[\x00-\x20\x7f]", url):
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    if report.get("finalUrl") != url or report.get("finalDisplayedUrl", url) != url:
        return False
    settings = report.get("configSettings")
    environment = report.get("environment")
    fetch_time = report.get("fetchTime")
    try:
        parsed_time = datetime.datetime.fromisoformat(fetch_time.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return False
    if parsed_time.tzinfo is None or parsed_time.utcoffset() is None:
        return False
    if (
        not isinstance(settings, dict)
        or settings.get("formFactor") not in ("mobile", "desktop")
        or not isinstance(environment, dict)
        or not isinstance(environment.get("hostUserAgent"), str)
        or not environment.get("hostUserAgent")
        or not isinstance(report.get("lighthouseVersion"), str)
        or not report.get("lighthouseVersion")
    ):
        return False
    audits = report.get("audits")
    if not isinstance(audits, dict):
        return False
    for key in (
        "largest-contentful-paint",
        "first-contentful-paint",
        "cumulative-layout-shift",
        "total-blocking-time",
    ):
        audit = audits.get(key)
        value = audit.get("numericValue") if isinstance(audit, dict) else None
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or value < 0
        ):
            return False
    return all(
        isinstance(_score(report, c), (int, float))
        and not isinstance(_score(report, c), bool)
        and math.isfinite(_score(report, c))
        and 0 <= _score(report, c) <= 1
        for c in CATEGORIES
    )


def summarize(raw_dir: Path, out_dir: Path) -> int:
    # Build the complete replacement separately; failed capture leaves old proof intact.
    with tempfile.TemporaryDirectory(prefix="lh-baseline-") as temp:
        staged = Path(temp) / "baseline"
        staged.mkdir()
        code = _summarize(raw_dir, staged)
        if code:
            return code
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        lock = out_dir.parent / ("." + out_dir.name + ".publish-lock")
        try:
            lock.mkdir()
        except FileExistsError:
            print(f"lh_baseline: publication lock exists: {lock}", file=sys.stderr)
            return 1
        try:
            with tempfile.TemporaryDirectory(
                prefix=".lh-publish-", dir=out_dir.parent
            ) as publish:
                replacement, backup = Path(publish) / "new", Path(publish) / "old"
                if out_dir.exists():
                    shutil.copytree(out_dir, replacement)
                else:
                    replacement.mkdir()
                for old in replacement.glob("*.report.json"):
                    old.unlink()
                for generated in staged.iterdir():
                    shutil.copy2(generated, replacement / generated.name)
                if out_dir.exists():
                    out_dir.rename(backup)
                try:
                    replacement.rename(out_dir)
                except BaseException:
                    if backup.exists():
                        backup.rename(out_dir)
                    raise
        finally:
            lock.rmdir()
    return 0


def _summarize(raw_dir: Path, out_dir: Path) -> int:
    try:
        expected_runs = int((raw_dir / ".expected-runs").read_text().strip())
        expected_preset = (raw_dir / ".expected-preset").read_text().strip()
        route_lines = (raw_dir / ".expected-routes").read_text().splitlines()
        if (
            expected_runs < 1
            or not route_lines
            or expected_preset not in ("mobile", "desktop")
        ):
            raise ValueError("empty capture declaration")
        expected_urls = {}
        for line in route_lines:
            slug, url = line.split("\t")
            parsed = urlparse(url)
            if (
                not re.fullmatch(r"[a-zA-Z0-9._-]+", slug)
                or slug in (".", "..")
                or slug in expected_urls
                or parsed.scheme not in ("http", "https")
                or not parsed.hostname
                or re.search(r"[\x00-\x20\x7f]", url)
            ):
                raise ValueError("invalid or duplicate route declaration")
            expected_urls[slug] = url
    except (OSError, ValueError) as exc:
        print(f"lh_baseline: invalid capture declaration: {exc}", file=sys.stderr)
        return 1
    grouped = {slug: {} for slug in expected_urls}
    digests = set()
    semantic_digests = set()
    capture_times = set()
    capture_identity = None
    for f in sorted(raw_dir.glob("*.json")):
        m = re.match(r"^(.+)\.(\d+)\.json$", f.name)
        if not m or m.group(1) not in grouped or str(int(m.group(2))) != m.group(2):
            print(f"lh_baseline: undeclared capture {f.name}", file=sys.stderr)
            return 1
        run = int(m.group(2))
        if run < 1 or run > expected_runs or run in grouped[m.group(1)]:
            print(f"lh_baseline: invalid run index {f.name}", file=sys.stderr)
            return 1
        try:
            payload = f.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            if digest in digests:
                raise ValueError("duplicate report bytes")
            digests.add(digest)
            candidate = json.loads(payload)
            if (
                not valid_report(candidate)
                or candidate["requestedUrl"] != expected_urls[m.group(1)]
                or candidate["configSettings"]["formFactor"] != expected_preset
            ):
                raise ValueError("invalid or redirected report")
            semantic_digest = hashlib.sha256(
                json.dumps(candidate, sort_keys=True).encode()
            ).hexdigest()
            if semantic_digest in semantic_digests:
                raise ValueError("duplicate report content")
            semantic_digests.add(semantic_digest)
            captured_at = datetime.datetime.fromisoformat(
                candidate["fetchTime"].replace("Z", "+00:00")
            )
            if captured_at in capture_times:
                raise ValueError("duplicate capture time")
            capture_times.add(captured_at)
            identity = json.dumps(
                {
                    "engine": candidate["lighthouseVersion"],
                    "browser": candidate["environment"]["hostUserAgent"],
                    "settings": candidate["configSettings"],
                },
                sort_keys=True,
            )
            if capture_identity is None:
                capture_identity = identity
            elif identity != capture_identity:
                raise ValueError("mixed capture identity")
            grouped[m.group(1)][run] = candidate
        except (OSError, ValueError) as exc:
            print(f"lh_baseline: rejected {f.name}: {exc}", file=sys.stderr)
            return 1
    rows = []
    form_factor = "mobile"
    for slug in sorted(grouped):
        if set(grouped[slug]) != set(range(1, expected_runs + 1)):
            print(f"lh_baseline: incomplete capture for {slug}", file=sys.stderr)
            return 1
        runs = [grouped[slug][i] for i in range(1, expected_runs + 1)]
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
    report_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in out_dir.glob("*.report.json")
    }
    proof = {
        "version": 1,
        "expected_runs": expected_runs,
        "routes": expected_urls,
        "capture_identity": capture_identity,
        "reports": report_hashes,
        "summary_sha256": hashlib.sha256(
            (out_dir / "SUMMARY.md").read_bytes()
        ).hexdigest(),
    }
    (out_dir / ".capture-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(f"lh_baseline: {len(rows)} routes -> {out_dir}/SUMMARY.md")
    return 0


def published_baseline_valid(base: Path) -> bool:
    """Validate the durable declaration, not just whichever reports remain."""
    try:
        proof = json.loads((base / ".capture-proof.json").read_text())
        if not isinstance(proof, dict) or proof.get("version") != 1:
            return False
        routes = proof.get("routes")
        hashes = proof.get("reports")
        if (
            not isinstance(routes, dict)
            or not routes
            or not isinstance(hashes, dict)
            or not isinstance(proof.get("expected_runs"), int)
            or proof["expected_runs"] < 1
            or set(hashes) != {slug + ".report.json" for slug in routes}
            or set(hashes) != {path.name for path in base.glob("*.report.json")}
        ):
            return False
        summary = base / "SUMMARY.md"
        if hashlib.sha256(summary.read_bytes()).hexdigest() != proof.get(
            "summary_sha256"
        ):
            return False
        for name, digest in hashes.items():
            payload = (base / name).read_bytes()
            if hashlib.sha256(payload).hexdigest() != digest:
                return False
            report = json.loads(payload)
            if not valid_report(report) or report["requestedUrl"] != routes[name[:-12]]:
                return False
            identity = json.dumps(
                {
                    "engine": report["lighthouseVersion"],
                    "browser": report["environment"]["hostUserAgent"],
                    "settings": report["configSettings"],
                },
                sort_keys=True,
            )
            if identity != proof.get("capture_identity"):
                return False
        return True
    except (OSError, ValueError, TypeError, KeyError):
        return False


def assertions(baseline_dir: Path, existing: dict = None) -> dict:
    """LHCI config derived from the baseline. Reads each report's requestedUrl for the
    route path: rebuilding it from the file slug is lossy (/a/b and /a-b share a slug)."""
    if not published_baseline_valid(baseline_dir):
        raise ValueError("invalid published baseline; recapture before deriving assertions")
    reports = sorted(baseline_dir.glob("*.report.json"))
    if not reports:
        raise ValueError(f"no baseline reports in {baseline_dir}")
    first = json.loads(reports[0].read_text())
    # The LHCI preset must match the captured baseline, or the first run fails every assertion.
    form_factor = (first.get("configSettings") or {}).get("formFactor") or "mobile"
    matrix = []
    source_urls = {}
    for f in reports:
        j = json.loads(f.read_text())
        if not valid_report(j):
            raise ValueError(f"invalid baseline report: {f.name}")
        url = urlparse(j.get("requestedUrl") or j.get("finalUrl") or "")
        path = (url.path or "/") + ("?" + url.query if url.query else "")

        source_urls[r"^https?://[^/?#]+" + re.escape(path) + "$"] = url.geturl()

        def floor(cat, tol):
            base = _score(j, cat)
            base = 1.0 if base is None else base
            return round(max(base - tol, FLOORS[cat]), 4)

        matrix.append(
            {
                "matchingUrlPattern": r"^https?://[^/?#]+" + re.escape(path) + "$",
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
    generated = {
        "_comment": f"{SENTINEL} - regenerate via /audit-setup --ci-only --force",
        "_note": 'Assertions default to "warn". Flip to "error" to enforce, or run /audit-setup --ci-only --enforce.',
        "ci": {
            "collect": collect,
            "assert": {"assertMatrix": matrix},
            "upload": {"target": "temporary-public-storage"},
        },
    }

    if existing is None:
        return generated
    merged = copy.deepcopy(existing)
    old_matrix = merged.get("ci", {}).get("assert", {}).get("assertMatrix", [])
    old_by_pattern = {entry.get("matchingUrlPattern"): entry for entry in old_matrix}
    # A fully enforced category remains enforced for newly added routes as well.
    for entry in matrix:
        old = old_by_pattern.get(entry["matchingUrlPattern"])
        if old is None:
            old = next((row for row in old_matrix if re.search(
                row.get("matchingUrlPattern", r"(?!)"), source_urls[entry["matchingUrlPattern"]]
            )), {})
        for category, value in entry["assertions"].items():
            prior = old.get("assertions", {}).get(category)
            levels = [x.get("assertions", {}).get(category) for x in old_matrix]
            if isinstance(prior, list):
                value[0] = prior[0]
            elif levels and all(isinstance(v, list) and v[0] == "error" for v in levels):
                value[0] = "error"
        combined = copy.deepcopy(old)
        combined.update(entry)
        combined["assertions"] = {**old.get("assertions", {}), **entry["assertions"]}
        entry.clear()
        entry.update(combined)
    ci = merged.setdefault("ci", {})
    ci.setdefault("collect", generated["ci"]["collect"])
    ci.setdefault("upload", generated["ci"]["upload"])
    ci.setdefault("assert", {})["assertMatrix"] = matrix
    return merged


def enforce(config: Path) -> int:
    data = json.loads(config.read_text())
    changed = 0

    def walk(node):
        nonlocal changed
        if isinstance(node, list):
            if (
                len(node) == 2
                and node[0] == "warn"
                and not isinstance(node[1], (list, tuple))
            ):
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


def normalize_hosts(hosts: list) -> list:
    result = []
    for host in hosts:
        # Accept the old scaffold's https://*.domain* notation, but only as
        # a domain boundary. Never retain its arbitrary URL suffix wildcard.
        if host.startswith("https://"):
            host = host[8:].rstrip("/*")
        host = host.lower()
        domain = host[2:] if host.startswith("*.") else host
        if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", domain):
            raise ValueError("allow-host must be a hostname or *.domain")
        result.append(host)
    if not result:
        raise ValueError("an allowed host is required")
    return result


def validate_preview_url(url: str, hosts: list) -> None:
    if re.search(r"[\x00-\x20\x7f]", url):
        raise ValueError("preview URL contains whitespace or control characters")
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError("preview URL needs HTTPS with no credentials or fragment")
    host = (parsed.hostname or "").lower()
    if len(host) > 253 or not all(
        re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in host.split(".")
    ):
        raise ValueError("preview URL hostname has an invalid DNS label")
    if parsed.port not in (None, 443):
        raise ValueError("preview URL must use the HTTPS port")
    if not any(
        host == pattern
        or (
            pattern.startswith("*.")
            and host.endswith(pattern[1:])
            and host != pattern[2:]
        )
        for pattern in normalize_hosts(hosts)
    ):
        raise ValueError("preview URL hostname is outside the allowed domains")


def validate_preview_origin(url: str, hosts: list) -> str:
    """Validate the workflow's base before writing it to an output file."""
    validate_preview_url(url, hosts)
    parsed = urlparse(url)
    if (
        parsed.path not in ("", "/")
        or "?" in url
        or "#" in url
        or parsed.port is not None
    ):
        raise ValueError(
            "preview base must be an origin without port, path, query or fragment"
        )
    return "https://" + parsed.hostname.lower()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Fail closed before any redirect target is contacted.
        return None


def preview_routes(base: str, baseline: Path, config: Path, hosts: list,
                   check_access: bool = True) -> list:
    if not published_baseline_valid(baseline):
        raise ValueError("invalid published baseline; recapture before checking preview routes")
    base = validate_preview_origin(base, hosts)
    matrix = json.loads(config.read_text())["ci"]["assert"]["assertMatrix"]
    urls = []
    for path in sorted(baseline.glob("*.report.json")):
        report = json.loads(path.read_text())
        if not valid_report(report):
            raise ValueError("invalid baseline report")
        route = urlparse(report.get("requestedUrl") or report["finalUrl"])
        url = base.rstrip("/") + (route.path or "/") + ("?" + route.query if route.query else "")
        validate_preview_url(url, hosts)
        if not any(re.search(entry["matchingUrlPattern"], url) and entry.get("assertions") for entry in matrix):
            raise ValueError("a collected route has no applicable assertion")
        if check_access:
            with urllib.request.build_opener(NoRedirect()).open(url, timeout=20) as response:
                if not 200 <= response.status < 300:
                    raise ValueError("preview route did not return a direct successful response")
        urls.append(url)
    if not urls:
        raise ValueError("no baseline routes")
    return urls


def check_results(directory: Path, expected: list, hosts: list) -> None:
    seen = set()
    for path in directory.glob("*.json"):
        report = json.loads(path.read_text())
        if not isinstance(report, dict) or "requestedUrl" not in report:
            continue
        if not valid_report(report):
            raise ValueError("invalid Lighthouse result")
        requested = report["requestedUrl"]
        final = report.get("finalDisplayedUrl") or report.get("finalUrl") or requested
        validate_preview_url(final, hosts)
        if requested not in expected or final != requested:
            raise ValueError("Lighthouse visited an unexpected or redirected route")
        seen.add(requested)
    if seen != set(expected):
        raise ValueError("Lighthouse results do not cover every requested route")


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
    c = sub.add_parser("preview-check")
    c.add_argument("--base-url", required=True)
    c.add_argument("--validate-only", action="store_true")
    c.add_argument("--results-dir", type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "preview-check":
        try:
            hosts = json.loads(os.environ["ALLOWED_HOSTS_JSON"])
            origin = validate_preview_origin(args.base_url, hosts)
            if args.validate_only:
                print(origin)
                return 0
            urls = preview_routes(
                args.base_url,
                Path("ops/lighthouse/baseline"),
                Path(".lighthouserc.json"),
                hosts,
                check_access=args.results_dir is None,
            )
            if args.results_dir:
                check_results(args.results_dir, urls, hosts)
            else:
                print("\n".join(urls))
            return 0
        except (OSError, ValueError, KeyError) as exc:
            print(f"lh_baseline: preview validation failed: {exc}", file=sys.stderr)
            return 1
    if args.cmd == "summarize":
        return summarize(args.raw_dir, args.out_dir)
    if args.cmd == "assertions":
        try:
            existing = (
                json.loads(args.out.read_text())
                if args.out and args.out.exists()
                else None
            )
            text = json.dumps(assertions(args.baseline_dir, existing), indent=2) + "\n"
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
