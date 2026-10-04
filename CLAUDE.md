# development-protocol: agent context

The public development-protocol stack: 20 portable skills and a 17-row evidence checklist for
Claude Code and Codex, installed by `install.sh` or as a Claude Code plugin. Every skill here is a
port of a private working setup. **Nothing private ships**: no home paths, no private names, no
house-only tooling. A private-data scanner enforces it.

## Where to go

This repo follows the ICM folder method (the bundled `/icm` skill): this file routes, each
room's `CONTEXT.md` holds its contract.

| Task                                                        | Go to             | Read                                                   | Skills |
| ----------------------------------------------------------- | ----------------- | ------------------------------------------------------ | ------ |
| Change or add a bundled skill, or re-port one               | `skills/`         | [skills/CONTEXT.md](skills/CONTEXT.md), `docs/PORTING.md` | none   |
| Change the standard, workflow, setup or daily-use docs      | `docs/`           | [docs/CONTEXT.md](docs/CONTEXT.md)                     | none   |
| Run or extend the test suite, sanitization or private scans | `tests/`          | [tests/CONTEXT.md](tests/CONTEXT.md)                   | none   |
| Record or check the drift lock against upstream sources     | `sync/`           | [sync/CONTEXT.md](sync/CONTEXT.md)                     | none   |
| Change the plugin or marketplace manifest, bump a version   | `.claude-plugin/` | [.claude-plugin/CONTEXT.md](.claude-plugin/CONTEXT.md) | none   |
| Change CI                                                   | `.github/`        | [.github/CONTEXT.md](.github/CONTEXT.md)               | none   |
| Change a maintainer release check (version bump guard)      | `scripts/`        | [scripts/CONTEXT.md](scripts/CONTEXT.md)               | none   |

`skills/<name>/` folders are copied whole by `install.sh` and loaded by the plugin, so no
`CONTEXT.md` or other agent file goes inside one; `skills/CONTEXT.md` covers them all. Root files
stay put: `README.md`, `CHANGELOG.md`, `UPDATES.md`, `LICENSE`, `install.sh`, `uninstall.sh`,
`health-check.sh`. `.devproto/` is a checklist workspace, not a room.

## Rules

- Every skill change follows `docs/PORTING.md`: standalone, stdlib-only Python 3.9+ or POSIX sh,
  slash references only to bundled skills, plain English, no em dashes, no emojis.
- `skills/research-stack/` is ported from the canonical public `research-stack` repo (same GitHub
  owner as this one; the handle stays in the credit files only). Its `focus/tags.json` is canonical; the copy here is
  `skills/research-stack/references/focus/tags.json`, and `FOCUS_HINTS` in
  `skills/development-protocol/scripts/devproto.py` mirrors its triggers. Change upstream first,
  then re-port per `docs/PORTING.md`.
- Use "the maintainer", never a personal name, outside the credit files the scanner allows
  (`README.md`, `docs/SETUP.md`, `docs/UPDATING.md`, `CHANGELOG.md`, `.claude-plugin/*.json`).
- Each re-port or public maintenance change gets a dated `UPDATES.md` entry; anything a user would
  notice also gets a `CHANGELOG.md` version line and a new `version` in `.claude-plugin/plugin.json`
  (the only place it lives). Any change under `skills/` or `.claude-plugin/` needs that bump:
  synced plugin installs update only when the version changes, and CI's `version` job fails
  without it.
- Commit on a branch, open a pull request, merge when CI is green.

## Verify

- `python3 -m unittest discover tests` (CI runs it with `-v`). Run as root, 2 install tests fail
  because root ignores `chmod 0`: `test_backup_and_manifest_survive_a_crash_partway_through_install`
  and `test_crash_midcopy_then_reinstall_and_uninstall_recovers_cleanly`. As a normal user all pass.
- `bash tests/sanitization.sh` (same as `python3 tests/scan_private.py`) prints `clean`.
- `python3 skills/icm/scripts/icm_check.py .` holds (exit 0) for this repo's own layout.
- Install into a throwaway home, then check and remove, as CI does:
  `HOME="$(mktemp -d)" bash -c './install.sh --yes --target both && ./health-check.sh --target both && ./uninstall.sh --yes'`

## Naming

Skill folders and slash names are kebab-case and match the `name` in their `SKILL.md`
frontmatter. Top-level docs in `docs/` are UPPERCASE `.md`; room contracts are `CONTEXT.md`.
