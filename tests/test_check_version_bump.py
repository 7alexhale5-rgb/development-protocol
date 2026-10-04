"""Tests for scripts/check_version_bump.py against throwaway git repositories.

Run from the repo root: python3 -m unittest discover tests
"""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/check_version_bump.py"

spec = importlib.util.spec_from_file_location("check_version_bump", SCRIPT)
cvb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cvb)

GIT_ID = ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.test"]


class CheckVersionBumpTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name)
        self.git("init", "-q", "-b", "main")
        self.write_version("1.0.0")
        self.write("skills/demo/SKILL.md", "v1\n")
        self.write("docs/notes.md", "notes\n")
        self.commit("base")
        self.git("switch", "-q", "-c", "feature")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *GIT_ID, *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def write_version(self, version):
        self.write(
            ".claude-plugin/plugin.json",
            json.dumps({"name": "demo", "version": version}) + "\n",
        )

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def run_check(self, base="main"):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cvb.main(["--base", base, "--repo", str(self.repo)])
        return code, out.getvalue()

    def test_skill_change_without_bump_fails(self):
        self.write("skills/demo/SKILL.md", "v2\n")
        self.commit("change skill")
        code, out = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertIn("skills/demo/SKILL.md", out)
        self.assertIn("1.0.0", out)

    def test_skill_change_with_bump_passes(self):
        self.write("skills/demo/SKILL.md", "v2\n")
        self.write_version("1.1.0")
        self.commit("change skill and bump")
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertIn("1.0.0 -> 1.1.0", out)

    def test_manifest_change_without_bump_fails(self):
        self.write(".claude-plugin/marketplace.json", "{}\n")
        self.commit("add marketplace entry")
        self.assertEqual(self.run_check()[0], 1)

    def test_new_skill_file_without_bump_fails(self):
        self.write("skills/other/SKILL.md", "new\n")
        self.commit("add a skill")
        self.assertEqual(self.run_check()[0], 1)

    def test_uncommitted_shipped_change_counts(self):
        self.write("skills/demo/new.md", "untracked\n")
        self.assertEqual(self.run_check()[0], 1)

    def test_docs_only_change_needs_no_bump(self):
        self.write("docs/notes.md", "more notes\n")
        self.commit("docs only")
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertIn("no bump needed", out)

    def test_only_branch_changes_count_when_base_moved_on(self):
        """A skill change that landed on the base after the branch point is not this
        branch's change, so a docs-only branch still needs no bump."""
        self.git("switch", "-q", "main")
        self.write("skills/demo/SKILL.md", "base moved\n")
        self.write_version("1.1.0")
        self.commit("base release")
        self.git("switch", "-q", "feature")
        self.write("docs/notes.md", "docs\n")
        self.commit("docs on branch")
        self.assertEqual(self.run_check()[0], 0)

    def test_stale_branch_version_fails_when_base_moved_on(self):
        """The base released 1.1.0 after the branch point; a branch still at 1.0.0 differs
        from the base but matches where it started, so installs never see its change."""
        self.git("switch", "-q", "main")
        self.write("docs/notes.md", "base moved\n")
        self.write_version("1.1.0")
        self.commit("base release")
        self.git("switch", "-q", "feature")
        self.write("skills/demo/SKILL.md", "v2\n")
        self.commit("change skill, no bump")
        code, out = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertIn("the branch point", out)

    def test_branch_matching_the_base_release_fails(self):
        """Both sides bumped to the same number: after merge the version would not change."""
        self.git("switch", "-q", "main")
        self.write_version("1.1.0")
        self.commit("base release")
        self.git("switch", "-q", "feature")
        self.write("skills/demo/SKILL.md", "v2\n")
        self.write_version("1.1.0")
        self.commit("change skill, same bump as base")
        self.assertEqual(self.run_check()[0], 1)

    def test_unknown_base_cannot_measure(self):
        code, out = self.run_check(base="no-such-branch")
        self.assertEqual(code, 2, out)
        self.assertIn("COULD NOT MEASURE", out)

    def test_unreadable_version_cannot_measure(self):
        self.write("skills/demo/SKILL.md", "v2\n")
        self.write(".claude-plugin/plugin.json", "{not json\n")
        self.commit("broken manifest")
        code, out = self.run_check()
        self.assertEqual(code, 2, out)

    def test_command_line_exit_code(self):
        self.write("skills/demo/SKILL.md", "v2\n")
        self.commit("change skill")
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--base", "main", "--repo", str(self.repo)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
