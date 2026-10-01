"""Tests for skills/development-protocol/scripts/_shared.py redact().

R2-5: output_tail is stored (after redaction) in a git-trackable .devproto/*.json
file, but the pattern set had gaps: connection-string credentials, common env-var
key/token/secret/password dumps, JWTs, Stripe live/test keys and Google API keys
all survived redact() unchanged. Run: python3 -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills/development-protocol/scripts"))
import _shared  # noqa: E402


class RedactTest(unittest.TestCase):
    def assert_redacted(self, secret, text=None):
        text = text if text is not None else f"failure output: {secret}\n"
        out = _shared.redact(text)
        self.assertNotIn(secret, out, f"{secret!r} survived redact()")
        self.assertIn("[REDACTED]", out)

    def test_connection_string_credentials_are_redacted(self):
        self.assert_redacted(
            "postgres://app:hunter2@db.internal:5432/prod",
            "DATABASE_URL=postgres://app:hunter2@db.internal:5432/prod\n",
        )

    def test_jwt_is_redacted(self):
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        self.assert_redacted(jwt)

    def test_stripe_live_key_is_redacted(self):
        self.assert_redacted("sk_live_" + "a1B2c3D4e5F6g7H8")

    def test_stripe_test_key_is_redacted(self):
        self.assert_redacted("sk_test_" + "a1B2c3D4e5F6g7H8")

    def test_google_api_key_is_redacted(self):
        self.assert_redacted("AIza" + "S" * 35)

    def test_generic_key_env_var_is_redacted(self):
        self.assert_redacted(
            "abc123def456",
            "SUPABASE_SERVICE_ROLE_KEY=abc123def456\n",
        )

    def test_generic_token_env_var_is_redacted(self):
        self.assert_redacted("t0k3n-value-xyz", "AUTH_TOKEN=t0k3n-value-xyz\n")

    def test_still_catches_existing_shapes(self):
        # Guard against a rewrite of REDACT_PATTERNS dropping prior coverage.
        self.assert_redacted("sk-ant-" + "a" * 20)
        self.assert_redacted("AKIA" + "B" * 16)


class RunBashTest(unittest.TestCase):
    """R2-6: run_bash's docstring promises it never raises for a caller. A
    command that writes invalid UTF-8 (e.g. a non-UTF-8 filename echoed by
    `rg --files`) raised UnicodeDecodeError out of the strict decode in
    subprocess.run(text=True), which no caller catches."""

    def test_invalid_utf8_output_does_not_raise(self):
        code, out, err = _shared.run_bash(r"printf '\xff\n'")
        self.assertEqual(code, 0)
        self.assertIsInstance(out, str)
        self.assertIsInstance(err, str)


class RunVerifierTest(unittest.TestCase):
    def test_pipeline_failure_propagates(self):
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            code, _ = _shared.run_verifier("false | tee check.log", Path(folder), 5)
        self.assertNotEqual(code, 0)

    def test_missing_bash_fails_cleanly(self):
        from unittest.mock import patch

        with patch.object(_shared.shutil, "which", return_value=None):
            code, output = _shared.run_verifier("true", ROOT, 5)
        self.assertEqual(code, 127)
        self.assertIn("bash", output)


class EvidenceSectionsTest(unittest.TestCase):
    def test_bundled_premortem_template_verifies_only_with_real_revisions(self):
        import subprocess
        import tempfile

        source = (ROOT / "skills/devilsadvocate/references/premortem.md").read_text()
        template = (
            source.split("## Output Template", 1)[1]
            .split("```markdown\n", 1)[1]
            .split("```", 1)[0]
        )
        title = "Top revisions to apply BEFORE building"
        self.assertFalse(_shared.sections_have_content(template, [title]))
        completed = template.replace(
            "[most critical revision, from the top-impact chain]",
            "Reject unsigned records before accepting a saved proof.",
        )
        with tempfile.TemporaryDirectory() as folder:
            evidence = Path(folder) / "premortem.md"
            evidence.write_text(completed)
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(_shared.__file__)),
                    "--evidence",
                    str(evidence),
                    "--section",
                    title,
                ],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_bundled_brainstorm_requires_filled_boundary(self):
        import tempfile
        import subprocess
        source = (ROOT / "skills/brainstorm-stack/SKILL.md").read_text()
        template = source.split("## Step 5: Generate the Context Document", 1)[1].split("```markdown\n", 1)[1].split("```", 1)[0]
        decisions = template.replace("[Decision made during questioning, with rationale]", "Use a local SQLite file for saved records.")
        completed = decisions.replace("[specific deliverables agreed during questioning]", "Local record storage only.").replace("[items explicitly excluded]", "No hosted service or external sends.")
        for text, expected in ((decisions, 1), (completed, 0)):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                evidence = Path(tmp) / "brainstorm.md"
                evidence.write_text(text)
                result = subprocess.run([sys.executable, str(Path(_shared.__file__)), "--evidence", str(evidence), "--section", "Key Decisions", "--section", "Project Boundary"], capture_output=True)
                self.assertEqual(result.returncode, expected)

    def test_empty_headings_fail(self):
        self.assertFalse(
            _shared.sections_have_content(
                "## Key Decisions\n\n## Project Boundary\n",
                ["Key Decisions", "Project Boundary"],
            )
        )

    def test_comments_placeholders_and_empty_bullets_fail(self):
        for body in (
            "<!-- add decisions here -->",
            "- ",
            "TODO",
            "[Decision with rationale]",
        ):
            with self.subTest(body=body):
                self.assertFalse(
                    _shared.sections_have_content(
                        "## Key Decisions\n" + body, ["Key Decisions"]
                    )
                )

    def test_nested_section_content_passes(self):
        text = "## Key Decisions\n### Storage\n- Use SQLite for local records.\n## Project Boundary\n- In scope: local data only.\n"
        self.assertTrue(
            _shared.sections_have_content(text, ["Key Decisions", "Project Boundary"])
        )

    def test_content_in_later_section_does_not_fill_empty_section(self):
        self.assertFalse(
            _shared.sections_have_content(
                "## Key Decisions\n## Other\nA real decision here.\n", ["Key Decisions"]
            )
        )

    def test_missing_file_cli_fails(self):
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(Path(_shared.__file__)),
                "--evidence",
                "/no-such-evidence.md",
                "--section",
                "Key Decisions",
            ],
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
