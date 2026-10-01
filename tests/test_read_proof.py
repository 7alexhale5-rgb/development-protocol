from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/relentless/scripts"))

import json
import os
import pathlib
import tempfile
import unittest

from read_proof import prove_read, prove_reads


class ReadProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.target = self.root / "target.txt"
        self.target.write_text("one\ntwo\n")
        self.transcript = self.root / "session.jsonl"

    def write_case(
        self,
        command=None,
        output="one\ntwo\n",
        exit_code=0,
        include_output=True,
        call_status="completed",
        outer_status="Script completed\nOutput:\n",
        script=None,
    ):
        command = command if command is not None else "cat " + str(self.target)
        script = (
            script
            if script is not None
            else "const r=await tools.exec_command({cmd:"
            + json.dumps(command)
            + "});text(r)"
        )
        call = {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call",
                "name": "exec",
                "call_id": "id-1",
                "status": call_status,
                "input": script,
            },
        }
        rows = [call]
        if include_output:
            out = {
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call_output",
                    "call_id": "id-1",
                    "output": [
                        {"type": "input_text", "text": outer_status},
                        {
                            "type": "input_text",
                            "text": json.dumps(
                                {"exit_code": exit_code, "output": output}
                            ),
                        },
                    ],
                },
            }
            rows.append(out)
        self.transcript.write_text("".join(json.dumps(row) + "\n" for row in rows))
        return prove_read(self.transcript, self.target)

    def test_exact_success(self):
        self.assertTrue(self.write_case()["proved"])

    def test_request_only(self):
        self.assertFalse(self.write_case(include_output=False)["proved"])

    def test_failed_nested_command(self):
        self.assertFalse(self.write_case(exit_code=1)["proved"])

    def test_failed_outer_call(self):
        self.assertFalse(self.write_case(call_status="failed")["proved"])

    def test_truncated_output(self):
        self.assertFalse(self.write_case(output="one\n")["proved"])

    def test_partial_sed(self):
        self.assertFalse(
            self.write_case(command="sed -n '1p' " + str(self.target), output="one\n")[
                "proved"
            ]
        )

    def test_head_only(self):
        self.assertFalse(
            self.write_case(command="head " + str(self.target), output="one\ntwo\n")[
                "proved"
            ]
        )

    def test_rg_only(self):
        self.assertFalse(
            self.write_case(command="rg one " + str(self.target), output="one\n")[
                "proved"
            ]
        )

    def test_unrelated_path(self):
        other = self.root / "other.txt"
        other.write_text(self.target.read_text())
        self.assertFalse(self.write_case(command="cat " + str(other))["proved"])

    def test_forged_js_result_not_exec(self):
        fake = 'text({exit_code:0,output:"one\\ntwo\\n"})'
        self.assertFalse(self.write_case(script=fake)["proved"])

    def test_orchestration_not_inferred(self):
        command = json.dumps("cat " + str(self.target))
        script = (
            "const results=await Promise.allSettled([tools.exec_command({cmd:"
            + command
            + "})]);text(results)"
        )
        self.assertFalse(self.write_case(script=script)["proved"])

    def test_outer_failure(self):
        self.assertFalse(self.write_case(outer_status="Script failed\n")["proved"])

    def test_changed_file(self):
        self.write_case()
        self.target.write_text("changed\n")
        self.assertFalse(prove_read(self.transcript, self.target)["proved"])

    def test_invalid_transcript(self):
        self.transcript.write_text("not json\n")
        self.assertFalse(prove_read(self.transcript, self.target)["proved"])

    def test_boolean_exit_is_not_success(self):
        self.assertFalse(self.write_case(exit_code=False)["proved"])

    def test_float_exit_is_not_success(self):
        self.assertFalse(self.write_case(exit_code=0.0)["proved"])

    def test_non_string_script_is_not_a_request(self):
        self.assertFalse(self.write_case(script={})["proved"])

    def test_non_object_record(self):
        self.transcript.write_text("[]\n")
        self.assertFalse(prove_read(self.transcript, self.target)["proved"])

    def test_non_object_payload(self):
        self.transcript.write_text(
            json.dumps({"type": "response_item", "payload": []}) + "\n"
        )
        self.assertFalse(prove_read(self.transcript, self.target)["proved"])

    def test_duplicate_call_id(self):
        self.write_case()
        lines = self.transcript.read_text().splitlines()
        self.transcript.write_text("\n".join([lines[0], lines[0], lines[1]]) + "\n")
        self.assertFalse(prove_read(self.transcript, self.target)["proved"])

    def test_duplicate_output_id(self):
        self.write_case()
        lines = self.transcript.read_text().splitlines()
        self.transcript.write_text("\n".join([lines[0], lines[1], lines[1]]) + "\n")
        self.assertFalse(prove_read(self.transcript, self.target)["proved"])

    def test_batch_two_targets_one_transcript_pass(self):
        self.write_case()
        second = self.root / "second.txt"
        second.write_text("second\n")
        script = (
            "const r=await tools.exec_command({cmd:"
            + json.dumps("cat " + str(second))
            + "});text(r)"
        )
        call = {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call",
                "name": "exec",
                "call_id": "id-2",
                "status": "completed",
                "input": script,
            },
        }
        out = {
            "type": "response_item",
            "payload": {
                "type": "custom_tool_call_output",
                "call_id": "id-2",
                "output": [
                    {"type": "input_text", "text": "Script completed\nOutput:\n"},
                    {
                        "type": "input_text",
                        "text": json.dumps({"exit_code": 0, "output": "second\n"}),
                    },
                ],
            },
        }
        with self.transcript.open("a") as stream:
            stream.write(json.dumps(call) + "\n" + json.dumps(out) + "\n")
        self.assertEqual(
            prove_reads(self.transcript, {self.target, second})["proved_paths"],
            {self.target, second},
        )


if __name__ == "__main__":
    unittest.main()
