"""Tests for devproto. Run from the repo root: python3 -m unittest discover tests"""

import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills/development-protocol/scripts/devproto.py"
sys.path.insert(0, str(SCRIPT.parent))
import devproto  # noqa: E402

FEATURE = "Add export button to the reports page"
TRIVIAL = "Fix typo in footer"


class DevprotoTest(unittest.TestCase):
    def test_failed_review_recheck_is_retained_after_git_recovers(self):
        self.init_git()
        self.start()
        self.close_until("review")
        self.assertTrue(self.pass_step("review")["ok"])
        original = devproto.git_identity
        executed = False

        def fail_verifier(*args):
            nonlocal executed
            executed = True
            return 1, "new review failed"

        def inspect(project):
            if executed:
                raise ValueError("Git identity temporarily unavailable")
            return original(project)

        with (
            patch.object(devproto, "run_verifier", side_effect=fail_verifier),
            patch.object(devproto, "git_identity", side_effect=inspect),
        ):
            out = self.pass_step("review")
        self.assertFalse(out["ok"])
        row = next(
            r
            for r in devproto.status(self.project, "w1")["steps"]
            if r["step_id"] == "review"
        )
        self.assertEqual(row["status"], "blocked")
        self.assertEqual(row["verifier_exit"], 1)
        self.assertIn("new review failed", row["output_tail"])
        self.assertIn("inspection", row["reason"])

    def test_closed_itinerary_must_prove_the_current_candidate(self):
        self.init_git()
        self.start()
        router = devproto.pathway_router()
        router.start(self.project, FEATURE, "live", "w1")
        for name in router.load(self.project, "w1")["pathways"]:
            router.log(self.project, "w1", name, "ev.md", "true")
        router.close(self.project, "w1")
        (self.project / "check.sh").write_text("# corrected implementation\nexit 0\n")
        self.close_until("closeout")
        self.assertFalse(self.pass_step("closeout")["ok"])
        router.reopen(self.project, "w1", "renew proof for corrected candidate")
        for name in router.load(self.project, "w1")["pathways"]:
            router.log(self.project, "w1", name, "ev.md", "true")
        router.close(self.project, "w1")
        self.assertTrue(self.pass_step("closeout")["completed"])

    def test_progressed_open_itinerary_can_explicitly_reset_for_checklist(self):
        router = devproto.pathway_router()
        router.start(self.project, FEATURE, "live", "w1")
        router.log(self.project, "w1", "govern", "ev.md", "true")
        prior = router.load(self.project, "w1")["pathways"]["govern"]
        self.start()
        reset = router.reopen(self.project, "w1", "enroll fresh checklist proof")
        self.assertFalse(reset["closed"])
        item = router.load(self.project, "w1")
        self.assertEqual(item["completion_history"][-1]["pathways"]["govern"], prior)
        self.assertIsNone(item["completion_history"][-1]["completion"])
        self.assertEqual(item["checklist_generation"], 1)
        self.assertTrue(
            all(row["status"] == "open" for row in item["pathways"].values())
        )
        for name in item["pathways"]:
            router.log(self.project, "w1", name, "ev.md", "true")
        router.close(self.project, "w1")
        self.close_until("closeout")
        self.assertTrue(self.pass_step("closeout")["completed"])

    def test_itinerary_cannot_seal_old_candidate_rows_under_new_binding(self):
        self.init_git()
        self.start()
        router = devproto.pathway_router()
        router.start(self.project, FEATURE, "live", "w1")
        for name in router.load(self.project, "w1")["pathways"]:
            router.log(self.project, "w1", name, "ev.md", "true")
        (self.project / "check.sh").write_text(
            "# changed after pathway proof\nexit 0\n"
        )
        self.assertFalse(router.close(self.project, "w1")["ok"])

    def test_conflicting_goal_intake_is_rejected_without_partial_enrollment(self):
        router = devproto.pathway_router()
        router.start(self.project, FEATURE, "live", "itinerary-first")
        original = router.item_path(self.project, "itinerary-first").read_bytes()
        with self.assertRaisesRegex(ValueError, "goal"):
            devproto.start(self.project, "Different security goal", "itinerary-first")
        self.assertFalse(devproto.store_path(self.project, "itinerary-first").exists())
        self.assertEqual(
            router.item_path(self.project, "itinerary-first").read_bytes(), original
        )

    def test_checklist_first_conflicting_itinerary_goal_leaves_both_stores_unchanged(
        self,
    ):
        router = devproto.pathway_router()
        devproto.start(self.project, FEATURE, "checklist-first")
        original = devproto.store_path(self.project, "checklist-first").read_bytes()
        with self.assertRaisesRegex(ValueError, "goal"):
            router.start(
                self.project, "Different security goal", "live", "checklist-first"
            )
        self.assertFalse(router.item_path(self.project, "checklist-first").exists())
        self.assertEqual(
            devproto.store_path(self.project, "checklist-first").read_bytes(), original
        )

    def test_goal_association_tampering_blocks_closeout_and_historical_proof(self):
        self.start()
        router = devproto.pathway_router()
        router.start(self.project, FEATURE, "live", "w1")
        for name in router.load(self.project, "w1")["pathways"]:
            router.log(self.project, "w1", name, "ev.md", "true")
        router.close(self.project, "w1")
        original = router.load(self.project, "w1")
        self.close_until("closeout")
        changed = json.loads(json.dumps(original))
        changed["goal"] = "Different security goal"
        router.save(self.project, changed)
        self.assertFalse(self.pass_step("closeout")["ok"])
        router.save(self.project, original)
        self.assertTrue(self.pass_step("closeout")["completed"])
        record = devproto.load(devproto.store_path(self.project, "w1"))
        self.assertTrue(devproto.retained_completion(self.project, record))
        record["goal"] = "Different security goal"
        self.assertFalse(devproto.retained_completion(self.project, record))
        self.assertFalse(router.retained_completion(self.project, changed))

    def test_missing_execution_generation_cannot_complete_legacy_work(self):
        self.start()
        path = devproto.store_path(self.project, "w1")
        record = devproto.load(path)
        record.pop("execution_generation", None)
        devproto.save(path, record)
        self.start()
        self.close_until("closeout")
        self.assertFalse(self.pass_step("closeout")["ok"])

    def test_closed_pre_intake_itinerary_is_not_relabelled_current(self):
        router = devproto.pathway_router()
        router.start(self.project, FEATURE, "live", "w1")
        for name in router.load(self.project, "w1")["pathways"]:
            router.log(self.project, "w1", name, "ev.md", "true")
        router.close(self.project, "w1")
        original = router.load(self.project, "w1")
        self.start()
        self.assertEqual(router.load(self.project, "w1"), original)
        self.close_until("closeout")
        self.assertFalse(self.pass_step("closeout")["ok"])
        router.reopen(self.project, "w1", "enroll current intake")
        for name in router.load(self.project, "w1")["pathways"]:
            router.log(self.project, "w1", name, "ev.md", "true")
        router.close(self.project, "w1")
        self.assertTrue(self.pass_step("closeout")["completed"])

    def test_checklist_reopen_requires_renewed_itinerary_generation(self):
        for itinerary_first in (False, True):
            with self.subTest(itinerary_reopened_first=itinerary_first):
                work_id = "cycle-" + str(itinerary_first)
                devproto.start(self.project, FEATURE, work_id)
                router = devproto.pathway_router()
                router.start(self.project, FEATURE, "live", work_id)
                for name in router.load(self.project, work_id)["pathways"]:
                    router.log(self.project, work_id, name, "ev.md", "true")
                router.close(self.project, work_id)

                def renew_checklist():
                    for row in devproto.status(self.project, work_id)["steps"]:
                        if row["step_id"] == "closeout":
                            break
                        if row["required"]:
                            devproto.step(
                                self.project,
                                work_id,
                                row["step_id"],
                                "pass",
                                "ev.md",
                                "true",
                            )
                        else:
                            devproto.step(
                                self.project,
                                work_id,
                                row["step_id"],
                                "na",
                                reason="not applicable to fixture",
                            )

                renew_checklist()
                self.assertTrue(
                    devproto.step(
                        self.project, work_id, "closeout", "pass", "ev.md", "true"
                    )["completed"]
                )
                original = devproto.load(devproto.store_path(self.project, work_id))
                if itinerary_first:
                    router.reopen(self.project, work_id, "renew itinerary")
                devproto.reopen(self.project, work_id, "renew changed work")
                (self.project / "ev.md").write_text("renewed documentation " + work_id)
                renew_checklist()
                blocked = devproto.step(
                    self.project, work_id, "closeout", "pass", "ev.md", "true"
                )
                self.assertFalse(blocked["ok"])
                self.assertTrue(devproto.retained_completion(self.project, original))
                if not itinerary_first:
                    router.reopen(self.project, work_id, "renew itinerary")
                for name in router.load(self.project, work_id)["pathways"]:
                    router.log(self.project, work_id, name, "ev.md", "true")
                router.close(self.project, work_id)
                self.assertTrue(
                    devproto.step(
                        self.project, work_id, "closeout", "pass", "ev.md", "true"
                    )["completed"]
                )

    def test_deleted_enrolled_itinerary_cannot_become_standalone(self):
        self.start()
        router = devproto.pathway_router()
        router.start(self.project, FEATURE, "live", "w1")
        (self.project / ".devproto/pathway/w1.json").unlink()
        self.close_until("closeout")
        out = self.pass_step("closeout")
        self.assertFalse(out["ok"])
        self.assertFalse(out["completed"])
        record = devproto.load(devproto.store_path(self.project, "w1"))
        self.assertEqual(record["itinerary_enrollment"]["mode"], "required")

    def test_unknown_enrollment_cannot_close_as_standalone(self):
        self.start()
        path = devproto.store_path(self.project, "w1")
        record = devproto.load(path)
        record.pop("itinerary_enrollment", None)
        devproto.save(path, record)
        self.start()  # Resume cannot manufacture an absent historical obligation.
        self.close_until("closeout")
        self.assertFalse(self.pass_step("closeout")["ok"])

    def test_pathway_first_intake_records_required_enrollment(self):
        router = devproto.pathway_router()
        router.start(self.project, FEATURE, "live", "w1")
        self.start()
        path = devproto.store_path(self.project, "w1")
        self.assertEqual(
            devproto.load(path)["itinerary_enrollment"]["mode"], "required"
        )
        (self.project / ".devproto/pathway/w1.json").unlink()
        self.close_until("closeout")
        self.assertFalse(self.pass_step("closeout")["ok"])

    def test_reopen_retains_each_completion_provenance_independently(self):
        self.start()
        self.close_until("closeout")
        self.pass_step("closeout")
        path = devproto.store_path(self.project, "w1")
        first = devproto.load(path)
        devproto.reopen(self.project, "w1", "Add shared pathway coverage")
        router = devproto.pathway_router()
        router.start(self.project, FEATURE, "live", "w1")
        for name in router.load(self.project, "w1")["pathways"]:
            router.log(self.project, "w1", name, "ev.md", "true")
        router.close(self.project, "w1")
        self.close_until("closeout")
        self.assertTrue(self.pass_step("closeout")["completed"])
        current = devproto.load(path)
        prior = dict(current["completion_history"][0], work_id="w1")
        self.assertEqual(
            prior.get("completion_provenance"), first["completion_provenance"]
        )
        self.assertTrue(devproto.retained_completion(self.project, prior))
        self.assertTrue(devproto.retained_completion(self.project, current))
        self.assertFalse(prior["completion_provenance"]["itinerary_required"])
        self.assertTrue(current["completion_provenance"]["itinerary_required"])

    def test_sealed_legacy_unknown_itinerary_provenance_stays_unverified(self):
        import shutil

        self.init_git()
        self.start()
        self.close_until("closeout")
        self.pass_step("closeout")
        record = devproto.load(devproto.store_path(self.project, "w1"))
        old_archive = devproto.archive_directory(self.project, record)
        record.pop("completion_provenance", None)
        legacy_archive = devproto.archive_directory(self.project, record)
        if legacy_archive != old_archive:
            shutil.copytree(old_archive, legacy_archive)
        record["completion"]["archive_dir"] = devproto.portable(
            self.project, legacy_archive
        )
        record["completion"]["receipt_sha256"] = devproto.completion_digest(record)
        ancestry = json.loads(
            (old_archive / record["completion"]["ancestry_sha256"]).read_text()
        )
        ancestry["receipt_sha256"] = devproto.completion_digest(record)
        payload = json.dumps(ancestry, sort_keys=True).encode()
        sha = __import__("hashlib").sha256(payload).hexdigest()
        (legacy_archive / sha).write_bytes(payload)
        record["completion"]["ancestry_sha256"] = sha
        router = devproto.pathway_router()
        router.start(self.project, FEATURE, "live", "w1")
        for archived in (True, False):
            with self.subTest(archive_and_ancestry=archived):
                legacy = json.loads(json.dumps(record))
                if not archived:
                    legacy["completion"].pop("archive_dir")
                    legacy["completion"].pop("ancestry_sha256")
                original = json.dumps(legacy, sort_keys=True)
                self.assertFalse(devproto.retained_completion(self.project, legacy))
                self.assertFalse(devproto.refresh(self.project, legacy))
                self.assertEqual(json.dumps(legacy, sort_keys=True), original)

    def test_explicit_itinerary_absence_is_immutable_and_bound(self):
        self.start()
        self.close_until("closeout")
        self.pass_step("closeout")
        record = devproto.load(devproto.store_path(self.project, "w1"))
        self.assertEqual(record.get("completion_provenance", {}).get("version"), 2)
        self.assertIs(record["completion_provenance"]["itinerary_required"], False)
        router = devproto.pathway_router()
        router.start(self.project, FEATURE, "live", "w1")
        self.assertTrue(
            devproto.status(self.project, "w1")["historical_receipts_valid"]
        )
        changed = json.loads(json.dumps(record))
        changed["completion_provenance"]["itinerary_required"] = True
        self.assertFalse(devproto.retained_completion(self.project, changed))

    def test_required_itinerary_proof_survives_origin_loss_and_archive_transfer(self):
        import shutil

        self.start()
        self.close_until("closeout")
        router = devproto.pathway_router()
        router.start(self.project, FEATURE, "live", "w1")
        for name in router.load(self.project, "w1")["pathways"]:
            router.log(self.project, "w1", name, "ev.md", "true")
        router.close(self.project, "w1")
        self.pass_step("closeout")
        record = devproto.load(devproto.store_path(self.project, "w1"))
        self.assertIs(
            record.get("completion_provenance", {}).get("itinerary_required"), True
        )
        item = router.load(self.project, "w1")
        shutil.rmtree(router.archive_directory(self.project, item))
        (self.project / ".devproto/pathway/w1.json").unlink()
        self.assertTrue(devproto.retained_completion(self.project, record))
        with tempfile.TemporaryDirectory() as directory:
            transferred = Path(directory).resolve()
            shutil.copytree(self.project / ".devproto", transferred / ".devproto")
            self.assertTrue(devproto.retained_completion(transferred, record))
            provenance = record["completion_provenance"]
            copied_json = devproto.historical_artifact(
                transferred,
                record,
                provenance["itinerary_source"],
                provenance["itinerary_sha256"],
            )
            original = copied_json.read_bytes()
            copied_json.write_bytes(b"corrupt")
            self.assertFalse(devproto.retained_completion(transferred, record))
            copied_json.write_bytes(original)
            proof_sha = next(
                row["sha256"]
                for row in item["pathways"].values()
                if row["status"] == "proved"
            )
            proof = devproto.historical_artifact(transferred, record, "", proof_sha)
            proof.unlink()
            self.assertFalse(devproto.retained_completion(transferred, record))

    def test_shared_itinerary_missing_archive_blocks_checklist_closeout(self):
        import importlib.util

        script = ROOT / "skills/pathway/scripts/pathway.py"
        spec = importlib.util.spec_from_file_location("itinerary_test", script)
        router = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(router)
        self.start()
        self.close_until("closeout")
        router.start(self.project, FEATURE, "live", "w1")
        for name in router.load(self.project, "w1")["pathways"]:
            router.log(self.project, "w1", name, "ev.md", "true")
        router.close(self.project, "w1")
        item = router.load(self.project, "w1")
        archive = router.archive_directory(self.project, item)
        sha = next(row["sha256"] for row in item["pathways"].values())
        artifact = archive / sha
        original = artifact.read_bytes()
        artifact.unlink()
        out = self.pass_step("closeout")
        self.assertFalse(out["ok"])
        self.assertFalse(out["ready"])
        artifact.write_bytes(original)
        out = self.pass_step("closeout")
        self.assertTrue(out["completed"])
        artifact.unlink()
        self.assertTrue(
            devproto.status(self.project, "w1")["historical_receipts_valid"]
        )
        record = devproto.load(devproto.store_path(self.project, "w1"))
        row = self.rows(out)["closeout"]
        retained = devproto.historical_artifact(
            self.project, record, str(artifact), sha
        )
        retained.write_bytes(b"corrupt")
        self.assertFalse(
            devproto.status(self.project, "w1")["historical_receipts_valid"]
        )

    def test_closeout_rejects_successful_verifier_without_completion_provenance(self):
        self.start()
        self.close_until("closeout")
        with patch.object(devproto, "retained_completion", return_value=False):
            out = self.pass_step("closeout")
            self.assertFalse(out["ok"])
            self.assertFalse(out["ready"])
            self.assertFalse(out["current_candidate_ready"])
            self.assertEqual(self.rows(out)["closeout"]["status"], "blocked")
        self.assertIsNone(out.get("completion"))

    def test_prechange_git_record_cannot_migrate_without_review_binding(self):
        self.start()
        self.close_until("closeout")
        self.pass_step("closeout")
        path = devproto.store_path(self.project, "w1")
        original = json.loads(path.read_text())
        original.pop("completion")
        self.init_git()
        identity = devproto.git_identity(self.project)
        baseline = self.project / ".devproto/evidence/w1-build-base.txt"
        baseline.parent.mkdir(parents=True, exist_ok=True)
        for provenance in ("release", "baseline", "both"):
            with self.subTest(provenance=provenance):
                record = json.loads(json.dumps(original))
                for row in record["steps"]:
                    row["git_identity"] = (
                        identity
                        if provenance != "baseline"
                        and row["step_id"] in devproto.RELEASE_STEPS
                        else None
                    )
                    row["candidate_sha256"] = ""
                if provenance != "release":
                    baseline.write_text(f"base {identity['head']}\nwork-id w1\n")
                elif baseline.exists():
                    baseline.unlink()
                self.assertFalse(devproto.retained_completion(self.project, record))
                devproto.refresh(self.project, record)
                self.assertNotIn("completion", record)

    def test_list_completed_proof_gap_never_reports_current_readiness(self):
        self.start()
        self.close_until("closeout")
        self.pass_step("closeout")
        out = devproto.status(self.project, "w1")
        self.assertFalse(out["ready"])
        stream = io.StringIO()
        with redirect_stdout(stream):
            devproto.print_human(devproto.list_items(self.project))
        self.assertIn("historical proof verified", stream.getvalue())
        record = json.loads(devproto.store_path(self.project, "w1").read_text())
        row = next(row for row in record["steps"] if row["status"] == "passed")
        archived = devproto.historical_artifact(
            self.project, record, row["evidence_path"], row["evidence_sha256"]
        )
        archived.unlink()
        out = devproto.status(self.project, "w1")
        self.assertFalse(out["ready"])
        self.assertFalse(out["historical_receipts_valid"])
        stream = io.StringIO()
        with redirect_stdout(stream):
            devproto.print_human(devproto.list_items(self.project))
        self.assertIn("historical proof gap", stream.getvalue())
        self.assertNotIn("ready", stream.getvalue())

    def test_completed_ancestry_survives_squash_gc_and_fresh_clone_transfer(self):
        import shutil

        self.init_git()
        original_branch = self.git("symbolic-ref", "--short", "HEAD")
        self.start()
        self.git("checkout", "-b", "feature")
        (self.project / "feature.py").write_text("answer = 1\n")
        self.git("add", "feature.py")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "feature",
        )
        reviewed = self.git("rev-parse", "HEAD")
        self.close_until("closeout")
        self.pass_step("closeout")
        self.git("checkout", original_branch)
        self.git("merge", "--squash", "feature")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "squash feature",
        )
        self.git("branch", "-D", "feature")
        self.git("reflog", "expire", "--expire=now", "--all")
        self.git("gc", "--prune=now")
        missing = subprocess.run(
            ["git", "-C", str(self.project), "cat-file", "-e", reviewed],
            capture_output=True,
        )
        self.assertNotEqual(
            missing.returncode, 0, "fixture must actually remove reviewed Git object"
        )
        self.assertTrue(
            devproto.status(self.project, "w1")["historical_receipts_valid"]
        )
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp).resolve() / "fresh"
            subprocess.run(
                ["git", "clone", "--no-local", "-q", str(self.project), str(clone)],
                check=True,
            )
            shutil.copytree(self.project / ".devproto", clone / ".devproto")
            self.assertTrue(devproto.status(clone, "w1")["historical_receipts_valid"])

    def test_interrupted_archive_publication_recovers_a_partial_old_destination(self):
        self.start()
        self.close_until("closeout")

        def interrupted(incoming, outgoing, **kwargs):
            outgoing.write(b"partial copy")
            raise OSError("simulated copy interruption")

        with patch.object(devproto.shutil, "copyfileobj", side_effect=interrupted):
            with self.assertRaises(OSError):
                self.pass_step("closeout")
        path = self.project / ".devproto/w1.json"
        record = json.loads(path.read_text())
        self.assertNotIn("completion", record)
        archive = devproto.archive_directory(self.project, record)
        (archive / record["steps"][0]["evidence_sha256"]).write_bytes(
            b"older partial destination"
        )
        self.assertTrue(
            devproto.status(self.project, "w1")["historical_receipts_valid"]
        )

    def test_slow_earlier_verifier_cannot_write_after_completion_seals(self):
        self.start()
        self.close_until("closeout")
        entered, release = threading.Event(), threading.Event()
        original = devproto.run_verifier
        outcomes = []

        def controlled(command, project, timeout):
            if threading.current_thread().name == "slow-verifier":
                entered.set()
                if not release.wait(10):
                    raise RuntimeError("fixture release deadline expired")
            return original(command, project, timeout)

        def slow():
            try:
                outcomes.append(self.pass_step("pathway"))
            except Exception as error:
                outcomes.append(error)

        worker = threading.Thread(target=slow, name="slow-verifier")
        with patch.object(devproto, "run_verifier", side_effect=controlled):
            worker.start()
            try:
                self.assertTrue(
                    entered.wait(5), "old verifier must enter its unlocked phase"
                )
                self.pass_step("closeout")
                path = self.project / ".devproto/w1.json"
                sealed = path.read_bytes()
            finally:
                release.set()
                worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(outcomes), 1)
        self.assertIsInstance(outcomes[0], ValueError)
        self.assertIn("became completed", str(outcomes[0]))
        self.assertEqual(path.read_bytes(), sealed)
        self.assertTrue(
            devproto.status(self.project, "w1")["historical_receipts_valid"]
        )

    def test_completed_proofs_survive_live_edits_and_archive_loss_is_recoverable(self):
        self.start()
        evidence = self.project / ".devproto/evidence/review.json"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text('{"verdict":"pass"}\n')
        instrument = self.project / "tests/test_behavior.py"
        instrument.parent.mkdir()
        instrument.write_text("assert True\n")
        for row in devproto.status(self.project, "w1")["steps"]:
            if row["required"]:
                self.pass_step(
                    row["step_id"],
                    evidence=str(evidence),
                    instruments=(str(instrument),),
                )
            else:
                devproto.step(
                    self.project, "w1", row["step_id"], "na", reason="not needed"
                )
        path = self.project / ".devproto/w1.json"
        receipt = path.read_bytes()
        devproto.start(self.project, "next confirmed bug fix", "w2")
        evidence.write_text('{"verdict":"later-task"}\n')
        instrument.write_text("assert False\n")
        devproto.step(
            self.project,
            "w2",
            "pathway",
            "pass",
            str(evidence),
            "true",
            instruments=(str(instrument),),
        )
        devproto.list_items(self.project)
        out = devproto.status(self.project, "w1")
        self.assertTrue(out["historical_receipts_valid"])
        self.assertEqual(
            path.read_bytes(), receipt, "status must not mutate sealed rows"
        )
        archive = self.project / out["completion"]["archive_dir"]
        artifact = next(archive.iterdir())
        saved = artifact.read_bytes()
        artifact.unlink()
        self.assertFalse(
            devproto.status(self.project, "w1")["historical_receipts_valid"]
        )
        self.assertEqual(path.read_bytes(), receipt)
        artifact.write_bytes(saved)
        self.assertTrue(
            devproto.status(self.project, "w1")["historical_receipts_valid"]
        )
        artifact.write_bytes(b"tampered proof")
        self.assertFalse(
            devproto.status(self.project, "w1")["historical_receipts_valid"]
        )
        artifact.write_bytes(saved)
        self.assertTrue(
            devproto.status(self.project, "w1")["historical_receipts_valid"]
        )
        self.assertEqual(path.read_bytes(), receipt)

        aliased_proof = self.project / "same-bytes-other-location"
        aliased_proof.write_bytes(saved)
        artifact.unlink()
        artifact.symlink_to(aliased_proof)
        self.assertFalse(
            devproto.status(self.project, "w1")["historical_receipts_valid"],
            "a redirected archive is invalid even with matching bytes",
        )
        artifact.unlink()
        artifact.write_bytes(saved)
        self.assertTrue(
            devproto.status(self.project, "w1")["historical_receipts_valid"]
        )

    def test_read_only_historical_output_scrubs_legacy_credentials(self):
        self.start()
        self.close_until("closeout")
        self.pass_step("closeout")
        path = self.project / ".devproto/w1.json"
        record = json.loads(path.read_text())
        secret = "synthetic-private-password"
        record["steps"][0]["verify_command"] = (
            "echo postgres://fixture:" + secret + "@localhost/db"
        )
        record["steps"][0]["output_tail"] = (
            "postgres://fixture:" + secret + "@localhost/db"
        )
        record["completion"]["receipt_sha256"] = "invalid receipt"
        path.write_text(json.dumps(record))
        saved = path.read_bytes()
        for flags in ([], ["--json"]):
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "check",
                    "--project",
                    str(self.project),
                    "--id",
                    "w1",
                    "--historical",
                    *flags,
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(secret, result.stdout + result.stderr)
            self.assertEqual(path.read_bytes(), saved)

    def test_reopening_cannot_replace_the_archived_git_baseline(self):
        self.init_git()
        self.start()
        self.close_until("closeout")
        self.pass_step("closeout")
        baseline = self.project / ".devproto/evidence/w1-build-base.txt"
        saved = baseline.read_bytes()
        baseline.write_text("base " + "0" * 40 + "\nwork-id w1\n")
        self.assertTrue(
            devproto.status(self.project, "w1")["historical_receipts_valid"]
        )
        with self.assertRaisesRegex(ValueError, "original baseline changed"):
            devproto.reopen(self.project, "w1", "new work")
        baseline.write_bytes(saved)
        self.assertFalse(devproto.reopen(self.project, "w1", "new work")["completed"])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name).resolve()
        (self.project / "ev.md").write_text("proof\n")

    def tearDown(self):
        self.tmp.cleanup()

    def start(self, goal=FEATURE, **kw):
        return devproto.start(self.project, goal, "w1", **kw)

    def pass_step(self, sid, verify="true", evidence="ev.md", **kw):
        return devproto.step(self.project, "w1", sid, "pass", evidence, verify, **kw)

    def rows(self, out):
        return {s["step_id"]: s for s in out["steps"]}

    def close_until(self, target):
        """Pass or n/a every row before target."""
        for s in devproto.status(self.project, "w1")["steps"]:
            if s["step_id"] == target:
                return
            if s["required"]:
                self.pass_step(s["step_id"])
            else:
                devproto.step(
                    self.project, "w1", s["step_id"], "na", reason="not needed"
                )

    def test_verifier_pipeline_failure_blocks(self):
        self.start()
        out = self.pass_step("pathway", "false | tee check.log")
        self.assertFalse(out["ok"])
        self.assertEqual(self.rows(out)["pathway"]["status"], "blocked")

    def test_command_secret_is_not_stored_or_displayed(self):
        self.start()
        token = "fixture-token-123456789"
        command = "printf '%s' 'Bearer " + token + "'"
        out = self.pass_step("pathway", command)
        self.assertTrue(out["ok"])
        row = self.rows(out)["pathway"]
        self.assertNotIn(token, json.dumps(out))
        self.assertNotIn(token, devproto.store_path(self.project, "w1").read_text())
        self.assertEqual(len(row["verify_command_sha256"]), 64)
        stream = io.StringIO()
        with redirect_stdout(stream):
            devproto.print_human(devproto.status(self.project, "w1"))
        self.assertNotIn(token, stream.getvalue())

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.project), *args],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()

    def init_git(self):
        self.git("init")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--allow-empty",
            "-m",
            "first",
        )

    def test_closeout_verifier_checks_merged_checkout_not_passing_feature(self):
        self.init_git()
        (self.project / "check.sh").write_text("exit 0\n")
        self.start()
        self.close_until("closeout")
        merged = self.project / ".devproto" / "merged-checkout"
        merged.mkdir()

        def git(*args):
            return subprocess.check_output(
                ["git", "-C", str(merged), *args], text=True, stderr=subprocess.DEVNULL
            ).strip()

        def commit(message):
            git("add", "mergedcheck.sh")
            git(
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.test",
                "commit",
                "-m",
                message,
            )
            return git("rev-parse", "HEAD")

        git("init")
        script = merged / "mergedcheck.sh"
        script.write_text("exit 1\n")
        sha = commit("failing merged code")
        branch = git("rev-parse", "--symbolic-full-name", "HEAD")
        # Original feature passes; only the committed separate merged checkout counts.
        self.assertEqual(
            subprocess.run(["bash", "check.sh"], cwd=self.project).returncode, 0
        )
        import shlex

        path = shlex.quote(str(merged))

        def command(expected):
            check = (
                f'test "$(git -C {path} rev-parse HEAD)" = {expected} && '
                f'test "$(git -C {path} rev-parse --symbolic-full-name HEAD)" = {shlex.quote(branch)} && '
                f'clean_status="$(git -C {path} status --porcelain --untracked-files=all)" && test -z "$clean_status"'
            )
            return f"{check} && (cd {path} && bash mergedcheck.sh) && {check}"

        self.assertFalse(self.pass_step("closeout", verify=command(sha))["ok"])
        script.write_text("exit 0\n")
        out = self.pass_step("closeout", verify=command(sha))
        self.assertFalse(
            out["ok"], "uncommitted green edit cannot certify failing merged SHA"
        )
        self.assertEqual(self.rows(out)["closeout"]["status"], "blocked")
        git("add", "mergedcheck.sh")
        self.assertFalse(
            self.pass_step("closeout", verify=command(sha))["ok"],
            "staged green edit is still not the recorded commit",
        )
        passing_sha = commit("passing merged code")
        self.assertFalse(
            self.pass_step("closeout", verify=command(sha))["ok"],
            "wrong recorded SHA must fail",
        )
        (merged / "untracked-input.py").write_text("answer = 1\n")
        self.assertFalse(
            self.pass_step("closeout", verify=command(passing_sha))["ok"],
            "untracked inputs must fail",
        )
        (merged / "untracked-input.py").unlink()
        # Each clean committed test below exits zero but changes the checkout while running.
        for body in (
            "touch generated-input.py\nexit 0\n",
            "git -c user.name=Fixture -c user.email=fixture@example.test commit --allow-empty -qm during-tests\nexit 0\n",
            "git checkout -qb during-tests\nexit 0\n",
        ):
            with self.subTest(body=body):
                script.write_text(body)
                current_sha = commit("mutation probe")
                out = self.pass_step("closeout", verify=command(current_sha))
                self.assertFalse(
                    out["ok"], "post-test cleanliness and identity changes must fail"
                )
                if (merged / "generated-input.py").exists():
                    (merged / "generated-input.py").unlink()
        script.write_text("exit 0\n")
        passing_sha = commit("final passing merged code")
        branch = git("rev-parse", "--symbolic-full-name", "HEAD")
        self.assertTrue(self.pass_step("closeout", verify=command(passing_sha))["ok"])

    def test_post_ship_receipt_notes_allow_compound_and_closeout(self):
        self.init_git()
        self.start()
        self.close_until("compound")
        notes = self.project / ".devproto" / "learnings" / "decision.md"
        notes.parent.mkdir(parents=True)
        notes.write_text("### Learnings\nDecision draft, promotion is separate work.\n")
        out = self.pass_step("compound", evidence=str(notes))
        self.assertTrue(out["ok"])
        self.assertTrue(devproto.status(self.project, "w1", "ship")["ready"])
        handoff = self.project / ".devproto" / "handoffs" / "closeout.md"
        handoff.parent.mkdir(parents=True)
        handoff.write_text("## Unknowns\nFresh merged SHA tested separately.\n")
        out = self.pass_step("closeout", evidence=str(handoff))
        self.assertTrue(out["ok"])
        self.assertFalse(out["ready"])
        self.assertTrue(out["historical_receipts_valid"])

    def test_retained_compound_report_requires_renewal_after_review_changes(self):
        # The instruction assertion checks structure; the real checklist below
        # proves that retaining today's report alone cannot complete closeout.
        instructions = (ROOT / "skills/closeout-stack/SKILL.md").read_text()
        self.assertIn("Renew retained compound proof", instructions)
        self.init_git()
        self.start()
        self.close_until("compound")
        report = self.project / ".devproto/learnings/retained.md"
        report.parent.mkdir(parents=True)
        report.write_text("### Learnings\nWork w1: retain the confirmed finding.\n")
        self.assertTrue(self.pass_step("compound", evidence=str(report))["ok"])
        renewed = self.project / ".devproto/reviews/renewed.md"
        renewed.parent.mkdir(parents=True)
        renewed.write_text("Renewed independent review of this candidate.\n")
        self.assertTrue(self.pass_step("review", evidence=str(renewed))["ok"])
        self.assertEqual(
            self.rows(devproto.status(self.project, "w1"))["compound"]["status"],
            "pending",
        )
        self.close_until("compound")
        with self.assertRaisesRegex(ValueError, "earlier steps"):
            self.pass_step("closeout")
        verifier = "test -f .devproto/learnings/retained.md && grep -q 'Work w1:' .devproto/learnings/retained.md && printf renewed-compound-proof"
        renewed_proof = self.pass_step(
            "compound", evidence=str(report), verify=verifier
        )
        self.assertTrue(renewed_proof["ok"])
        self.assertIn(
            "renewed-compound-proof",
            self.rows(renewed_proof)["compound"]["output_tail"],
        )
        self.assertTrue(self.pass_step("closeout")["completed"])

    def test_post_ship_source_changes_block_earliest_review_not_downstream(self):
        self.init_git()
        self.start()
        self.close_until("compound")
        decision = self.project / "docs" / "decisions" / "x.md"
        decision.parent.mkdir(parents=True)
        decision.write_text("Unreviewed shipped documentation\n")
        status = devproto.status(self.project, "w1")
        self.assertEqual(status["next_step"], "review")
        with self.assertRaisesRegex(ValueError, "earlier steps"):
            devproto.step(
                self.project,
                "w1",
                "compound",
                "blocked",
                reason="upstream proof reopened",
            )
        out = devproto.step(
            self.project,
            "w1",
            "review",
            "blocked",
            reason="source changed after review",
        )
        self.assertEqual(self.rows(out)["review"]["status"], "blocked")
        self.assertEqual(self.rows(out)["compound"]["status"], "pending")

    def test_changed_candidate_reopens_review_and_later_rows(self):
        self.init_git()
        self.start()
        self.close_until("commit")
        self.pass_step("commit")
        (self.project / "source.py").write_text("changed implementation\n")
        out = devproto.status(self.project, "w1", "commit")
        self.assertFalse(out["ready"])
        self.assertEqual(self.rows(out)["review"]["status"], "pending")
        self.assertEqual(self.rows(out)["commit"]["status"], "pending")

    def test_head_change_during_review_verifier_blocks_without_file_changes(self):
        self.init_git()
        self.start()
        self.close_until("review")
        out = self.pass_step(
            "review",
            "git -c user.name=Fixture -c user.email=fixture@example.test commit --allow-empty -m changed",
        )
        self.assertFalse(out["ok"])
        self.assertIn("Git HEAD or branch changed", out["error"])

    def test_candidate_mutation_during_review_verifier_blocks(self):
        self.init_git()
        self.start()
        self.close_until("review")
        out = self.pass_step("review", "printf changed > source.py")
        self.assertFalse(out["ok"])

    def test_transient_intake_failure_can_retry_without_creating_record(self):
        with patch.object(
            devproto,
            "git_identity",
            side_effect=ValueError("Git identity lookup failed"),
        ):
            with self.assertRaisesRegex(ValueError, "lookup failed"):
                self.start()
        self.assertFalse(devproto.store_path(self.project, "w1").exists())

    def test_flag_restart_preserves_intake_gap(self):
        self.git("init")
        self.start(TRIVIAL)
        out = self.start(TRIVIAL, force=["research"])
        self.assertTrue(
            any("baseline unavailable" in note for note in out["rule_notes"])
        )

    def test_commit_proof_reopens_on_head_change_only_from_commit_onward(self):
        self.init_git()
        self.start()
        self.close_until("commit")
        self.pass_step("commit")
        self.pass_step("ship")
        self.assertTrue(devproto.status(self.project, "w1", "ship")["ready"])
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--allow-empty",
            "-m",
            "second",
        )
        out = devproto.status(self.project, "w1", "commit")
        self.assertFalse(out["ready"])
        rows = self.rows(out)
        self.assertEqual(rows["commit"]["status"], "pending")
        self.assertEqual(rows["ship"]["status"], "pending")
        self.assertEqual(rows["build"]["status"], "passed")

    def test_branch_switch_invalidates_commit_proof(self):
        self.init_git()
        self.start()
        self.close_until("commit")
        self.pass_step("commit")
        self.git("checkout", "-b", "other")
        self.assertFalse(devproto.status(self.project, "w1", "commit")["ready"])

    def test_final_commit_requires_review_renewal_but_keeps_build_proof(self):
        self.init_git()
        self.start()
        self.close_until("commit")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--allow-empty",
            "-m",
            "work",
        )
        out = devproto.status(self.project, "w1", "commit")
        self.assertEqual(self.rows(out)["build"]["status"], "passed")
        self.assertEqual(self.rows(out)["review"]["status"], "pending")
        self.pass_step("review")
        self.pass_step("simplify")
        self.assertTrue(self.pass_step("commit")["ok"])
        self.assertTrue(devproto.status(self.project, "w1", "commit")["ready"])

    def test_legacy_command_and_output_are_scrubbed_on_status(self):
        self.start()
        self.pass_step("pathway")
        path = devproto.store_path(self.project, "w1")
        record = devproto.load(path)
        row = record["steps"][0]
        token = "fixture-legacy-token-123456"
        row["verify_command"] = "printf 'Bearer " + token + "'"
        row["output_tail"] = "Bearer " + token
        row.pop("verify_command_sha256", None)
        devproto.save(path, record)
        out = devproto.status(self.project, "w1")
        self.assertNotIn(token, json.dumps(out))
        self.assertNotIn(token, path.read_text())
        self.assertEqual(self.rows(out)["pathway"]["status"], "passed")

    def test_legacy_git_release_receipt_requires_new_binding(self):
        self.init_git()
        self.start()
        self.close_until("commit")
        self.pass_step("commit")
        path = devproto.store_path(self.project, "w1")
        record = devproto.load(path)
        self.rows(record)["commit"].pop("git_identity")
        devproto.save(path, record)
        self.assertFalse(devproto.status(self.project, "w1", "commit")["ready"])

    def test_head_change_during_commit_verifier_blocks(self):
        self.init_git()
        self.start()
        self.close_until("commit")
        out = self.pass_step(
            "commit",
            "git -c user.name=Fixture "
            "-c user.email=fixture@example.test "
            "commit --allow-empty -m changed",
        )
        self.assertFalse(out["ok"])
        self.assertIn("Git HEAD or branch changed", out["error"])
        self.assertEqual(self.rows(out)["build"]["status"], "passed")

    def test_missing_git_cannot_accept_legacy_release_receipt(self):
        self.init_git()
        self.start()
        self.close_until("commit")
        self.pass_step("commit")
        path = devproto.store_path(self.project, "w1")
        record = devproto.load(path)
        self.rows(record)["commit"].pop("git_identity")
        devproto.save(path, record)
        with patch.object(devproto.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, "Git identity unavailable"):
                devproto.status(self.project, "w1")

    def test_older_success_cannot_overwrite_identical_newer_failure(self):
        self.start()
        self.pass_step("pathway", "false")

        def older_verifier(*args):
            with patch.object(
                devproto, "run_verifier", return_value=(1, "new failure")
            ):
                self.pass_step("pathway", "false")
            return 0, "older success"

        with patch.object(devproto, "run_verifier", side_effect=older_verifier):
            with self.assertRaisesRegex(ValueError, "changed by someone else"):
                self.pass_step("pathway", "false")
        row = self.rows(devproto.status(self.project, "w1"))["pathway"]
        self.assertEqual(row["status"], "blocked")
        self.assertEqual(row["output_tail"], "new failure")

    # ---- row rules -------------------------------------------------------

    def test_seventeen_rows_map_to_bundled_skills(self):
        self.assertEqual(len(devproto.STEPS), 17)
        for _, skill, _ in devproto.STEPS:
            name = skill.split()[0].lstrip("/")
            self.assertTrue((ROOT / "skills" / name / "SKILL.md").is_file(), name)

    def test_feature_goal_rows(self):
        r = {k: v["required"] for k, v in self.rows(self.start()).items()}
        self.assertTrue(r["brainstorm"])  # not trivial
        self.assertTrue(r["visual-spec"] and r["design"])  # "page"
        self.assertFalse(r["research"])
        self.assertTrue(r["planning"] and r["verify"] and r["compound"])

    def test_trivial_goal_rows(self):
        r = {
            k: v["required"]
            for k, v in self.rows(devproto.start(self.project, TRIVIAL, "t1")).items()
        }
        for sid in (
            "brainstorm",
            "spec",
            "planning",
            "premortem",
            "audit-setup",
            "verify",
            "simplify",
            "compound",
        ):
            self.assertFalse(r[sid], sid)
        for sid in ("pathway", "build", "review", "commit", "ship", "closeout"):
            self.assertTrue(r[sid], sid)

    def test_require_and_optional(self):
        r = self.rows(self.start(force=["research"], optional=["design"]))
        self.assertTrue(r["research"]["required"])
        self.assertFalse(r["design"]["required"])
        with self.assertRaises(ValueError):
            devproto.start(self.project, "x", "o2", optional=["review"])

    def test_start_explains_goal_word_rules(self):
        notes = devproto.start(self.project, "Fix typo on the settings page", "n1")[
            "rule_notes"
        ]
        self.assertTrue(any('"typo"' in n for n in notes))
        self.assertTrue(any('"page"' in n for n in notes))

    def test_start_is_idempotent_and_rejects_goal_change(self):
        self.assertEqual(self.start()["next_step"], "pathway")
        self.assertEqual(self.start()["work_id"], "w1")
        with self.assertRaises(ValueError):
            devproto.start(self.project, "something else", "w1")

    def test_rerun_start_applies_flags_before_first_step_only(self):
        self.start()
        out = self.start(force=["research"])
        self.assertTrue(self.rows(out)["research"]["required"])
        self.pass_step("pathway")
        with self.assertRaisesRegex(ValueError, "already has recorded steps"):
            self.start(optional=["research"])

    # ---- research focus hints -------------------------------------------

    def test_focus_hints_mirror_the_research_stack_manifest(self):
        manifest = json.loads(
            (ROOT / "skills/research-stack/references/focus/tags.json").read_text()
        )
        expected = [(tag, lens["triggers"]) for tag, lens in manifest["tags"].items()]
        self.assertEqual(devproto.FOCUS_HINTS, expected)
        self.assertEqual(devproto.MAX_FOCUS, manifest["limits"]["max_tags"])

    def test_focus_tags_rank_by_distinct_matches_then_manifest_order(self):
        goal = "research the auth library for the checkout dashboard"
        # ui-ux matches checkout and dashboard (2); security and devtools tie at 1.
        self.assertEqual(devproto.focus_tags(goal), ["ui-ux", "security", "devtools"])
        many = (
            "research seo keywords, wcag aria, cve auth, latency lcp, postgres redis, "
            "gdpr compliance, npm packages, pricing competitors"
        )
        self.assertEqual(len(devproto.focus_tags(many)), devproto.MAX_FOCUS)
        self.assertEqual(devproto.focus_tags("research the release date"), [])

    def test_research_row_suggests_focus_tags(self):
        out = devproto.start(
            self.project, "Research which auth library to pick for the checkout", "f1"
        )
        hint = "/research-stack --focus ui-ux,security,devtools"
        self.assertIn(
            f"research focus suggested from the goal: {hint}", out["rule_notes"]
        )
        self.assertEqual(out["research_focus"], hint)
        self.close_until_for("f1", "research")
        buf = io.StringIO()
        with redirect_stdout(buf):
            devproto.main(["--project", str(self.project), "status", "--id", "f1"])
        text = buf.getvalue()
        self.assertIn(f"Next step: research  (run {hint})", text)
        self.assertIn(f"suggested: {hint}", text)
        devproto.step(self.project, "f1", "research", "pass", "ev.md", "true")
        self.assertNotIn("research_focus", devproto.status(self.project, "f1"))

    def test_no_focus_hint_without_a_match_or_without_research(self):
        out = devproto.start(self.project, "Research the release date", "f2")
        self.assertTrue(self.rows(out)["research"]["required"])
        self.assertNotIn("research_focus", out)
        self.assertFalse(any("focus" in n for n in out["rule_notes"]))
        # A lens word with research off gives no hint either.
        out = devproto.start(self.project, "Add a checkout dashboard", "f3")
        self.assertFalse(self.rows(out)["research"]["required"])
        self.assertNotIn("research_focus", out)
        self.assertFalse(any("focus" in n for n in out["rule_notes"]))

    def close_until_for(self, work_id, target):
        for s in devproto.status(self.project, work_id)["steps"]:
            if s["step_id"] == target:
                return
            if s["required"]:
                devproto.step(
                    self.project, work_id, s["step_id"], "pass", "ev.md", "true"
                )
            else:
                devproto.step(
                    self.project, work_id, s["step_id"], "na", reason="not needed"
                )

    # ---- order and results ----------------------------------------------

    def test_cannot_skip_ahead(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "earlier steps are still open"):
            self.pass_step("build")

    def test_blocked_result_also_needs_earlier_rows_closed(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "earlier steps are still open"):
            devproto.step(self.project, "w1", "build", "blocked", reason="out of order")
        # na is still exempt from the same check (conditional rows only)
        devproto.step(self.project, "w1", "research", "na", reason="no unknowns")

    def test_required_row_cannot_be_na(self):
        self.start()
        with self.assertRaises(ValueError):
            devproto.step(self.project, "w1", "pathway", "na", reason="skip")

    # ---- set-optional (finding 5: audit-setup on a non-Node repo) --------

    def test_set_optional_unblocks_a_required_row_for_na(self):
        self.start()  # FEATURE goal: audit-setup is required (not trivial)
        self.assertTrue(
            self.rows(devproto.status(self.project, "w1"))["audit-setup"]["required"]
        )
        out = devproto.set_optional(
            self.project,
            "w1",
            "audit-setup",
            "explicitly approved optional row, applicability verified",
        )
        self.assertFalse(self.rows(out)["audit-setup"]["required"])
        # Now na works where it was refused before.
        devproto.step(self.project, "w1", "audit-setup", "na", reason="no Node tooling")
        self.assertEqual(
            self.rows(devproto.status(self.project, "w1"))["audit-setup"]["status"],
            "not-applicable",
        )

    def test_set_optional_refuses_always_required_rows(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "always required"):
            devproto.set_optional(self.project, "w1", "pathway", "not needed")

    def test_set_optional_refuses_an_already_recorded_row(self):
        self.start()
        self.close_until("audit-setup")
        self.pass_step("audit-setup")
        with self.assertRaisesRegex(ValueError, "already has a recorded result"):
            devproto.set_optional(self.project, "w1", "audit-setup", "too late")

    def test_set_optional_refuses_without_a_reason(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "reason"):
            devproto.set_optional(self.project, "w1", "audit-setup", "")

    def test_set_optional_refuses_an_already_optional_row(self):
        self.start()  # research is not required for FEATURE (no research words)
        with self.assertRaisesRegex(ValueError, "already optional"):
            devproto.set_optional(self.project, "w1", "research", "still not needed")

    def test_failing_verifier_blocks_with_exit_code(self):
        self.start()
        out = self.pass_step("pathway", verify="echo nope; exit 3")
        self.assertFalse(out["ok"])
        row = out["steps"][0]
        self.assertEqual((row["status"], row["verifier_exit"]), ("blocked", 3))
        self.assertIn("nope", row["output_tail"])
        self.assertIn("exited 3", row["reason"])

    def test_output_tail_redacts_secrets(self):
        self.start()
        fake_key = "AKIA" + "Q" * 16  # matches the AWS-key pattern, not a real key
        out = self.pass_step("pathway", verify=f"echo TOKEN={fake_key}; exit 1")
        tail = out["steps"][0]["output_tail"]
        self.assertNotIn(fake_key, tail)
        self.assertIn("REDACTED", tail)

    def test_pass_requires_evidence_file(self):
        self.start()
        with self.assertRaises(ValueError):
            self.pass_step("pathway", evidence="missing.md")

    def test_symlinked_instrument_rejected(self):
        self.start()
        (self.project / "real.py").write_text("x\n")
        (self.project / "link.py").symlink_to(self.project / "real.py")
        with self.assertRaises(ValueError):
            self.pass_step("pathway", instruments=["link.py"])

    def test_verifier_runs_in_project_folder(self):
        self.start()
        self.assertEqual(
            self.pass_step("pathway", verify="test -f ev.md")["steps"][0]["status"],
            "passed",
        )

    def test_full_run_completes_with_verified_history_not_current_readiness(self):
        self.start()
        self.close_until("closeout")
        self.pass_step("closeout")
        st = devproto.status(self.project, "w1")
        self.assertFalse(st["ready"])
        self.assertTrue(st["historical_receipts_valid"])
        self.assertFalse(devproto.status(self.project, "w1", through="commit")["ready"])
        self.assertIsNone(st["next_step"])

    def test_through_limits_the_gate(self):
        self.start()
        self.close_until("ship")
        self.assertFalse(devproto.status(self.project, "w1")["ready"])
        self.assertTrue(devproto.status(self.project, "w1", through="commit")["ready"])
        self.assertFalse(devproto.status(self.project, "w1", through="ship")["ready"])

    # ---- tamper and reopen ----------------------------------------------

    def test_changed_evidence_reopens_step_and_later_passes(self):
        self.start()
        (self.project / "b.md").write_text("brainstorm\n")
        self.pass_step("pathway", evidence="b.md")
        self.pass_step("brainstorm")
        devproto.step(self.project, "w1", "research", "na", reason="no unknowns")
        (self.project / "b.md").write_text("edited\n")
        r = {
            k: v["status"]
            for k, v in self.rows(devproto.status(self.project, "w1")).items()
        }
        self.assertEqual(r["pathway"], "pending")
        self.assertEqual(r["brainstorm"], "pending")
        self.assertEqual(r["research"], "not-applicable")

    def test_changed_instrument_reopens_step(self):
        self.start()
        grader = self.project / "grader.py"
        grader.write_text("assert True\n")
        self.pass_step("pathway", instruments=["grader.py"])
        grader.write_text("pass  # weakened\n")
        self.assertEqual(
            devproto.status(self.project, "w1")["steps"][0]["status"], "pending"
        )

    def test_refresh_hashes_small_untouched_evidence_but_stays_passed(self):
        # R2-7: below the stat-shortcut size threshold, refresh() always
        # hashes rather than trusting (mtime, size) alone -- coarse-mtime
        # filesystems (HFS+, exFAT, some bind mounts) round mtime to whole
        # seconds, so a same-second rewrite of the same size would otherwise
        # be missed. Evidence/instrument files are typically small, so this
        # always-hash path is the common case, not an edge case.
        self.start()
        self.pass_step("pathway")
        calls = []
        orig = devproto.digest

        def counting(path):
            calls.append(path)
            return orig(path)

        devproto.digest = counting
        try:
            out = devproto.status(self.project, "w1")
        finally:
            devproto.digest = orig
        self.assertTrue(calls, "a small file must be hashed, not trusted via stat")
        self.assertEqual(out["steps"][0]["status"], "passed")

    def test_refresh_reopens_a_same_second_same_size_rewrite_of_small_evidence(self):
        # The exact bug: rewrite the same-size content within the same mtime
        # tick. On a coarse-mtime filesystem this is indistinguishable from
        # "untouched" by (mtime, size) alone; always-hashing below the
        # threshold catches it regardless of filesystem mtime resolution.
        self.start()
        self.pass_step("pathway")
        ev = self.project / "ev.md"
        st = ev.stat()
        ev.write_text("PROOF\n")  # same length as "proof\n", different bytes
        os.utime(ev, ns=(st.st_atime_ns, st.st_mtime_ns))  # pin to the same tick
        self.assertEqual(
            devproto.status(self.project, "w1")["steps"][0]["status"], "pending"
        )

    def test_refresh_skips_rehash_for_a_large_untouched_file_via_stat_shortcut(self):
        # At/above the threshold the stat shortcut is kept for performance;
        # this is the residual case the SKILL.md/docstring call out.
        self.start(goal=FEATURE)
        big = self.project / "big.bin"
        big.write_bytes(b"\0" * (1_000_000))
        self.pass_step("pathway", evidence="big.bin")
        calls = []
        orig = devproto.digest

        def counting(path):
            calls.append(path)
            return orig(path)

        devproto.digest = counting
        try:
            out = devproto.status(self.project, "w1")
        finally:
            devproto.digest = orig
        self.assertEqual(
            calls, [], "a large untouched file should use the stat shortcut"
        )
        self.assertEqual(out["steps"][0]["status"], "passed")

    def test_refresh_rehashes_and_stays_passed_when_stat_moves_but_content_matches(
        self,
    ):
        # rewriting the identical bytes changes mtime (and can change inode
        # timestamps) without changing content: the stat shortcut misses, but
        # the hash fallback it falls back to must still recognize "unchanged".
        self.start()
        self.pass_step("pathway")
        (self.project / "ev.md").write_text("proof\n")  # same bytes, new mtime
        self.assertEqual(
            devproto.status(self.project, "w1")["steps"][0]["status"], "passed"
        )

    def test_rerecording_an_earlier_step_reopens_later_passes(self):
        self.start()
        self.pass_step("pathway")
        self.pass_step("brainstorm")
        (self.project / "brief2.md").write_text("new brief\n")
        out = self.pass_step("pathway", evidence="brief2.md")
        r = {k: v["status"] for k, v in self.rows(out).items()}
        self.assertEqual((r["pathway"], r["brainstorm"]), ("passed", "pending"))

    def test_identical_repass_keeps_later_passes(self):
        self.start()
        self.pass_step("pathway")
        self.pass_step("brainstorm")
        self.pass_step("pathway")
        self.assertEqual(
            self.rows(devproto.status(self.project, "w1"))["brainstorm"]["status"],
            "passed",
        )

    def test_verifier_that_rewrites_evidence_gets_a_clear_reason(self):
        self.start()
        out = self.pass_step("pathway", verify="echo changed > ev.md")
        self.assertIn("changed the evidence", out["steps"][0]["reason"])

    # ---- process handling -------------------------------------------------

    def test_timeout_kills_child_processes(self):
        self.start()
        out = self.pass_step(
            "pathway", verify="sh -c 'sleep 2; touch late.txt' & wait", timeout=1
        )
        self.assertEqual(out["steps"][0]["verifier_exit"], 124)
        time.sleep(2.5)
        self.assertFalse((self.project / "late.txt").exists())

    def test_background_child_does_not_hang_a_finished_verifier(self):
        self.start()
        t0 = time.time()
        out = self.pass_step("pathway", verify="(sleep 30 &) ; true", timeout=20)
        self.assertLess(time.time() - t0, 10)
        self.assertEqual(out["steps"][0]["status"], "passed")

    def test_verifier_gets_no_stdin(self):
        self.start()
        self.assertEqual(
            self.pass_step("pathway", verify="read x", timeout=5)["steps"][0][
                "verifier_exit"
            ],
            1,
        )

    def test_status_is_readable_while_a_verifier_runs(self):
        self.start()
        th = threading.Thread(target=self.pass_step, args=("pathway", "sleep 2"))
        th.start()
        time.sleep(0.5)
        t0 = time.time()
        devproto.status(self.project, "w1")
        self.assertLess(time.time() - t0, 1.0)
        th.join()

    # ---- store hygiene ------------------------------------------------------

    def test_paths_are_stored_relative(self):
        self.start()
        self.assertEqual(
            self.pass_step("pathway")["steps"][0]["evidence_path"], "ev.md"
        )

    def test_checklist_file_is_not_private_to_owner(self):
        old = os.umask(0o022)
        try:
            self.start()
        finally:
            os.umask(old)
        mode = (self.project / ".devproto/w1.json").stat().st_mode & 0o777
        self.assertTrue(mode & 0o044, oct(mode))
        self.assertEqual(list((self.project / ".devproto").glob("*.tmp")), [])

    def test_missing_id_leaves_no_files(self):
        with self.assertRaises(ValueError):
            devproto.status(self.project, "nope")
        self.assertFalse((self.project / ".devproto").exists())

    def test_gitignore_written_even_if_store_existed(self):
        (self.project / ".devproto/evidence").mkdir(parents=True)
        self.start()
        self.assertIn(".lock", (self.project / ".devproto/.gitignore").read_text())
        self.assertEqual(devproto.list_items(self.project)["items"][0]["work_id"], "w1")

    def test_bad_work_id_rejected(self):
        with self.assertRaises(ValueError):
            devproto.start(self.project, "goal", "../escape")

    # ---- CLI ----------------------------------------------------------------

    def test_cli_exit_codes(self):
        base = [sys.executable, str(SCRIPT), "--project", str(self.project)]
        subprocess.run(
            base + ["start", "--goal", TRIVIAL, "--id", "c1"],
            check=True,
            capture_output=True,
        )
        self.assertEqual(
            subprocess.run(
                base + ["check", "--id", "c1"], capture_output=True
            ).returncode,
            1,
        )
        res = subprocess.run(
            base + ["--json", "status", "--id", "c1"], capture_output=True, text=True
        )
        self.assertEqual(json.loads(res.stdout)["next_step"], "pathway")
        self.assertEqual(
            subprocess.run(
                base + ["status", "--id", "nope"], capture_output=True
            ).returncode,
            2,
        )
        bad = self.project / ".devproto/bad.json"
        bad.write_text(
            json.dumps({"steps": [{"step_id": s} for s in devproto.STEP_IDS]})
        )
        res = subprocess.run(
            base + ["status", "--id", "bad"], capture_output=True, text=True
        )
        self.assertEqual(res.returncode, 2)
        self.assertNotIn("Traceback", res.stderr)

    def test_cli_set_optional_wiring(self):
        base = [sys.executable, str(SCRIPT), "--project", str(self.project)]
        subprocess.run(
            base + ["start", "--goal", FEATURE, "--id", "so1"],
            check=True,
            capture_output=True,
        )
        r = subprocess.run(
            base
            + [
                "set-optional",
                "--id",
                "so1",
                "--step",
                "audit-setup",
                "--reason",
                "explicit optional-row policy",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        res = subprocess.run(
            base + ["--json", "status", "--id", "so1"], capture_output=True, text=True
        )
        rows = {s["step_id"]: s for s in json.loads(res.stdout)["steps"]}
        self.assertFalse(rows["audit-setup"]["required"])

    def test_json_and_project_flags_work_before_or_after_the_subcommand(self):
        base = [sys.executable, str(SCRIPT)]
        before = subprocess.run(
            base
            + [
                "--project",
                str(self.project),
                "--json",
                "start",
                "--goal",
                TRIVIAL,
                "--id",
                "o1",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(before.returncode, 0, before.stderr)
        self.assertEqual(json.loads(before.stdout)["work_id"], "o1")
        after = subprocess.run(
            base + ["status", "--id", "o1", "--json", "--project", str(self.project)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(after.returncode, 0, after.stderr)
        self.assertEqual(json.loads(after.stdout)["work_id"], "o1")
        mixed = subprocess.run(
            base + ["--project", str(self.project), "status", "--id", "o1", "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(mixed.stdout)["work_id"], "o1")

    def test_steps_command_lists_all_rows(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            devproto.main(["steps"])
        self.assertEqual(len(buf.getvalue().strip().splitlines()), 17)
        self.assertIn("/closeout-stack", buf.getvalue())

    def test_doctor_finds_skill_files(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            devproto.main(["--project", str(self.project), "doctor"])
        self.assertIn("PASS  skill_file_next_to_script", buf.getvalue())
        self.assertIn("PASS  reference_file_next_to_script", buf.getvalue())

    # ---- print_human branches ------------------------------------------------

    def test_print_human_doctor_warn_branch(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            devproto.print_human(devproto.doctor(self.project))
        # self.project is a plain tempdir, not a git repo: a WARN line, not PASS
        self.assertIn("WARN  project_is_git_repo", buf.getvalue())

    def test_print_human_list_branch(self):
        self.start()
        buf = io.StringIO()
        with redirect_stdout(buf):
            devproto.print_human(devproto.list_items(self.project))
        self.assertIn("w1", buf.getvalue())
        self.assertIn("next: pathway", buf.getvalue())

    def test_print_human_list_branch_shows_errors(self):
        (self.project / ".devproto").mkdir()
        (self.project / ".devproto/broken.json").write_text("not json")
        buf = io.StringIO()
        with redirect_stdout(buf):
            devproto.print_human(devproto.list_items(self.project))
        self.assertIn("broken", buf.getvalue())

    def test_print_human_error_branch(self):
        self.start()
        out = self.pass_step("pathway", verify="exit 1")
        self.assertFalse(out["ok"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            devproto.print_human(out)
        self.assertIn("ERROR:", buf.getvalue())

    def test_print_human_ready_through_scope(self):
        self.start()
        self.pass_step("pathway")
        out = devproto.status(self.project, "w1", through="pathway")
        self.assertTrue(out["ready"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            devproto.print_human(out)
        self.assertIn("READY through pathway.", buf.getvalue())


class IntakeBaselineTest(unittest.TestCase):
    def test_planning_commits_do_not_move_intake_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)

            def commit(message):
                subprocess.run(
                    [
                        "git",
                        "-C",
                        directory,
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
                    ["git", "-C", directory, "rev-parse", "HEAD"], text=True
                ).strip()

            base = commit("intake")
            devproto.start(project, TRIVIAL, "work")
            baseline = project / ".devproto/evidence/work-build-base.txt"
            self.assertTrue(baseline.is_file())
            original = baseline.read_bytes()
            commit("planning changed project")
            devproto.start(project, TRIVIAL, "work")
            self.assertEqual(baseline.read_bytes(), original)
            self.assertIn(base, original.decode())
            baseline.unlink()
            devproto.start(project, TRIVIAL, "work")
            self.assertFalse(
                baseline.exists(), "resume must not invent missing intake evidence"
            )

    def test_unborn_repository_can_start_with_explicit_proof_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            result = devproto.start(project, TRIVIAL, "new")
            self.assertTrue(result["ok"])
            self.assertFalse(
                (project / ".devproto/evidence/new-build-base.txt").exists()
            )
            record = json.loads((project / ".devproto/new.json").read_text())
            self.assertTrue(
                any("baseline unavailable" in note for note in record["rule_notes"])
            )


if __name__ == "__main__":
    unittest.main()
