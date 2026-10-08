"""Tests for the icm skill's walk-test checker.

A good tree must hold (exit 0), each seeded break must fail (exit 1), and a tree that cannot be
read must be "could not measure" (exit 2), never a pass.

Run from the repo root: python3 -m unittest discover tests
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills/icm/scripts/icm_check.py"
BROKEN_FIXTURE = ROOT / "tests/fixtures/icm-broken"

spec = importlib.util.spec_from_file_location("icm_check", SCRIPT)
icm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(icm)

ROOM = (
    "# Build\n\n## Inputs\n\n- plan\n\n## Process\n\n1. build\n\n"
    "## Outputs\n\n- code\n\n## Human check\n\nThe maintainer runs it.\n"
)
MAP = (
    "# P\n\n| Task | Go to | Read |\n| --- | --- | --- |\n"
    "| Build | src/ | [src/CONTEXT.md](src/CONTEXT.md) |\n"
)


def good(root: Path) -> Path:
    (root / "CLAUDE.md").write_text(MAP)
    (root / "AGENTS.md").symlink_to("CLAUDE.md")
    (root / "src").mkdir()
    (root / "src" / "CONTEXT.md").write_text(ROOM)
    return root


def run_args(args):
    with contextlib.redirect_stdout(io.StringIO()):
        return icm.main(args)


def run(root):
    return run_args([str(root)])


class IcmCheckTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)

    def append(self, path: Path, text: str):
        with path.open("a") as fh:
            fh.write(text)

    # The seeded broken fixture on disk.

    def test_seeded_broken_fixture_fails_with_each_planted_break(self):
        result = icm.check(str(BROKEN_FIXTURE))
        self.assertNotIn("unmeasured", result)
        errors = "\n".join(result["errors"])
        self.assertIn("01_ResearchNotes: stage folder not named NN_kebab-name", errors)
        self.assertIn("01_ResearchNotes: stage folder has no CONTEXT.md", errors)
        self.assertIn("app/CONTEXT.md: missing ## Human check", errors)
        self.assertIn("CLAUDE.md: broken link -> docs/plan.md", errors)
        self.assertEqual(len(result["errors"]), 4, errors)
        self.assertEqual(run(BROKEN_FIXTURE), 1)

    def test_seeded_broken_fixture_fails_from_the_command_line(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPT), str(BROKEN_FIXTURE), "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["exit"], 1)

    def test_fixed_copy_of_the_fixture_holds(self):
        """The fixture fails only because of its planted breaks: repair them and it holds."""
        fixed = self.tmp / "fixed"
        shutil.copytree(BROKEN_FIXTURE, fixed)
        shutil.rmtree(fixed / "01_ResearchNotes")
        self.append(
            fixed / "app" / "CONTEXT.md", "\n## Human check\n\nA person reads it.\n"
        )
        (fixed / "docs").mkdir()
        (fixed / "docs" / "plan.md").write_text("plan\n")
        self.assertEqual(run(fixed), 0)

    def test_this_repo_passes_its_own_walk_test(self):
        self.assertEqual(run(ROOT), 0)

    # Exit codes.

    def test_good_tree_holds(self):
        self.assertEqual(run(good(self.tmp)), 0)

    def test_missing_root_cannot_measure(self):
        self.assertEqual(run(self.tmp / "nope"), 2)

    def test_traversal_failure_is_unmeasured(self):
        root = good(self.tmp)

        def denied(*args, **kwargs):
            kwargs["onerror"](PermissionError("seeded inaccessible stage"))
            return iter(())

        with mock.patch.object(icm.os, "walk", denied):
            measured = icm.check(str(root))
            self.assertIn("unmeasured", measured)
            self.assertEqual(run(root), 2)

    def test_unrouted_unreadable_directory_symlink_is_not_probed(self):
        project = self.tmp / "project"
        project.mkdir()
        root = good(project)
        target = self.tmp / "outside-unreadable"
        target.mkdir()
        link = root / "unrouted-link"
        link.symlink_to(target, target_is_directory=True)
        original = icm.os.listdir

        def denied(path):
            if Path(path) in (link, target):
                raise PermissionError("unreferenced symlink target cannot be listed")
            return original(path)

        with mock.patch.object(icm.os, "listdir", side_effect=denied):
            self.assertEqual(run(root), 0)

    def test_explicitly_routed_symlink_room_still_checks_contract(self):
        root = good(self.tmp)
        target = root / ".hidden-room"
        target.mkdir()
        (target / "CONTEXT.md").write_text("# Missing required sections\n")
        (root / "routed-link").symlink_to(target, target_is_directory=True)
        self.append(root / "CLAUDE.md", "\n[Explicit room](routed-link/CONTEXT.md)\n")
        self.assertEqual(run(root), 1)

    def test_json_report_carries_the_exit_code(self):
        root = good(self.tmp)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = icm.main([str(root), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["exit"], 0)

    def test_origin_and_materialized_roots_go_together(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                icm.main([str(self.tmp), "--origin-root", str(self.tmp)])
        self.assertEqual(ctx.exception.code, 2)

    # The map.

    def test_no_map(self):
        root = good(self.tmp)
        (root / "AGENTS.md").unlink()
        (root / "CLAUDE.md").unlink()
        self.assertEqual(run(root), 1)

    def test_map_without_routing_table(self):
        root = good(self.tmp)
        (root / "CLAUDE.md").write_text("# P\n\nJust prose.\n")
        self.assertEqual(run(root), 1)

    def test_router_can_carry_the_table(self):
        root = good(self.tmp)
        (root / "CLAUDE.md").write_text("# P\n\nSee CONTEXT.md.\n")
        (root / "CONTEXT.md").write_text(MAP)
        self.assertEqual(run(root), 0)

    def test_where_to_go_list_routes(self):
        root = good(self.tmp)
        (root / "CLAUDE.md").write_text(
            "# P\n\n## Where to go\n\n- Build: `src/CONTEXT.md`.\n"
        )
        self.assertEqual(run(root), 0)

    def test_fenced_routing_and_headings_cannot_pass(self):
        root = good(self.tmp)
        (root / "CLAUDE.md").write_text("```markdown\n" + MAP + "```\n")
        (root / "src/CONTEXT.md").write_text("```markdown\n" + ROOM + "```\n")
        self.assertEqual(run(root), 1)

    def test_native_codex_guide_must_reach_the_map(self):
        root = good(self.tmp)
        (root / "AGENTS.md").unlink()
        (root / "AGENTS.md").write_text("# Native rules\nKeep these instructions.\n")
        self.assertEqual(run(root), 1)

    def test_agents_alias_must_reach_a_map(self):
        root = good(self.tmp)
        (root / "AGENTS.md").unlink()
        (root / "unrelated.md").write_text("unrelated prose")
        (root / "AGENTS.md").symlink_to("unrelated.md")
        self.assertEqual(run(root), 1)

    def test_dangling_agents_is_error(self):
        root = good(self.tmp)
        (root / "AGENTS.md").unlink()
        (root / "AGENTS.md").symlink_to("absent.md")
        self.assertEqual(run(root), 1)

    def test_alternate_map_links_are_checked(self):
        root = good(self.tmp)
        (root / "AGENTS.md").unlink()
        (root / "AGENTS.md").write_text(MAP + "\n[gone](missing.md)\n")
        self.assertEqual(run(root), 1)

    # Rooms and stages.

    def test_room_missing_contract_heading(self):
        root = good(self.tmp)
        (root / "src" / "CONTEXT.md").write_text(
            ROOM.replace("## Outputs", "## Results")
        )
        self.assertEqual(run(root), 1)

    def test_room_missing_human_check(self):
        root = good(self.tmp)
        (root / "src" / "CONTEXT.md").write_text(ROOM.split("## Human check")[0])
        self.assertEqual(run(root), 1)

    def test_room_too_long(self):
        root = good(self.tmp)
        (root / "src" / "CONTEXT.md").write_text(ROOM + "line\n" * 80)
        self.assertEqual(run(root), 1)

    def test_eighty_lines_with_newline_are_eighty(self):
        root = good(self.tmp)
        room = ROOM + "line\n" * (80 - len(ROOM.splitlines()))
        (root / "src/CONTEXT.md").write_text(room)
        self.assertEqual(run(root), 0)

    def test_bad_stage_name_and_missing_context(self):
        root = good(self.tmp)
        (root / "01_Research Notes").mkdir()
        errors = icm.check(str(root))["errors"]
        self.assertTrue(any("NN_kebab-name" in e for e in errors), errors)
        self.assertTrue(any("no CONTEXT.md" in e for e in errors), errors)

    def test_no_rooms(self):
        root = good(self.tmp)
        (root / "src" / "CONTEXT.md").unlink()
        (root / "CLAUDE.md").write_text(
            MAP.replace("[src/CONTEXT.md](src/CONTEXT.md)", "src/CONTEXT.md")
        )
        self.assertEqual(run(root), 1)

    def test_three_rooms_require_workspace_context(self):
        root = good(self.tmp)
        for name in ("docs", "ops"):
            (root / name).mkdir()
            (root / name / "CONTEXT.md").write_text(ROOM)
        self.assertEqual(run(root), 1)
        (root / "CONTEXT.md").write_text(
            "# Workspace\nPurpose, form, run, stable rules, changing records and status.\n"
        )
        self.assertEqual(run(root), 0)

    def test_nested_project_rooms_do_not_trigger_parent_requirement(self):
        root = good(self.tmp)
        child = root / "child"
        child.mkdir()
        good(child)
        for name in ("docs", "ops"):
            (child / name).mkdir()
            (child / name / "CONTEXT.md").write_text(ROOM)
        self.assertEqual(run(root), 0)

    def test_agents_only_child_is_a_project_boundary(self):
        root = good(self.tmp)
        child = root / "child"
        child.mkdir()
        good(child)
        (child / "AGENTS.md").unlink()
        (child / "CLAUDE.md").rename(child / "AGENTS.md")
        self.assertEqual(icm.check(str(root))["rooms"], 1)

    def test_lowercase_agent_note_is_not_a_project_boundary(self):
        root = good(self.tmp)
        notes = root / "notes"
        notes.mkdir()
        (notes / "agents.md").write_text("# Team notes\n")
        (notes / "CONTEXT.md").write_text("# Missing room contract\n")
        actual_exists = icm.os.path.lexists

        def case_insensitive_exists(path):
            target = Path(path)
            return actual_exists(path) or (
                target.parent.is_dir()
                and target.name.casefold() in {
                    name.casefold() for name in icm.os.listdir(target.parent)
                }
            )

        with mock.patch.object(icm.os.path, "lexists", case_insensitive_exists):
            self.assertFalse(icm.is_project_boundary(str(notes)))
            measured = icm.check(str(root))
        self.assertEqual(measured["rooms"], 2)
        self.assertTrue(any("Inputs" in error for error in measured["errors"]))

    def test_routed_hidden_room_is_counted_and_checked(self):
        root = good(self.tmp)
        (root / ".research").mkdir()
        (root / ".research/CONTEXT.md").write_text("# Incomplete\n")
        self.append(root / "CLAUDE.md", "\n[Research](.research/CONTEXT.md)\n")
        self.assertEqual(run(root), 1)

    def test_hidden_room_reached_through_room_is_checked(self):
        root = good(self.tmp)
        (root / ".research").mkdir()
        (root / ".research" / "CONTEXT.md").write_text("# incomplete")
        self.append(
            root / "src" / "CONTEXT.md", "\n[research](../.research/CONTEXT.md)\n"
        )
        self.assertEqual(run(root), 1)

    # Links.

    def test_broken_link(self):
        root = good(self.tmp)
        (root / "src" / "CONTEXT.md").write_text(ROOM + "\n[gone](missing.md)\n")
        self.assertEqual(run(root), 1)

    def test_example_links_in_code_are_not_links(self):
        root = good(self.tmp)
        self.append(
            root / "CLAUDE.md",
            "\nUse `[text](path.md)` as an example only.\n"
            "\n```markdown\n[example](missing.md)\n```\n",
        )
        self.assertEqual(run(root), 0)

    def test_code_label_does_not_hide_real_broken_link(self):
        root = good(self.tmp)
        self.append(root / "CLAUDE.md", "\n[`real missing file`](missing.md)\n")
        self.assertEqual(run(root), 1)

    def test_angle_link_with_spaces_is_checked(self):
        root = good(self.tmp)
        self.append(root / "CLAUDE.md", "\n[missing](<docs/missing plan.md>)\n")
        self.assertEqual(run(root), 1)

    def test_reference_link_is_checked(self):
        root = good(self.tmp)
        self.append(
            root / "CLAUDE.md", "\n[missing][plan]\n\n[plan]: docs/missing.md\n"
        )
        self.assertEqual(run(root), 1)

    def test_shortcut_and_collapsed_references_are_checked(self):
        root = good(self.tmp)
        self.append(
            root / "CLAUDE.md",
            "\n[plan][] and [other]\n\n[plan]: <docs/missing plan.md>\n[other]: other.md\n",
        )
        self.assertEqual(len(icm.check(str(root))["errors"]), 2)

    def test_unused_reference_definition_is_not_a_link(self):
        root = good(self.tmp)
        self.append(root / "CLAUDE.md", "\n[unused]: missing.md\n")
        self.assertEqual(run(root), 0)

    def test_case_mismatch_is_a_broken_link(self):
        root = good(self.tmp)
        (root / "src/CONTEXT.md").rename(root / "src/context.md")
        self.assertEqual(run(root), 1)

    def test_balanced_and_escaped_link_destinations(self):
        root = good(self.tmp)
        (root / "src" / "notes(v2).md").write_text("notes")
        self.append(
            root / "CLAUDE.md",
            "\n" + r"[notes](src/notes(v2).md) [escaped](src/notes\(v2\).md)" + "\n",
        )
        self.assertEqual(run(root), 0)

    def test_missing_backtick_route_is_broken_even_with_another_room(self):
        root = good(self.tmp)
        (root / "CLAUDE.md").write_text("# Map\n- Build: `missing/CONTEXT.md`\n")
        self.assertEqual(run(root), 1)

    def test_angle_route_with_spaces_does_not_make_fragment_target(self):
        root = good(self.tmp)
        room = root / "research notes"
        room.mkdir()
        (room / "CONTEXT.md").write_text((root / "src/CONTEXT.md").read_text())
        (root / "CLAUDE.md").write_text(
            "# Map\n- Read [room](<research notes/CONTEXT.md>)\n"
        )
        self.assertEqual(run(root), 0)

    def test_missing_table_backtick_route_is_checked(self):
        root = good(self.tmp)
        (root / "CLAUDE.md").write_text(
            "# Map\n| Task | Room |\n| --- | --- |\n| Build | `missing/CONTEXT.md` |\n"
        )
        self.assertEqual(run(root), 1)

    # Proof binding.

    def test_manifest_binds_the_bytes_actually_checked(self):
        root = good(self.tmp)
        measured = icm.check(str(root))
        guide = root / "CLAUDE.md"
        self.assertEqual(
            measured["manifest"][str(guide)]["content_sha256"],
            hashlib.sha256(guide.read_bytes()).hexdigest(),
        )

    def test_relocated_tree_resolves_links_in_its_origin_namespace(self):
        origin = self.tmp / "origin"
        origin.mkdir()
        good(origin)
        shared = self.tmp / "shared"
        shared.mkdir()
        (shared / "rules.md").write_text("shared rules\n")
        self.append(origin / "CLAUDE.md", "\n[shared rules](../shared/rules.md)\n")
        exported = self.tmp / "export" / "tree"
        shutil.copytree(origin, exported, symlinks=True)
        # Read in its own place, the exported copy's outside link points nowhere.
        self.assertEqual(run(exported), 1)
        # Read in the origin namespace, the same bytes resolve.
        args = [
            str(exported),
            "--origin-root",
            str(origin),
            "--materialized-root",
            str(exported),
        ]
        self.assertEqual(run_args(args), 0)


if __name__ == "__main__":
    unittest.main()
