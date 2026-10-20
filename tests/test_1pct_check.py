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
    def test_bold_first_action_establishes_lazy_paragraph_scope(self):
        for outer,indent in (('- Account tasks','  '),('1. Account tasks','   ')):
            for action in ('You send this draft.','Enter your password.'):
                for br in ('','  ',chr(92)):
                    text=outer+'\n'+indent+'## Next steps\n'+indent+'**'+action+'**'+br+'\nThen run the tests.'
                    self.assertIn('next-steps-heading',check.find_violations(text))

    def test_blank_separated_parent_paragraph_retires_child_scope(self):
        for text in ('- Parent\n  - Child\n\n  Details.\n    ## Next steps\n    - Enter your password.\n\n  Run the tests.','1. Parent\n   - Child\n\n   Details.\n     ## Next steps\n     - Enter your password.\n\n   Run the tests.'):
            self.assertIn('next-steps-heading',check.find_violations(text))

    def test_hard_break_does_not_end_lazy_list_paragraph(self):
        for prefix in ('- Account tasks\n  ## Next steps\n  - Enter your password.','1. Account tasks\n   ## Next steps\n   - Enter your password.'):
            for br in ('  ',chr(92)):
                self.assertIn('next-steps-heading',check.find_violations(prefix+br+'\nThen run the tests.'))

    def test_lazy_dedented_continuation_stays_in_next_actions(self):
        for prefix in ('- Account tasks\n  ## Next steps\n  - Enter your password.\n','1. Account tasks\n   ## Next steps\n   - Enter your password.\n'):
            for tail in ('Then run the tests.','and run the tests.'):
                self.assertIn('next-steps-heading',check.find_violations(prefix+tail))

    def test_populated_list_scope_ends_before_sibling_or_dedent(self):
        for suffix in ('- Tests passed.','\nTests passed.'):
            text='- Account tasks\n  ## Next steps\n  - Enter your password.\n'+suffix
            self.assertNotIn('next-steps-heading',check.find_violations(text))
        text='- Parent\n  - Child\n  ## Next steps\n    ### Next step\n  You send this draft.'
        self.assertNotIn('next-steps-heading',check.find_violations(text))

    def test_context_labels_keep_action_case(self):
        for label in ('### **Account access**:', '### Account access:', '**Account access**:'):
            with self.subTest(label=label):
                self.assertNotIn('next-steps-heading',check.find_violations('## Next steps\n'+label+'\n- Enter your password in the browser.'))
        self.assertNotIn('next-steps-heading',check.find_violations('## Next steps\n### You send this draft to Alice'))

    def test_subsection_boundaries_never_merge_work_into_recipient(self):
        for heading in ('### Remaining work','**Remaining work**'):
            self.assertIn('next-steps-heading',check.find_violations('## Next steps\n- You send this draft to Alice\n'+heading+'\nRun Tests'))
        self.assertNotIn('next-steps-heading',check.find_violations('## Next steps\n- Enter your password.\n### Next step\n- You send this draft.'))
        self.assertIn('next-steps-heading',check.find_violations('## Next steps\n- Run the tests.\n### Next step\n- You send this draft.'))

    def test_blank_paragraph_and_bold_nested_container(self):
        self.assertIn('next-steps-heading',check.find_violations('## Next steps\n- You send this draft to Alice\n\nRun Tests'))
        self.assertNotIn('next-steps-heading',check.find_violations('## Next steps\n**Next step**\n- Enter your password.'))
        self.assertIn('next-steps-heading',check.find_violations('## Next steps\n**Next step**\n- Enter your password.\n- Run Tests'))

    def test_nested_label_sibling_and_markdown_hard_break(self):
        self.assertNotIn('next-steps-heading',check.find_violations('## Next steps\n**Next step**\n- Enter your password.\n## Notes\nTests passed.'))
        for br in ('  ', '\\'):
            self.assertIn('next-steps-heading',check.find_violations('## Next steps\n- You send this draft to Alice'+br+'\n  Run Tests'))

    def test_hard_break_after_wrapped_recipient(self):
        for br in ('  ', '\\'):
            self.assertIn('next-steps-heading',check.find_violations('## Next steps\n- You send this draft\n  to Alice'+br+'\n  Run Tests'))

    def test_backslash_break_keeps_personal_actions_valid(self):
        self.assertNotIn('next-steps-heading',check.find_violations('## Next steps\n- Enter your password.\\\n  You send this draft.'))

    def test_indented_heading_keeps_nested_work_visible(self):
        self.assertIn('next-steps-heading',check.find_violations('## Next steps\n- Enter your password.\n\n  ## Remaining work\n  Run the tests.'))
        self.assertNotIn('next-steps-heading',check.find_violations('## Next steps\n- Enter your password.\n## Notes\nTests passed.'))

    def test_markdown_sibling_and_bold_hard_break_boundaries(self):
        self.assertNotIn('next-steps-heading',check.find_violations('## Next steps\n- Enter your password.\n\n ## Notes\nTests passed.'))
        for br in ('  ', '\\'):
            self.assertIn('next-steps-heading',check.find_violations('## Next steps\n- You send this draft to Alice\n  **Run Tests**'+br+'\n- Enter your password.'))

    def test_parent_list_boundary_survives_nested_bullets(self):
        for outer,inner,indent in (('- ','  - ','  '),('1. ','   - ','   '),('- ','  1. ','  ')):
            prefix='## Next steps\n'+outer+'Enter your password.\n'+inner+'You send this draft.\n\n'+indent+'## Remaining work\n'+indent
            self.assertIn('next-steps-heading',check.find_violations(prefix+'Run the tests.'))
            self.assertNotIn('next-steps-heading',check.find_violations(prefix+'You confirm the scope.'))

    def test_nested_next_container_keeps_parent_context(self):
        prefix='## Next steps\n- Enter your password.\n\n  **Next step**\n\n  ## Account access\n  '
        self.assertNotIn('next-steps-heading',check.find_violations(prefix+'You send this draft.'))
        self.assertIn('next-steps-heading',check.find_violations(prefix+'Run the tests.'))

    def test_tab_columns_keep_nested_work_visible(self):
        prefix='## Next steps\n- Enter your password.\n\n\t## Remaining work\n\t'
        self.assertIn('next-steps-heading',check.find_violations(prefix+'Run the tests.'))
        self.assertNotIn('next-steps-heading',check.find_violations(prefix+'You send this draft.'))

    def test_dedented_paragraph_ends_list_before_sibling(self):
        prefix='## Next steps\n- Enter your password.\n\nYou send this draft.\n\n  ## Notes\nTests passed.'
        self.assertNotIn('next-steps-heading',check.find_violations(prefix))

    def test_list_heading_does_not_leak_into_next_section(self):
        text='## Status\n- Completed work\n  #### Details\n\n**Next steps**\n- Enter your password.\n\n### Remaining work\n- Run the tests.'
        self.assertIn('next-steps-heading',check.find_violations(text))

    def test_structural_dedent_ends_list_without_blank_line(self):
        for heading in ('### You send this draft.','### Account access\n  You send this draft.'):
            self.assertNotIn('next-steps-heading',check.find_violations('## Next steps\n- Enter your password.\n'+heading+'\n\n  ## Notes\nTests passed.'))

    def test_explicit_indented_heading_uses_own_level(self):
        self.assertIn('next-steps-heading',check.find_violations('#### Status\n\n ## Next steps\n- Enter your password.\n\n### Remaining work\n- Run the tests.'))
        self.assertNotIn('next-steps-heading',check.find_violations(' ## Next steps\n- Enter your password.\n ## Notes\nTests passed.'))

    def test_bold_label_after_real_indented_outer_heading(self):
        self.assertIn('next-steps-heading',check.find_violations('#### Status\n ## Work\n**Next steps**\n- Enter your password.\n### Remaining work\n- Run the tests.'))

    def test_empty_trailing_next_step_is_not_borrowed_content(self):
        for text in ('**Next steps**\n- Enter your password.\n\n**Next steps**','## Next steps\n- Enter your password.\n### Next steps'):
            self.assertIn('next-steps-heading',check.find_violations(text))
        self.assertNotIn('next-steps-heading',check.find_violations('## Next steps\n### Next step\n- Enter your password.'))

    def test_empty_nested_heading_closes_at_its_own_sibling(self):
        for sibling in ('### Account access','### Next step'):
            self.assertIn('next-steps-heading',check.find_violations('## Next steps\n### Next step\n'+sibling+'\n- Enter your password.'))
        self.assertNotIn('next-steps-heading',check.find_violations('## Next steps\n### Next step\n#### Account access\n- Enter your password.'))

    def test_pending_heading_uses_list_scope(self):
        self.assertIn('next-steps-heading',check.find_violations('## Next steps\n- Enter your password.\n  ### Next step\n  ### Account access\n  - You send this draft.'))
        self.assertNotIn('next-steps-heading',check.find_violations('## Next steps\n- Enter your password.\n  ### Next step\n    - You send this draft.'))

    def test_empty_child_never_borrows_sibling_or_dedented_content(self):
        prefix='## Next steps\n- Enter your password.\n  ### Next step\n'
        for ending in ('- You send this draft.','You send this draft.','\nYou send this draft.','  - You send this draft.\n- Enter your password.'):
            with self.subTest(ending=ending):
                if ending.startswith('  -'):
                    self.assertNotIn('next-steps-heading',check.find_violations(prefix+ending))
                else:self.assertIn('next-steps-heading',check.find_violations(prefix+ending))

    def test_same_scope_nested_notes_closes_personal_section(self):
        for outer,indent in (('- ','  '),('1. ','   ')):
            text=outer+'Account tasks\n'+indent+'## Next steps\n'+indent+'- Enter your password.\n'+indent+'## Notes\n'+indent+'Tests passed.'
            self.assertNotIn('next-steps-heading',check.find_violations(text))
        self.assertIn('next-steps-heading',check.find_violations('## Next steps\n- Enter your password.\n  ## Notes\n  Run the tests.'))

    def test_bold_lazy_continuations_keep_personal_section_scope(self):
        for outer,indent in (('- ','  '),('1. ','   ')):
            for br in ('','  ','\\'):
                prefix=outer+'Account tasks\n'+indent+'## Next steps\n'+indent+'- Enter your password.'+br+'\n'
                for work in ('**Then run the tests.**','**Remaining work**\nRun the tests.'):
                    with self.subTest(outer=outer,br=br,work=work):
                        self.assertIn('next-steps-heading',check.find_violations(prefix+work))
                self.assertNotIn('next-steps-heading',check.find_violations(prefix+'**You send this draft.**'))

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

    def test_personal_actions_allow_context_but_not_extra_work(self):
        for action in ('You send this draft to Alice.','You send this draft to Alice and Bob.','Please enter your password in the browser.','You must confirm the scope of the production change.'):
            self.assertNotIn('next-steps-heading',check.find_violations('## Next steps\n- '+action))
        for body in ('- Enter your password.\n  **Then run the tests.**','- Enter your password.\n### Run the tests','- Enter your password in the browser and run the tests.'):
            self.assertIn('next-steps-heading',check.find_violations('## Next steps\n'+body))

    def test_qualified_personal_steps_do_not_hide_separate_actions(self):
        for body in ('- Enter your password in the browser\n**Run the tests**','- Enter your password in the browser\n\n**Run the tests**','- Enter your password in the browser and you must run the tests','- You send this draft to Alice and **run** the tests.'):
            self.assertIn('next-steps-heading',check.find_violations('## Next steps\n'+body))
        for label in ('### Account access:','### **Account access**'):
            text='## Next steps\n- You send this draft to Alice.\n'+label+'\n- Enter your password in the browser.'
            self.assertNotIn('next-steps-heading',check.find_violations(text))
            self.assertIn('next-steps-heading',check.find_violations(text+'\n- Run the tests.'))

    def test_nested_next_step_sections_do_not_hide_work(self):
        for body in (
            "- Enter your password.\n### Remaining work\n- Run the tests.",
            "- Enter your password.\n#### Work\n- Run the tests.",
            "- Enter your password.\n**Remaining work**\n- Run the tests.",
        ):
            self.assertIn("next-steps-heading", check.find_violations("## Next steps\n" + body))

    def test_long_heading_near_match_is_bounded(self):
        code = "import importlib.util; s=importlib.util.spec_from_file_location('hook'," + repr(str(HOOK)) + "); m=importlib.util.module_from_spec(s);s.loader.exec_module(m);assert m.find_violations('Next steps'+' '*2000+'x')==[]"
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=2)
        self.assertEqual(result.returncode, 0, result.stderr)

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

    def test_strict_personal_context_does_not_block(self):
        for action in ('You send this draft to Alice and Bob.','Please enter your password in the browser.','You must confirm the scope of the production change.'):
            self.say('## Next steps\n- '+action)
            result=self.run_hook(ONE_PCT_STRICT='1')
            self.assertEqual(result.returncode,0,result.stderr)

    def test_required_scope_approval_is_diagnostic_only(self):
        for text in (
            "Stop sign: this production change is outside the approved scope. Waiting for your approval.",
        ):
            self.say(text)
            result = self.run_hook(ONE_PCT_STRICT="1")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("waiting-on-go", json.loads(self.log.read_text().splitlines()[-1])["flags"])

    def test_already_approved_work_wait_remains_blocking(self):
        for text in ('Waiting for your approval.', 'Once you approve, I will run the already-authorized tests.', 'I will run the already-approved tests once you confirm.'):
            self.say(text)
            self.assertEqual(self.run_hook(ONE_PCT_STRICT='1').returncode,2)

    def test_required_wait_code_does_not_expand_exact_exception(self):
        wait='Stop sign: this production change is outside the approved scope. Waiting for your approval.'
        for text in (wait+'\n```\nRun Tests\n```','```\nRun Tests\n```\n'+wait):
            self.say(text)
            self.assertEqual(self.run_hook(ONE_PCT_STRICT='1').returncode,2)

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
