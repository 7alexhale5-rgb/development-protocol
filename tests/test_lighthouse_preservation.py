"""Public setup composition and preservation controls, without browser/network calls."""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from tests.test_audit_setup import Base, audit_kit, lh_baseline, report


class LighthousePreservationTest(Base):
    def published(self):
        raw = self.root / "raw"
        self.capture_manifest(
            raw, {"home": "https://source.test/", "about": "https://source.test/about"}
        )
        for index, route in enumerate(("home", "about"), 1):
            item = report(
                "https://source.test/" + ("about" if route == "about" else ""), 0.9
            )
            item["fetchTime"] = f"2026-09-30T00:00:{index:02d}Z"
            (raw / f"{route}.1.json").write_text(json.dumps(item))
        base = self.root / "ops/lighthouse/baseline"
        self.assertEqual(self.quiet(lh_baseline.summarize, raw, base)[0], 0)
        return base

    def test_ci_consumers_refuse_incomplete_or_changed_capture(self):
        base = self.published()
        config = self.root / "rc.json"
        config.write_text(json.dumps(lh_baseline.assertions(base)))
        for name in (
            "about.report.json",
            "home.report.json",
            "SUMMARY.md",
            ".capture-proof.json",
        ):
            path = base / name
            original = path.read_bytes()
            with self.subTest(artifact=name):
                if name in ("about.report.json", ".capture-proof.json"):
                    path.unlink()
                else:
                    path.write_bytes(original + b"\n")
                self.assertFalse(lh_baseline.published_baseline_valid(base))
                with self.assertRaisesRegex(ValueError, "published baseline"):
                    lh_baseline.assertions(base)
                with patch.object(lh_baseline.urllib.request, "build_opener") as opener:
                    with self.assertRaisesRegex(ValueError, "published baseline"):
                        lh_baseline.preview_routes(
                            "https://preview.vercel.app", base, config, ["*.vercel.app"]
                        )
                opener.assert_not_called()
                path.write_bytes(original)
                self.assertEqual(
                    len(lh_baseline.assertions(base)["ci"]["assert"]["assertMatrix"]), 2
                )
                self.assertEqual(
                    len(
                        lh_baseline.preview_routes(
                            "https://preview.vercel.app",
                            base,
                            config,
                            ["*.vercel.app"],
                            False,
                        )
                    ),
                    2,
                )

    def test_orchestrator_refuses_lock_before_valid_baseline_skip(self):
        self.pkg()
        base = self.published()
        helper = base.parent / "lh_baseline.py"
        helper.write_bytes(Path(lh_baseline.__file__).read_bytes())
        lock = base.parent / ".baseline.publish-lock"
        lock.mkdir()
        marker = lock / "owner"
        marker.write_text("unfinished publication")
        for dry_run in (False, True):
            for force in (False, True):
                with (
                    self.subTest(dry_run=dry_run, force=force),
                    patch.object(audit_kit, "status") as status,
                    patch.object(audit_kit, "setup_lighthouse") as capture,
                ):
                    code, output = self.quiet(
                        audit_kit.run_all,
                        self.root,
                        only="lighthouse",
                        dry_run=dry_run,
                        force=force,
                    )
                self.assertEqual(code, 1)
                self.assertIn("manual recovery", output)
                status.assert_not_called()
                capture.assert_not_called()
                self.assertEqual(marker.read_text(), "unfinished publication")

    def test_generated_rerun_preserves_locked_raw_capture(self):
        self.pkg()
        self.quiet(
            audit_kit.write_baseline_files, self.root, "https://source.test", "/", 1
        )
        out = self.root / "ops/lighthouse"
        raw = out / "baseline/.raw"
        raw.mkdir(parents=True)
        saved = raw / "retained.1.json"
        saved.write_bytes(b"unique recovery capture")
        lock = out / ".baseline.publish-lock"
        lock.mkdir()
        (lock / "owner").write_text("unfinished publication")
        with tempfile.TemporaryDirectory() as temp:
            bin_dir = Path(temp)
            capture = bin_dir / "capture-called"
            npx = bin_dir / "npx"
            npx.write_text('#!/bin/sh\nprintf capture > "$CAPTURE_MARKER"\nexit 1\n')
            npx.chmod(0o755)
            env = dict(
                os.environ,
                PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                CHROME_PATH="/fixture/chrome",
                CAPTURE_MARKER=str(capture),
            )
            result = subprocess.run(
                ["sh", str(out / "run-baseline.sh")],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("manual recovery", result.stderr)
            self.assertFalse(capture.exists())
        self.assertEqual(saved.read_bytes(), b"unique recovery capture")
        self.assertEqual((lock / "owner").read_text(), "unfinished publication")

    def test_publication_lock_refuses_capture_before_any_dependency_work(self):
        for force in (False, True):
            for has_baseline in (False, True):
                with self.subTest(force=force, has_baseline=has_baseline):
                    root = self.root / f"capture-{force}-{has_baseline}"
                    root.mkdir()
                    (root / "package.json").write_text("{}")
                    lock = root / "ops/lighthouse/.baseline.publish-lock"
                    lock.mkdir(parents=True)
                    marker = lock / "owner"
                    marker.write_text("retained unfinished capture")
                    if has_baseline:
                        base = lock.parent / "baseline"
                        base.mkdir()
                        (base / "home.report.json").write_text(
                            json.dumps(report("https://example.test/", 0.9))
                        )
                    with (
                        patch.object(audit_kit, "require_node18"),
                        patch.object(audit_kit, "node_version", return_value=(22, 19)),
                        patch.object(audit_kit, "ensure_dev") as install,
                        patch.object(audit_kit, "find_chrome") as chrome,
                        patch.object(audit_kit.subprocess, "run") as capture,
                    ):
                        capture.return_value.returncode = 0
                        with self.assertRaisesRegex(
                            audit_kit.SetupError, "publication lock.*manual recovery"
                        ):
                            audit_kit.setup_lighthouse(
                                root, target_url="https://example.test", force=force
                            )
                    install.assert_not_called()
                    chrome.assert_not_called()
                    capture.assert_not_called()
                    self.assertEqual(marker.read_text(), "retained unfinished capture")

    def test_helper_backups_are_reported_and_exclusions_are_deduplicated(self):
        out = self.root / "ops/lighthouse"
        out.mkdir(parents=True)
        custom = "# user exclusion\nprivate-data/"
        (out / ".gitignore").write_text(custom)
        (out / "lh_baseline.py").write_bytes(b"# prior helper\n")
        _, output = self.quiet(
            audit_kit.write_baseline_files, self.root, "https://example.test", "/", 3
        )
        backups = list(out.glob(".audit-setup-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertIn(str(backups[0]), output)
        self.assertEqual(
            (backups[0] / "lh_baseline.py").read_bytes(), b"# prior helper\n"
        )
        first = (out / ".gitignore").read_bytes()
        self.quiet(
            audit_kit.write_baseline_files, self.root, "https://example.test", "/", 3
        )
        self.assertEqual((out / ".gitignore").read_bytes(), first)
        self.assertTrue(first.decode().startswith(custom + "\n"))
        self.assertEqual(first.decode().count(".audit-setup-backup-*/"), 1)

    def test_normal_run_rejects_invalid_existing_baseline(self):
        self.pkg(devDependencies={"lighthouse": "^13"}, scripts={})
        base = self.root / "ops/lighthouse/baseline"
        base.mkdir(parents=True)
        saved = base / "home.report.json"
        saved.write_text(json.dumps(report("https://example.test/", 0.9)))
        original = saved.read_bytes()
        with (
            patch.object(audit_kit, "require_node18"),
            patch.object(audit_kit, "node_version", return_value=(22, 19)),
            patch.object(audit_kit, "ensure_dev") as install,
        ):
            code, _ = self.quiet(audit_kit.run_all, self.root, only="lighthouse")
        self.assertEqual(code, 1)
        self.assertEqual(saved.read_bytes(), original)
        install.assert_not_called()

    def test_replacing_helpers_retains_prior_bytes(self):
        out = self.root / "ops/lighthouse"
        out.mkdir(parents=True)
        prior = {
            "lh_baseline.py": b"# unique prior helper\n",
            "run-baseline.sh": b"# unique prior rerun\n",
        }
        for name, payload in prior.items():
            (out / name).write_bytes(payload)
        audit_kit.write_baseline_files(self.root, "https://example.test", "/", 3)
        for name, payload in prior.items():
            retained = [
                p
                for p in out.rglob(name)
                if p != out / name and p.read_bytes() == payload
            ]
            self.assertTrue(retained, name)
        self.assertIn(".audit-setup-backup-*/", (out / ".gitignore").read_text())

    def test_ci_only_helper_backups_are_ignored(self):
        self.pkg(devDependencies={"@lhci/cli": "^0.14"}, scripts={})
        out = self.root / "ops/lighthouse"
        base = out / "baseline"
        self.publish_baseline(base, {"home": report("https://example.test/", 0.9)})
        old = b"# unique old CI helper\n"
        (out / "lh_baseline.py").write_bytes(old)
        subprocess.run(
            ["git", "init", "-q", str(self.root)], check=True, capture_output=True
        )
        with patch.object(audit_kit, "ensure_dev"):
            self.quiet(audit_kit.lighthouse_ci, self.root, force=True)
        copies = [
            p
            for p in out.rglob("lh_baseline.py")
            if p != out / "lh_baseline.py" and p.read_bytes() == old
        ]
        self.assertEqual(len(copies), 1)
        proc = subprocess.run(
            ["git", "check-ignore", str(copies[0])], cwd=self.root, capture_output=True
        )
        self.assertEqual(proc.returncode, 0)
