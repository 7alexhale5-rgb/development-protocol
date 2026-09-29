# Changelog

## 2.0.0 (2026-09-29)

- The whole development stack, not only the protocol: 19 skills (development-protocol, pathway,
  brainstorm-stack, research-stack, karpathy, planning-stack, visual-spec, design-stack,
  devilsadvocate, audit-setup, build-stack, review-stack, simplify, commit, ship, compound,
  closeout-stack, relentless, 1pct).
- Checklist moved to the 17-row standard, one row per skill.
- Checklist fixes from three review rounds: verifier runs without holding the lock, kills its whole
  process tree on timeout or interrupt, ignores background children; re-recording an earlier row
  reopens later rows; `--through` for pre-merge gates; `--optional`; symlinked instruments refused;
  clear reasons for each failure.
- Installer with dry run, backups and restore; uninstaller; health check.
- Docs: STANDARD, WORKFLOW, SETUP, DAILY-USE, TROUBLESHOOTING, UPDATING, PORTING.
- Private-data scan in tests and CI.

## 1.0.0 (2026-09-29)

- First shareable development-protocol skill with the evidence-checked checklist.
