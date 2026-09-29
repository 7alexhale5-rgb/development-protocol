"""End-to-end tests for install.sh / uninstall.sh / health-check.sh.

Runs the real scripts against an isolated $HOME so nothing here touches the
machine's actual ~/.claude or ~/.agents skill folders.
"""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASH = shutil.which("bash") or "/bin/bash"


def run(args, home, cwd=ROOT, timeout=60):
    env = dict(os.environ)
    env["HOME"] = str(home)
    return subprocess.run(
        [BASH, *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def write_marker_skill(root: Path, name: str, text: str):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(text)


class InstallUninstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="devproto-home-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.claude_skills = self.tmp / ".claude" / "skills"

    # ---- F1: re-install must not re-back-up the stack's own copies --------

    def test_double_install_then_uninstall_restores_preexisting_skill(self):
        write_marker_skill(self.claude_skills, "pathway", "ORIGINAL USER PATHWAY\n")

        r1 = run([str(ROOT / "install.sh"), "--target", "claude", "--yes"], self.tmp)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        installed = (self.claude_skills / "pathway" / "SKILL.md").read_text()
        self.assertNotIn("ORIGINAL USER PATHWAY", installed)

        r2 = run([str(ROOT / "install.sh"), "--target", "claude", "--yes"], self.tmp)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)

        # Exactly one backup of the real pre-existing skill should exist across
        # every backup-*/restore.tsv, never one written by the second install.
        state_dir = self.tmp / ".devproto-stack"
        hits = 0
        for restore in state_dir.glob("backup-*/restore.tsv"):
            hits += sum(
                1 for line in restore.read_text().splitlines() if "/pathway" in line
            )
        self.assertEqual(
            hits, 1, "second install must not back up the stack's own copy"
        )

        r3 = run([str(ROOT / "uninstall.sh"), "--yes"], self.tmp)
        self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)

        # The pre-existing user skill comes back with its original content.
        restored = (self.claude_skills / "pathway" / "SKILL.md").read_text()
        self.assertEqual(restored, "ORIGINAL USER PATHWAY\n")

        # A skill with no pre-existing copy is simply gone.
        self.assertFalse((self.claude_skills / "ship").exists())

    # ---- F3: backup stamp/manifest survive a crash mid-install ------------

    def test_backup_and_manifest_survive_a_crash_partway_through_install(self):
        tmp_repo = Path(tempfile.mkdtemp(prefix="devproto-repo-"))
        self.addCleanup(shutil.rmtree, tmp_repo, ignore_errors=True)
        for item in ("install.sh", "uninstall.sh", "health-check.sh", "skills"):
            src = ROOT / item
            dst = tmp_repo / item
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        write_marker_skill(self.claude_skills, "1pct", "ORIGINAL USER 1PCT\n")

        # Make the second skill (alphabetically, after "1pct") fail to copy so
        # the run aborts after "1pct" has already been backed up.
        broken = tmp_repo / "skills" / "audit-setup" / "SKILL.md"
        old_mode = broken.stat().st_mode
        broken.chmod(0)
        self.addCleanup(lambda: broken.chmod(old_mode))

        r = run(
            [str(tmp_repo / "install.sh"), "--target", "claude", "--yes"],
            self.tmp,
            cwd=tmp_repo,
        )
        self.assertNotEqual(
            r.returncode, 0, "install.sh should abort on the cp failure"
        )
        self.assertIn("uninstall.sh", r.stderr)
        self.assertIn("restore.tsv", r.stderr)

        state_dir = self.tmp / ".devproto-stack"
        backups_txt = state_dir / "backups.txt"
        self.assertTrue(
            backups_txt.exists(), "backups.txt stamp must be written before the crash"
        )
        stamps = [l for l in backups_txt.read_text().splitlines() if l.strip()]
        self.assertEqual(len(stamps), 1)

        restore_tsv = state_dir / f"backup-{stamps[0]}" / "restore.tsv"
        self.assertTrue(restore_tsv.exists())
        self.assertIn("1pct", restore_tsv.read_text())

        manifest = state_dir / "installed.txt"
        self.assertTrue(
            manifest.exists(),
            "manifest must be updated right after each cp, not only at the end",
        )
        self.assertIn("1pct", manifest.read_text())

        broken.chmod(old_mode)
        r2 = run([str(tmp_repo / "uninstall.sh"), "--yes"], self.tmp, cwd=tmp_repo)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertEqual(
            (self.claude_skills / "1pct" / "SKILL.md").read_text(),
            "ORIGINAL USER 1PCT\n",
        )

    # ---- F8: uninstall keeps a changed installed SKILL.md instead of deleting

    def test_uninstall_keeps_a_locally_changed_skill_instead_of_deleting_it(self):
        r1 = run([str(ROOT / "install.sh"), "--target", "claude", "--yes"], self.tmp)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)

        edited = self.claude_skills / "ship" / "SKILL.md"
        text = edited.read_text()
        edited.write_text(text + "\n<!-- local edit -->\n")

        r2 = run([str(ROOT / "uninstall.sh"), "--yes"], self.tmp)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn("ship", r2.stdout)

        # It must not be silently deleted: the edited content survives somewhere
        # under the state dir, and the live install location is cleared.
        self.assertFalse(edited.exists())
        state_dir = self.tmp / ".devproto-stack"
        kept = list(state_dir.rglob("ship/SKILL.md"))
        self.assertTrue(
            kept, "changed SKILL.md should be moved to a backup, not deleted"
        )
        self.assertTrue(any("local edit" in p.read_text() for p in kept))

    # ---- R2-2: re-install must back up a locally edited installed skill ---

    def test_reinstall_backs_up_a_locally_edited_skill_instead_of_deleting_it(self):
        r1 = run([str(ROOT / "install.sh"), "--target", "claude", "--yes"], self.tmp)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)

        edited = self.claude_skills / "ship" / "SKILL.md"
        text = edited.read_text()
        edited.write_text(text + "\n<!-- local install-time edit -->\n")

        r2 = run([str(ROOT / "install.sh"), "--target", "claude", "--yes"], self.tmp)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)

        state_dir = self.tmp / ".devproto-stack"
        kept = list(state_dir.rglob("ship/SKILL.md"))
        self.assertTrue(
            kept, "edited SKILL.md must be backed up, not silently overwritten"
        )
        self.assertTrue(any("local install-time edit" in p.read_text() for p in kept))

        # The live copy is now the fresh, bundled one.
        self.assertNotIn("local install-time edit", edited.read_text())

    # ---- R3-3: an edited stack copy must never come back via uninstall ----

    def test_install_edit_reinstall_uninstall_leaves_no_live_stack_skill(self):
        r1 = run([str(ROOT / "install.sh"), "--target", "claude", "--yes"], self.tmp)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)

        edited = self.claude_skills / "ship" / "SKILL.md"
        text = edited.read_text()
        edited.write_text(text + "\n<!-- local edit before reinstall -->\n")

        r2 = run([str(ROOT / "install.sh"), "--target", "claude", "--yes"], self.tmp)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)

        state_dir = self.tmp / ".devproto-stack"
        # The edited copy must be recorded outside restore.tsv/backups.txt, so
        # uninstall's restore step can never put it back.
        for restore in state_dir.glob("backup-*/restore.tsv"):
            self.assertNotIn(
                "ship",
                restore.read_text(),
                "an edited stack copy must not be tracked in restore.tsv",
            )
        edited_tsv = state_dir / "edited.tsv"
        self.assertTrue(edited_tsv.exists())
        self.assertIn("ship", edited_tsv.read_text())

        r3 = run([str(ROOT / "uninstall.sh"), "--yes"], self.tmp)
        self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)

        # No live copy anywhere -- neither the fresh install nor the edited
        # backup was left (or restored) at the live path.
        self.assertFalse((self.claude_skills / "ship").exists())
        # But the edit itself is not lost -- it is still on disk, just not live.
        kept = list(state_dir.rglob("ship/SKILL.md"))
        self.assertTrue(
            kept, "the edited copy must still exist somewhere under state_dir"
        )
        self.assertTrue(
            any("local edit before reinstall" in p.read_text() for p in kept)
        )
        self.assertIn("ship", r3.stdout)

    # ---- R2-8: a crash mid-copy must not be mistaken for a user skill -----

    def test_crash_midcopy_then_reinstall_and_uninstall_recovers_cleanly(self):
        tmp_repo = Path(tempfile.mkdtemp(prefix="devproto-repo-"))
        self.addCleanup(shutil.rmtree, tmp_repo, ignore_errors=True)
        for item in ("install.sh", "uninstall.sh", "health-check.sh", "skills"):
            src = ROOT / item
            dst = tmp_repo / item
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        write_marker_skill(self.claude_skills, "1pct", "ORIGINAL USER 1PCT\n")

        broken = tmp_repo / "skills" / "audit-setup" / "SKILL.md"
        old_mode = broken.stat().st_mode
        broken.chmod(0)

        r1 = run(
            [str(tmp_repo / "install.sh"), "--target", "claude", "--yes"],
            self.tmp,
            cwd=tmp_repo,
        )
        self.assertNotEqual(r1.returncode, 0)
        self.assertTrue((self.claude_skills / "audit-setup").exists())

        broken.chmod(old_mode)
        r2 = run(
            [str(tmp_repo / "install.sh"), "--target", "claude", "--yes"],
            self.tmp,
            cwd=tmp_repo,
        )
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)

        # The crashed partial copy must not be mistaken for a real pre-existing
        # user skill and backed up.
        state_dir = self.tmp / ".devproto-stack"
        hits = 0
        for restore in state_dir.glob("backup-*/restore.tsv"):
            hits += sum(
                1 for line in restore.read_text().splitlines() if "/audit-setup" in line
            )
        self.assertEqual(
            hits, 0, "the crashed partial copy must not be backed up as a user skill"
        )
        self.assertTrue((self.claude_skills / "audit-setup" / "scripts").exists())

        r3 = run([str(tmp_repo / "uninstall.sh"), "--yes"], self.tmp, cwd=tmp_repo)
        self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)
        self.assertEqual(
            (self.claude_skills / "1pct" / "SKILL.md").read_text(),
            "ORIGINAL USER 1PCT\n",
        )
        self.assertFalse((self.claude_skills / "audit-setup").exists())

    # ---- F9: --target with no value must not hang -------------------------

    def test_install_target_with_no_value_fails_fast(self):
        r = run([str(ROOT / "install.sh"), "--target"], self.tmp, timeout=10)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Nothing changed", r.stdout)

    def test_health_check_target_with_no_value_fails_fast(self):
        r = run([str(ROOT / "health-check.sh"), "--target"], self.tmp, timeout=10)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
