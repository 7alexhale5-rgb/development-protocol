"""Tests for the /1pct Stop hook. Run from the repo root: python3 -m unittest discover tests"""

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "skills/1pct/hooks/1pct-check.py"
_spec = importlib.util.spec_from_file_location("one_pct_check", HOOK)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


class Patterns(unittest.TestCase):
    def test_each_red_flag_is_caught(self):
        cases = {
            "ready-to-implement": "Plan is set. Ready to implement?",
            "ready-to-proceed": "Tests pass. Ready to proceed?",
            "would-you-like": "Would you like me to add the migration?",
            "suggested-next": "Suggested next:\n- A\n- B",
            "shall-i-continue": "Step 3 done. Shall I continue?",
            "fresh-session": "We could finish this in a fresh session.",
            "whats-next-summary": "Committed at abc123. What's next?",
            "context-as-question": "Context is MODERATE, should I close out?",
        }
        for label, text in cases.items():
            with self.subTest(label):
                self.assertIn(label, check.find_violations(text))

    def test_additional_stall_signals_and_human_only_controls(self):
        cases = {
            "want-me-to": "Do you want me to continue?",
            "should-i": "Should I run the next check?",
            "let-me-know": "Let me know if you would like me to continue.",
            "say-the-word": "Just say the word.",
            "i-can-if-you-like": "If you would like, I can run it.",
            "waiting-on-go": "Waiting for your approval.",
            "next-steps-heading": "## Next steps\n- Run the tests.\n- Merge the approved change.",
        }
        for label, text in cases.items():
            with self.subTest(label):
                self.assertIn(label, check.find_violations(text))
        self.assertNotIn("next-steps-heading", check.find_violations("## Next steps\n- Enter your password.\n- You send this draft."))
        self.assertIn("next-steps-heading", check.find_violations("## Next steps\n- Enter your password.\n- Run the tests."))

    def test_human_exemption_checks_complete_sections(self):
        cases = (
            "## Next steps\n- Enter your password.\n\n- Run the tests.",
            "## Next steps\n- Run the tests.\n## Next steps\n- You send this draft.",
            "## Next steps\n- Enter your password.\n  Then run the tests.",
            "## Next steps\n- Enter your password.\n\nRun the tests.",
            "## Next steps\n- Enter your password.\n\n  Run the tests.",
            "## Next steps\n- Enter your password and run tests.",
            "## Next steps\n- Send the migration to production.",
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertIn("next-steps-heading", check.find_violations(text))
        for text in (
            "## Next steps\n- Enter your password.\n\n- You send this draft.",
            "## Next steps\n- Enter your password.\n## Other notes\nTests passed.",
            "## Next steps\n- Enter your password.\n## Next steps\n- You send this draft.",
        ):
            with self.subTest(text=text):
                self.assertNotIn("next-steps-heading", check.find_violations(text))

    def test_human_exemption_rejects_topic_words_and_ambiguity(self):
        for action in (
            "Fix the OAuth callback.", "Add password validation.",
            "Implement the pricing page.", "Draft regression tests.",
            "Review the draft.", "OAuth consent needs work.",
            "Decide whether to use the existing parser.",
        ):
            with self.subTest(action=action):
                self.assertIn("next-steps-heading", check.find_violations("## Next steps\n- " + action))

    def test_quoted_phrases_in_code_are_not_flagged(self):
        text = "The skill bans `Would you like me to` and\n```\nReady to proceed?\n```\nDone."
        self.assertEqual(check.find_violations(text), [])

    def test_decisive_text_is_clean(self):
        text = "Phase 2 shipped @ abc123. Dispatching Phase 3."
        self.assertEqual(check.find_violations(text), [])
        self.assertEqual(check.find_violations(""), [])

    def test_last_assistant_text_claude_and_codex_formats(self):
        with tempfile.TemporaryDirectory() as d:
            claude = Path(d) / "c.jsonl"
            claude.write_text(
                json.dumps({"type": "assistant", "message": {"role": "assistant",
                            "content": [{"type": "text", "text": "first"}]}}) + "\n"
                + json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}) + "\n"
                + json.dumps({"type": "assistant", "message": {"role": "assistant",
                              "content": [{"type": "text", "text": "last"}]}}) + "\n"
            )  # fmt: skip
            self.assertEqual(check._last_assistant_text(claude), "last")
            codex = Path(d) / "x.jsonl"
            codex.write_text(json.dumps({"type": "response_item", "payload": {
                "role": "assistant", "content": [{"type": "output_text", "text": "codex"}]}}) + "\n")  # fmt: skip
            self.assertEqual(check._last_assistant_text(codex), "codex")


class HookRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name).resolve()
        self.transcript = self.home / ".claude" / "projects" / "p" / "s.jsonl"
        self.transcript.parent.mkdir(parents=True)
        self.say("Step 3 is done. Would you like me to run step 4?")
        self.log = self.home / ".devproto-stack" / "logs" / "1pct-violations.log"

    def tearDown(self):
        self.tmp.cleanup()

    def say(self, text, path=None):
        rec = {"type": "assistant",
               "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}  # fmt: skip
        (path or self.transcript).write_text(json.dumps(rec) + "\n")

    def run_hook(self, payload=None, **env_extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith("ONE_PCT_")}
        env["HOME"] = str(self.home)
        env.update(env_extra)
        stdin = payload if isinstance(payload, str) else json.dumps(
            payload or {"transcript_path": str(self.transcript)})  # fmt: skip
        return subprocess.run([sys.executable, str(HOOK)], input=stdin,
                              capture_output=True, text=True, env=env)  # fmt: skip

    def test_measures_without_blocking_by_default(self):
        r = self.run_hook()
        self.assertEqual(r.returncode, 0, r.stderr)
        entry = json.loads(self.log.read_text().splitlines()[-1])
        self.assertEqual(entry["flags"], ["would-you-like"])
        self.assertEqual(entry["transcript"], "p/s.jsonl")
        self.assertEqual(stat.S_IMODE(self.log.stat().st_mode), 0o600)

    def test_strict_mode_blocks(self):
        r = self.run_hook(ONE_PCT_STRICT="1")
        self.assertEqual(r.returncode, 2)
        self.assertIn("would-you-like", r.stderr)

    def test_strict_mode_blocks_loose_mixed_lists_and_topic_exemptions(self):
        for text in (
            "## Next steps\n- Enter your password.\n\n- Run the tests.",
            "## Next steps\n- Implement the pricing page.\n- Draft regression tests.",
        ):
            with self.subTest(text=text):
                self.say(text)
                result = self.run_hook(ONE_PCT_STRICT="1")
                self.assertEqual(result.returncode, 2)
                self.assertIn("next-steps-heading", result.stderr)
                self.assertIn("next-steps-heading", json.loads(self.log.read_text().splitlines()[-1])["flags"])

    def test_stop_hook_active_does_not_block_or_log_twice(self):
        r = self.run_hook({"transcript_path": str(self.transcript), "stop_hook_active": True}, ONE_PCT_STRICT="1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.log.exists())

    def test_clean_turn_is_not_logged(self):
        self.say("Step 4 done. Running step 5.")
        self.assertEqual(self.run_hook(ONE_PCT_STRICT="1").returncode, 0)
        self.assertFalse(self.log.exists())

    def test_path_outside_agent_homes_is_ignored(self):
        outside = self.home / "elsewhere.jsonl"
        self.say("Would you like me to continue?", outside)
        r = self.run_hook({"transcript_path": str(outside)}, ONE_PCT_STRICT="1")
        self.assertEqual(r.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_disable_bad_stdin_and_log_dir_override(self):
        self.assertEqual(
            self.run_hook(ONE_PCT_STRICT="1", ONE_PCT_DISABLE="1").returncode, 0
        )
        self.assertEqual(self.run_hook("not json").returncode, 0)
        other = self.home / "logs2"
        self.assertEqual(self.run_hook(ONE_PCT_LOG_DIR=str(other)).returncode, 0)
        self.assertTrue((other / "1pct-violations.log").is_file())
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
