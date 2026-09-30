# tests — suite

## Inputs

- Working: `tests/test_*.py` (14 files, one per skill/module area), `tests/sanitization.sh`,
  `tests/fixtures/`.
- Reference: `skills/**` (what's under test), `install.sh` (covered by `test_install.py`).

## Process

1. `python3 -m unittest discover tests` runs the full suite.
2. `bash tests/sanitization.sh` checks for leaked private content separately (not part of
   unittest discovery).
3. Add a new `test_<area>.py` when a skill gains a script or a contract worth locking.

## Outputs

- Exit code only; `tests/generic-patterns.txt` and `tests/fixtures/` are inputs, not outputs.

## Human check

Alex reads the suite's pass/fail before any push to the public repo. Pass: full green plus
sanitization clean. Fail: do not push; fix or revert.
