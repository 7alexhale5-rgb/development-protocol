"""Tests for the audit-setup kit. Run from the repo root: python3 -m unittest discover tests

No network, no package installs: install_dev is patched wherever a step would install.
"""

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills/audit-setup"
sys.path.insert(0, str(SKILL / "scripts"))
import audit_kit  # noqa: E402
import lh_baseline  # noqa: E402


def report(url, perf, a11y=1.0, bp=1.0, seo=1.0, form="mobile"):
    return {
        "requestedUrl": url,
        "finalUrl": url,
        "lighthouseVersion": "13.0.0",
        "fetchTime": "2026-09-30T00:00:00Z",
        "environment": {"hostUserAgent": "fixture-browser"},
        "configSettings": {"formFactor": form},
        "categories": {
            "performance": {"score": perf},
            "accessibility": {"score": a11y},
            "best-practices": {"score": bp},
            "seo": {"score": seo},
        },
        "audits": {
            "largest-contentful-paint": {"numericValue": 2100},
            "first-contentful-paint": {"numericValue": 1000},
            "cumulative-layout-shift": {"numericValue": 0.01},
            "total-blocking-time": {"numericValue": 50},
        },
    }


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def pkg(self, **data):
        (self.root / "package.json").write_text(json.dumps(data, indent=2))

    def quiet(self, fn, *a, **kw):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            result = fn(*a, **kw)
        return result, out.getvalue()

    def capture_manifest(self, raw, routes, runs=1):
        raw.mkdir(exist_ok=True)
        (raw / ".expected-routes").write_text(
            "".join(f"{slug}\t{url}\n" for slug, url in routes.items())
        )
        (raw / ".expected-runs").write_text(f"{runs}\n")
        (raw / ".expected-preset").write_text("mobile\n")


class DetectionTest(Base):
    def test_dep_check_ignores_script_values(self):
        self.pkg(scripts={"dead-code": "knip"}, devDependencies={"lighthouse": "^13"})
        self.assertFalse(audit_kit.has_dep(self.root, "knip"))
        self.assertTrue(audit_kit.has_dep(self.root, "lighthouse"))

    def test_package_manager_from_lockfile(self):
        self.assertEqual(audit_kit.detect_pm(self.root), "npm")
        (self.root / "pnpm-lock.yaml").write_text("")
        self.assertEqual(audit_kit.detect_pm(self.root), "pnpm")
        self.assertEqual(audit_kit.pm_run(self.root, "analyze"), "pnpm analyze")

    def test_playwright_test_dir_is_read_from_config(self):
        (self.root / "playwright.config.ts").write_text(
            "export default { testDir: './e2e' }"
        )
        self.assertEqual(audit_kit.playwright_test_dir(self.root), "e2e")
        (self.root / "e2e/a11y").mkdir(parents=True)
        (self.root / "e2e/a11y/smoke.spec.ts").write_text("")
        self.assertTrue(audit_kit.axe_spec_present(self.root))

    def test_routes_skip_dynamic_and_group_folders(self):
        for name in ("about", "[slug]", "(marketing)", "pricing"):
            (self.root / "app" / name).mkdir(parents=True)
            (self.root / "app" / name / "page.tsx").write_text("")
        self.assertEqual(
            audit_kit.detect_routes(self.root), ["/", "/about", "/pricing"]
        )

    def test_routes_default_to_root(self):
        self.assertEqual(audit_kit.detect_routes(self.root), ["/"])

    def test_lighthouse_version_follows_node(self):
        self.assertEqual(audit_kit.lighthouse_pkg((22, 18)), "lighthouse@12.6.1")
        self.assertEqual(audit_kit.lighthouse_pkg((20, 5)), "lighthouse@12.6.1")
        self.assertEqual(audit_kit.lighthouse_pkg((22, 19)), "lighthouse@^13")

    def test_all_workflow_templates_pin_actions_by_sha(self):
        """SKILL.md claims "Actions are pinned by commit SHA." A bare @v5/@v12 tag is
        mutable and defeats that claim; every `uses:` must carry a 40-char SHA."""
        unpinned = []
        for tmpl in (SKILL / "references").glob("*.yml.tmpl"):
            for m in re.finditer(r"uses:\s*(\S+)@(\S+)", tmpl.read_text()):
                ref = m.group(2)
                if not re.fullmatch(r"[0-9a-f]{40}", ref):
                    unpinned.append(f"{tmpl.name}: {m.group(1)}@{ref}")
        self.assertEqual(unpinned, [])

    def test_axe_spec_routes_are_substituted(self):
        starter = (SKILL / "references/axe-playwright-starter.spec.ts").read_text()
        out = audit_kit.render_axe_spec(starter, ["/", "/docs/intro"])
        self.assertIn('{ name: "home", path: "/" },', out)
        self.assertIn('{ name: "docs-intro", path: "/docs/intro" },', out)
        self.assertEqual(out.count("const ROUTES"), 1)

    def test_axe_spec_escapes_hostile_route_names(self):
        """A route name/path containing a quote must not break out of its string
        literal into executable JS. rs-security.md: warn (code injection)."""
        starter = (SKILL / "references/axe-playwright-starter.spec.ts").read_text()
        hostile = "/x'}, {name:'y',path:'/'+require('child_process').execSync('id')+'"
        out = audit_kit.render_axe_spec(starter, [hostile])
        expected_name = hostile.strip("/").replace("/", "-")
        expected_line = (
            f"  {{ name: {json.dumps(expected_name)}, path: {json.dumps(hostile)} }},"
        )
        # Both name and path must appear as one properly escaped JSON string token
        # each, on exactly the line our own renderer emits, never as raw JS breaking
        # out of the literal into a second attacker-controlled object.
        self.assertIn(expected_line, out)
        self.assertEqual(out.count("\n" + expected_line + "\n"), 1)


class BaselineTest(Base):
    def raw(self, slug, run, rep):
        d = self.root / "raw"
        d.mkdir(exist_ok=True)
        rep["fetchTime"] = f"2026-09-30T00:00:{run:02d}Z"
        (d / f"{slug}.{run}.json").write_text(json.dumps(rep))

    def test_summarize_keeps_median_run(self):
        self.capture_manifest(self.root / "raw", {"home": "http://x/"}, 3)
        for i, perf in enumerate((0.5, 0.9, 0.7), 1):
            self.raw("home", i, report("http://x/", perf))
        code, _ = self.quiet(
            lh_baseline.summarize, self.root / "raw", self.root / "out"
        )
        self.assertEqual(code, 0)
        kept = json.loads((self.root / "out/home.report.json").read_text())
        self.assertEqual(kept["categories"]["performance"]["score"], 0.7)
        self.assertIn("| `home` | 3 | 70 |", (self.root / "out/SUMMARY.md").read_text())

    def test_summarize_fails_loudly_with_no_runs(self):
        self.capture_manifest(self.root / "raw", {"home": "http://x/"}, 3)
        code, _ = self.quiet(
            lh_baseline.summarize, self.root / "raw", self.root / "out"
        )
        self.assertEqual(code, 1)

    def test_capture_refuses_incomplete_duplicate_mixed_and_redirected_runs(self):
        raw = self.root / "raw"
        self.capture_manifest(raw, {"home": "https://x.test/"}, 3)
        originals = [report("https://x.test/", score) for score in (0.7, 0.8, 0.9)]
        for i, value in enumerate(originals, 1):
            value["fetchTime"] = f"2026-09-30T00:00:{i:02d}Z"
        for i, value in enumerate(originals, 1):
            (raw / f"home.{i}.json").write_text(json.dumps(value))
        out = self.root / "out"
        self.assertEqual(self.quiet(lh_baseline.summarize, raw, out)[0], 0)
        before = (out / "home.report.json").read_bytes()
        cases = [
            lambda items: items.pop(),
            lambda items: items.__setitem__(1, items[0].copy()),
            lambda items: items[1].update(finalUrl="https://x.test/login"),
            lambda items: items[1].update(finalDisplayedUrl="https://x.test/login"),
            lambda items: items[1]["audits"].pop("first-contentful-paint"),
            lambda items: items[1]["audits"]["total-blocking-time"].update(
                numericValue=float("nan")
            ),
            lambda items: items[1].update(lighthouseVersion="12.0.0"),
            lambda items: items[1]["configSettings"].update(formFactor="desktop"),
            lambda items: [
                item["configSettings"].update(formFactor="desktop") for item in items
            ],
            lambda items: items[1].update(fetchTime=items[0]["fetchTime"]),
            lambda items: items[1].update(fetchTime="invalid"),
        ]
        for mutate in cases:
            with self.subTest(mutate=cases.index(mutate)):
                for path in raw.glob("home.*.json"):
                    path.unlink()
                items = json.loads(json.dumps(originals))
                mutate(items)
                for i, value in enumerate(items, 1):
                    (raw / f"home.{i}.json").write_text(
                        json.dumps(value, sort_keys=(i == 2))
                    )
                self.assertEqual(self.quiet(lh_baseline.summarize, raw, out)[0], 1)
                self.assertEqual((out / "home.report.json").read_bytes(), before)

    def test_capture_refuses_missing_manifest_and_malformed_sibling(self):
        raw = self.root / "raw"
        raw.mkdir()
        (raw / "home.1.json").write_text(json.dumps(report("https://x.test/", 0.8)))
        self.assertEqual(
            self.quiet(lh_baseline.summarize, raw, self.root / "out")[0], 1
        )
        self.capture_manifest(raw, {"home": "https://x.test/"}, 2)
        (raw / "home.2.json").write_text("{bad")
        self.assertEqual(
            self.quiet(lh_baseline.summarize, raw, self.root / "out")[0], 1
        )

    def test_capture_refuses_stale_publication_lock(self):
        raw = self.root / "raw"
        self.capture_manifest(raw, {"home": "https://x.test/"})
        (raw / "home.1.json").write_text(json.dumps(report("https://x.test/", 0.8)))
        lock = self.root / ".out.publish-lock"
        lock.mkdir()
        self.assertEqual(
            self.quiet(lh_baseline.summarize, raw, self.root / "out")[0], 1
        )
        self.assertTrue(lock.exists())

    def test_enforce_scalar_warning_tuple(self):
        path = self.root / "rc.json"
        path.write_text(
            json.dumps({"ci": {"assert": {"assertions": {"custom": ["warn", 0.8]}}}})
        )
        self.assertEqual(self.quiet(lh_baseline.enforce, path)[0], 0)
        self.assertEqual(
            json.loads(path.read_text())["ci"]["assert"]["assertions"]["custom"][0],
            "error",
        )

    def test_assertions_use_requested_url_and_floors(self):
        base = self.root / "b"
        base.mkdir()
        (base / "docs-intro.report.json").write_text(
            json.dumps(report("https://x.test/docs/intro", 0.95, seo=0.9))
        )
        cfg = lh_baseline.assertions(base)
        entry = cfg["ci"]["assert"]["assertMatrix"][0]
        self.assertEqual(entry["matchingUrlPattern"], r"^https?://[^/?#]+/docs/intro$")
        a = entry["assertions"]
        self.assertEqual(a["categories:performance"], ["warn", {"minScore": 0.92}])
        self.assertEqual(a["categories:accessibility"][1]["minScore"], 1.0)
        self.assertEqual(
            a["categories:seo"][1]["minScore"], 0.95
        )  # floor beats baseline - tolerance
        self.assertNotIn("settings", cfg["ci"]["collect"])
        self.assertIn(lh_baseline.SENTINEL, cfg["_comment"])

    def test_desktop_baseline_sets_desktop_preset(self):
        base = self.root / "b"
        base.mkdir()
        (base / "home.report.json").write_text(
            json.dumps(report("https://x.test/", 0.9, form="desktop"))
        )
        self.assertEqual(
            lh_baseline.assertions(base)["ci"]["collect"]["settings"],
            {"preset": "desktop"},
        )

    def test_enforce_flips_warn_to_error(self):
        base = self.root / "b"
        base.mkdir()
        (base / "home.report.json").write_text(
            json.dumps(report("https://x.test/", 0.9))
        )
        rc = self.root / ".lighthouserc.json"
        rc.write_text(json.dumps(lh_baseline.assertions(base)))
        self.quiet(lh_baseline.enforce, rc)
        text = rc.read_text()
        self.assertNotIn('"warn"', text)
        self.assertEqual(text.count('"error"'), 4)

    def test_rerun_script_renders_and_is_posix_sh(self):
        self.pkg(name="x")
        audit_kit.write_baseline_files(
            self.root, "http://localhost:3000", "/ /about", 3
        )
        script = self.root / "ops/lighthouse/run-baseline.sh"
        text = script.read_text()
        self.assertNotIn("__", text.replace("__file__", ""))
        self.assertIn("LH_TARGET_URL", text)
        self.assertIn("TARGET_URL=http://localhost:3000", text)
        self.assertTrue((self.root / "ops/lighthouse/lh_baseline.py").exists())
        self.assertIn(".expected-routes", text)
        self.assertIn(".expected-runs", text)
        self.assertEqual(subprocess.run(["sh", "-n", str(script)]).returncode, 0)
        self.assertEqual(
            subprocess.run(
                ["sh", "-n", str(SKILL / "references/lh-bless.sh.tmpl")]
            ).returncode,
            0,
        )

    def test_rerun_files_preserve_custom_gitignore(self):
        out = self.root / "ops/lighthouse"
        out.mkdir(parents=True)
        (out / ".gitignore").write_text("custom.tmp")
        audit_kit.write_baseline_files(self.root, "https://x.test", "/", 3)
        lines = (out / ".gitignore").read_text().splitlines()
        self.assertIn("custom.tmp", lines)
        self.assertEqual(lines.count("baseline/.raw/"), 1)
        audit_kit.write_baseline_files(self.root, "https://x.test", "/", 3)
        self.assertEqual(
            (out / ".gitignore").read_text().splitlines().count("baseline/.raw/"), 1
        )

    def test_rerun_script_defends_against_shell_injection(self):
        """A hostile --target-url/--routes value must never break out of the quoted
        shell-source position it is substituted into. rs-security.md: critical."""
        self.pkg(name="x")
        hostile_url = 'http://x"; touch INJECTED_URL; x="'
        hostile_routes = "/a'; touch INJECTED_ROUTE; echo '"
        audit_kit.write_baseline_files(self.root, hostile_url, hostile_routes, 3)
        script = self.root / "ops/lighthouse/run-baseline.sh"
        text = script.read_text()
        self.assertEqual(subprocess.run(["sh", "-n", str(script)]).returncode, 0)
        # Isolate just the variable-assignment prelude (before Chrome detection / the
        # Lighthouse loop) and evaluate it standalone: if the injected `touch` ran, the
        # hostile value broke out of its quoting at generation time.
        prelude = text.split("set -eu\n", 1)[1].split("\nHERE=", 1)[0]
        check = subprocess.run(
            ["sh", "-c", prelude + '\nprintf "%s\\036%s" "$TARGET_URL" "$ROUTES"'],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(check.returncode, 0, check.stderr)
        got_url, got_routes = check.stdout.split("\036")
        self.assertEqual(got_url, hostile_url)
        self.assertEqual(got_routes, hostile_routes)
        self.assertFalse((self.root / "INJECTED_URL").exists())
        self.assertFalse((self.root / "INJECTED_ROUTE").exists())

    def test_rejects_target_url_with_embedded_newline(self):
        """R2-1: the comment above the assignments in run-baseline.sh.tmpl contains the
        literal tokens __TARGET_URL__/__ROUTES__, so the old chained str.replace() also
        rewrote that comment. A target URL with a newline then split the comment across
        two lines, and the second line became executable shell on every rerun."""
        self.pkg(name="x")
        hostile_url = "http://x\ntouch pwned; #"
        with self.assertRaises(audit_kit.SetupError):
            audit_kit.write_baseline_files(self.root, hostile_url, "/", 3)
        self.assertFalse((self.root / "pwned").exists())
        self.assertFalse((self.root / "ops/lighthouse/run-baseline.sh").exists())

    def test_rejects_target_url_without_http_scheme(self):
        self.pkg(name="x")
        for bad in ["not-a-url", "ftp://x.test", "javascript:alert(1)", ""]:
            with self.assertRaises(audit_kit.SetupError):
                audit_kit.write_baseline_files(self.root, bad, "/", 3)

    def test_url_containing_placeholder_token_does_not_corrupt_the_script(self):
        """Secondary finding in R2-1: sequential, unanchored str.replace() means a URL
        containing the literal text __ROUTES__ gets rewritten a second time by the
        routes substitution, producing an unbalanced-quote script."""
        self.pkg(name="x")
        url_with_token = "http://example.test/__ROUTES__"
        audit_kit.write_baseline_files(self.root, url_with_token, "/", 3)
        script = self.root / "ops/lighthouse/run-baseline.sh"
        text = script.read_text()
        self.assertEqual(subprocess.run(["sh", "-n", str(script)]).returncode, 0)
        import shlex

        self.assertIn(shlex.quote(url_with_token), text)

    def test_comment_no_longer_carries_the_substitution_tokens(self):
        """The template's own comment must not contain __TARGET_URL__/__ROUTES__ as
        literal substrings, or a blind substitution rewrites the comment too."""
        text = (SKILL / "references/run-baseline.sh.tmpl").read_text()
        self.assertNotIn("__TARGET_URL__", text.split("TARGET_URL=", 1)[0])
        self.assertNotIn("__ROUTES__", text.split("TARGET_URL=", 1)[0])


class QualityCiTest(Base):
    def setUp(self):
        super().setUp()
        # Keep an installed workflow linter from running (and printing) during tests.
        hide = patch.object(audit_kit.shutil, "which", return_value=None)
        hide.start()
        self.addCleanup(hide.stop)

    def test_refuses_without_tests(self):
        self.pkg(scripts={"build": "next build"})
        with self.assertRaises(audit_kit.SetupError):
            self.quiet(audit_kit.quality_ci, self.root, branch="main")

    def test_renders_next_typegen_and_no_blank_step_gaps(self):
        self.pkg(
            scripts={"test": "vitest", "build": "next build"},
            devDependencies={"typescript": "5", "next": "16"},
            engines={"node": ">=20"},
        )
        (self.root / "package-lock.json").write_text("{}")
        self.quiet(audit_kit.quality_ci, self.root, branch="main")
        ci = (self.root / ".github/workflows/ci.yml").read_text()
        self.assertIn(audit_kit.QCI_SENTINEL, ci)
        self.assertIn("npx next typegen", ci)
        self.assertIn('node-version: "20"', ci)
        self.assertIn("run: npm run test", ci)
        self.assertIn("run: npm run build", ci)
        self.assertNotIn("__", ci)
        self.assertNotIn("\n\n      - name", ci)
        self.assertTrue((self.root / ".github/dependabot.yml").exists())

    def test_without_typescript_or_build_steps_are_dropped_cleanly(self):
        self.pkg(scripts={"test": "node --test"})
        self.quiet(audit_kit.quality_ci, self.root, branch="main")
        ci = (self.root / ".github/workflows/ci.yml").read_text()
        self.assertNotIn("TypeScript", ci)
        self.assertNotIn("Production build", ci)
        self.assertNotIn("\n\n      - name", ci)

    def test_hand_written_workflow_is_not_overwritten(self):
        self.pkg(scripts={"test": "vitest"})
        wf = self.root / ".github/workflows/ci.yml"
        wf.parent.mkdir(parents=True)
        wf.write_text("name: mine\n")
        with self.assertRaises(audit_kit.SetupError):
            self.quiet(audit_kit.quality_ci, self.root, branch="main")
        self.assertEqual(wf.read_text(), "name: mine\n")
        self.quiet(audit_kit.quality_ci, self.root, uninstall=True)
        self.assertTrue(wf.exists())

    def test_dry_run_writes_nothing(self):
        self.pkg(scripts={"test": "vitest"})
        self.quiet(audit_kit.quality_ci, self.root, branch="main", dry_run=True)
        self.assertFalse((self.root / ".github").exists())

    def test_yarn_classic_uses_frozen_lockfile_and_level_audit(self):
        self.pkg(scripts={"test": "vitest"})
        (self.root / "yarn.lock").write_text("")
        self.quiet(audit_kit.quality_ci, self.root, branch="main")
        ci = (self.root / ".github/workflows/ci.yml").read_text()
        self.assertIn("run: yarn install --frozen-lockfile", ci)
        self.assertIn("run: yarn audit --level high", ci)

    def test_yarn_berry_uses_immutable_and_npm_audit(self):
        self.pkg(scripts={"test": "vitest"})
        (self.root / "yarn.lock").write_text("")
        (self.root / ".yarnrc.yml").write_text("")
        self.quiet(audit_kit.quality_ci, self.root, branch="main")
        ci = (self.root / ".github/workflows/ci.yml").read_text()
        self.assertIn("run: yarn install --immutable", ci)
        self.assertIn("run: yarn npm audit --severity high", ci)

    def test_bun_branch_uses_bun_run_and_skips_unsupported_cache(self):
        self.pkg(scripts={"test": "vitest"})
        (self.root / "bun.lock").write_text("")
        self.quiet(audit_kit.quality_ci, self.root, branch="main")
        ci = (self.root / ".github/workflows/ci.yml").read_text()
        self.assertIn("run: bun install --frozen-lockfile", ci)
        self.assertIn("run: bun run test", ci)
        self.assertIn("run: bun audit", ci)
        self.assertIn("cache-dependency-path: bun.lock", ci)
        # actions/setup-node has no bun cache support; an explicit empty string is
        # its own documented "no caching" default, not a broken/unsupported value.
        self.assertIn('cache: ""', ci)

    def test_workdir_is_used_in_dependabot_manifest_filter(self):
        (self.root / "web").mkdir()
        (self.root / "web/package.json").write_text(
            json.dumps({"scripts": {"test": "vitest"}})
        )
        self.quiet(audit_kit.quality_ci, self.root, branch="main")
        dam = (self.root / ".github/workflows/dependabot-auto-merge.yml").read_text()
        self.assertIn("^web/package(-lock)?", dam)
        self.assertIn(
            "working-directory: web",
            (self.root / ".github/workflows/ci.yml").read_text(),
        )


class LighthouseCiTest(Base):
    def baseline(self):
        d = self.root / "ops/lighthouse/baseline"
        d.mkdir(parents=True)
        (d / "home.report.json").write_text(json.dumps(report("https://x.test/", 0.9)))

    def test_needs_a_baseline(self):
        self.pkg(name="x")
        with self.assertRaises(audit_kit.SetupError):
            self.quiet(audit_kit.lighthouse_ci, self.root)

    def test_install_writes_owned_files_and_scripts(self):
        self.pkg(name="x")
        self.baseline()
        with patch.object(audit_kit, "install_dev") as install:
            self.quiet(
                audit_kit.lighthouse_ci,
                self.root,
                allow_hosts=["https://*.example.test*"],
            )
        install.assert_called_once_with(self.root, "@lhci/cli")
        wf = (self.root / ".github/workflows/lighthouse-ci.yml").read_text()
        self.assertIn(audit_kit.LHCI_SENTINEL, wf)
        self.assertIn('["*.example.test"]', wf)
        self.assertNotIn("{{DOMAIN_ALLOWLIST}}", wf)
        self.assertIn(
            "npm run lh:bless", (self.root / ".github/ci/README.md").read_text()
        )
        scripts = json.loads((self.root / "package.json").read_text())["scripts"]
        self.assertEqual(scripts["lh:bless"], "sh .github/ci/lh-bless.sh")
        # Uninstall removes what it owns and strips the scripts.
        self.quiet(audit_kit.lighthouse_ci, self.root, uninstall=True)
        self.assertFalse((self.root / ".github/workflows/lighthouse-ci.yml").exists())
        self.assertNotIn(
            "lhci",
            json.loads((self.root / "package.json").read_text()).get("scripts", {}),
        )

    def test_uninstall_keeps_hand_edited_workflow_and_names_it(self):
        wf = self.root / ".github/workflows/lighthouse-ci.yml"
        wf.parent.mkdir(parents=True)
        wf.write_text("name: mine\n")
        result, out = self.quiet(audit_kit.lighthouse_ci, self.root, uninstall=True)
        self.assertTrue(wf.exists())
        self.assertIn(str(wf.relative_to(self.root)), out)

    def test_uninstall_deletes_only_files_carrying_their_own_sentinel(self):
        self.pkg(name="x")
        self.baseline()
        with patch.object(audit_kit, "install_dev"):
            self.quiet(
                audit_kit.lighthouse_ci,
                self.root,
                allow_hosts=["https://*.example.test*"],
            )
        # lh-bless.sh carries its OWN sentinel (distinct from the workflow's), so a
        # hand-edit there must not be caught by checking the workflow's sentinel.
        bless = self.root / ".github/ci/lh-bless.sh"
        bless.write_text("#!/bin/sh\necho hand-edited\n")
        self.quiet(audit_kit.lighthouse_ci, self.root, uninstall=True)
        self.assertFalse((self.root / ".github/workflows/lighthouse-ci.yml").exists())
        self.assertFalse((self.root / ".github/ci/README.md").exists())
        self.assertFalse((self.root / ".lighthouserc.json").exists())
        self.assertTrue(bless.exists())
        self.assertEqual(bless.read_text(), "#!/bin/sh\necho hand-edited\n")

    def test_uninstall_keeps_a_hand_edited_package_json_script(self):
        """R3-6: strip lhci/lh:bless scripts only when their value still
        matches what this skill wrote -- a user's own script under either
        name (pre-existing, or hand-edited after install) must survive."""
        self.pkg(name="x")
        self.baseline()
        with patch.object(audit_kit, "install_dev"):
            self.quiet(
                audit_kit.lighthouse_ci,
                self.root,
                allow_hosts=["https://*.example.test*"],
            )
        pkg_path = self.root / "package.json"
        pkg = json.loads(pkg_path.read_text())
        pkg["scripts"]["lhci"] = "echo my own custom lhci step"
        pkg_path.write_text(json.dumps(pkg, indent=2))

        self.quiet(audit_kit.lighthouse_ci, self.root, uninstall=True)

        scripts = json.loads(pkg_path.read_text()).get("scripts", {})
        self.assertEqual(scripts.get("lhci"), "echo my own custom lhci step")
        # lh:bless was untouched by the user and still matches what was
        # written, so it is still stripped.
        self.assertNotIn("lh:bless", scripts)


class RunTest(Base):
    def test_not_a_node_project(self):
        code, out = self.quiet(audit_kit.run_all, self.root)
        self.assertEqual(code, 2)

    def test_second_run_is_a_no_op_and_keeps_status_file(self):
        self.pkg(name="x", devDependencies={"knip": "6"}, scripts={"dead-code": "knip"})
        (self.root / "knip.json").write_text("{}")
        code, out = self.quiet(audit_kit.run_all, self.root, only="knip")
        self.assertEqual(code, 0)
        self.assertIn("nothing to do", out)
        self.assertFalse((self.root / "ops/audit/STATUS.md").exists())

    def test_canary_catches_a_step_that_produced_nothing(self):
        self.pkg(name="x")
        with patch.object(
            audit_kit, "setup_knip"
        ):  # "succeeds" without writing knip.json
            code, out = self.quiet(audit_kit.run_all, self.root, only="knip")
        self.assertEqual(code, 1)
        status = (self.root / "ops/audit/STATUS.md").read_text()
        self.assertIn("canary knip", status)

    def test_failed_step_is_reported_not_swallowed(self):
        self.pkg(name="x")
        with patch.object(
            audit_kit, "setup_knip", side_effect=audit_kit.SetupError("network down")
        ):
            code, _ = self.quiet(audit_kit.run_all, self.root, only="knip")
        self.assertEqual(code, 1)
        self.assertIn(
            "FAILED: knip (network down)",
            (self.root / "ops/audit/STATUS.md").read_text(),
        )

    def test_dry_run_changes_nothing(self):
        self.pkg(name="x")
        code, out = self.quiet(audit_kit.run_all, self.root, dry_run=True)
        self.assertEqual(code, 0)
        self.assertIn("would set up", out)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["package.json"])

    def test_os_error_in_a_tool_is_caught_with_a_clean_message(self):
        self.pkg(name="x")
        with patch.object(audit_kit, "setup_knip", side_effect=OSError("disk full")):
            code, _ = self.quiet(audit_kit.run_all, self.root, only="knip")
        self.assertEqual(code, 1)
        self.assertIn(
            "FAILED: knip (disk full)",
            (self.root / "ops/audit/STATUS.md").read_text(),
        )


class ReviewDesignAuditTest(Base):
    """review-design-audit M1-M3: status refuses without package.json, a malformed
    package.json is a named error (not a silent {}), OSError per tool in `run` is
    caught cleanly (covered in RunTest)."""

    def test_status_cli_refuses_without_package_json(self):
        code, err = self.quiet(
            audit_kit.main, ["--project-dir", str(self.root), "status"]
        )
        self.assertEqual(code, 2)
        self.assertIn("no package.json", err)

    def test_status_cli_succeeds_with_package_json(self):
        self.pkg(name="x")
        code, out = self.quiet(
            audit_kit.main, ["--project-dir", str(self.root), "status"]
        )
        self.assertEqual(code, 0)
        self.assertIn("Audit Setup", out)

    def test_malformed_package_json_is_a_named_error(self):
        (self.root / "package.json").write_text("{not json")
        with self.assertRaises(audit_kit.SetupError) as ctx:
            audit_kit.read_pkg(self.root)
        self.assertIn("malformed package.json", str(ctx.exception))

    def test_status_cli_reports_malformed_package_json_cleanly(self):
        (self.root / "package.json").write_text("{not json")
        code, err = self.quiet(
            audit_kit.main, ["--project-dir", str(self.root), "status"]
        )
        self.assertEqual(code, 1)
        self.assertIn("malformed package.json", err)

    def test_missing_package_json_is_still_a_quiet_empty_dict(self):
        # Absence is a normal state many callers rely on (a project with no
        # package.json yet); only a malformed file is a named error.
        self.assertEqual(audit_kit.read_pkg(self.root), {})

    def test_project_dir_accepted_before_the_subcommand(self):
        self.pkg(name="x")
        code, out = self.quiet(
            audit_kit.main, ["--project-dir", str(self.root), "status"]
        )
        self.assertEqual(code, 0, out)

    def test_project_dir_accepted_after_the_subcommand(self):
        """SKILL.md's own table shows `KIT status --project-dir <path>`, i.e.
        after the subcommand -- the CLI must accept that order too, not only
        the one before it."""
        self.pkg(name="x")
        code, out = self.quiet(
            audit_kit.main, ["status", "--project-dir", str(self.root)]
        )
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()


class ReviewRegressionTest(Base):
    def baseline(self):
        base = self.root / 'ops/lighthouse/baseline'
        base.mkdir(parents=True, exist_ok=True)
        (base / 'home.report.json').write_text(json.dumps(report('https://preview.vercel.app/', .9)))
        return base

    def test_existing_baseline_requires_valid_report_and_current_helper(self):
        self.pkg()
        raw = self.root / "raw"
        self.capture_manifest(raw, {"home": "https://preview.vercel.app/"})
        (raw / "home.1.json").write_text(
            json.dumps(report("https://preview.vercel.app/", 0.9))
        )
        base = self.root / "ops/lighthouse/baseline"
        self.assertEqual(self.quiet(lh_baseline.summarize, raw, base)[0], 0)
        helper = self.root / "ops/lighthouse/lh_baseline.py"
        helper.parent.mkdir(parents=True, exist_ok=True)
        helper.write_bytes((SKILL / "scripts/lh_baseline.py").read_bytes())
        with patch.object(audit_kit, "require_node18"):
            self.assertIsNone(self.quiet(audit_kit.setup_lighthouse, self.root)[0])
            helper.write_text("stale helper")
            with self.assertRaises(audit_kit.SetupError):
                self.quiet(audit_kit.setup_lighthouse, self.root)
            helper.write_bytes((SKILL / "scripts/lh_baseline.py").read_bytes())
            broken = report("https://preview.vercel.app/", 0.9)
            broken["finalUrl"] = "https://preview.vercel.app/login"
            (base / "home.report.json").write_text(json.dumps(broken))
            with self.assertRaises(audit_kit.SetupError):
                self.quiet(audit_kit.setup_lighthouse, self.root)
            (base / "home.report.json").write_text("{bad")
            with self.assertRaises(audit_kit.SetupError):
                self.quiet(audit_kit.setup_lighthouse, self.root)

    def test_existing_baseline_refuses_deleted_or_mutated_report(self):
        self.pkg()
        raw = self.root / "raw"
        self.capture_manifest(raw, {"home": "https://preview.vercel.app/"})
        (raw / "home.1.json").write_text(
            json.dumps(report("https://preview.vercel.app/", 0.9))
        )
        base = self.root / "ops/lighthouse/baseline"
        self.assertEqual(self.quiet(lh_baseline.summarize, raw, base)[0], 0)
        helper = self.root / "ops/lighthouse/lh_baseline.py"
        helper.parent.mkdir(parents=True, exist_ok=True)
        helper.write_bytes((SKILL / "scripts/lh_baseline.py").read_bytes())
        report_path = base / "home.report.json"
        original = report_path.read_bytes()
        with (
            patch.object(audit_kit, "require_node18"),
            patch.object(audit_kit, "ensure_dev") as install,
        ):
            report_path.write_text(
                json.dumps(report("https://preview.vercel.app/", 0.8))
            )
            with self.assertRaises(audit_kit.SetupError):
                self.quiet(audit_kit.setup_lighthouse, self.root)
            report_path.unlink()
            with self.assertRaises(audit_kit.SetupError):
                self.quiet(audit_kit.setup_lighthouse, self.root)
            report_path.write_bytes(original)
            (base / ".capture-proof.json").unlink(missing_ok=True)
            with self.assertRaises(audit_kit.SetupError):
                self.quiet(audit_kit.setup_lighthouse, self.root)
        install.assert_not_called()

    def test_ci_refuses_stale_owned_helper_before_workflow(self):
        self.pkg()
        self.baseline()
        helper = self.root / "ops/lighthouse/lh_baseline.py"
        helper.parent.mkdir(parents=True, exist_ok=True)
        helper.write_text('"""Lighthouse baseline helper."""\n# preview-check\n')
        with patch.object(audit_kit, "ensure_dev") as install:
            with self.assertRaises(audit_kit.SetupError):
                self.quiet(audit_kit.lighthouse_ci, self.root)
        install.assert_not_called()
        self.assertFalse((self.root / ".github/workflows/lighthouse-ci.yml").exists())

    def test_uninstall_dry_runs_preserve_files_and_scripts(self):
        self.pkg(scripts={'lhci': 'lhci autorun', 'lh:bless': 'sh .github/ci/lh-bless.sh'})
        paths = {'.github/workflows/ci.yml': audit_kit.QCI_SENTINEL,
                 '.github/workflows/dependabot-auto-merge.yml': audit_kit.QCI_SENTINEL,
                 '.github/workflows/lighthouse-ci.yml': audit_kit.LHCI_SENTINEL,
                 '.github/ci/lh-bless.sh': audit_kit.LH_BLESS_SENTINEL,
                 '.github/ci/README.md': audit_kit.LHCI_SENTINEL,
                 '.lighthouserc.json': audit_kit.LHCI_SENTINEL}
        for name, text in paths.items():
            p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.quiet(audit_kit.quality_ci, self.root, uninstall=True, dry_run=True)
        self.quiet(audit_kit.lighthouse_ci, self.root, uninstall=True, dry_run=True)
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_lighthouse_refuses_unowned_sibling_before_install(self):
        self.pkg(); self.baseline()
        p = self.root / '.lighthouserc.json'; p.write_text('{"custom": true}')
        with patch.object(audit_kit, 'ensure_dev') as install:
            with self.assertRaises(audit_kit.SetupError):
                self.quiet(audit_kit.lighthouse_ci, self.root)
        install.assert_not_called()
        self.assertEqual(p.read_text(), '{"custom": true}')

    def test_refresh_keeps_enforcement_and_custom_configuration(self):
        base = self.baseline(); rc = self.root / '.lighthouserc.json'
        old = lh_baseline.assertions(base)
        old['ci']['collect']['numberOfRuns'] = 7
        old['ci']['assert']['assertMatrix'][0]['assertions']['categories:performance'][0] = 'error'
        old['ci']['upload'] = {'target': 'filesystem', 'outputDir': 'private-results'}
        rc.write_text(json.dumps(old))
        self.assertEqual(lh_baseline.main(['assertions', '--baseline-dir', str(base), '--out', str(rc)]), 0)
        new = json.loads(rc.read_text())
        self.assertEqual(new['ci']['assert']['assertMatrix'][0]['assertions']['categories:performance'][0], 'error')
        self.assertEqual(new['ci']['collect']['numberOfRuns'], 7)
        self.assertEqual(new['ci']['upload'], old['ci']['upload'])

    def test_query_assertion_matches_only_the_requested_route(self):
        base = self.baseline()
        (base / 'home.report.json').write_text(json.dumps(report('https://x.test/search?q=term', .9)))
        pattern = lh_baseline.assertions(base)['ci']['assert']['assertMatrix'][0]['matchingUrlPattern']
        self.assertIsNotNone(re.search(pattern, 'https://preview.vercel.app/search?q=term'))
        self.assertIsNone(re.search(pattern, 'https://preview.vercel.app/other/search?q=term'))
        self.assertIsNone(re.search(pattern, 'https://search?q=term'))

    def test_complete_capture_replaces_obsolete_reports_and_preserves_other_files(self):
        base = self.baseline()
        (base / "old.report.json").write_text(json.dumps(report("https://x/old", 0.9)))
        (base / "notes.txt").write_text("keep")
        raw = self.root / "raw"
        self.capture_manifest(raw, {"home": "https://x/"})
        (raw / "home.1.json").write_text(json.dumps(report("https://x/", 0.8)))
        self.assertEqual(lh_baseline.summarize(raw, base), 0)
        self.assertFalse((base / "old.report.json").exists())
        self.assertEqual((base / "notes.txt").read_text(), "keep")

    def test_invalid_report_does_not_replace_previous_capture(self):
        base = self.baseline()
        before = (base / "home.report.json").read_bytes()
        raw = self.root / "raw"
        self.capture_manifest(raw, {"home": "https://x/"})
        bad = report("https://x/", None)
        bad["runtimeError"] = {"code": "NO_FCP"}
        (raw / "home.1.json").write_text(json.dumps(bad))
        self.assertEqual(lh_baseline.summarize(raw, base), 1)
        self.assertEqual((base / "home.report.json").read_bytes(), before)

    def test_partial_knip_is_missing(self):
        self.pkg(devDependencies={'knip': '^6'})
        self.assertTrue(audit_kit.missing(self.root, 'knip'))

    def test_partial_quality_ci_repairs_only_missing_companion(self):
        self.pkg(scripts={'test': 'node --test'})
        p = self.root / '.github/workflows/ci.yml'; p.parent.mkdir(parents=True)
        p.write_text('# ' + audit_kit.QCI_SENTINEL + '\ncustom-owned-content\n')
        before = p.read_bytes()
        self.assertTrue(audit_kit.missing(self.root, 'quality-ci'))
        self.quiet(audit_kit.quality_ci, self.root)
        self.assertEqual(p.read_bytes(), before)
        self.assertTrue((p.parent / 'dependabot-auto-merge.yml').exists())

    def test_run_quality_ci_reaches_nested_package(self):
        (self.root / 'web').mkdir()
        (self.root / 'web/package.json').write_text(json.dumps({'scripts': {'test': 'node --test'}}))
        code, _ = self.quiet(audit_kit.run_all, self.root, only='quality-ci', dry_run=True)
        self.assertEqual(code, 0)

    def test_axe_starter_uses_configured_base_url(self):
        text = (SKILL / 'references/axe-playwright-starter.spec.ts').read_text()
        self.assertIn('page.goto(route.path,', text)
        self.assertNotIn('http://localhost:3000', text)

    def test_dependabot_merge_is_bound_to_checked_sha(self):
        text = (SKILL / 'references/dependabot-auto-merge.yml.tmpl').read_text()
        self.assertIn('--match-head-commit "$HEAD_SHA"', text)
        self.assertIn('headRefOid', text)

    def test_preview_host_boundaries_and_credentials(self):
        for url in ['https://preview.vercel.app.attacker.example/', 'https://preview.vercel.app@127.0.0.1/', 'https://preview.vercel.app/\n']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                lh_baseline.validate_preview_url(url, ['*.vercel.app'])
        lh_baseline.validate_preview_url('https://preview.vercel.app/', ['*.vercel.app'])

    def test_capture_route_names_do_not_collide(self):
        audit_kit.write_baseline_files(
            self.root, "https://x.test", "/ /home /docs/intro /docs-intro", 1
        )
        binary = self.root / "bin"
        binary.mkdir()
        stub = binary / "npx"
        stub.write_text(
            "#!/usr/bin/env python3\nimport sys,json,os,hashlib\nargs=sys.argv[1:]\np=next(a.split('=',1)[1] for a in args if a.startswith('--output-path='))\nr=json.loads(os.environ['FIXTURE_REPORT'])\nr['requestedUrl']=args[2]\nr['finalUrl']=args[2]\nr['fetchTime']='2026-09-30T00:00:00.'+str(int(hashlib.sha256(args[2].encode()).hexdigest()[:6],16)%1000000).zfill(6)+'Z'\nopen(p,'w').write(json.dumps(r))\n"
        )
        stub.chmod(0o755)
        env = dict(
            os.environ,
            PATH=str(binary) + os.pathsep + os.environ["PATH"],
            CHROME_PATH=sys.executable,
            FIXTURE_REPORT=json.dumps(report("https://x/", 0.9)),
        )
        for key in ("LH_TARGET_URL", "LH_ROUTES", "LH_RUNS"):
            env.pop(key, None)
        result = subprocess.run(
            ["sh", "ops/lighthouse/run-baseline.sh"],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(audit_kit.baseline_count(self.root), 4)

    def test_failed_capture_command_cannot_publish_written_report(self):
        audit_kit.write_baseline_files(self.root, "https://x.test", "/", 1)
        binary = self.root / "bin"
        binary.mkdir()
        stub = binary / "npx"
        stub.write_text(
            '#!/bin/sh\nfor arg do case "$arg" in --output-path=*) file=${arg#--output-path=}; printf "%s" "{}" > "$file";; esac; done\nexit 7\n'
        )
        stub.chmod(0o755)
        env = dict(
            os.environ,
            PATH=str(binary) + os.pathsep + os.environ["PATH"],
            CHROME_PATH=sys.executable,
        )
        for key in ("LH_TARGET_URL", "LH_ROUTES", "LH_RUNS"):
            env.pop(key, None)
        result = subprocess.run(
            ["sh", "ops/lighthouse/run-baseline.sh"],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(audit_kit.baseline_count(self.root), 0)

    def test_explicit_capture_arguments_override_environment(self):
        self.pkg()
        def capture(*args, **kwargs):
            self.assertEqual(kwargs['env']['LH_TARGET_URL'], 'https://staging.test')
            self.assertEqual(kwargs['env']['LH_ROUTES'], '/chosen')
            self.assertEqual(kwargs['env']['LH_RUNS'], '2')
            self.baseline()
            return subprocess.CompletedProcess(args, 0)
        with patch.dict(os.environ, {'LH_TARGET_URL': 'https://prod.test', 'LH_ROUTES': '/wrong', 'LH_RUNS': '9'}), \
             patch.object(audit_kit, 'require_node18'), patch.object(audit_kit, 'ensure_dev'), \
             patch.object(audit_kit, 'node_version', return_value=(22, 19)), \
             patch.object(audit_kit, 'find_chrome', return_value='/fixture/chrome'), \
             patch.object(audit_kit.subprocess, 'run', side_effect=capture):
            self.quiet(audit_kit.setup_lighthouse, self.root, 'https://staging.test', '/chosen', 2)

    def test_playwright_managed_chromium_is_found(self):
        executable = self.root / 'chromium'; executable.write_text('fixture')
        with patch.dict(os.environ, {'CHROME_PATH': ''}), patch.object(Path, 'exists', return_value=False), \
             patch.object(audit_kit.shutil, 'which', return_value=None), \
             patch.object(audit_kit.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, str(executable)+'\n')):
            self.assertEqual(audit_kit.find_chrome(self.root), str(executable))

    def test_preview_missing_assertion_and_redirected_result_fail(self):
        base = self.baseline(); rc = self.root / '.lighthouserc.json'
        rc.write_text(json.dumps(lh_baseline.assertions(base)))
        expected = lh_baseline.preview_routes('https://preview.vercel.app', base, rc, ['*.vercel.app'], False)
        self.assertEqual(expected, ['https://preview.vercel.app/'])
        results = self.root / 'results'; results.mkdir()
        rep = report(expected[0], .9); rep['finalUrl'] = 'https://preview.vercel.app/login'
        (results / 'lhr.json').write_text(json.dumps(rep))
        with self.assertRaises(ValueError):
            lh_baseline.check_results(results, expected, ['*.vercel.app'])
        self.assertIsNone(lh_baseline.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere.test'))
        cfg = json.loads(rc.read_text()); cfg['ci']['assert']['assertMatrix'] = []; rc.write_text(json.dumps(cfg))
        with self.assertRaises(ValueError):
            lh_baseline.preview_routes('https://preview.vercel.app', base, rc, ['*.vercel.app'], False)

    def test_route_with_no_valid_runs_preserves_entire_previous_set(self):
        base = self.baseline(); old = (base / 'home.report.json').read_bytes()
        raw = self.root / 'raw'; raw.mkdir()
        (raw / '.expected-slugs').write_text('home\nabout\n')
        (raw / 'home.1.json').write_text(json.dumps(report('https://x/', .9)))
        self.assertEqual(lh_baseline.summarize(raw, base), 1)
        self.assertEqual((base / 'home.report.json').read_bytes(), old)
