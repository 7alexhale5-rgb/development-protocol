from pathlib import Path
import sys

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "skills/relentless/scripts")
)

"""Staged integration checks; all ledgers/transcripts live in temporary dirs."""

import contextlib
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import sweep


SESSION = "00000000-0000-4000-8000-000000000001"


def receipt(
    path,
    *,
    text=None,
    exit_code=0,
    call_id="read-1",
    command=None,
    include_output=True,
    status="completed",
):
    command = command if command is not None else "cat " + str(path.resolve())
    source = (
        "const r=await tools.exec_command({cmd:" + json.dumps(command) + "});text(r)"
    )
    call = {
        "type": "response_item",
        "payload": {
            "type": "custom_tool_call",
            "name": "exec",
            "call_id": call_id,
            "status": status,
            "input": source,
        },
    }
    rows = [call]
    if include_output:
        rows.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call_output",
                    "call_id": call_id,
                    "output": [
                        {"type": "input_text", "text": "Script completed\nOutput:\n"},
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {
                                    "exit_code": exit_code,
                                    "output": text
                                    if text is not None
                                    else path.read_text(),
                                }
                            ),
                        },
                    ],
                },
            }
        )
    return rows


class CodexSweepTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.target = self.project / "test.txt"
        self.target.write_text("line one\nline two\n")
        self.codex_root = self.root / "sessions"
        self.transcript = (
            self.codex_root / "2026" / "09" / "30" / ("sample-" + SESSION + ".jsonl")
        )
        self.transcript.parent.mkdir(parents=True)
        env = patch.dict(
            os.environ,
            {
                "SWEEP_HOME": str(self.root / "sweeps"),
                "SWEEP_TRANSCRIPTS": str(self.root / "claude"),
                "SWEEP_CODEX_TRANSCRIPTS": str(self.codex_root),
                "SWEEP_CODEX_READ_PROOF": "1",
                "CODEX_THREAD_ID": SESSION,
            },
            clear=False,
        )
        env.start()
        self.addCleanup(env.stop)
        old_claude = os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        self.addCleanup(
            lambda: (
                os.environ.__setitem__("CLAUDE_CODE_SESSION_ID", old_claude)
                if old_claude is not None
                else os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
            )
        )

    def write_transcript(self, rows):
        meta = {"type": "session_meta", "payload": {"id": SESSION}}
        self.transcript.write_text(
            "".join(json.dumps(row) + "\n" for row in [meta, *rows])
        )

    def run_cli(self, *args):
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            try:
                return sweep.main(list(args))
            except SystemExit as error:
                return int(error.code or 0)

    def make_ledger(self, slug="proof"):
        self.assertEqual(
            self.run_cli(
                "init",
                "--slug",
                slug,
                "--goal",
                "g",
                "--done",
                "d",
                "--depth",
                "2",
                "--project",
                str(self.project),
            ),
            0,
        )
        self.assertEqual(self.run_cli("add", "--slug", slug, "test.txt"), 0)
        self.assertEqual(
            self.run_cli(
                "visit",
                "--slug",
                slug,
                "test.txt",
                "--depth",
                "2",
                "--evidence",
                "full transcript output",
            ),
            0,
        )
        return slug

    def test_real_receipt_closes_fake_ledger(self):
        self.write_transcript(receipt(self.target))
        slug = self.make_ledger()
        self.assertEqual(self.run_cli("close", "--slug", slug), 0)
        self.assertFalse(sweep.ledger_path(slug).exists())

    def test_request_only_refuses_close(self):
        self.write_transcript(receipt(self.target, include_output=False))
        self.assertEqual(self.run_cli("close", "--slug", self.make_ledger()), 1)

    def closed_ledger(self):
        self.write_transcript(receipt(self.target))
        self.assertEqual(self.run_cli("close", "--slug", self.make_ledger()), 0)
        return next((self.root / "sweeps").rglob("ledger.json"))

    def test_missing_file_and_transcript_fail_from_different_session(self):
        ledger = self.closed_ledger()
        self.target.unlink()
        self.transcript.unlink()
        os.environ["CODEX_THREAD_ID"] = "00000000-0000-4000-8000-000000000002"
        self.assertEqual(sweep.verify_ledger(ledger)[0], 1)

    def test_missing_proof_fails_without_session_or_opt_in(self):
        ledger = self.closed_ledger()
        self.target.unlink()
        self.transcript.unlink()
        os.environ.pop("CODEX_THREAD_ID")
        os.environ.pop("SWEEP_CODEX_READ_PROOF")
        self.assertEqual(sweep.verify_ledger(ledger)[0], 1)

    def test_required_codex_proof_survives_removed_opt_in(self):
        ledger = self.closed_ledger()
        os.environ.pop("SWEEP_CODEX_READ_PROOF")
        os.environ.pop("CODEX_THREAD_ID")
        self.assertEqual(sweep.verify_ledger(ledger)[0], 0)
        self.transcript.unlink()
        self.assertEqual(sweep.verify_ledger(ledger)[0], 1)

    def test_initial_codex_visit_requires_explicit_opt_in(self):
        self.write_transcript(receipt(self.target))
        os.environ.pop("SWEEP_CODEX_READ_PROOF")
        self.assertEqual(self.run_cli("close", "--slug", self.make_ledger()), 1)

    def test_file_kind_survives_deletion_before_visit(self):
        self.write_transcript(receipt(self.target))
        self.assertEqual(
            self.run_cli(
                "init",
                "--slug",
                "deleted",
                "--goal",
                "g",
                "--done",
                "d",
                "--project",
                str(self.project),
            ),
            0,
        )
        self.assertEqual(self.run_cli("add", "--slug", "deleted", "test.txt"), 0)
        self.target.unlink()
        self.assertEqual(
            self.run_cli(
                "visit",
                "--slug",
                "deleted",
                "test.txt",
                "--depth",
                "2",
                "--evidence",
                "read",
            ),
            0,
        )
        os.environ.pop("CODEX_THREAD_ID")
        os.environ.pop("SWEEP_CODEX_READ_PROOF")
        self.assertEqual(self.run_cli("close", "--slug", "deleted"), 1)

    def test_non_file_items_remain_verifiable_after_session_change(self):
        self.assertEqual(
            self.run_cli(
                "init",
                "--slug",
                "domain",
                "--goal",
                "g",
                "--done",
                "d",
                "--project",
                str(self.project),
            ),
            0,
        )
        self.assertEqual(self.run_cli("add", "--slug", "domain", "company:123"), 0)
        self.assertEqual(
            self.run_cli(
                "visit",
                "--slug",
                "domain",
                "company:123",
                "--depth",
                "2",
                "--evidence",
                "record checked",
            ),
            0,
        )
        self.assertEqual(self.run_cli("close", "--slug", "domain"), 0)
        os.environ.pop("CODEX_THREAD_ID")
        ledger = next((self.root / "sweeps").rglob("ledger.json"))
        self.assertEqual(sweep.verify_ledger(ledger)[0], 0)

    def test_legacy_item_without_retained_kind_cannot_certify_deleted_file(self):
        ledger = self.closed_ledger()
        data = json.loads(ledger.read_text())
        for key in ("item_kind", "proof_provider", "read_proof_required"):
            data["universe"][0].pop(key, None)
        ledger.write_text(json.dumps(data))
        self.target.unlink()
        self.transcript.unlink()
        os.environ.pop("CODEX_THREAD_ID")
        self.assertEqual(sweep.verify_ledger(ledger)[0], 1)

    def test_legacy_missing_file_revisit_cannot_clear_proof(self):
        self.write_transcript(receipt(self.target))
        slug = self.make_ledger("legacy-open")
        ledger = sweep.ledger_path(slug)
        data = json.loads(ledger.read_text())
        for key in ("item_kind", "proof_provider", "read_proof_required"):
            data["universe"][0].pop(key, None)
        ledger.write_text(json.dumps(data))
        self.target.unlink()
        self.transcript.unlink()
        self.assertEqual(self.run_cli("close", "--slug", slug), 1)
        self.assertEqual(self.run_cli("visit", "--slug", slug, "test.txt",
                                     "--force", "--depth", "2", "--evidence",
                                     "revisit without a target"), 0)
        self.assertEqual(self.run_cli("close", "--slug", slug), 1)

    def add_missing_ledger(self, ident):
        slug = "add-missing"
        self.assertEqual(self.run_cli("init", "--slug", slug, "--goal", "g", "--done", "d",
                                     "--depth", "2", "--project", str(self.project)), 0)
        self.assertEqual(self.run_cli("visit", "--slug", slug, ident, "--add-missing",
                                     "--depth", "2", "--evidence", "record checked"), 0)
        return slug

    def test_add_missing_non_file_closes_and_verifies(self):
        slug = self.add_missing_ledger("company:123")
        self.assertEqual(self.run_cli("close", "--slug", slug), 0)
        ledger = next((self.root / "sweeps").rglob("ledger.json"))
        self.assertEqual(sweep.verify_ledger(ledger)[0], 0)

    def test_add_missing_file_requires_full_read(self):
        self.write_transcript(receipt(self.target, include_output=False))
        slug = self.add_missing_ledger("test.txt")
        self.assertEqual(self.run_cli("close", "--slug", slug), 1)
        self.write_transcript(receipt(self.target))
        self.assertEqual(self.run_cli("close", "--slug", slug), 0)

    def test_failed_refuses_close(self):
        self.write_transcript(receipt(self.target, exit_code=1))
        self.assertEqual(self.run_cli("close", "--slug", self.make_ledger()), 1)

    def test_truncated_refuses_close(self):
        self.write_transcript(receipt(self.target, text="line one\n"))
        self.assertEqual(self.run_cli("close", "--slug", self.make_ledger()), 1)

    def test_partial_command_refuses_close(self):
        self.write_transcript(receipt(self.target, command="head " + str(self.target)))
        self.assertEqual(self.run_cli("close", "--slug", self.make_ledger()), 1)

    def test_changed_file_refuses_close(self):
        self.write_transcript(receipt(self.target))
        slug = self.make_ledger()
        self.target.write_text("changed\n")
        self.assertEqual(self.run_cli("close", "--slug", slug), 1)

    def test_deleted_file_refuses_close(self):
        self.write_transcript(receipt(self.target))
        slug = self.make_ledger()
        self.target.unlink()
        self.assertEqual(self.run_cli("close", "--slug", slug), 1)

    def test_directory_target_refuses_close(self):
        self.write_transcript(receipt(self.target))
        slug = self.make_ledger()
        self.target.unlink()
        self.target.mkdir()
        self.assertEqual(self.run_cli("close", "--slug", slug), 1)

    def test_unknown_session_refuses_close(self):
        self.write_transcript(receipt(self.target))
        slug = self.make_ledger()
        self.transcript.unlink()
        self.assertEqual(self.run_cli("close", "--slug", slug), 1)

    def test_duplicate_record_refuses_close(self):
        rows = receipt(self.target)
        self.write_transcript(rows + [rows[1]])
        self.assertEqual(self.run_cli("close", "--slug", self.make_ledger()), 1)

    def test_invalid_uuid_refuses_discovery(self):
        self.assertIsNone(sweep.codex_session_file("../bad"))
        self.assertIsNone(sweep.codex_session_file("sess-a"))

    def test_mismatched_session_metadata_refuses_discovery(self):
        self.write_transcript(receipt(self.target))
        lines = self.transcript.read_text().splitlines()
        lines[0] = json.dumps(
            {
                "type": "session_meta",
                "payload": {"id": "00000000-0000-4000-8000-000000000002"},
            }
        )
        self.transcript.write_text("\n".join(lines) + "\n")
        self.assertIsNone(sweep.codex_session_file(SESSION))
        self.assertEqual(self.run_cli("close", "--slug", self.make_ledger()), 1)

    def test_missing_session_metadata_refuses_discovery(self):
        self.transcript.write_text(
            "".join(json.dumps(row) + "\n" for row in receipt(self.target))
        )
        self.assertIsNone(sweep.codex_session_file(SESSION))
        self.assertEqual(self.run_cli("close", "--slug", self.make_ledger()), 1)

    def test_later_session_switch_refuses_even_successful_read(self):
        other = "00000000-0000-4000-8000-000000000002"
        self.write_transcript(
            [{"type": "session_meta", "payload": {"id": other}}, *receipt(self.target)]
        )
        self.assertIsNotNone(sweep.codex_session_file(SESSION))
        self.assertEqual(self.run_cli("close", "--slug", self.make_ledger()), 1)

    def test_two_targets_single_session_pass(self):
        second = self.project / "second.txt"
        second.write_text("second\n")
        self.write_transcript(receipt(self.target) + receipt(second, call_id="read-2"))
        found, proved = sweep.codex_session_proofs(SESSION, {self.target, second})
        self.assertTrue(found)
        self.assertEqual(proved, {self.target.resolve(), second.resolve()})

    def test_claude_mode_unchanged_when_not_opted_in(self):
        os.environ.pop("SWEEP_CODEX_READ_PROOF")
        os.environ["CLAUDE_CODE_SESSION_ID"] = "sess-a"
        self.assertIsNone(sweep.codex_session_file("sess-a"))
        doc = self.root / "claude" / "project" / "sess-a.jsonl"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            json.dumps(
                {
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "claude-read",
                                "name": "Read",
                                "input": {"file_path": str(self.target)},
                            }
                        ]
                    }
                }
            )
            + "\n"
            + json.dumps(
                {
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "claude-read",
                                "content": self.target.read_text(),
                            }
                        ]
                    }
                }
            )
            + "\n"
        )
        slug = self.make_ledger("claude")
        self.assertEqual(self.run_cli("close", "--slug", slug), 0)

    def test_mixed_claude_visit_uses_claude_lane_with_codex_opt_in(self):
        os.environ["CLAUDE_CODE_SESSION_ID"] = "sess-a"
        doc = self.root / "claude" / "project" / "sess-a.jsonl"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            json.dumps(
                {
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "claude-read",
                                "name": "Read",
                                "input": {"file_path": str(self.target)},
                            }
                        ]
                    }
                }
            )
            + "\n"
            + json.dumps(
                {
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "claude-read",
                                "content": self.target.read_text(),
                            }
                        ]
                    }
                }
            )
            + "\n"
        )
        slug = self.make_ledger("mixed")
        self.assertEqual(self.run_cli("close", "--slug", slug), 0)


if __name__ == "__main__":
    unittest.main()
