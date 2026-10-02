# Skills room: the 19 bundled skills

One job: keep every bundled skill a standalone, portable port that works on a fresh machine with
only this repo installed. Paths relative to the repo root.

## Inputs

- `docs/PORTING.md`: the porting contract (output layout, frontmatter, what to remove or
  replace, bundled slash names, checklist wiring, portability, writing rules).
- `skills/<name>/SKILL.md`: one per skill, frontmatter `name` equal to the folder name and a
  `description` of 40 to 1,024 characters. Optional `references/*.md`, `scripts/`, `hooks/`,
  `agents/`.
- `skills/development-protocol/scripts/devproto.py`: the checklist tool every skill records its
  row with, and `skills/development-protocol/scripts/_shared.py`, which `pathway` and `relentless`
  scripts import by relative path.
- For `skills/research-stack/`: the canonical public `research-stack` repo. Its `focus/tags.json`
  is canonical; here it is `skills/research-stack/references/focus/tags.json`, with the lenses
  `references/focus/<tag>.md` and `references/tool-registry.json`. `FOCUS_HINTS` in `devproto.py`
  mirrors the manifest's triggers.
- For a re-port: the drifted source on the maintainer's machine. It is never copied in.
- Missing input: no source, or a source that cannot be made standalone, is not ported.

## Process

1. Port under `docs/PORTING.md`: keep the method, phases, gates, checklists, failure modes and
   dated lessons; drop or replace home paths, house engines, private names, personal rules and
   private skills. Paid tools get a free fallback.
2. Scripts are Python 3.9+ standard library or POSIX sh only, each with a unit test under
   `tests/` when the logic is more than a few lines.
3. Slash references point only to bundled skills (the list in `docs/PORTING.md`) or agent
   built-ins; `tests/test_package.py` fails on any other.
4. State the checklist row the skill satisfies and how to record it with `devproto.py ... step`.
5. For research-stack, change upstream `focus/tags.json` first, then re-port the manifest, lenses
   and registry here, update `FOCUS_HINTS`, and run
   `python3 skills/research-stack/scripts/focus_check.py lint --root skills/research-stack`.
6. Never add a `CONTEXT.md` or other agent file inside `skills/<name>/`: `install.sh` copies each
   folder whole and the plugin loads it as is.
7. Run `bash tests/sanitization.sh skills/<name>` (prints `clean`), then
   `python3 -m unittest discover tests`. Read back every file written.

## Outputs

- Edited or new `skills/<name>/` files, their tests under `tests/`, and a dated `UPDATES.md`
  entry per skill (plus a `CHANGELOG.md` line when a user would notice).
- Report per skill: files written with line counts, source line count, and each thing dropped
  with the reason.

## Human check

The maintainer runs the changed skill once on a real task and reads the diff. Pass: the skill
works with only this repo installed, the scan is clean and the suite is green. Fail: fix the port
before merge.
