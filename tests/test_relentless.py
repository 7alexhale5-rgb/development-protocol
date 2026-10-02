"""Tests for the relentless sweep ledger and its Stop hook.

Run from the repo root: python3 -m unittest discover tests
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills/relentless"
SWEEP = SKILL / "scripts/sweep.py"
HOOK = SKILL / "hooks/relentless-stop.py"
MUTANTS = SKILL / "scripts/mutants.py"
sys.path.insert(0, str(SWEEP.parent))
import sweep  # noqa: E402
import _shared  # noqa: E402 (loaded onto sys.path as a side effect of importing sweep)

CLEAN = ("SWEEP_HOME", "SWEEP_TRANSCRIPTS", "SWEEP_SESSION_ID",
         "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "RELENTLESS_LOG")  # fmt: skip


def quiet(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()):
        with contextlib.redirect_stderr(io.StringIO()):
            return fn(*args)


class SelfTests(unittest.TestCase):
    """The scripts carry their own self-tests; mutants.py proves those can fail."""

    def test_sweep_selftest(self):
        self.assertEqual(quiet(sweep.selftest), 0)

    def test_hook_selftest(self):
        r = subprocess.run([sys.executable, str(HOOK), "--selftest"],
                           capture_output=True, text=True, env=self.env())  # fmt: skip
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_every_mutant_is_killed(self):
        r = subprocess.run([sys.executable, str(MUTANTS)],
                           capture_output=True, text=True, env=self.env())  # fmt: skip
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr)
        self.assertIn("every mutant killed", r.stdout)

    @staticmethod
    def env():
        return {k: v for k, v in os.environ.items() if k not in CLEAN}


class RunBashTest(unittest.TestCase):
    """F10: sweep.py's bash runner (shared with pathway.py) never raises."""

    def test_missing_bash_is_a_clean_failure_not_a_crash(self):
        orig = _shared.shutil.which
        _shared.shutil.which = lambda name: None
        try:
            code, out, err = _shared.run_bash("echo hi")
        finally:
            _shared.shutil.which = orig
        self.assertEqual(code, 127)
        self.assertEqual(out, "")
        self.assertIn("bash", err)

    def test_oserror_starting_bash_is_a_clean_failure(self):
        orig = _shared.subprocess.run

        def boom(*a, **k):
            raise OSError("simulated: bash disappeared mid-launch")

        _shared.subprocess.run = boom
        try:
            code, out, err = _shared.run_bash("echo hi")
        finally:
            _shared.subprocess.run = orig
        self.assertEqual(code, 126)
        self.assertIn("simulated", err)

    def test_timeout_is_a_clean_failure(self):
        code, out, err = _shared.run_bash("sleep 5", timeout=0.1)
        self.assertEqual(code, 124)
        self.assertIn("timed out", err)

    def test_enumerate_ids_reports_missing_bash_without_raising(self):
        orig = _shared.shutil.which
        _shared.shutil.which = lambda name: None
        try:
            ids, record, error = sweep.enumerate_ids("echo hi")
        finally:
            _shared.shutil.which = orig
        self.assertIsNone(ids)
        self.assertIsNotNone(error)
        self.assertIn("bash", error)


class Store(unittest.TestCase):
    """The ledger defaults to <repo>/.sweeps/, found from anywhere in the repo."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.repo = base / "repo"
        (self.repo / "src" / "deep").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        self.other = base / "plain"
        self.other.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def sweep(self, *argv, cwd=None, session="s1", **extra):
        env = {k: v for k, v in os.environ.items() if k not in CLEAN}
        if session:
            env["SWEEP_SESSION_ID"] = session
        env.update(extra)
        return subprocess.run([sys.executable, str(SWEEP), *argv], cwd=str(cwd or self.repo),
                              capture_output=True, text=True, env=env)  # fmt: skip

    def init(self, slug="demo", **kw):
        return self.sweep("init", "--slug", slug, "--goal", "g", "--done", "d", **kw)

    def test_default_store_is_repo_dot_sweeps(self):
        r = self.init(cwd=self.repo / "src" / "deep")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.repo / ".sweeps/demo/ledger.json").is_file())
        self.assertTrue((self.repo / ".sweeps/demo/RESUME.md").is_file())
        # found again from another folder of the same repo
        r = self.sweep("add", "a", "b", cwd=self.repo / "src")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads((self.repo / ".sweeps/demo/ledger.json").read_text())
        self.assertEqual(data["project"], str(self.repo))
        self.assertEqual(len(data["universe"]), 2)

    def test_project_flag_must_be_a_real_folder(self):
        r = self.sweep(
            "status", "--project", str(self.other / "nope"), "--slug", "demo"
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("is not a folder", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_project_flag_picks_the_store(self):
        r = self.init(cwd=self.other)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.sweep(
            "status", "--project", str(self.repo), "--slug", "demo", cwd=self.other
        )
        self.assertEqual(r.returncode, 0)
        self.assertIn("no sweep ledger", r.stdout)  # the repo store is empty
        r = self.sweep("init", "--project", str(self.repo), "--slug", "demo",
                       "--goal", "g", "--done", "d", cwd=self.other)  # fmt: skip
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.repo / ".sweeps/demo/ledger.json").is_file())

    def test_outside_git_the_folder_itself_holds_the_store(self):
        self.assertEqual(self.init(cwd=self.other).returncode, 0)
        self.assertTrue((self.other / ".sweeps/demo/ledger.json").is_file())

    def test_sweep_home_overrides_the_store(self):
        home = self.other / "store"
        self.assertEqual(self.init(SWEEP_HOME=str(home)).returncode, 0)
        self.assertTrue((home / "demo/ledger.json").is_file())
        self.assertFalse((self.repo / ".sweeps").exists())

    def test_session_id_prefers_sweep_session_id(self):
        self.init(CLAUDE_CODE_SESSION_ID="claude-id")
        data = json.loads((self.repo / ".sweeps/demo/ledger.json").read_text())
        self.assertEqual(data["session_id"], "s1")
        self.init("demo2", session=None, CLAUDE_CODE_SESSION_ID="claude-id")
        data = json.loads((self.repo / ".sweeps/demo2/ledger.json").read_text())
        self.assertEqual(data["session_id"], "claude-id")

    def test_codex_thread_id_is_recorded_when_no_override_exists(self):
        self.init("codex", session=None, CODEX_THREAD_ID="codex-thread")
        data = json.loads((self.repo / ".sweeps/codex/ledger.json").read_text())
        self.assertEqual(data["session_id"], "codex-thread")

    def test_file_without_auditable_session_cannot_close(self):
        target = self.repo / "readme.txt"
        target.write_text("whole file\n")
        self.init(session=None)
        self.sweep("add", "--slug", "demo", "readme.txt", session=None)
        self.sweep(
            "visit", "--slug", "demo", "readme.txt", "--depth", "2", "--evidence", "read", session=None
        )
        result = self.sweep("close", "--slug", "demo", session=None)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("never opened", result.stderr)

    def test_file_with_missing_transcript_cannot_close(self):
        (self.repo / "readme.txt").write_text("whole file\n")
        self.init()
        self.sweep("add", "readme.txt")
        self.sweep("visit", "readme.txt", "--depth", "2", "--evidence", "read")
        result = self.sweep("close", "--slug", "demo", SWEEP_TRANSCRIPTS=str(self.other / "missing"))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("never opened", result.stderr)

    def test_old_closed_file_ledger_with_unauditable_reads_fails_verify(self):
        (self.repo / "readme.txt").write_text("whole file\n")
        self.init(session=None)
        self.sweep("add", "--slug", "demo", "readme.txt", session=None)
        self.sweep(
            "visit", "--slug", "demo", "readme.txt", "--depth", "2", "--evidence", "read", session=None
        )
        closed = self.repo / ".sweeps/demo/ledger.json"
        data = json.loads(closed.read_text())
        data.update(status="closed", forced=[], unauditable=1)
        closed.write_text(json.dumps(data))
        result = self.sweep("verify", str(closed), session=None)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("unauditable", result.stderr)

    def test_verify_reads_a_closed_ledger(self):
        self.init()
        self.sweep("add", "item-one", "item-two")
        open_ledger = self.repo / ".sweeps/demo/ledger.json"
        self.assertEqual(self.sweep("verify", str(open_ledger)).returncode, 1)
        self.sweep(
            "visit", "item-one", "item-two", "--depth", "2", "--evidence", "read"
        )
        r = self.sweep("close", "--slug", "demo")
        self.assertEqual(r.returncode, 0, r.stderr)
        closed = next((self.repo / ".sweeps/_closed").glob("demo-*/ledger.json"))
        before = closed.read_bytes()
        r = self.sweep("verify", str(closed.parent))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(closed.read_bytes(), before, "verify must not write")
        self.assertEqual(
            self.sweep("verify", str(self.other / "nope.json")).returncode, 2
        )

    def fire(self, cwd, session="s1", event="Stop"):
        env = {k: v for k, v in os.environ.items() if k not in CLEAN}
        payload = {"session_id": session, "hook_event_name": event, "cwd": str(cwd)}
        return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                              capture_output=True, text=True, env=env, cwd=str(self.other))  # fmt: skip

    def test_hook_reads_the_store_of_the_payload_cwd(self):
        self.init()
        self.sweep("add", "x")
        r = self.fire(self.repo / "src")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("not done", r.stderr)
        self.assertTrue((self.repo / ".sweeps/stop-hook.log").is_file())
        # a project with no sweeps: silent, and no .sweeps/ folder is created
        r = self.fire(self.other)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertFalse((self.other / ".sweeps").exists())
        # another session's sweep never blocks
        self.assertEqual(self.fire(self.repo, session="s2").returncode, 0)

    def test_hook_fails_open_on_bad_stdin(self):
        env = {k: v for k, v in os.environ.items() if k not in CLEAN}
        r = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True,
                           text=True, env=env, cwd=str(self.other))  # fmt: skip
        self.assertEqual(r.returncode, 0)
        self.assertFalse((self.other / ".sweeps").exists())


if __name__ == "__main__":
    unittest.main()


class ReviewFixTests(unittest.TestCase):
    setUp = Store.setUp
    tearDown = Store.tearDown
    sweep = Store.sweep
    init = Store.init

    def test_failed_and_partial_read_requests_do_not_establish_full_coverage(self):
        from unittest.mock import patch
        transcripts = self.other / 'transcripts/proj'; transcripts.mkdir(parents=True)
        target = self.repo / 'a.py'; target.write_text('one\ntwo\nthree\n')
        transcript = transcripts / 's1.jsonl'
        def write(request, result=None):
            records = [{'message': {'content': [request]}}]
            if result is not None:
                records.append({'message': {'content': [result]}})
            transcript.write_text('\n'.join(json.dumps(r) for r in records))
        request = {'type': 'tool_use', 'id': 'r1', 'name': 'Read', 'input': {'file_path': str(target)}}
        with patch.dict(os.environ, {'SWEEP_TRANSCRIPTS': str(transcripts.parent)}):
            write(request)
            self.assertNotIn(str(target), sweep.session_reads('s1')[1])
            write(request, {'type': 'tool_result', 'tool_use_id': 'r1', 'is_error': True, 'content': 'denied'})
            self.assertNotIn(str(target), sweep.session_reads('s1')[1])
            write(request, {'type': 'tool_result', 'tool_use_id': 'r1', 'content': '1→one\n'})
            self.assertNotIn(str(target), sweep.session_reads('s1')[1])
            write(request, {'type': 'tool_result', 'tool_use_id': 'r1', 'content': '1→one\n2→two\n3→three\n'})
            self.assertIn(str(target), sweep.session_reads('s1')[1])

    def test_init_rechecks_existence_after_lock_acquisition(self):
        from unittest.mock import patch
        path = self.other / 'store/demo/ledger.json'
        @contextlib.contextmanager
        def concurrent_init(*args, **kwargs):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"winner": true}')
            yield
        with patch.dict(os.environ, {'SWEEP_HOME': str(path.parents[1])}), patch.object(sweep, 'ledger_lock', concurrent_init):
            with self.assertRaises(SystemExit):
                quiet(sweep.main, ['init', '--slug', 'demo', '--goal', 'g', '--done', 'd', '--project', str(self.repo)])
        self.assertEqual(json.loads(path.read_text()), {'winner': True})

    def test_revive_preserves_history_and_allows_normal_close(self):
        self.init()
        self.sweep('add', 'one', 'two', 'three', 'four')
        self.sweep('defer', 'three', 'four', '--why', 'later')
        self.sweep('visit', 'one', 'two', 'three', 'four', '--depth', '2', '--evidence', 'done')
        self.assertNotEqual(self.sweep('close').returncode, 0)
        result = self.sweep('revive', 'three', 'four', '--why', 'now completed')
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.repo / '.sweeps/demo/ledger.json').read_text())
        self.assertEqual(data['deferred'], [])
        self.assertTrue(any(row['event'] == 'revive' for row in data['log']))
        self.assertEqual(self.sweep('close').returncode, 0)

    def test_hook_rechecks_owner_and_open_status_under_lock(self):
        import importlib.util
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('relentless_stop_test', HOOK)
        hook = importlib.util.module_from_spec(spec); spec.loader.exec_module(hook)
        self.init()
        path = self.repo / '.sweeps/demo/ledger.json'
        for event in ('Stop', 'StopFailure'):
            for changed in ({'session_id': 'new-owner'}, {'status': 'checkpointed'}):
                data = json.loads(path.read_text()); data.update(status='open', session_id='s1'); path.write_text(json.dumps(data))
                def selected(session):
                    data.update(changed); path.write_text(json.dumps(data))
                    return [path]
                payload = json.dumps({'session_id': 's1', 'hook_event_name': event, 'cwd': str(self.repo)})
                with patch.object(sweep, 'open_ledgers_for', selected), patch.object(sys, 'stdin', io.StringIO(payload)):
                    result = quiet(hook.main)
                self.assertEqual(result, 0)
                self.assertEqual(json.loads(path.read_text()), data)


    def test_partial_reads_combine_and_failed_results_cannot_close(self):
        self.init()
        target = self.repo / 'readme.txt'; target.write_text('first\nsecond\n')
        self.sweep('add', 'readme.txt')
        self.sweep('visit', 'readme.txt', '--depth', '2', '--evidence', 'read all')
        root = self.other / 'transcripts/proj'; root.mkdir(parents=True)
        transcript = root / 's1.jsonl'
        records = []
        for ident, text in [('r1', '1→first\n'), ('r2', '2→second\n')]:
            records.append({'message': {'content': [{'type': 'tool_use', 'id': ident, 'name': 'Read',
                                                     'input': {'file_path': str(target), 'limit': 1}}]}})
            records.append({'message': {'content': [{'type': 'tool_result', 'tool_use_id': ident,
                                                     'is_error': ident == 'r2', 'content': text}]}})
        transcript.write_text('\n'.join(json.dumps(row) for row in records))
        environment = {'SWEEP_TRANSCRIPTS': str(root.parent)}
        self.assertEqual(self.sweep('close', **environment).returncode, 1)
        records[-1]['message']['content'][0]['is_error'] = False
        transcript.write_text('\n'.join(json.dumps(row) for row in records))
        self.assertEqual(self.sweep('close', **environment).returncode, 0)
