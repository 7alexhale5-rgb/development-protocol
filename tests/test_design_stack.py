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
        self.assertIn('  "bg": "#0B0D10"', fm)
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



class ReviewExtractionTest(unittest.TestCase):
    def test_hue_wraps_and_rejects_invalid_numbers(self):
        self.assertEqual(ex.hsl_to_hex(360, 100, 50), "#FF0000")
        self.assertEqual(ex.hsl_to_hex(-120, 100, 50), "#0000FF")
        for values in [(0, 101, 50), (0, 50, -1), (float('nan'), 50, 50)]:
            with self.assertRaises(ValueError):
                ex.hsl_to_hex(*values)

    def test_transparency_is_not_silently_dropped(self):
        with self.assertRaisesRegex(ValueError, "alpha"):
            ex.parse_color("hsla(0, 100%, 50%, 0)")
        self.assertEqual(ex.parse_color("hsla(0, 100%, 50%, 1)"), "#FF0000")
        self.assertEqual(ex.parse_color("hsl(360 100% 50%)"), "#FF0000")

    def test_explicit_font_family_overrides_prose_default(self):
        tables = ex.parse_all_pipe_tables("## Typography\n| Token | Family | Size | Weight |\n|---|---|---|---|\n| body | Inter | 16px | 400 |\n")
        self.assertEqual(ex.extract_typography(tables, "default", "display")[0]['fontFamily'], 'Inter')

    def test_yaml_strings_keep_their_type_and_escapes(self):
        import json
        for value in ['2026', 'null', 'true', 'yes', 'line\nquote"', 'plain']:
            self.assertEqual(json.loads(ex.yaml_string(value)), value)

if __name__ == "__main__":
    unittest.main()


class ReportAndAssetTest(unittest.TestCase):
    def test_report_requires_every_dimension_and_catches_punctuated_failure(self):
        import verify_design as verify
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'evidence').mkdir(); proof = root / 'evidence/design.md'
            lines = ['- ' + key + ': pass - fixture evidence' for key in verify.DIMENSIONS]
            proof.write_text('## Verify report\n' + '\n'.join(lines))
            verify.verify_report(root, proof, True)
            proof.write_text('## Verify report\n' + '\n'.join(lines[:-1]))
            with self.assertRaises(ValueError):
                verify.verify_report(root, proof, True)
            proof.write_text('## Verify report\n' + '\n'.join(lines) + '\n- DESIGN.md lint: fail - schema errors')
            with self.assertRaises(ValueError):
                verify.verify_report(root, proof, True)

    def test_runtime_needs_all_screenshots(self):
        import verify_design as verify
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'evidence').mkdir(); proof = root / 'evidence/design.md'
            proof.write_text('## Verify report\n' + '\n'.join('- ' + key + ': pass - proof' for key in verify.DIMENSIONS))
            (proof.parent / 'design-1440.png').write_bytes(b'fixture')
            with self.assertRaises(ValueError):
                verify.verify_report(root, proof)
            for width in (390, 768):
                (proof.parent / f'design-{width}.png').write_bytes(b'fixture')
            verify.verify_report(root, proof)

    def test_asset_manifest_expected_slots_and_actual_usage_are_required(self):
        import verify_design as verify
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(OSError):
                verify.verify_assets(root, ['icon:save'])
            manifest = root / 'ASSETS.md'; manifest.write_text('')
            with self.assertRaises(ValueError):
                verify.verify_assets(root, ['icon:save'])
            kit = root / 'public/kit'; kit.mkdir(parents=True)
            (kit / 'icon-save.svg').write_text('<svg/>')
            manifest.write_text('- slot: icon:save file: kit/icon-save.svg source: hand-built SVG')
            with self.assertRaises(ValueError):
                verify.verify_assets(root, ['icon:save'])
            (root / 'page.html').write_text('<img src="/kit/icon-save.svg">')
            verify.verify_assets(root, ['icon:save'])
            with self.assertRaises(ValueError):
                verify.verify_assets(root, ['icon:save', 'og'])
            (kit / 'orphan.svg').write_text('<svg/>')
            with self.assertRaises(ValueError):
                verify.verify_assets(root, ['icon:save'])

    def test_compound_numstat_counts_deletions_and_binary_entries(self):
        import subprocess
        text = (ROOT / 'skills/compound/SKILL.md').read_text()
        awk = next(line.split('| ', 1)[1] for line in text.splitlines() if '| awk -F' in line)
        for data, expected in [('0\t5\tdeleted.txt\n', '+0, -5, binary: 0'),
                               ('3\t0\tnew.txt\n-\t-\timage.png\n', '+3, -0, binary: 1')]:
            result = subprocess.run(['bash', '-c', awk], input=data, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(expected, result.stdout)

    def test_streak_date_uses_local_timezone(self):
        import subprocess
        import os
        with tempfile.TemporaryDirectory() as folder:
            env = dict(os.environ, TZ='UTC', GIT_AUTHOR_DATE='2026-09-29T00:30:00+0900',
                       GIT_COMMITTER_DATE='2026-09-29T00:30:00+0900')
            subprocess.run(['git', 'init', '-q', folder], check=True)
            subprocess.run(['git', '-C', folder, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
                            'commit', '-q', '--allow-empty', '-m', 'fixture'], env=env, check=True)
            date = subprocess.check_output(['git', '-C', folder, 'log', '--format=%ad',
                                            '--date=format-local:%Y-%m-%d'], env=env, text=True)
            self.assertEqual(date.strip(), '2026-09-28')
