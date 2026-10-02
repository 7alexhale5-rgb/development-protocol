"""A work review cannot lose its recorded pre-build scope."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/review-stack/scripts/verify_review.py"

class ReviewScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        def commit(message):
            subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--allow-empty", "-qm", message], check=True)
            return subprocess.check_output(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True).strip()
        self.base = commit("before build")
        self.head = commit("committed during build")
        self.proof = self.repo / ".devproto/evidence/job-build-base.txt"
        self.proof.parent.mkdir(parents=True)
        self.proof.write_text(f"base {self.base}\nwork-id job\n")
        self.data = {"commit": self.head, "base": self.base, "work_id": "job", "verdict": "SHIP_IT", "gate": "PASS", "findings": [], "criteria": [{"verdict": "PASS", "evidence": "executed behavior test"}]}
    def run_check(self, scoped=True):
        report = self.repo / "review.json"
        report.write_text(json.dumps(self.data))
        args = [sys.executable, str(SCRIPT), str(report), "--commit", self.head, "--project", str(self.repo)]
        if scoped:
            args += ["--work-id", "job"]
        return subprocess.run(args, capture_output=True, text=True)
    def test_complete_recorded_scope_passes(self):
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
    def test_missing_baseline_fails(self):
        self.proof.unlink()
        self.assertNotEqual(self.run_check().returncode, 0)
    def test_committed_middle_cannot_be_omitted(self):
        self.data["base"] = self.head
        self.assertNotEqual(self.run_check().returncode, 0)
    def test_missing_report_scope_fails(self):
        self.data.pop("base")
        self.assertNotEqual(self.run_check().returncode, 0)
    def test_wrong_work_id_fails(self):
        self.data["work_id"] = "other"
        self.assertNotEqual(self.run_check().returncode, 0)
    def test_duplicate_baseline_fields_fail(self):
        self.proof.write_text(f"base {self.base}\nbase {self.head}\nwork-id job\n")
        self.assertNotEqual(self.run_check().returncode, 0)
    def test_noncommit_baseline_fails(self):
        self.proof.write_text("base " + "a" * 40 + "\nwork-id job\n")
        self.data["base"] = "a" * 40
        self.assertNotEqual(self.run_check().returncode, 0)
    def test_scoped_report_cannot_downgrade_to_ad_hoc(self):
        self.assertNotEqual(self.run_check(scoped=False).returncode, 0)
    def test_work_baseline_cannot_be_hidden_by_stripping_report_fields(self):
        self.data.pop("base")
        self.data.pop("work_id")
        self.assertNotEqual(self.run_check(scoped=False).returncode, 0)
    def test_genuine_ad_hoc_review_passes(self):
        self.proof.unlink()
        self.data.pop("base")
        self.data.pop("work_id")
        r = self.run_check(scoped=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

if __name__ == "__main__":
    unittest.main()
