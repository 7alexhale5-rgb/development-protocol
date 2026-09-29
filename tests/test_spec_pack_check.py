"""Tests for the visual-spec gate. Run from the repo root: python3 -m unittest discover tests"""

import hashlib
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills/visual-spec"
sys.path.insert(0, str(SKILL / "scripts"))
import spec_pack_check as spc  # noqa: E402

FENCE_RE = re.compile(r"^#### (\S+)[^\n]*\n\n```[a-z]+\n(.*?)\n```", re.M | re.S)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def example_files() -> dict:
    """The worked example in references/pack-format.md, keyed by file name."""
    text = (SKILL / "references/pack-format.md").read_text()
    return {name: body + "\n" for name, body in FENCE_RE.findall(text)}


def write_manifest(d: Path, rows: list) -> None:
    for r in rows:
        if "file" in r:
            r["sha256"] = sha(d / r["file"])
    (d / "manifest.json").write_text(json.dumps(rows))


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def build_example(self) -> list:
        files = example_files()
        rows = json.loads(files.pop("manifest.json"))
        for name, body in files.items():
            (self.d / name).write_text(body)
        write_manifest(self.d, rows)
        return rows

    def run_main(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = spc.main([str(self.d)])
        return code, buf.getvalue()

    # The documented example must pass, so the doc and the gate cannot drift apart.
    def test_documented_example_passes(self):
        self.build_example()
        fails, passes, judged = spc.check_pack(self.d)
        self.assertEqual(fails, [])
        self.assertTrue(any(p.startswith("N1 all 3 wireframes") for p in passes))
        self.assertTrue(judged)
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("-> PASS", out)

    def test_small_pack_reports_every_failure_not_just_the_first(self):
        # Ported from the original self-test: four independent faults, all reported.
        (self.d / "01-navigation.mmd").write_text(
            'flowchart TB\n  HOME["A"] --> B["B"]\n  H["H"] --> B\n'
        )
        wf = (
            'block-beta\n  columns 2\n  H["x"]:2\n  F["y"]\n  S["go"]:2\n'
            "  class H header\n  class F field\n  class S action\n"
        )
        (self.d / "02-wireframe-b.mmd").write_text(wf)
        (self.d / "03-wireframe-h.mmd").write_text(wf)
        (self.d / "04-1-flow.mmd").write_text(
            'flowchart TB\n  A["a"] --> B["b"]\n  class A,B reported;\n'
        )
        rows = []
        for f in sorted(p.name for p in self.d.glob("*.mmd")):
            r = {"file": f, "title": f}
            if "wireframe" in f:
                r.update(workflow="04", security="who")
            rows.append(r)
        write_manifest(self.d, rows)
        fails, _, _ = spc.check_pack(self.d)
        self.assertEqual(len(fails), 4, fails)
        want = {
            "N1": "['H']",
            "F2": "no UNKNOWN",
            "P1": "none present",
            "P4": "none present",
        }
        for key, frag in want.items():
            self.assertTrue(
                any(f.startswith(key) and frag in f for f in fails), (key, fails)
            )

    def test_missing_manifest_is_exit_2(self):
        (self.d / "01-x.mmd").write_text("mindmap\n  root((x))\n")
        code, out = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn("missing", out)

    def test_unparseable_or_wrong_shape_manifest_is_exit_2(self):
        (self.d / "manifest.json").write_text("{not json")
        self.assertEqual(self.run_main()[0], 2)
        (self.d / "manifest.json").write_text(json.dumps({"file": "x"}))
        self.assertEqual(self.run_main()[0], 2)

    def test_not_a_directory_and_bad_usage_are_exit_2(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(spc.main([str(self.d / "nope")]), 2)
            self.assertEqual(spc.main([]), 2)

    def test_tampered_source_fails_m1(self):
        self.build_example()
        with open(self.d / "05-wireframe-b-new-ticket.mmd", "a") as f:
            f.write("%% edited after hashing\n")
        fails, _, _ = spc.check_pack(self.d)
        self.assertIn(
            "M1 05-wireframe-b-new-ticket.mmd sha256 differs from manifest", fails
        )
        self.assertEqual(self.run_main()[0], 1)

    def test_unlisted_source_fails_m1(self):
        self.build_example()
        (self.d / "08-extra.mmd").write_text("mindmap\n  root((x))\n")
        fails, _, _ = spc.check_pack(self.d)
        self.assertIn("M1 08-extra.mmd on disk but not in manifest", fails)

    def test_screen_only_rows(self):
        rows = self.build_example()
        rows.append({"screen": "screens/b-390.png", "width": 390})
        write_manifest(self.d, rows)
        fails, _, _ = spc.check_pack(self.d)
        self.assertEqual(
            fails, ["M1 manifest row 7 names a missing screen: screens/b-390.png"]
        )
        (self.d / "screens").mkdir()
        (self.d / "screens/b-390.png").write_bytes(b"png")
        self.assertEqual(spc.check_pack(self.d)[0], [])

    def test_row_with_neither_file_nor_screen_fails(self):
        rows = self.build_example()
        rows.append({"title": "orphan"})
        write_manifest(self.d, rows)
        fails, _, _ = spc.check_pack(self.d)
        self.assertIn(
            "M1 manifest row 7 has neither a file nor a screen: orphan", fails
        )

    def test_action_count_must_match_declared_mode(self):
        rows = self.build_example()
        for r in rows:
            if r.get("file") == "04-wireframe-a-home.mmd":
                r["actions"] = "one"
        write_manifest(self.d, rows)
        fails, _, _ = spc.check_pack(self.d)
        self.assertTrue(
            any(f.startswith("W2 04-wireframe-a-home.mmd: 2 action") for f in fails)
        )

    def test_wireframe_row_needs_workflow_and_security(self):
        rows = self.build_example()
        for r in rows:
            if r.get("file") == "06-wireframe-c-ticket.mmd":
                del r["security"]
        write_manifest(self.d, rows)
        fails, _, _ = spc.check_pack(self.d)
        self.assertIn(
            "W3 06-wireframe-c-ticket.mmd: manifest row lacks ['security']", fails
        )

    def test_unclassed_block_and_missing_header_fail_w1(self):
        rows = self.build_example()
        (self.d / "06-wireframe-c-ticket.mmd").write_text(
            'block-beta\n  columns 2\n  S["Status"] D["Due"]\n  class S field\n'
        )
        write_manifest(self.d, rows)
        fails, _, _ = spc.check_pack(self.d)
        self.assertIn("W1 06-wireframe-c-ticket.mmd: unclassed blocks ['D']", fails)
        self.assertIn("W1 06-wireframe-c-ticket.mmd: no header block", fails)

    def test_untagged_mindmap_leaf_fails_m2(self):
        rows = self.build_example()
        (self.d / "01-process-map.mmd").write_text(
            "mindmap\n  root((Shop))\n    Intake\n      Customer drops bike\n"
        )
        write_manifest(self.d, rows)
        fails, _, _ = spc.check_pack(self.d)
        self.assertTrue(
            any(f.startswith("M2 01-process-map.mmd: 1 leaf") for f in fails)
        )

    def test_unclassed_flowchart_node_fails_f1(self):
        rows = self.build_example()
        path = self.d / "02-workflow-intake.mmd"
        path.write_text(path.read_text().replace("  class H issue\n", ""))
        write_manifest(self.d, rows)
        fails, _, _ = spc.check_pack(self.d)
        self.assertIn("F1 02-workflow-intake.mmd: unclassed nodes ['H']", fails)

    def test_unknowns_none_in_manifest_satisfies_f2(self):
        rows = self.build_example()
        path = self.d / "02-workflow-intake.mmd"
        path.write_text(path.read_text().replace("UNKNOWN:", "Open:"))
        write_manifest(self.d, rows)
        self.assertTrue(any(f.startswith("F2") for f in spc.check_pack(self.d)[0]))
        rows[1]["unknowns"] = "none"
        write_manifest(self.d, rows)
        self.assertEqual(spc.check_pack(self.d)[0], [])

    def test_navigation_needs_home_and_reaches_chained_edges(self):
        rows = self.build_example()
        nav = self.d / "07-navigation.mmd"
        nav.write_text('flowchart TB\n  START["A. Desk"] --> NEW["B. New"]\n')
        write_manifest(self.d, rows)
        self.assertIn("N1 navigation map has no HOME node", spc.check_pack(self.d)[0])
        nav.write_text(
            'flowchart TB\n  HOME["A. Desk"] --> NEW["B. New"] --> FIND["C. Ticket"]\n'
        )
        write_manifest(self.d, rows)
        self.assertEqual(spc.check_pack(self.d)[0], [])

    def test_summary_must_be_last_heading(self):
        self.build_example()
        idx = self.d / "index.md"
        idx.write_text(idx.read_text() + "\n## Appendix\n")
        fails, _, _ = spc.check_pack(self.d)
        self.assertTrue(any(f.startswith("S1") for f in fails))


if __name__ == "__main__":
    unittest.main()
