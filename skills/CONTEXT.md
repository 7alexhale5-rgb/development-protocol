# skills — the 19-skill stack + conductor

## Inputs

- Working: `skills/<name>/SKILL.md` for each of the 19 packages (commit, planning-stack,
  research-stack, build-stack, brainstorm-stack, devilsadvocate, karpathy, design-stack,
  relentless, development-protocol, closeout-stack, visual-spec, compound, review-stack,
  pathway, ship, 1pct, simplify, audit-setup).
- Reference: `docs/STANDARD.md` (the checklist `development-protocol` enforces).

## Process

1. Read `docs/STANDARD.md` before editing a skill's evidence/verifier contract.
2. Edit the skill's `SKILL.md` (and any scripts under it) directly.
3. `bash tests/sanitization.sh` — every skill here is a sanitized copy; this catches leaked
   private paths or client names before commit.
4. `python3 -m unittest discover tests` for the full suite.

## Outputs

- Updated `skills/<name>/SKILL.md`; `CHANGELOG.md` gets a line for a user-facing change.

## Human check

Alex reads `bash health-check.sh` output ("every line should say PASS") after a skill change.
Pass: all PASS, sanitization clean. Fail: fix before pushing to the public repo.
