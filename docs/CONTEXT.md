# docs — user-facing documentation

## Inputs

- Working: `docs/SETUP.md`, `WORKFLOW.md`, `STANDARD.md`, `TROUBLESHOOTING.md`, `UPDATING.md`,
  `PORTING.md`, `DAILY-USE.md`.
- Reference: `README.md` (links into each of these), `install.sh` (must match `SETUP.md`).

## Process

1. Update the relevant doc when `install.sh`, `health-check.sh`, or a skill's public interface
   changes.
2. Keep `README.md`'s skill table in sync with `skills/` — it is the install-time index.
3. No automated check; proofread against the actual `install.sh` flags before committing.

## Outputs

- Edited `docs/*.md`; `README.md` if the top-level index changed.

## Human check

Alex (or an external installer following the docs cold) runs `./install.sh` and
`./health-check.sh` against the doc's instructions. Pass: docs match actual script behavior.
Fail: fix the doc, not the script, unless the script is also wrong.
