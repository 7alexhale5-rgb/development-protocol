"""Tests for the planning-stack scripts. Run from the repo root: python3 -m unittest discover tests"""

import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills/planning-stack/scripts"
sys.path.insert(0, str(SCRIPTS))
import lens_classify  # noqa: E402
import plan_approval_check  # noqa: E402

ALWAYS = ["adversary", "observability", "reversibility", "economist", "test-strategist"]


class LensClassifyTest(unittest.TestCase):
    def test_always_on_lenses_fire_alone_for_a_plain_goal(self):
        r = lens_classify.classify("Add an export button to the reports page")
        self.assertEqual(r["fired_lenses"], ALWAYS)
        self.assertEqual(r["matches"], {})
        self.assertEqual(r["dropped"], [])

    def test_whole_word_match_only(self):
        # "product" must not fire sre through "prod"; "authorship" must not fire compliance.
        r = lens_classify.classify("Rename the product authorship field")
        self.assertNotIn("sre", r["fired_lenses"])
        self.assertNotIn("compliance", r["fired_lenses"])
        r = lens_classify.classify("Deploy the fix to prod")
        self.assertEqual(r["matches"]["sre"], ["deploy", "prod"])

    def test_plural_counts(self):
        r = lens_classify.classify("Add webhooks for failed payments")
        self.assertEqual(r["matches"]["compliance"], ["payment"])
        self.assertEqual(r["matches"]["concurrency"], ["webhook"])

    def test_irregular_plurals_keep_word_boundaries(self):
        result = lens_classify.classify("libraries and dependencies need retries")
        self.assertEqual(result["matches"].get("supply-chain"), ["library", "dependency"])
        self.assertEqual(result["matches"].get("concurrency"), ["retry"])
        self.assertFalse(lens_classify._hit("retry", "preretries"))

    def test_constraints_text_counts(self):
        r = lens_classify.classify("Speed up reports", "must keep the postgres schema")
        self.assertEqual(r["matches"]["data-integrity"], ["schema", "postgres"])

    def test_cap_drops_weakest_gated_lens(self):
        goal = (
            "deploy to prod with a schema migration on postgres, a webhook retry queue, "
            "a new npm package, and payment card data"
        )
        r = lens_classify.classify(goal)
        self.assertEqual(len(r["fired_lenses"]), lens_classify.MAX_LENSES)
        self.assertEqual(r["fired_lenses"][:5], ALWAYS)
        # sre, supply-chain and compliance tie at 2 hits; ties drop alphabetically.
        self.assertEqual(r["dropped"], ["compliance", "sre"])
        self.assertNotIn("compliance", r["matches"])
        self.assertIn("supply-chain", r["fired_lenses"])

    def test_cli(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(lens_classify.main(["--goal", "add a cron worker"]), 0)
        self.assertIn("concurrency", json.loads(buf.getvalue())["fired_lenses"])
        with redirect_stderr(io.StringIO()):
            self.assertEqual(lens_classify.main(["--goal", "  "]), 1)
            self.assertEqual(
                lens_classify.main(
                    ["--goal", "x", "--constraints-file", "/nonexistent/file"]
                ),
                1,
            )


class PlanApprovalCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        Path("plan.md").write_text("# Plan\n\nDo the thing.\n")
        self.digest = hashlib.sha256(Path("plan.md").read_bytes()).hexdigest()

    def tearDown(self):
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def record(self, **over):
        fields = {
            "plan": "plan.md",
            "sha256": self.digest,
            "approved_by": "Sam",
            "approved_at": "2026-09-29T10:00:00-05:00",
            "words": '"yes, proceed"',
        }
        fields.update(over)
        text = "".join(f"{k}: {v}\n" for k, v in fields.items() if v is not None)
        Path("approval.md").write_text(text)
        return Path("approval.md")

    def test_matching_record_passes(self):
        code, msg = plan_approval_check.check(self.record())
        self.assertEqual(code, 0, msg)

    def test_edited_plan_fails(self):
        rec = self.record()
        with open("plan.md", "a") as f:
            f.write("One more step.\n")
        code, msg = plan_approval_check.check(rec)
        self.assertEqual(code, 1)
        self.assertIn("plan changed since approval", msg)

    def test_missing_fields_fail(self):
        code, msg = plan_approval_check.check(self.record(words='""', approved_by=None))
        self.assertEqual(code, 1)
        self.assertIn("approved_by", msg)
        self.assertIn("words", msg)

    def test_unreadable_plan_or_record_is_exit_2(self):
        self.assertEqual(plan_approval_check.check(self.record(plan="gone.md"))[0], 2)
        self.assertEqual(plan_approval_check.check(Path("no-record.md"))[0], 2)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(plan_approval_check.main([]), 2)

    def test_uppercase_digest_accepted(self):
        self.assertEqual(
            plan_approval_check.check(self.record(sha256=self.digest.upper()))[0], 0
        )


if __name__ == "__main__":
    unittest.main()
