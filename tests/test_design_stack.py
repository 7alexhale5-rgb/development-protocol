"""Tests for the design-stack DESIGN.md extractor. Run from the repo root: python3 -m unittest discover tests"""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills/design-stack/scripts"))
import extract_design_md as ex  # noqa: E402

SYSTEM = """# Harbor - Interface System

Calm, dense tooling for dispatch teams.

## 1. Principles

- Numbers first, chrome last.
- One accent per screen.

## 2. Colors

| Token | Hex | Role |
|---|---|---|
| `--bg` | `#0b0d10;` | Page ground |
| `--text` | #EEE | Body text |
| `--accent` | hsl(24, 95%, 53%) | Primary action |
| `--broken` | var(--x) | not a color |

## 3. Typography

Display: Fraunces, serif
Body: Inter, sans-serif

| Token | Size | Line height | Weight | Tracking |
|---|---|---|---|---|
| display-lg | 48 | 1.05 | 600 semibold | -0.01em |
| body | 16px | 1.5 | 400 | 0.08em uppercase |
| button | 14 | 20px | 500 | - |

## 4. Spacing

| Token | Value |
|---|---|
| space-4 | 16 |
| space-6 | 24px |

## 5. Radii

| Token | Value |
|---|---|
| radius-none | 0 |
| radius-md | 8 |
| radius-pill | 9999px |
"""


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.tok = ex.extract_all(
            SYSTEM, ex.infer_project("x/.interface-design/system.md", SYSTEM)
        )

    def test_project_name_drops_subtitle(self):
        self.assertEqual(self.tok["project"], "Harbor")
        self.assertEqual(
            self.tok["description"], "Calm, dense tooling for dispatch teams."
        )

    def test_colors_normalized_and_non_colors_skipped(self):
        colors = {c["name"]: c["hex"] for c in self.tok["colors"]}
        self.assertEqual(
            colors, {"bg": "#0B0D10", "text": "#EEEEEE", "accent": "#F97015"}
        )

    def test_heading_ancestry_keeps_sections_apart(self):
        # Spacing and radius rows must not leak into typography.
        names = [t["name"] for t in self.tok["typography"]]
        self.assertEqual(names, ["display-lg", "body", "button"])

    def test_typography_fields(self):
        t = {x["name"]: x for x in self.tok["typography"]}
        self.assertEqual(t["display-lg"]["fontFamily"], "Fraunces, serif")
        self.assertEqual(t["body"]["fontFamily"], "Inter, sans-serif")
        self.assertEqual(t["display-lg"]["fontWeight"], 600)
        self.assertEqual(t["display-lg"]["fontSize"], "48px")
        self.assertEqual(t["display-lg"]["letterSpacing"], "-0.01em")
        self.assertEqual(t["body"]["letterSpacing"], "0.08em")
        self.assertIsNone(t["button"]["letterSpacing"])
        self.assertEqual(t["button"]["lineHeight"], "20px")

    def test_rounded_scale(self):
        r = {x["name"]: x["value"] for x in self.tok["rounded"]}
        self.assertEqual(r, {"none": "0px", "md": "8px", "pill": "999px"})

    def test_prose_keeps_bullets(self):
        self.assertIn("- Numbers first, chrome last.", self.tok["overview"])

    def test_components_reference_tokens(self):
        comps = ex.build_components(self.tok)
        self.assertEqual(comps["buttonPrimary"]["backgroundColor"], "{colors.accent}")
        self.assertEqual(comps["buttonPrimary"]["rounded"], "{rounded.pill}")
        self.assertEqual(comps["buttonPrimary"]["padding"], "{spacing.space-6}")
        self.assertEqual(comps["input"]["padding"], "{spacing.space-4}")

    def test_front_matter_quotes_hex_and_plain_numbers(self):
        text, _, _ = ex.convert(SYSTEM, "p/.interface-design/system.md", "p/DESIGN.md")
        fm = text.split("---")[1]
        self.assertIn('  bg: "#0B0D10"', fm)
        self.assertIn("    lineHeight: 1.05", fm)
        self.assertIn('    backgroundColor: "{colors.accent}"', fm)
        self.assertIn("## Do's and Don'ts", text)
        self.assertIn("](.interface-design/system.md)", text)
        self.assertNotIn(chr(0x2014), text)

    def test_cli_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "system.md"
            src.write_text(SYSTEM)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = ex.main([str(src), str(Path(d) / "DESIGN.md"), "--dry-run"])
            self.assertEqual(code, 0)
            self.assertTrue(out.getvalue().startswith("---\nversion: alpha"))
            self.assertFalse((Path(d) / "DESIGN.md").exists())
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(ex.main([str(src)]), 2)

    def test_hsl_matches_reference_rounding(self):
        self.assertEqual(ex.hsl_to_hex(0, 0, 50), "#808080")
        self.assertEqual(ex.hsl_to_hex(210, 100, 50), "#0080FF")


if __name__ == "__main__":
    unittest.main()
