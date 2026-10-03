"""Tests for the pathway router. Run from the repo root: python3 -m unittest discover tests"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, contextmanager
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills/pathway/scripts"))
import pathway  # noqa: E402


class PathwayTest(unittest.TestCase):
    def test_retained_artifact_provider_preserves_proof_validation(self):
        import shutil

        self.start()
        for name in pathway.load(self.project, "w1")["pathways"]:
            pathway.log(self.project, "w1", name, "ev.md", "true")
        pathway.close(self.project, "w1")
        item = pathway.load(self.project, "w1")
        archive = pathway.archive_directory(self.project, item)
        copies = self.project / "retained-copies"
        copies.mkdir()
        for row in item["pathways"].values():
            if row["status"] == "proved":
                shutil.copyfile(archive / row["sha256"], copies / row["sha256"])
        shutil.rmtree(archive)
        provider = lambda source, sha: copies / sha
        self.assertFalse(pathway.retained_completion(self.project, item))
        self.assertTrue(
            pathway.retained_completion(self.project, item, artifact_provider=provider)
        )
        artifact = next(copies.iterdir())
        original = artifact.read_bytes()
        artifact.write_bytes(b"corrupt")
        self.assertFalse(
            pathway.retained_completion(self.project, item, artifact_provider=provider)
        )
        artifact.write_bytes(original)
        linked = self.project / "linked-proof"
        linked.write_bytes(original)
        artifact.unlink()
        artifact.symlink_to(linked)
        self.assertFalse(
            pathway.retained_completion(self.project, item, artifact_provider=provider)
        )


    def test_stale_release_is_ineligible_while_docs_remain_owed(self):
        self.start(tier="demoable")
        for name in list(pathway.load(self.project, "w1")["pathways"]):
            pathway.log(self.project, "w1", name, "ev.md", "true")
        pathway.cover(self.project, "w1", "release", True, False)
        (self.project / "release.md").write_text("released")
        pathway.log(self.project, "w1", "release", "release.md", "true")
        pathway.cover(self.project, "w1", "docs", True, False)
        (self.project / "release.md").write_text("changed")
        self.assertEqual(pathway.report(self.project, "w1")["recommended_pathway"], "docs")

    def test_documentation_precedes_release_and_closeout_waits_for_itinerary(self):
        self.start()
        for name in pathway.CATALOG:
            if name in ("docs", "release"):
                continue
            if name in pathway.load(self.project, "w1")["pathways"]:
                pathway.log(self.project, "w1", name, "ev.md", "true")
        out = pathway.report(self.project, "w1")
        self.assertEqual(out["recommended_pathway"], "docs")
        self.assertFalse(pathway.close(self.project, "w1")["ok"])
        pathway.log(self.project, "w1", "docs", "ev.md", "true")
        out = pathway.report(self.project, "w1")
        self.assertEqual(out["recommended_pathway"], "release")
        self.assertNotIn("/closeout-stack", out["card"]["execution_stack"])
        pathway.log(self.project, "w1", "release", "ev.md", "true")
        self.assertTrue(pathway.close(self.project, "w1")["closed"])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name).resolve()
        (self.project / "ev.md").write_text("proof\n")

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, goal="Add CSV export for the billing service", tier="live"):
        return pathway.start(self.project, goal, tier, "w1")

    def test_tier_seeds_itinerary_and_goal_words_pull_extras(self):
        r = self.start()
        self.assertEqual(
            r["coverage"]["open"],
            [
                "govern",
                "data",
                "implementation",
                "quality",
                "observability",
                "docs",
                "release",
            ],
        )
        r = pathway.start(self.project, "Redesign the settings page", "demoable", "w2")
        self.assertEqual(
            r["coverage"]["open"], ["govern", "design", "implementation", "quality"]
        )

    def test_same_goal_reuses_open_outcome_instead_of_minting_a_second(self):
        self.start()
        again = pathway.start(self.project, "Add CSV export for the billing service")
        self.assertEqual(again["work_id"], "w1")
        self.assertIn("reusing", again["note"])

    def test_recommends_first_open_in_foundation_order(self):
        r = self.start()
        self.assertEqual(r["recommended_pathway"], "govern")
        self.assertEqual(r["card"]["skill"], "/development-protocol")

    def test_log_needs_passing_verifier(self):
        self.start()
        bad = pathway.log(self.project, "w1", "govern", "ev.md", "false")
        self.assertFalse(bad["ok"])
        self.assertEqual(bad["pathways"]["govern"]["status"], "blocked")
        good = pathway.log(self.project, "w1", "govern", "ev.md", "grep -q proof ev.md")
        self.assertEqual(good["pathways"]["govern"]["status"], "proved")
        self.assertEqual(good["recommended_pathway"], "data")

    def test_verifier_that_rewrites_evidence_is_blocked(self):
        self.start()
        r = pathway.log(self.project, "w1", "govern", "ev.md", "echo more >> ev.md")
        self.assertFalse(r["ok"])
        self.assertEqual(r["pathways"]["govern"]["status"], "blocked")

    def test_changed_evidence_reopens_and_fails_trust(self):
        self.start()
        pathway.log(self.project, "w1", "govern", "ev.md", "true")
        (self.project / "ev.md").write_text("edited\n")
        r = pathway.report(self.project, "w1")
        self.assertEqual(r["trust"], "fail")
        self.assertEqual(r["recommended_pathway"], "govern")
        self.assertEqual(r["suggested_autonomy_tier"], "recommend")
        r = pathway.log(self.project, "w1", "govern", "ev.md", "true")
        self.assertEqual(r["trust"], "pass")

    def test_cover_add_keeps_proofs_and_na_needs_reason(self):
        self.start()
        pathway.log(self.project, "w1", "govern", "ev.md", "true")
        r = pathway.cover(self.project, "w1", "security", add=True, na=False)
        self.assertIn("security", r["coverage"]["open"])
        self.assertEqual(r["pathways"]["govern"]["status"], "proved")
        with self.assertRaises(ValueError):
            pathway.cover(self.project, "w1", "docs", add=False, na=True, reason=" ")
        with self.assertRaises(ValueError):
            pathway.log(self.project, "w1", "field", "ev.md", "true")

    def test_close_blocks_until_every_pathway_closed(self):
        self.start(tier="demoable")
        self.assertFalse(pathway.close(self.project, "w1")["ok"])
        for p in ("govern", "implementation", "quality"):
            pathway.log(self.project, "w1", p, "ev.md", "true")
        pathway.cover(
            self.project, "w1", "data", add=False, na=True, reason="no stored data"
        )
        r = pathway.close(self.project, "w1")
        self.assertTrue(r["closed"])

    def test_autonomy_needs_rate_trust_and_checklist(self):
        self.start(tier="demoable")
        for p in ("govern", "implementation"):
            pathway.log(self.project, "w1", p, "ev.md", "true")
        self.assertEqual(
            pathway.report(self.project, "w1")["suggested_autonomy_tier"], "recommend"
        )
        store = self.project / ".devproto"
        (store / "w1.json").write_text(
            json.dumps({"steps": [{"step_id": "pathway", "status": "passed"}]})
        )
        self.assertEqual(
            pathway.report(self.project, "w1")["suggested_autonomy_tier"],
            "execute-safe",
        )
        (store / "w1.json").write_text(
            json.dumps({"steps": [{"step_id": "build", "status": "blocked"}]})
        )
        self.assertEqual(
            pathway.report(self.project, "w1")["suggested_autonomy_tier"], "recommend"
        )

    def test_pilot_writes_report_and_opens_missing_outcomes(self):
        other = self.project / "b"
        other.mkdir()
        self.start()
        out = self.project / "pilot.md"
        r = pathway.pilot(
            [str(self.project), str(other)], "Harden the release path", str(out)
        )
        self.assertTrue(out.is_file())
        self.assertEqual(len(r["assignments"]), 2)
        self.assertEqual(len(pathway.items(other)), 1)

    def test_cli_exit_codes(self):
        def run():
            with redirect_stdout(io.StringIO()):
                return pathway.main(["--project", str(self.project), "--json", "next"])

        self.assertEqual(run(), 2)
        self.start()
        self.assertEqual(run(), 0)

    def test_json_and_project_flags_work_before_or_after_the_subcommand(self):
        def out(argv):
            buf = io.StringIO()
            with redirect_stdout(buf):
                pathway.main(argv)
            return json.loads(buf.getvalue())

        self.start()
        before = out(["--project", str(self.project), "--json", "next", "--id", "w1"])
        after = out(["next", "--id", "w1", "--json", "--project", str(self.project)])
        mixed = out(["--project", str(self.project), "next", "--id", "w1", "--json"])
        self.assertEqual(before["work_id"], "w1")
        self.assertEqual(after["work_id"], "w1")
        self.assertEqual(mixed["work_id"], "w1")

    def test_log_output_tail_redacts_secrets(self):
        self.start()
        fake_key = "AKIA" + "Q" * 16  # matches the AWS-key pattern, not a real key
        r = pathway.log(
            self.project, "w1", "govern", "ev.md", f"echo TOKEN={fake_key}; false"
        )
        tail = r["pathways"]["govern"]["output_tail"]
        self.assertNotIn(fake_key, tail)
        self.assertIn("REDACTED", tail)

    def test_doctor_finds_skill_files_and_warns_when_sibling_missing(self):
        r = pathway.doctor(self.project)
        self.assertTrue(r["checks"]["skill_file_next_to_script"])
        self.assertTrue(r["checks"]["project_folder_exists"])
        self.assertIn("skill_installed:development-protocol", r["warnings"])
        self.assertTrue(r["warnings"]["skill_installed:development-protocol"])

    def test_doctor_cli_prints_human_readable_lines(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            pathway.main(["--project", str(self.project), "doctor"])
        self.assertIn("PASS  skill_file_next_to_script", buf.getvalue())
        self.assertIn("pathway doctor:", buf.getvalue())

    def test_concurrent_cover_calls_do_not_corrupt_the_store(self):
        # F4: pathway.py reuses devproto's per-store lock, so a batch of writes
        # from separate processes cannot interleave into a torn/lost update.
        self.start()
        import subprocess as sp

        script = str(ROOT / "skills/pathway/scripts/pathway.py")
        procs = [
            sp.Popen(
                [
                    sys.executable,
                    script,
                    "--project",
                    str(self.project),
                    "cover",
                    "--id",
                    "w1",
                    "--pathway",
                    "security",
                    "--na",
                    "--reason",
                    f"reason {i}",
                ],
                stdout=sp.DEVNULL,
                stderr=sp.DEVNULL,
            )
            for i in range(5)
        ]
        for p in procs:
            self.assertEqual(p.wait(), 0)
        final = pathway.report(self.project, "w1")
        self.assertEqual(final["pathways"]["security"]["status"], "na")


    def test_persisted_verifier_command_is_redacted(self):
        self.start()
        fake = "example-bearer-value-123456"
        cmd = "printf '%s' 'Bearer " + fake + "'"
        pathway.log(self.project, "w1", "govern", "ev.md", cmd)
        self.assertNotIn(fake, pathway.item_path(self.project, "w1").read_text())

    def test_report_refresh_holds_store_lock(self):
        self.start()
        held = []
        real_load = pathway.load
        @contextmanager
        def guard(project):
            held.append(True)
            try:
                yield
            finally:
                held.pop()
        def guarded_load(project, work_id):
            self.assertTrue(held, "report loaded state without the store lock")
            return real_load(project, work_id)
        with patch.object(pathway, "_store_lock", guard), patch.object(pathway, "load", guarded_load):
            pathway.report(self.project, "w1")

    def test_slow_verifier_cannot_overwrite_newer_na(self):
        self.start()
        def changed(*args):
            pathway.cover(self.project, "w1", "govern", add=False, na=True, reason="new decision")
            return 0, "ok"
        with patch.object(pathway, "_run_verifier", changed):
            with self.assertRaisesRegex(ValueError, "changed while"):
                pathway.log(self.project, "w1", "govern", "ev.md", "true")
        self.assertEqual(pathway.report(self.project, "w1")["pathways"]["govern"]["status"], "na")

    def test_slow_verifier_cannot_overwrite_newer_block(self):
        self.start()
        def changed(*args):
            with patch.object(pathway, "_run_verifier", return_value=(1, "newer failure")):
                pathway.log(self.project, "w1", "govern", "ev.md", "false")
            return 0, "old success"
        with patch.object(pathway, "_run_verifier", changed):
            with self.assertRaisesRegex(ValueError, "changed while"):
                pathway.log(self.project, "w1", "govern", "ev.md", "true")
        self.assertEqual(pathway.report(self.project, "w1")["pathways"]["govern"]["status"], "blocked")

    def close_demo(self):
        self.start(goal="Write a tiny tool", tier="demoable")
        for name in ("govern", "implementation", "quality"):
            pathway.log(self.project, "w1", name, "ev.md", "true")
        self.assertTrue(pathway.close(self.project, "w1")["closed"])

    def test_later_work_reuses_live_evidence_without_reopening_history(self):
        self.close_demo()
        record = pathway.item_path(self.project, "w1").read_bytes()
        pathway.start(self.project, "Second independent feature", "demoable", "w2")
        (self.project / "ev.md").write_text("new evidence")
        self.assertEqual(pathway.select(self.project, ""), "w2")
        out = pathway.report(self.project, "w1")
        self.assertTrue(out["closed"])
        self.assertTrue(out["historical_receipts_valid"])
        self.assertEqual(pathway.item_path(self.project, "w1").read_bytes(), record)
        archive = self.project / out["completion"]["archive_dir"]
        artifact = next(archive.iterdir())
        content = artifact.read_bytes()
        artifact.unlink()
        self.assertFalse(pathway.report(self.project, "w1")["historical_receipts_valid"])
        self.assertEqual(pathway.item_path(self.project, "w1").read_bytes(), record)
        artifact.write_bytes(content)
        self.assertTrue(pathway.report(self.project, "w1")["historical_receipts_valid"])

    def test_closed_outcome_cannot_be_changed_by_late_verifier(self):
        self.start(goal="Write a tiny tool", tier="demoable")
        for name in ("govern", "implementation", "quality"):
            pathway.log(self.project, "w1", name, "ev.md", "true")
        saved = []
        def late(*args):
            pathway.close(self.project, "w1")
            saved.append(pathway.item_path(self.project, "w1").read_bytes())
            return 0, "old verifier result"
        with patch.object(pathway, "_run_verifier", side_effect=late):
            with self.assertRaisesRegex(ValueError, "historical"):
                pathway.log(self.project, "w1", "govern", "ev.md", "true")
        self.assertEqual(pathway.item_path(self.project, "w1").read_bytes(), saved[0])
        self.assertTrue(pathway.report(self.project, "w1")["historical_receipts_valid"])

    def test_old_verifier_is_rejected_after_close_and_explicit_reopen(self):
        self.start(goal="Write a tiny tool", tier="demoable")
        def old_result(*args):
            with patch.object(pathway, "_run_verifier", return_value=(0, "new result")):
                for name in ("govern", "implementation", "quality"):
                    pathway.log(self.project, "w1", name, "ev.md", "true")
            pathway.close(self.project, "w1")
            pathway.reopen(self.project, "w1", "approved next phase")
            return 0, "result from before close"
        with patch.object(pathway, "_run_verifier", side_effect=old_result):
            with self.assertRaisesRegex(ValueError, "changed while"):
                pathway.log(self.project, "w1", "govern", "ev.md", "true")
        self.assertEqual(pathway.report(self.project, "w1")["pathways"]["govern"]["status"], "open")

    def test_interrupted_archive_can_resume_without_partial_final_blob(self):
        self.start(goal="Write a tiny tool", tier="demoable")
        for name in ("govern", "implementation", "quality"):
            pathway.log(self.project, "w1", name, "ev.md", "true")
        def interrupted(source, destination):
            destination.write(b"partial")
            raise KeyboardInterrupt()
        with patch.object(pathway.shutil, "copyfileobj", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                pathway.close(self.project, "w1")
        self.assertFalse(pathway.report(self.project, "w1")["closed"])
        self.assertTrue(pathway.close(self.project, "w1")["historical_receipts_valid"])

    def test_legacy_closed_claim_without_provenance_is_unverified(self):
        self.close_demo()
        path = pathway.item_path(self.project, "w1")
        record = json.loads(path.read_text())
        record.pop("completion")
        path.write_text(json.dumps(record))
        before = path.read_bytes()
        self.assertFalse(pathway.report(self.project, "w1")["historical_receipts_valid"])
        self.assertFalse(pathway.close(self.project, "w1")["ok"])
        self.assertEqual(path.read_bytes(), before)

    def test_added_coverage_requires_explicit_reopen_of_closed_work(self):
        self.close_demo()
        with self.assertRaisesRegex(ValueError, "reopen"):
            pathway.cover(self.project, "w1", "security", add=True, na=False)
        pathway.reopen(self.project, "w1", "approved new security scope")
        result = pathway.cover(self.project, "w1", "security", add=True, na=False)
        self.assertFalse(result["closed"])
        self.assertEqual(pathway.select(self.project, ""), "w1")

    def test_scope_evidence_ignores_progress_but_tracks_itinerary_changes(self):
        self.start()
        before = pathway.scope(self.project, "w1")
        pathway.log(self.project, "w1", "govern", "ev.md", "true")
        self.assertEqual(before, pathway.scope(self.project, "w1"))
        pathway.cover(self.project, "w1", "security", add=True, na=False)
        self.assertNotEqual(before, pathway.scope(self.project, "w1"))

    def test_legacy_command_is_redacted_when_status_is_read(self):
        self.start()
        item = pathway.load(self.project, "w1")
        item["pathways"]["govern"]["verify"] = "echo AUTH_TOKEN=synthetic-private-value"
        pathway.save(self.project, item)
        pathway.report(self.project, "w1")
        self.assertNotIn("synthetic-private-value", pathway.item_path(self.project, "w1").read_text())

if __name__ == "__main__":
    unittest.main()
