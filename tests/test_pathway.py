"""Tests for the pathway router. Run from the repo root: python3 -m unittest discover tests"""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills/pathway/scripts"))
import pathway  # noqa: E402


class PathwayTest(unittest.TestCase):
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
                "release",
                "docs",
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


if __name__ == "__main__":
    unittest.main()
