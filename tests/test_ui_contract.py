"""Routing checks only; these do not grade a rendered interface."""

import re
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLOOR = Path("skills/design-stack/references/quality-floor.md")
ANCHOR = "product-interfaces-tasks-records-controls"
CONSUMERS = [
    Path("skills") / name / "SKILL.md"
    for name in (
        "design-stack",
        "build-stack",
        "review-stack",
        "development-protocol",
        "visual-spec",
        "karpathy",
        "planning-stack",
        "pathway",
    )
] + [
    Path("skills/design-stack/references/critique.md"),
    Path("skills/design-stack/references/pipeline-phases.md"),
    Path("skills/development-protocol/reference.md"),
]


def routing_gaps(root):
    """Every route resolves to the one installed source, not a private host file."""
    gaps = []
    floor = root / FLOOR
    if not floor.is_file():
        return [str(FLOOR)]
    if "## Product interfaces: tasks, records, controls" not in floor.read_text():
        gaps.append("missing product contract anchor")
    if (
        "## Craft and performance are separate acceptance requirements"
        not in floor.read_text()
    ):
        gaps.append("missing craft and performance section")
    for relative in CONSUMERS:
        path = root / relative
        if not path.is_file():
            gaps.append(str(relative))
            continue
        links = re.findall(r"\]\(([^)]+)#" + ANCHOR + r"\)", path.read_text())
        if not any((path.parent / link).resolve() == floor.resolve() for link in links):
            gaps.append(str(relative))
    return gaps


class UIContractRouting(unittest.TestCase):
    def test_all_build_and_review_routes_resolve_the_canonical_installed_contract(self):
        self.assertEqual(routing_gaps(ROOT), [])

    def test_a_removed_pointer_is_detected_in_each_consumer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for relative in [FLOOR] + CONSUMERS:
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, root / relative)
            self.assertEqual(routing_gaps(root), [])
            for relative in CONSUMERS:
                with self.subTest(consumer=str(relative)):
                    path = root / relative
                    original = path.read_text()
                    path.write_text(original.replace("#" + ANCHOR, "#wrong-section"))
                    self.assertEqual(routing_gaps(root), [str(relative)])
                    path.write_text(original)

    def test_missing_canonical_source_or_section_never_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(routing_gaps(root), [str(FLOOR)])
            (root / FLOOR).parent.mkdir(parents=True)
            (root / FLOOR).write_text("# A different guide\n")
            self.assertIn("missing product contract anchor", routing_gaps(root))
            self.assertIn("missing craft and performance section", routing_gaps(root))
