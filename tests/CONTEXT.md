# Test room: suite, sanitization and private scans

One job: prove the package is well formed, the scripts behave, the installers are safe, and
nothing private ships. Paths relative to the repo root.

## Inputs

- `tests/test_*.py`: unittest modules, one per scripted skill (`test_devproto.py`,
  `test_pathway.py`, `test_focus.py`, `test_validate_report.py`, `test_audit_setup.py`,
  `test_icm.py`, and others), `test_check_version_bump.py` for the maintainer script, plus `test_package.py` (frontmatter, slash references, zsh-safe shell snippets,
  stdlib-only imports, manifests valid JSON, CI pinned by SHA, private scan clean) and
  `test_install.py` (install, uninstall and recovery against a throwaway home).
- `tests/fixtures/`: research report fixtures, good and bad, with and without focus addenda;
  `tests/fixtures/icm-broken/`, a seeded broken ICM project for `test_icm.py` (broken on
  purpose; its own `CLAUDE.md` makes it a nested project the repo's walk test skips).
- `tests/scan_private.py` and its wrapper `tests/sanitization.sh`; patterns in
  `tests/generic-patterns.txt`.
- Optional maintainer-only private list via `DEVPROTO_PRIVATE_PATTERNS`; never commit it
  (`tests/private-patterns.txt` is gitignored).

## Process

1. Run `python3 -m unittest discover tests` (CI adds `-v`).
2. Run `bash tests/sanitization.sh` (or `python3 tests/scan_private.py [path ...]`). It scans
   files git would publish and prints `clean` or each hit. The maintainer also runs it with
   `DEVPROTO_PRIVATE_PATTERNS` set on the release commit.
3. Installer tests set `HOME` to a temporary folder. Two of them break a file with `chmod 0` to
   simulate a crash partway through a copy; root ignores that, so as root
   `test_backup_and_manifest_survive_a_crash_partway_through_install` and
   `test_crash_midcopy_then_reinstall_and_uninstall_recovers_cleanly` fail. That is expected in a
   root container; they must pass as a normal user and in CI.
4. A new script gets a test here; a new leak shape gets a generic pattern only if it is safe to
   publish, otherwise it goes in the private list.

## Outputs

- `tests/test_*.py`, `tests/fixtures/*`, `tests/generic-patterns.txt`, `tests/scan_private.py`,
  `tests/sanitization.sh`.

## Human check

Review CI on the exact pull request commit (Linux and macOS, Python 3.9 and 3.13). Pass: all green
and the scan prints `clean`. Fail: blocks merging.
