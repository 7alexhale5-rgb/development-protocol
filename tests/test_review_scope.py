"""A work review cannot lose its recorded pre-build scope."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/review-stack/scripts/verify_review.py"
sys.path.insert(0, str(ROOT / "skills/development-protocol/scripts"))
from devproto import STEP_IDS


class ReviewScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

        def commit(message):
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.repo),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.test",
                    "commit",
                    "--allow-empty",
                    "-qm",
                    message,
                ],
                check=True,
            )
            return subprocess.check_output(
                ["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True
            ).strip()

        self.base = commit("before build")
        self.head = commit("committed during build")
        self.proof = self.repo / ".devproto/evidence/job-build-base.txt"
        self.proof.parent.mkdir(parents=True)
        self.proof.write_text(f"base {self.base}\nwork-id job\n")
        self.data = {
            "commit": self.head,
            "base": self.base,
            "work_id": "job",
            "verdict": "SHIP_IT",
            "gate": "PASS",
            "findings": [],
            "criteria": [{"verdict": "PASS", "evidence": "executed behavior test"}],
        }

    def seal_snapshot(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--snapshot", "--project", str(self.repo)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.data["candidate_sha256"] = result.stdout.strip()

    def run_check(self, scoped=True):
        if "candidate_sha256" not in self.data:
            self.seal_snapshot()
        report = self.proof.parent / "review.json"
        report.write_text(json.dumps(self.data))
        args = [
            sys.executable,
            str(SCRIPT),
            str(report),
            "--commit",
            self.head,
            "--project",
            str(self.repo),
        ]
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
                r = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        str(report),
                        "--commit",
                        self.head,
                        "--project",
                        str(self.repo),
                        "--work-id=" + identifier,
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_same_head_with_uncommitted_work_is_a_valid_scope(self):
        self.proof.write_text(f"base {self.head}\nwork-id job\n")
        self.data["base"] = self.head
        (self.repo / "new.py").write_text("answer = 1\n")
        r = self.run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_unrelated_baseline_commit_fails(self):
        subprocess.run(
            ["git", "-C", str(self.repo), "checkout", "--orphan", "unrelated"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.test",
                "commit",
                "--allow-empty",
                "-qm",
                "unrelated",
            ],
            check=True,
        )
        unrelated = subprocess.check_output(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True
        ).strip()
        subprocess.run(
            ["git", "-C", str(self.repo), "checkout", "--detach", self.head],
            check=True,
            capture_output=True,
        )
        self.proof.write_text(f"base {unrelated}\nwork-id job\n")
        self.data["base"] = unrelated
        self.assertNotEqual(self.run_check().returncode, 0)

    def test_open_legacy_record_without_baseline_blocks_ad_hoc(self):
        self.proof.unlink()
        (self.repo / ".devproto/job.json").write_text(
            json.dumps(
                {"work_id": "job", "steps": [{"step_id": "build", "status": "pending"}]}
            )
        )
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
        subprocess.run(
            ["git", "-C", str(self.repo), "update-index", "--chmod=+x", "source.py"],
            check=True,
        )
        self.assertNotEqual(self.run_check().returncode, 0)

    def test_file_to_directory_replacement_is_supported(self):
        target = self.repo / "config"
        target.write_text("old config\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "config"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.test",
                "commit",
                "-qm",
                "file config",
            ],
            check=True,
        )
        self.head = subprocess.check_output(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True
        ).strip()
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
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.test",
                "commit",
                "-qm",
                "final candidate",
            ],
            check=True,
        )
        self.head = subprocess.check_output(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True
        ).strip()
        self.assertNotEqual(
            self.run_check().returncode,
            0,
            "precommit review cannot certify changed HEAD",
        )
        self.data["commit"] = self.head
        self.seal_snapshot()  # Simulate a new independent review of the final package.
        self.assertEqual(self.run_check().returncode, 0)

    def test_intervening_empty_commit_invalidates_stale_requested_commit(self):
        self.assertEqual(self.run_check().returncode, 0)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.test",
                "commit",
                "--allow-empty",
                "-qm",
                "intervening identity change",
            ],
            check=True,
        )
        self.assertNotEqual(
            self.run_check().returncode,
            0,
            "unchanged tree cannot certify a stale requested commit",
        )

    def test_present_report_branch_must_match_current_branch(self):
        self.data["branch"] = "refs/heads/not-the-current-branch"
        self.assertNotEqual(self.run_check().returncode, 0)

    def test_matching_report_branch_and_detached_identity_are_supported(self):
        self.data["branch"] = subprocess.check_output(
            ["git", "-C", str(self.repo), "symbolic-ref", "HEAD"], text=True
        ).strip()
        self.assertEqual(self.run_check().returncode, 0)
        subprocess.run(
            ["git", "-C", str(self.repo), "checkout", "--detach", self.head],
            check=True,
            capture_output=True,
        )
        self.data["branch"] = None
        self.assertEqual(self.run_check().returncode, 0)

    def test_identity_change_during_standalone_validation_fails(self):
        import importlib.util
        from unittest.mock import patch

        for mutation in ("empty-commit", "branch"):
            with self.subTest(mutation=mutation):
                self.head = subprocess.check_output(
                    ["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True
                ).strip()
                self.data["commit"] = self.head
                self.seal_snapshot()
                report = self.proof.parent / "review.json"
                report.write_text(json.dumps(self.data))
                spec = importlib.util.spec_from_file_location(
                    "standalone_review_identity", SCRIPT
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                original_snapshot = module.candidate_snapshot

                def changed_identity(project):
                    snapshot = original_snapshot(project)
                    if mutation == "empty-commit":
                        subprocess.run(
                            [
                                "git",
                                "-C",
                                str(project),
                                "-c",
                                "user.name=Fixture",
                                "-c",
                                "user.email=fixture@example.test",
                                "commit",
                                "--allow-empty",
                                "-qm",
                                "during verification",
                            ],
                            check=True,
                        )
                    else:
                        subprocess.run(
                            [
                                "git",
                                "-C",
                                str(project),
                                "checkout",
                                "-qb",
                                "intervening-branch",
                            ],
                            check=True,
                        )
                    return snapshot

                argv = [
                    str(SCRIPT),
                    str(report),
                    "--commit",
                    self.head,
                    "--project",
                    str(self.repo),
                    "--work-id",
                    "job",
                ]
                with (
                    patch.object(
                        module, "candidate_snapshot", side_effect=changed_identity
                    ),
                    patch.object(sys, "argv", argv),
                ):
                    self.assertEqual(
                        module.main(),
                        1,
                        "identity changes during verification must fail",
                    )

    def test_closeout_only_record_is_unknown_not_closed(self):
        (self.repo / ".devproto/job.json").write_text(
            json.dumps(
                {
                    "work_id": "job",
                    "steps": [{"step_id": "closeout", "status": "passed"}],
                }
            )
        )
        self.data.pop("base")
        self.data.pop("work_id")
        self.assertNotEqual(self.run_check(scoped=False).returncode, 0)

    def test_absent_gitlink_is_an_explicit_proof_gap(self):
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "update-index",
                "--add",
                "--cacheinfo",
                f"160000,{self.head},module",
            ],
            check=True,
        )
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--snapshot", "--project", str(self.repo)],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(r.returncode, 0)

    def test_regular_file_cannot_hide_indexed_gitlink(self):
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "update-index",
                "--add",
                "--cacheinfo",
                f"160000,{self.head},module",
            ],
            check=True,
        )
        (self.repo / "module").write_text("replacement\n")
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--snapshot", "--project", str(self.repo)],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(r.returncode, 0)

    def test_untracked_nested_repository_is_an_explicit_proof_gap(self):
        nested = self.repo / "nested"
        subprocess.run(["git", "init", "-q", str(nested)], check=True)
        (nested / "source.py").write_text("answer = 1\n")
        subprocess.run(["git", "-C", str(nested), "add", "source.py"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(nested),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.test",
                "commit",
                "-qm",
                "nested",
            ],
            check=True,
        )
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--snapshot", "--project", str(self.repo)],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(r.returncode, 0)

    def test_unreadable_store_cannot_be_ad_hoc(self):
        import os

        if os.geteuid() == 0:
            self.skipTest("root can read mode-zero directories")
        self.proof.unlink()
        self.data.pop("base")
        self.data.pop("work_id")
        self.seal_snapshot()
        report = self.repo / "outside-review.json"
        # Ignore the report itself to retain the previously sealed candidate.
        (self.repo / ".git/info/exclude").write_text("outside-review.json\n")
        report.write_text(json.dumps(self.data))
        store = self.repo / ".devproto"
        store.chmod(0)
        try:
            r = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(report),
                    "--commit",
                    self.head,
                    "--project",
                    str(self.repo),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(r.returncode, 0)
        finally:
            store.chmod(0o700)

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

    def complete_genuine_work(self):
        import devproto

        self.proof.unlink()
        devproto.start(self.repo, "trivial copy edit", "job")
        evidence = self.proof.parent / "completed-proof.md"
        evidence.write_text("executed proof")
        for row in devproto.status(self.repo, "job")["steps"]:
            if row["required"]:
                devproto.step(
                    self.repo, "job", row["step_id"], "pass", str(evidence), "true"
                )
            else:
                devproto.step(
                    self.repo, "job", row["step_id"], "na", reason="conditional fixture"
                )
        self.data.pop("base")
        self.data.pop("work_id")

    def test_historical_work_stays_closed_after_new_candidate_and_list(self):
        import devproto

        self.complete_genuine_work()
        (self.repo / "later-feature.py").write_text("answer = 2\n")
        self.seal_snapshot()
        first = self.run_check(scoped=False)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        devproto.list_items(self.repo)
        devproto.status(self.repo, "job")
        after = self.run_check(scoped=False)
        self.assertEqual(after.returncode, 0, after.stdout + after.stderr)

    def test_unsupported_legacy_terminal_claim_is_not_a_completed_receipt(self):
        (self.repo / ".devproto/job.json").write_text(
            json.dumps(
                {
                    "work_id": "job",
                    "steps": [
                        {"step_id": step, "status": "passed"} for step in STEP_IDS
                    ],
                }
            )
        )
        self.data.pop("base")
        self.data.pop("work_id")
        self.assertNotEqual(self.run_check(scoped=False).returncode, 0)

    def test_retained_legacy_completion_migrates_before_candidate_refresh(self):
        import devproto

        self.complete_genuine_work()
        record_path = self.repo / ".devproto/job.json"
        record = json.loads(record_path.read_text())
        record.pop("completion")
        record_path.write_text(json.dumps(record))
        (self.repo / "later.py").write_text("answer = 3\n")
        devproto.list_items(self.repo)
        self.assertTrue(devproto.status(self.repo, "job")["completed"])
        self.assertEqual(self.run_check(scoped=False).returncode, 0)

    def test_missing_historical_evidence_still_blocks_ad_hoc_review(self):
        import devproto

        self.complete_genuine_work()
        (self.proof.parent / "completed-proof.md").unlink()
        record = json.loads((self.repo / ".devproto/job.json").read_text())
        self.assertTrue(devproto.status(self.repo, "job")["historical_receipts_valid"])
        archive = self.repo / record["completion"]["archive_dir"]
        next(archive.iterdir()).unlink()
        out = devproto.status(self.repo, "job")
        self.assertFalse(out["historical_receipts_valid"])
        self.assertNotEqual(self.run_check(scoped=False).returncode, 0)

    def test_completed_check_cannot_certify_new_release_and_reopen_retains_base(self):
        import devproto

        self.complete_genuine_work()
        baseline = self.proof.read_bytes()
        self.assertFalse(devproto.status(self.repo, "job")["current_candidate_ready"])
        check = subprocess.run(
            [
                sys.executable,
                str(ROOT / "skills/development-protocol/scripts/devproto.py"),
                "check",
                "--project",
                str(self.repo),
                "--id",
                "job",
            ],
            capture_output=True,
        )
        self.assertNotEqual(check.returncode, 0)
        with self.assertRaisesRegex(ValueError, "historical"):
            devproto.step(self.repo, "job", "closeout", "pass", str(self.proof), "true")
        out = devproto.reopen(self.repo, "job", "new requested work")
        self.assertFalse(out["completed"])
        self.assertEqual(self.proof.read_bytes(), baseline)
        self.assertNotEqual(self.run_check(scoped=False).returncode, 0)

    def test_historical_check_is_read_only_and_not_a_release_prerequisite(self):
        self.complete_genuine_work()
        command = [
            sys.executable,
            str(ROOT / "skills/development-protocol/scripts/devproto.py"),
            "check",
            "--project",
            str(self.repo),
            "--id",
            "job",
            "--historical",
            "--json",
        ]
        out = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse(json.loads(out.stdout)["current_candidate_ready"])
        self.assertNotEqual(
            subprocess.run(
                command + ["--through", "commit"], capture_output=True
            ).returncode,
            0,
        )
        (self.proof.parent / "completed-proof.md").unlink()
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        record = json.loads((self.repo / ".devproto/job.json").read_text())
        next((self.repo / record["completion"]["archive_dir"]).iterdir()).unlink()
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_pathway_close_accepts_completed_protocol_only_as_history(self):
        import devproto
        sys.path.insert(0, str(ROOT / "skills/pathway/scripts"))
        import pathway

        self.complete_genuine_work()
        itinerary = pathway.start(self.repo, "trivial copy edit", "demoable", "job")
        evidence = self.repo / ".devproto/evidence/pathway-proof.md"
        evidence.write_text("executed itinerary check")
        for name in itinerary["coverage"]["open"]:
            pathway.log(self.repo, "job", name, str(evidence), "true")
        self.assertTrue(pathway.close(self.repo, "job")["closed"])
        command = [sys.executable, str(ROOT / "skills/development-protocol/scripts/devproto.py"),
                   "check", "--project", str(self.repo), "--id", "job", "--json"]
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        out = subprocess.run(command + ["--historical"], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse(json.loads(out.stdout)["current_candidate_ready"])

    def test_historical_check_rejects_active_work(self):
        import devproto

        self.proof.unlink()
        devproto.start(self.repo, "new feature", "job")
        command = [
            sys.executable,
            str(ROOT / "skills/development-protocol/scripts/devproto.py"),
            "check",
            "--project",
            str(self.repo),
            "--id",
            "job",
            "--historical",
        ]
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_completed_work_does_not_prevent_new_ad_hoc_review(self):
        self.complete_genuine_work()
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
