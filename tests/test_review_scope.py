"""A work review cannot lose its recorded pre-build scope."""
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
    def seal_snapshot(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--snapshot", "--project", str(self.repo)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.data["candidate_sha256"] = result.stdout.strip()
    def run_check(self, scoped=True):
        if "candidate_sha256" not in self.data:
            self.seal_snapshot()
        report = self.proof.parent / "review.json"
        report.write_text(json.dumps(self.data))
        args = [sys.executable, str(SCRIPT), str(report), "--commit", self.head, "--project", str(self.repo)]
        if scoped:
            args += ["--work-id", "job"]
        return subprocess.run(args, capture_output=True, text=True)
    def test_uncommitted_change_invalidates_review(self):
        reviewed = self.repo / "implementation.py"
        reviewed.write_text("answer = 1\n")
        first = self.run_check()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        reviewed.write_text("answer = 2\n")
        self.assertNotEqual(self.run_check().returncode, 0)
    def test_all_supported_work_id_prefixes(self):
        for identifier in ("_repair", ".repair", "-repair"):
            with self.subTest(identifier=identifier):
                self.proof.unlink()
                self.proof = self.proof.parent / f"{identifier}-build-base.txt"
                self.proof.write_text(f"base {self.base}\nwork-id {identifier}\n")
                self.data["work_id"] = identifier
                self.seal_snapshot()
                report = self.proof.parent / "review.json"
                report.write_text(json.dumps(self.data))
                r = subprocess.run([sys.executable, str(SCRIPT), str(report), "--commit", self.head, "--project", str(self.repo), "--work-id=" + identifier], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
    def test_same_head_with_uncommitted_work_is_a_valid_scope(self):
        self.proof.write_text(f"base {self.head}\nwork-id job\n")
        self.data["base"] = self.head
        (self.repo / "new.py").write_text("answer = 1\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
    def test_unrelated_baseline_commit_fails(self):
        subprocess.run(["git", "-C", str(self.repo), "checkout", "--orphan", "unrelated"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--allow-empty", "-qm", "unrelated"], check=True)
        unrelated = subprocess.check_output(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True).strip()
        subprocess.run(["git", "-C", str(self.repo), "checkout", "--detach", self.head], check=True, capture_output=True)
        self.proof.write_text(f"base {unrelated}\nwork-id job\n")
        self.data["base"] = unrelated
        self.assertNotEqual(self.run_check().returncode, 0)
    def test_open_legacy_record_without_baseline_blocks_ad_hoc(self):
        self.proof.unlink()
        (self.repo / ".devproto/job.json").write_text(json.dumps({"work_id": "job", "steps": [{"step_id": "build", "status": "pending"}]}))
        self.data.pop("base")
        self.data.pop("work_id")
        self.assertNotEqual(self.run_check(scoped=False).returncode, 0)
    def test_staged_content_changed_behind_restored_worktree_invalidates_review(self):
        target = self.repo / "source.py"
        target.write_text("answer = 1\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "source.py"], check=True)
        self.assertEqual(self.run_check().returncode, 0)
        target.write_text("answer = 2\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "source.py"], check=True)
        target.write_text("answer = 1\n")
        self.assertNotEqual(self.run_check().returncode, 0)
    def test_index_only_mode_change_invalidates_review(self):
        target = self.repo / "source.py"
        target.write_text("answer = 1\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "source.py"], check=True)
        self.assertEqual(self.run_check().returncode, 0)
        subprocess.run(["git", "-C", str(self.repo), "update-index", "--chmod=+x", "source.py"], check=True)
        self.assertNotEqual(self.run_check().returncode, 0)
    def test_file_to_directory_replacement_is_supported(self):
        target = self.repo / "config"
        target.write_text("old config\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "config"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-qm", "file config"], check=True)
        self.head = subprocess.check_output(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True).strip()
        self.data["commit"] = self.head
        target.unlink()
        target.mkdir()
        (target / "settings.json").write_text("{}\n")
        self.assertEqual(self.run_check().returncode, 0)
    def test_final_commit_requires_and_accepts_renewed_review(self):
        target = self.repo / "source.py"
        target.write_text("answer = 1\n")
        self.assertEqual(self.run_check().returncode, 0)
        subprocess.run(["git", "-C", str(self.repo), "add", "source.py"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-qm", "final candidate"], check=True)
        self.head = subprocess.check_output(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True).strip()
        self.assertNotEqual(self.run_check().returncode, 0, "precommit review cannot certify changed HEAD")
        self.data["commit"] = self.head
        self.seal_snapshot()  # Simulate a new independent review of the final package.
        self.assertEqual(self.run_check().returncode, 0)
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
    def test_completed_work_does_not_prevent_new_ad_hoc_review(self):
        record = self.repo / ".devproto/job.json"
        record.write_text(json.dumps({"work_id": "job", "steps": [{"step_id": "closeout", "status": "passed"}]}))
        self.data.pop("base")
        self.data.pop("work_id")
        r = self.run_check(scoped=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
    def test_genuine_ad_hoc_review_passes(self):
        self.proof.unlink()
        self.data.pop("base")
        self.data.pop("work_id")
        r = self.run_check(scoped=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

if __name__ == "__main__":
    unittest.main()
