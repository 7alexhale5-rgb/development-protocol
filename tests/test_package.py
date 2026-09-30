"""Package-level checks: every skill is well formed, references resolve, nothing private ships."""

import importlib.util
import json
import os
import re
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
BUNDLED = {p.name for p in SKILLS.iterdir() if (p / "SKILL.md").is_file()}
# Agent built-ins, plugin commands, and credited upstream skills ("retro" from gstack).
BUILTIN = {
    "plugin",
    "retro",
    "clear",
    "compact",
    "config",
    "mcp",
    "help",
    "model",
    "init",
    "review",
    "permissions",
    "hooks",
    "agents",
    "resume",
    "goal",
    "loop",
    "schedule",
    "memory",
    "status",
    "cost",
    "doctor",
    "login",
    "logout",
    "effort",
    "fast",
    "skills",
}
SLASH = re.compile(
    r"`/([a-z][a-z0-9]*(?:-[a-z0-9]+)*)(?=[`\s])"
)  # `/name` or `/name args`


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def shipped_markdown():
    for f in (
        list(SKILLS.rglob("*.md"))
        + list((ROOT / "docs").glob("*.md"))
        + [ROOT / "README.md"]
    ):
        if f.is_file():
            yield f


class PackageTest(unittest.TestCase):
    def test_every_skill_has_matching_frontmatter(self):
        for name in sorted(BUNDLED):
            fm = frontmatter((SKILLS / name / "SKILL.md").read_text())
            self.assertEqual(fm.get("name"), name, name)
            desc = fm.get("description", "")
            self.assertTrue(
                40 <= len(desc) <= 1024, f"{name}: description length {len(desc)}"
            )

    def test_slash_references_resolve(self):
        missing = []
        for f in shipped_markdown():
            text = re.sub(r"https?://\S+", "", f.read_text())
            for n, line in enumerate(text.splitlines(), 1):
                for m in SLASH.finditer(line):
                    ref = m.group(1)
                    if ref in BUNDLED or ref in BUILTIN:
                        continue
                    missing.append(f"{f.relative_to(ROOT)}:{n}: /{ref}")
        self.assertEqual(
            missing, [], "unbundled slash references:\n" + "\n".join(missing)
        )

    def test_no_bash_only_variable_call_pattern_in_docs(self):
        """zsh (macOS's default shell) does not word-split an unquoted
        variable, so a `D="python3 ..."; $D steps` snippet works in bash and
        fails with "command not found" in zsh. Every shell example must use a
        `name() { ...; }` function instead, which behaves the same in both."""
        offenders = []
        pattern = re.compile(r'^\s*[A-Za-z_][A-Za-z0-9_]*="(?:python3|node|bash)\b')
        for f in shipped_markdown():
            for n, line in enumerate(f.read_text().splitlines(), 1):
                if pattern.match(line):
                    offenders.append(f"{f.relative_to(ROOT)}:{n}: {line.strip()}")
        self.assertEqual(
            offenders,
            [],
            "bash-only variable-call pattern (breaks on zsh):\n" + "\n".join(offenders),
        )

    def test_private_data_scan_is_clean(self):
        r = subprocess.run(
            [sys.executable, str(ROOT / "tests/scan_private.py")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, r.stdout[-3000:])

    def test_scanner_handles_unicode_names_and_windows_paths(self):
        planted = SKILLS / 'zz-résumé.md'
        for content in ['see ' + '/Us' + 'ers/someone/private', 'C:' + chr(92) + 'Users' + chr(92) + 'someone' + chr(92) + 'private.txt']:
            planted.write_text(content)
            try:
                result = subprocess.run([sys.executable, str(ROOT / 'tests/scan_private.py'), str(planted)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stdout)
            finally:
                planted.unlink()

    def test_scanner_catches_a_planted_leak(self):
        planted = SKILLS / "zz-planted-leak.md"
        planted.write_text("see " + "/Us" + "ers/someone/private and other stuff\n")
        try:
            r = subprocess.run(
                [sys.executable, str(ROOT / "tests/scan_private.py"), str(planted)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 1)
        finally:
            planted.unlink()

    def test_scanner_catches_a_private_name_only_via_the_private_patterns_file(self):
        """R3-7: exercise DEVPROTO_PRIVATE_PATTERNS itself, with a made-up
        codename (never a real client name) that no generic pattern in
        tests/generic-patterns.txt would ever catch on its own."""
        codename = "zyxelquartz-nowhere-corp"
        planted = SKILLS / "zz-planted-private-name.md"
        planted.write_text(f"internal note: {codename} project status\n")
        with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False
        ) as private_list:
            private_list.write(codename + "\n")
            private_path = private_list.name
        try:
            # Without the private list, the generic patterns alone must miss it.
            r_clean = subprocess.run(
                [sys.executable, str(ROOT / "tests/scan_private.py"), str(planted)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r_clean.returncode, 0, r_clean.stdout + r_clean.stderr)

            # With DEVPROTO_PRIVATE_PATTERNS pointed at the private list, it must catch it.
            env = dict(os.environ, DEVPROTO_PRIVATE_PATTERNS=private_path)
            r_private = subprocess.run(
                [sys.executable, str(ROOT / "tests/scan_private.py"), str(planted)],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(r_private.returncode, 1)
        finally:
            planted.unlink()
            os.unlink(private_path)

    def test_credit_exemption_is_exact_path_not_basename(self):
        # README.md is a real credit file and must stay clean even when the
        # maintainer's private pattern list flags the author's name.
        priv = ROOT / "tests" / "_tmp_private_patterns.txt"
        priv.write_text("Al" + "ex Ha" + "le\n")
        env = dict(os.environ, DEVPROTO_PRIVATE_PATTERNS=str(priv))
        try:
            clean = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tests/scan_private.py"),
                    str(ROOT / "README.md"),
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(clean.returncode, 0, clean.stdout)

            # A file with the SAME BASENAME as a credit file, but at a
            # different path, must not inherit the exemption.
            planted = SKILLS / "SETUP.md"
            planted.write_text("Al" + "ex Ha" + "le wrote this note\n")
            try:
                hit = subprocess.run(
                    [sys.executable, str(ROOT / "tests/scan_private.py"), str(planted)],
                    capture_output=True,
                    text=True,
                    env=env,
                )
                self.assertEqual(hit.returncode, 1, hit.stdout)
            finally:
                planted.unlink()
        finally:
            priv.unlink()

    def test_plugin_manifests_are_valid_json(self):
        for p in (ROOT / ".claude-plugin").glob("*.json"):
            data = json.loads(p.read_text())
            self.assertIn("name", data)

    def test_scripts_are_standard_library_only(self):
        allowed_third_party = set()
        stdlib = set(getattr(sys, "stdlib_module_names", ())) or None
        stdlib_dir = sysconfig.get_paths()["stdlib"]

        def is_stdlib(mod):
            if stdlib is not None:
                return mod in stdlib
            spec = importlib.util.find_spec(
                mod
            )  # Python 3.9 has no stdlib_module_names
            return bool(spec) and (
                spec.origin in ("built-in", "frozen", None)
                or str(spec.origin).startswith(stdlib_dir)
            )

        for f in list(SKILLS.rglob("*.py")):
            for m in re.finditer(
                r"^\s*(?:from|import)\s+([A-Za-z_][\w]*)", f.read_text(), re.M
            ):
                mod = m.group(1)
                local = any(
                    (d / f"{mod}.py").exists()
                    for d in (
                        f.parent,
                        f.parent.parent / "scripts",
                        # F11: pathway.py and sweep.py import the
                        # development-protocol skill's _shared.py by relative
                        # path (skills/<this>/scripts -> ../../development-protocol/scripts).
                        f.parent.parent.parent / "development-protocol" / "scripts",
                    )
                )
                self.assertTrue(
                    is_stdlib(mod)
                    or mod == "__future__"
                    or local
                    or mod in allowed_third_party,
                    f"{f.relative_to(ROOT)} imports {mod}",
                )

    def test_own_ci_workflow_pins_actions_by_sha_and_sets_permissions(self):
        """R2-9: audit-setup's generated workflow templates (and the ship skill's
        text) require actions pinned by full commit SHA -- this repo's own CI
        must meet the standard it ships, not just tell others to."""
        ci = (ROOT / ".github/workflows/ci.yml").read_text()
        unpinned = [
            f"{m.group(1)}@{m.group(2)}"
            for m in re.finditer(r"uses:\s*(\S+)@(\S+)", ci)
            if not re.fullmatch(r"[0-9a-f]{40}", m.group(2))
        ]
        self.assertEqual(unpinned, [])
        self.assertIn("permissions:", ci)
        self.assertIn("contents: read", ci)


if __name__ == "__main__":
    unittest.main()
