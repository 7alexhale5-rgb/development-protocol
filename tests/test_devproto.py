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
            ["git", "-C", str(self.project), *args], stderr=subprocess.DEVNULL,
            text=True).strip()

    def init_git(self):
        self.git("init")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
                 "commit", "--allow-empty", "-m", "first")

    def test_commit_proof_reopens_on_head_change_only_from_commit_onward(self):
        self.init_git()
        self.start()
        self.close_until("commit")
        self.pass_step("commit")
        self.pass_step("ship")
        self.assertTrue(devproto.status(self.project, "w1", "ship")["ready"])
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
                 "commit", "--allow-empty", "-m", "second")
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

    def test_first_commit_keeps_precommit_progress(self):
        self.init_git()
        self.start()
        self.close_until("commit")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
                 "commit", "--allow-empty", "-m", "work")
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
        out = self.pass_step("commit", "git -c user.name=Fixture "
                             "-c user.email=fixture@example.test "
                             "commit --allow-empty -m changed")
        self.assertFalse(out["ok"])
        self.assertIn("Git HEAD or branch changed", out["error"])
        self.assertEqual(self.rows(out)["build"]["status"], "passed")

    def test_missing_git_cannot_accept_legacy_release_receipt(self):
        self.init_git()
        self.start()
        self.close_until('commit')
        self.pass_step('commit')
        path = devproto.store_path(self.project, 'w1')
        record = devproto.load(path)
        self.rows(record)['commit'].pop('git_identity')
        devproto.save(path, record)
        with patch.object(devproto.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Git identity unavailable'):
                devproto.status(self.project, 'w1')

    def test_older_success_cannot_overwrite_identical_newer_failure(self):
        self.start()
        self.pass_step('pathway', 'false')
        def older_verifier(*args):
            with patch.object(devproto, 'run_verifier', return_value=(1, 'new failure')):
                self.pass_step('pathway', 'false')
            return 0, 'older success'
        with patch.object(devproto, 'run_verifier', side_effect=older_verifier):
            with self.assertRaisesRegex(ValueError, 'changed by someone else'):
                self.pass_step('pathway', 'false')
        row = self.rows(devproto.status(self.project, 'w1'))['pathway']
        self.assertEqual(row['status'], 'blocked')
        self.assertEqual(row['output_tail'], 'new failure')

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
        self.assertIn(f"research focus suggested from the goal: {hint}", out["rule_notes"])
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
                devproto.step(self.project, work_id, s["step_id"], "pass", "ev.md", "true")
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
            self.project, "w1", "audit-setup", "pure Python repo, no package.json"
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

    def test_full_run_reaches_ready(self):
        self.start()
        self.close_until("closeout")
        self.pass_step("closeout")
        st = devproto.status(self.project, "w1")
        self.assertTrue(st["ready"])
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
                "pure Python repo",
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


if __name__ == "__main__":
    unittest.main()
